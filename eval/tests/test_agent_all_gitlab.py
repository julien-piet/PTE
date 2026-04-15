# eval/tests/test_agent_all_gitlab.py
#
# Integration tests: run the agent on every GitLab task in
# raw_webarena_tasks_all_gitlab.json (186 tasks, both string_match and
# program_html eval types).
#
# Tasks run concurrently up to num_workers() at a time, matching the
# parallelism of run_tasks_batch.py.
#
# Run all 186 tasks:
#   python3 -m pytest eval/tests/test_agent_all_gitlab.py -v
#
# Smoke test (first 5 tasks):
#   python3 -m pytest eval/tests/test_agent_all_gitlab.py --task-limit 5 -v -s
#
# Single task by ID:
#   python3 -m pytest eval/tests/test_agent_all_gitlab.py --task-id 389 -v -s
#
# Save results to a JSON log:
#   python3 -m pytest eval/tests/test_agent_all_gitlab.py -v --output gitlab_results.json
#
# Force-reset GitLab state before every task:
#   python3 -m pytest eval/tests/test_agent_all_gitlab.py -v --force-reset
#
# Plug in a custom agent runner:
#   python3 -m pytest eval/tests/test_agent_all_gitlab.py \
#       --agent-runner my_agent_runner.MyAgentRunner -v -s

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from agent.auth import StaticAuth
from eval.docker.workers import num_workers, worker_session
from eval.run_program_html_benchmark import AgentRunner


def _serialize_plan(plan) -> list:
    return [
        {
            "step_id": step.step_id,
            "tool_name": step.tool_name.value if hasattr(step.tool_name, "value") else str(step.tool_name),
            "arguments": [
                {"name": a.name, "value": a.value, "value_type": a.value_type}
                for a in (step.arguments or [])
            ],
            "depends_on": step.depends_on or [],
            "hints": step.hints or "",
        }
        for step in plan
    ]

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Task loading
# ---------------------------------------------------------------------------

TASK_FILE = Path(__file__).parent / "raw_webarena_tasks_all_gitlab.json"


