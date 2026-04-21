# eval/tests/test_agent_all_shopping.py
#
# Integration tests: run the agent on every shopping task in
# raw_webarena_tasks_all_shopping.json (187 tasks, both string_match and
# program_html eval types).
#
# Unlike the GitLab tests there are no Docker workers — shopping runs against
# a single fixed server.  The shared session-scoped ``agent_runner`` from
# conftest.py is used directly.
#
# Run all 187 tasks:
#   python3 -m pytest eval/tests/test_agent_all_shopping.py -v
#
# Smoke test (first 5 tasks):
#   python3 -m pytest eval/tests/test_agent_all_shopping.py --task-limit 5 -v -s
#
# Single task by ID:
#   python3 -m pytest eval/tests/test_agent_all_shopping.py -k "task_158" -v -s
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
# Plug in a custom agent runner:
#   python3 -m pytest eval/tests/test_agent_all_shopping.py \
#       --agent-runner my_agent_runner.MyAgentRunner -v -s
#
# Task breakdown (187 total):
#   string_match  : 130  (88 original + 42 converted from url_match)
#   program_html  :  57  (47 original + 10 converted from url_match+program_html)
#
# read_only flag:
#   True  → string_match tasks (lookup/navigation, no state change)
#   False → program_html tasks (writes state that may need reset)

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Task loading
# ---------------------------------------------------------------------------

TASK_FILE = Path(__file__).parent / "raw_webarena_tasks_all_shopping.json"


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
    return f"task_{task['task_id']}_shopping"


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

    # string_match detail
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

def test_agent_accomplishes_shopping_task(
    agent_runner,
    session_event_loop,
    result_log,
    request,
    task: Dict[str, Any],
) -> None:
    """
    Assert the agent correctly accomplishes a single shopping task.

    Dispatches to the appropriate evaluator based on eval_types:
      - string_match  : checks the agent's text answer against reference_answers
      - program_html  : opens a Playwright browser and checks page content

    The agent runs through the full plan-then-execute pipeline
    (``automated=True``, no re-planning).
    """
    force_reset = request.config.getoption("--force-reset", default=False)
    read_only = task.get("read_only", False)

    # For write tasks, honour --force-reset by temporarily patching require_reset.
    if force_reset and not read_only:
        task = {**task, "require_reset": True}

    passed, agent_result, error, html_detail = session_event_loop.run_until_complete(
        agent_runner.run_agent_on_task(task)
    )

    result_log.append({
        "task_id":    task["task_id"],
        "intent":     task.get("intent", ""),
        "eval_types": task.get("eval", {}).get("eval_types", []),
        "read_only":  task.get("read_only"),
        "passed":     passed and not error,
        "answer":     agent_result.get("answer") if agent_result else None,
        "error":      error,
    })

    if error:
        pytest.fail(f"Task {task['task_id']}: agent error: {error}")

    assert passed, _make_failure_message(task, agent_result, html_detail)
