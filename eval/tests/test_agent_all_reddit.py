# eval/tests/test_agent_all_reddit.py
#
# Integration tests: run the agent on every Reddit task in
# webarena-verified-reddit.json (106 tasks, all reddit-only).
#
# Tasks run concurrently up to num_workers() at a time, matching the
# parallelism of scripts/run_tasks_batch_new.py.
#
# Run all 106 tasks:
#   python3 -m pytest eval/tests/test_agent_all_reddit.py -v
#
# Smoke test (first 5 tasks):
#   python3 -m pytest eval/tests/test_agent_all_reddit.py --task-limit 5 -v -s
#
# Single task by ID:
#   python3 -m pytest eval/tests/test_agent_all_reddit.py --task-id 731 -v -s
#
# Multiple tasks by ID:
#   python3 -m pytest eval/tests/test_agent_all_reddit.py --task-id 731,404,599 -v -s
#
# Save results to a JSON log:
#   python3 -m pytest eval/tests/test_agent_all_reddit.py -v --output reddit_results.json
#
# Plug in a custom agent runner:
#   python3 -m pytest eval/tests/test_agent_all_reddit.py \
#       --agent-runner my_agent_runner.MyAgentRunner -v -s
#
# Evaluation notes:
#   - retrieve tasks  : agent answer is checked against expected retrieved_data
#                       (fuzzy substring match — all expected values must appear)
#   - mutate tasks    : the full verification requires a NetworkEventEvaluator
#                       (browser network capture) which is not available in API
#                       mode; these tasks are marked "network_event_only" and
#                       count as passed if the agent ran without error.

import asyncio
import json
import re
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest

from agent.auth import StaticAuth
from config.servers import SERVER_URLS as _SERVER_URLS
from eval.docker import workers_new as _workers_new
from eval.run_program_html_benchmark import AgentRunner
from eval.tests.agent_test_utils import extract_agent_details, task_status
from config.init_tokens.refresh_reddit_session import refresh_session as _refresh_reddit_session


@asynccontextmanager
async def _local_session(reddit_url: str):
    """Stub worker session for a single local Reddit instance."""
    yield {"worker_id": "local", "reddit_url": reddit_url}


PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Task loading
# ---------------------------------------------------------------------------

TASK_FILE = Path(__file__).parent / "test_files" / "webarena-verified-reddit.json"


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
# Evaluation
# ---------------------------------------------------------------------------

def _evaluate_reddit_task(
    task: Dict[str, Any],
    agent_result: Optional[Dict[str, Any]],
) -> Tuple[bool, str]:
    """
    Evaluate a Reddit task result against AgentResponseEvaluator criteria.

    Returns (passed, eval_mode) where eval_mode is one of:
      "agent_response"    — retrieve task; answer checked against expected data
      "network_event_only"— mutate task; NetworkEventEvaluator needed (not
                            available in API mode), so passed iff no agent error
      "no_evaluator"      — no AgentResponseEvaluator present; treated as passed
    """
    eval_list = task.get("eval", [])
    answer = ((agent_result or {}).get("answer") or "")

    agent_eval = next(
        (e for e in eval_list if e.get("evaluator") == "AgentResponseEvaluator"),
        None,
    )

    if agent_eval is None:
        return True, "no_evaluator"

    expected = agent_eval.get("expected", {})
    task_type = expected.get("task_type", "")

    if task_type == "mutate":
        # Full verification requires browser network capture (NetworkEventEvaluator).
        # In API mode we can only confirm the agent ran without error.
        return True, "network_event_only"

    if task_type == "retrieve":
        retrieved_data = expected.get("retrieved_data")
        if not retrieved_data:
            return True, "agent_response"

        answer_lower = answer.lower()
        for item in retrieved_data:
            if isinstance(item, str):
                if item.lower() not in answer_lower:
                    return False, "agent_response"
            elif isinstance(item, dict):
                for v in item.values():
                    if v is not None and str(v).lower() not in answer_lower:
                        return False, "agent_response"
            elif isinstance(item, list):
                # Any element of this list must appear in the answer
                found = any(str(v).lower() in answer_lower for v in item if v is not None)
                if not found:
                    return False, "agent_response"

        return True, "agent_response"

    return True, "agent_response"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_prompt(task: Dict[str, Any]) -> str:
    """Build the agent prompt from a task dict, handling start_urls (list)."""
    intent = task.get("intent", "")
    start_urls = task.get("start_urls") or [task.get("start_url", "")]
    start_url = start_urls[0] if start_urls else ""
    # Strip __REDDIT__ and other placeholders; keep any trailing path
    path = re.sub(r"__[A-Z_]+__", "", start_url).strip("/")
    return f"Start URL path: /{path}\n\nTask: {intent}" if path else intent


