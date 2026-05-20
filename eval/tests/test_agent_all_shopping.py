# eval/tests/test_agent_all_shopping.py
#
# Integration tests: run the agent on every shopping task in
# raw_webarena_tasks_all_shopping.json (187 tasks, both string_match and
# program_html eval types).
#
# Tasks run concurrently up to num_workers() at a time when --multi-docker
# is set; otherwise a single worker is used.
#
# Run all 187 tasks:
#   python3 -m pytest eval/tests/test_agent_all_shopping.py -v
#
# Smoke test (first 5 tasks):
#   python3 -m pytest eval/tests/test_agent_all_shopping.py --task-limit 5 -v -s
#
# Single task by ID:
#   python3 -m pytest eval/tests/test_agent_all_shopping.py --task-id 158 -v -s
#
# Multiple tasks by ID:
#   python3 -m pytest eval/tests/test_agent_all_shopping.py --task-id 158,201,389 -v -s
#
# Only string_match tasks:
#   python3 -m pytest eval/tests/test_agent_all_shopping.py -k "string_match" -v
#
# Save results to a JSON log:
#   python3 -m pytest eval/tests/test_agent_all_shopping.py -v --output shopping_results.json
#
# Force-reset shopping state before every write task:
#   python3 -m pytest eval/tests/test_agent_all_shopping.py -v --force-reset
#
# Use multi-docker worker pool:
#   python3 -m pytest eval/tests/test_agent_all_shopping.py -v --multi-docker
#
# Plug in a custom agent runner:
#   python3 -m pytest eval/tests/test_agent_all_shopping.py \
#       --agent-runner my_agent_runner.MyAgentRunner -v -s

import asyncio
import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from agent.auth import StaticAuth
from config.base_urls import SERVER_URLS as _SERVER_URLS
from eval.docker import workers_new as _workers_new
from eval.run_program_html_benchmark import AgentRunner
from eval.tests.agent_test_utils import extract_agent_details, task_status


@asynccontextmanager
async def _local_session(shopping_url: str):
    """Stub worker session for a single local shopping instance."""
    yield {"worker_id": "local", "shopping_url": shopping_url}


PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Task loading
# ---------------------------------------------------------------------------

TASK_FILE = Path(__file__).parent / "raw_webarena_tasks_all_shopping.json"


def _load_tasks(config=None) -> List[Dict[str, Any]]:
    tasks = json.loads(TASK_FILE.read_text())
    if config is not None:
        task_id = config.getoption("--task-id", default=None)
        if task_id is not None:
            ids = {int(x.strip()) for x in task_id.split(",")}
            tasks = [t for t in tasks if t.get("task_id") in ids]
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
        f"  read_only  : {task.get('read_only')}",
    ]

    ra = ev.get("reference_answers") or {}
    if ra:
        if ra.get("must_include"):
            lines.append(f"  must_include : {ra['must_include']}")
        if ra.get("must_exclude"):
            lines.append(f"  must_exclude : {ra['must_exclude']}")
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

def test_agent_accomplishes_shopping_tasks(
    session_event_loop,
    acquire_lock,
    result_log,
    request,
) -> None:
    tasks = _load_tasks(request.config)
    force_reset = request.config.getoption("--force-reset", default=False)
    multi_docker = request.config.getoption("--multi-docker", default=False)
    base_url = request.config.getoption("--base-url", default=_SERVER_URLS["shopping"])

    if multi_docker:
        n_workers = _workers_new.num_workers()
    else:
        n_workers = 1

    from scripts.refresh_shopping_tokens import refresh_tokens as _refresh_shopping_tokens
    shopping_token = _refresh_shopping_tokens(base_url=_SERVER_URLS["shopping"])

    print(f"\nRunning {len(tasks)} tasks with {n_workers} workers")

    async def run_all() -> tuple:
        sem = asyncio.Semaphore(n_workers)
        remaining = len(tasks)
        remaining_lock = asyncio.Lock()

        async def run_one(task: Dict[str, Any]) -> Dict[str, Any]:
            async with sem:
                try:
                    if multi_docker:
                        worker_ctx = _workers_new.worker_session(
                            str(task["task_id"]),
                            server="shopping",
                            acquire_lock=acquire_lock,
                            read_only=task.get("read_only", True),
                        )
                    else:
                        worker_ctx = _local_session(base_url)

                    async with worker_ctx as w:
                        runner = AgentRunner(headless=True, enable_reset=False, force_reset=False)
                        runner.server = "shopping"
                        runner.base_url = w["shopping_url"]

                        await runner._init_agent()

                        if runner._agent.execution_agent is not None:
                            runner._agent.execution_agent.auth = StaticAuth(
                                {"Authorization": f"Bearer {shopping_token}"}
                            )
                            runner._agent.execution_agent.task_id = str(task["task_id"])

                        run_task = task
                        if force_reset and not task.get("read_only", False):
                            run_task = {**task, "require_reset": True}

                        passed, agent_result, error, html_detail = await runner.run_agent_on_task(run_task)

                        async with remaining_lock:
                            nonlocal remaining
                            remaining -= 1
                            print(f"\n[{remaining} tasks remaining] Task {task['task_id']} done ({'PASS' if passed and not error else 'FAIL'})")

                        details = extract_agent_details(runner)
                        status = task_status(passed, error, details["plan_steps"])

                        return {
                            "task": task,
                            "passed": passed,
                            "agent_result": agent_result,
                            "error": error,
                            "html_detail": html_detail,
                            "plan": details["plan_steps"],
                            "parsed_outputs": details["parsed_outputs"],
                            "execution": details["raw_execution"],
                            "planning_log": details["planning_log"],
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
        print("\nKeyboardInterrupt — collecting partial results...")
        for task in asyncio.all_tasks(session_event_loop):
            task.cancel()
        all_done = session_event_loop.run_until_complete(
            asyncio.gather(*asyncio.all_tasks(session_event_loop), return_exceptions=True)
        )
        results = [r for r in all_done if isinstance(r, dict)]
        interrupted = True

    failures = []
    for r in results:
        task = r["task"]
        passed = r["passed"]
        error = r["error"]

        result_log.append({
            "task_id":         task["task_id"],
            "intent":          task.get("intent", ""),
            "eval_types":      task.get("eval", {}).get("eval_types", []),
            "read_only":       task.get("read_only"),
            "passed":          passed and not error,
            "status":          r.get("status"),
            "answer":          r["agent_result"].get("answer") if r["agent_result"] else None,
            "error":           error,
            "worker_id":       r.get("worker_id"),
            "plan":            r.get("plan"),
            "plan_step_count": len(r["plan"]) if r.get("plan") else None,
            "execution":       r.get("execution"),
            "parsed_outputs":  r.get("parsed_outputs"),
            "planning_log":    r.get("planning_log"),
        })

        if error:
            failures.append(f"Task {task['task_id']}: agent error: {error}")
        elif not passed:
            failures.append(_make_failure_message(task, r["agent_result"], r["html_detail"]))

    if interrupted:
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

    total = len(results)
    passed_count = sum(1 for r in results if r["passed"] and not r["error"])
    failed_count = total - passed_count
    print(f"\nResults: {passed_count}/{total} passed, {failed_count}/{total} failed")

    if failures:
        pytest.fail("\n\n".join(failures))
