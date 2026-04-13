# eval/tests/test_agent_all_gitlab.py
#
# Integration tests: run the agent on every GitLab task in
# raw_webarena_tasks_all_gitlab.json (186 tasks, both string_match and
# program_html eval types).
#
# Each test acquires a dedicated Docker worker, runs the agent against that
# worker's GitLab instance, evaluates the result, then releases the worker.
#
# Run all 186 tasks:
#   python3 -m pytest eval/tests/test_agent_all_gitlab.py -v
#
# Smoke test (first 5 tasks):
#   python3 -m pytest eval/tests/test_agent_all_gitlab.py --task-limit 5 -v -s
#
# Single task by ID:
#   python3 -m pytest eval/tests/test_agent_all_gitlab.py -k "task_389" -v -s
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

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from agent.auth import StaticAuth
from eval.docker.workers import worker_session
from eval.run_program_html_benchmark import AgentRunner

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Task loading
# ---------------------------------------------------------------------------

TASK_FILE = Path(__file__).parent / "raw_webarena_tasks_all_gitlab.json"


def _load_tasks() -> List[Dict[str, Any]]:
    with open(TASK_FILE) as f:
        return json.load(f)


def _get_tasks(config=None) -> List[Dict[str, Any]]:
    tasks = _load_tasks()
    if config is not None:
        limit = config.getoption("--task-limit", default=None)
        if limit is not None:
            tasks = tasks[:limit]
    return tasks


def pytest_generate_tests(metafunc):
    if "task" in metafunc.fixturenames:
        tasks = _get_tasks(metafunc.config)
        metafunc.parametrize("task", tasks, ids=[_task_id(t) for t in tasks])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _task_id(task: Dict[str, Any]) -> str:
    return f"task_{task['task_id']}_gitlab"


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

    # string_match detail
    ra = ev.get("reference_answers") or {}
    if ra:
        if ra.get("must_include"):
            lines.append(f"  must_include : {ra['must_include']}")
        if ra.get("exact_match") is not None:
            lines.append(f"  exact_match  : {ra['exact_match']!r}")
        if ra.get("fuzzy_match") is not None:
            lines.append(f"  fuzzy_match  : {ra['fuzzy_match']!r}")
    if ev.get("string_note"):
        lines.append(f"  string_note  : {ev['string_note']}")
    if agent_result:
        answer = agent_result.get("answer", "")
        lines.append(f"  agent_answer : {str(answer)[:300]!r}")

    # program_html detail
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
                    snippet = str(chk["extracted_content"])[:300]
                    lines.append(f"    content_snippet : {snippet!r}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

def test_agent_accomplishes_gitlab_task(
    session_event_loop,
    acquire_lock,
    result_log,
    request,
    task: Dict[str, Any],
) -> None:
    force_reset = request.config.getoption("--force-reset", default=False)
    read_only = task.get("read_only", False)

    async def _run():
        async with worker_session(
            str(task["task_id"]),
            acquire_lock=acquire_lock,
            read_only=read_only,
        ) as w:
            runner = AgentRunner(
                headless=True,
                enable_reset=True,
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

            return await runner.run_agent_on_task(task)

    passed, agent_result, error, html_detail = session_event_loop.run_until_complete(_run())

    result_log.append({
        "task_id":    task["task_id"],
        "intent":     task.get("intent", ""),
        "eval_types": task.get("eval", {}).get("eval_types", []),
        "passed":     passed and not error,
        "answer":     agent_result.get("answer") if agent_result else None,
        "error":      error,
    })

    if error:
        pytest.fail(f"Task {task['task_id']}: agent error: {error}")

    assert passed, _make_failure_message(task, agent_result, html_detail)