def _make_failure_message(
    task: Dict[str, Any],
    agent_result: Optional[Dict[str, Any]],
    eval_mode: str,
) -> str:
    eval_list = task.get("eval", [])
    agent_eval = next(
        (e for e in eval_list if e.get("evaluator") == "AgentResponseEvaluator"), {}
    )
    expected = agent_eval.get("expected", {})
    lines = [
        f"Task {task['task_id']} FAILED  [{eval_mode}]",
        f"  intent   : {task['intent']}",
        f"  expected : {json.dumps(expected.get('retrieved_data'), ensure_ascii=False)[:200]}",
    ]
    if agent_result:
        lines.append(f"  answer   : {str(agent_result.get('answer', ''))[:300]!r}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

def test_agent_accomplishes_reddit_tasks(
    session_event_loop,
    acquire_lock,
    result_log,
    request,
) -> None:
    tasks = _load_tasks(request.config)
    multi_docker = request.config.getoption("--multi-docker", default=False)
    base_url = request.config.getoption("--base-url") or _SERVER_URLS["reddit"]
    reddit_extra_url = _SERVER_URLS["reddit_extra"]

    if multi_docker:
        n_workers = _workers_new.num_workers()
    else:
        n_workers = 1
        print("\nRefreshing Reddit session...")
        _reddit_session = _refresh_reddit_session(base_url=base_url)
        print(f"  Session ready (PHPSESSID: {_reddit_session[:8]}...)")

    print(f"\nRunning {len(tasks)} Reddit tasks with {n_workers} workers")

    async def run_all() -> Tuple[list, bool]:
        sem = asyncio.Semaphore(n_workers)
        remaining = len(tasks)
        remaining_lock = asyncio.Lock()

        async def run_one(task: Dict[str, Any]) -> Dict[str, Any]:
            async with sem:
                try:
                    if multi_docker:
                        worker_ctx = _workers_new.worker_session(
                            str(task["task_id"]),
                            server="reddit",
                            acquire_lock=acquire_lock,
                            read_only=task.get("read_only", False),
                        )
                    else:
                        worker_ctx = _local_session(base_url)

                    async with worker_ctx as w:
                        worker_reddit_url = w.get("reddit_url") or w.get("server_url") or base_url

                        runner = AgentRunner(headless=True, enable_reset=False)
                        runner.server = "reddit"
                        runner.base_url = worker_reddit_url

                        # Initialize the agent directly with both Reddit servers in one call
                        # rather than going through _init_agent (which would initialize with
                        # only "reddit" and miss "reddit_extra" for the Playwright API server).
                        from agent.agent import Agent as _Agent
                        runner._agent = _Agent(api_dir=runner.api_dir, env_file=runner.env_file)
                        runner._agent.initialize({
                            "reddit": worker_reddit_url,
                            "reddit_extra": reddit_extra_url,
                        })

                        if runner._agent.execution_agent is not None:
                            if multi_docker:
                                session = _refresh_reddit_session(base_url=worker_reddit_url)
                            else:
                                session = _reddit_session
                            runner._agent.execution_agent.auth = StaticAuth({
                                "Cookie": f"PHPSESSID={session}",
                                "X-Experimental-API": "1",
                            })
                            runner._agent.execution_agent.task_id = str(task["task_id"])

                        prompt = _build_prompt(task)
                        # All reddit_api_schema.json endpoints are FastAPI wrapper calls
                        # (port 7791). Override "reddit" → reddit_extra_url so the filename
                        # match in _inject_base_urls routes to the right server.
                        result = await runner._agent.run_task(prompt, servers={
                            "reddit": reddit_extra_url,
                            "reddit_extra": reddit_extra_url,
                        })
                        agent_result = {
                            "success": True,
                            "answer": result.answer,
                            "execution_result": result.outputs,
                        }

                        passed, eval_mode = _evaluate_reddit_task(task, agent_result)

                        async with remaining_lock:
                            nonlocal remaining
                            remaining -= 1
                            status_str = "PASS" if passed else "FAIL"
                            print(
                                f"\n[{remaining} tasks remaining] "
                                f"Task {task['task_id']} done ({status_str} / {eval_mode})"
                            )

                        details = extract_agent_details(runner)
                        status = task_status(passed, None, details["plan_steps"])

                        return {
                            "task": task,
                            "passed": passed,
                            "eval_mode": eval_mode,
                            "agent_result": agent_result,
                            "error": None,
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
                        "eval_mode": "error",
                        "agent_result": None,
                        "error": str(e),
                        "plan": None,
                        "parsed_outputs": None,
                        "execution": None,
                        "planning_log": None,
                        "worker_id": None,
                        "status": "failed",
                    }

        futures = [asyncio.ensure_future(run_one(t)) for t in tasks]
        try:
            return list(await asyncio.gather(*futures)), False
        except BaseException:
            print("\nInterrupted — cancelling remaining tasks...")
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
        for t in asyncio.all_tasks(session_event_loop):
            t.cancel()
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
        eval_mode = r.get("eval_mode", "")

        result_log.append({
            "task_id":         task["task_id"],
            "intent":          task.get("intent", ""),
            "eval_mode":       eval_mode,
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
            failures.append(_make_failure_message(task, r["agent_result"], eval_mode))

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
            print(f"\nPartial results ({len(result_log)} tasks) written to {out_path}")
        pytest.exit("Interrupted by user", returncode=1)

    total = len(results)
    passed_count = sum(1 for r in results if r["passed"] and not r["error"])
    failed_count = total - passed_count
    network_only = sum(1 for r in results if r.get("eval_mode") == "network_event_only")
    print(
        f"\nResults: {passed_count}/{total} passed, {failed_count}/{total} failed"
        f"  ({network_only} mutate tasks counted as passed — require NetworkEventEvaluator to verify)"
    )

    if failures:
        pytest.fail("\n\n".join(failures))