def _load_tasks(config=None) -> List[Dict[str, Any]]:
    with open(TASK_FILE) as f:
        tasks = json.load(f)
    if config is not None:
        task_id = config.getoption("--task-id", default=None)
        if task_id is not None:
            tasks = [t for t in tasks if t.get("task_id") == task_id]
        else:
            limit = config.getoption("--task-limit", default=None)
            if limit is not None:
                tasks = tasks[:limit]
    return tasks


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_failure_message(
    task: Dict[str, Any],
    agent_result: Optional[Dict[str, Any]],
    html_detail: Optional[Dict[str, Any]],
) -> str:
    ev = task.get("eval", {})
    lines = [
        f"Task {task['task_id']} FAILED",
        f"  intent     : {task['intent']}",
        f"  eval_types : {ev.get('eval_types', [])}",
    ]

    ra = ev.get("reference_answers") or {}
    if ra.get("must_include"):
        lines.append(f"  must_include : {ra['must_include']}")
    if ra.get("exact_match") is not None:
        lines.append(f"  exact_match  : {ra['exact_match']!r}")
    if ra.get("fuzzy_match") is not None:
        lines.append(f"  fuzzy_match  : {ra['fuzzy_match']!r}")
    if ev.get("string_note"):
        lines.append(f"  string_note  : {ev['string_note']}")
    if agent_result:
        lines.append(f"  agent_answer : {str(agent_result.get('answer', ''))[:300]!r}")

    if html_detail:
        top_error = html_detail.get("error")
        checks = html_detail.get("checks", [])
        if top_error and not checks:
            lines.append(f"  html_error   : {top_error}")
        for i, chk in enumerate(checks, 1):
            status = "PASS" if chk["passed"] else "FAIL"
            lines.append(f"  check {i} [{status}]: {chk.get('raw_url', '')}")
            if not chk["passed"]:
                if chk.get("missing"):
                    lines.append(f"    missing         : {chk['missing']}")
                if chk.get("excluded_found"):
                    lines.append(f"    excluded_found  : {chk['excluded_found']}")
                if chk.get("error"):
                    lines.append(f"    error           : {chk['error']}")
                if chk.get("extracted_content") is not None:
                    lines.append(f"    content_snippet : {str(chk['extracted_content'])[:300]!r}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

def test_agent_accomplishes_gitlab_tasks(
    session_event_loop,
    acquire_lock,
    result_log,
    request,
) -> None:
    tasks = _load_tasks(request.config)
    force_reset = request.config.getoption("--force-reset", default=False)
    n_workers = num_workers()

    print(f"\nRunning {len(tasks)} tasks with {n_workers} workers")

    async def run_all() -> tuple:
        sem = asyncio.Semaphore(n_workers)

        async def run_one(task: Dict[str, Any]) -> Dict[str, Any]:
            async with sem:
                try:
                    async with worker_session(
                        str(task["task_id"]),
                        acquire_lock=acquire_lock,
                        read_only=task.get("read_only", False),
                    ) as w:
                        runner = AgentRunner(
                            headless=True,
                            enable_reset=False,
                            force_reset=force_reset,
                            gitlab_base_url=w["gitlab_url"],
                        )
                        runner.server = "gitlab"
                        runner.base_url = w["gitlab_url"]

                        await runner._init_agent()

                        if runner._agent.execution_agent is not None:
                            runner._agent.execution_agent.auth = StaticAuth(
                                {"PRIVATE-TOKEN": w["glpat"]}
                            )
                            runner._agent.execution_agent.task_id = str(task["task_id"])

                        passed, agent_result, error, html_detail = await runner.run_agent_on_task(task)

                        # Capture execution details for structured logging, even on failure.
                        plan_steps = None
                        parsed_outputs = None
                        raw_execution = None
                        _agent = getattr(runner, "_agent", None)
                        if _agent is not None:
                            pr = getattr(_agent, "last_plan_response", None)
                            if pr is not None:
                                plan_steps = _serialize_plan(pr.plan)
                            ea = getattr(_agent, "execution_agent", None)
                            if ea is not None:
                                raw_execution = getattr(ea, "last_raw_outputs", None)
                                ctx = getattr(ea, "last_ctx", None)
                                if ctx is not None:
                                    parsed_outputs = getattr(ctx, "step_outputs", None)

                        if error:
                            status = "failed" if plan_steps is None else "execution_failed"
                        elif passed:
                            status = "success"
                        else:
                            status = "execution_failed"

                        return {
                            "task": task,
                            "passed": passed,
                            "agent_result": agent_result,
                            "error": error,
                            "html_detail": html_detail,
                            "plan": plan_steps,
                            "parsed_outputs": parsed_outputs,
                            "execution": raw_execution,
                            "worker_id": w["worker_id"],
                            "status": status,
                        }
                except Exception as e:
                    return {
                        "task": task,
                        "passed": False,
                        "agent_result": None,
                        "error": str(e),
                        "html_detail": None,
                        "plan": None,
                        "parsed_outputs": None,
                        "execution": None,
                        "worker_id": None,
                        "status": "failed",
                    }

        futures = [asyncio.ensure_future(run_one(t)) for t in tasks]
        try:
            return list(await asyncio.gather(*futures)), False
        except BaseException:
            print("\nInterrupted — cancelling remaining tasks and releasing workers...")
            for f in futures:
                f.cancel()
            all_results = await asyncio.gather(*futures, return_exceptions=True)
            partial = [r for r in all_results if isinstance(r, dict)]
            return partial, True

    interrupted = False
    try:
        results, interrupted = session_event_loop.run_until_complete(run_all())
    except KeyboardInterrupt:
        results, interrupted = [], True

    failures = []
    for r in results:
        task = r["task"]
        passed = r["passed"]
        error = r["error"]

        result_log.append({
            "task_id":        task["task_id"],
            "intent":         task.get("intent", ""),
            "eval_types":     task.get("eval", {}).get("eval_types", []),
            "passed":         passed and not error,
            "status":         r.get("status"),
            "answer":         r["agent_result"].get("answer") if r["agent_result"] else None,
            "error":          error,
            "worker_id":      r.get("worker_id"),
            "plan":           r.get("plan"),
            "plan_step_count": len(r["plan"]) if r.get("plan") else None,
            "execution":      r.get("execution"),
            "parsed_outputs": r.get("parsed_outputs"),
        })

        if error:
            failures.append(f"Task {task['task_id']}: agent error: {error}")
        elif not passed:
            failures.append(_make_failure_message(task, r["agent_result"], r["html_detail"]))

    if interrupted:
        # Write whatever completed to disk immediately, then exit cleanly.
        output_name = request.config.getoption("--output", default=None)
        if output_name and result_log:
            import json as _json
            from datetime import datetime, timezone
            from pathlib import Path as _Path
            logs_dir = _Path(__file__).parent / "logs"
            logs_dir.mkdir(exist_ok=True)
            out_path = logs_dir / output_name
            summary = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "interrupted": True,
                "total": len(result_log),
                "passed": sum(1 for e in result_log if e["passed"]),
                "failed": sum(1 for e in result_log if not e["passed"]),
                "results": result_log,
            }
            out_path.write_text(_json.dumps(summary, indent=2))
            print(f"\n📄 Partial results ({len(result_log)} tasks) written to {out_path}")
        pytest.exit("Interrupted by user", returncode=1)

    if failures:
        pytest.fail("\n\n".join(failures))
