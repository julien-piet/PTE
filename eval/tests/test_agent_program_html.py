# eval/tests/test_agent_program_html.py
#
# Integration tests: verify the agent can accomplish every program_html task
# from raw_webarena_tasks_no_map.json.
#
# Each test runs the agent through the full plan-then-execute pipeline
# (no mid-task re-planning), then opens a fresh authenticated Playwright
# browser to evaluate the result using ProgramHtmlEvaluator.
#
# Excluded task IDs: 118, 528-532, 585-589
#
# Run all program_html tasks (~371):
#   python3 -m pytest eval/tests/test_agent_program_html.py -v
#
# Run only the first N tasks (e.g. 2 for a smoke test):
#   python3 -m pytest eval/tests/test_agent_program_html.py --task-limit 2 -v -s
#
# Run a single task by ID:
#   python3 -m pytest eval/tests/test_agent_program_html.py -k "task_389" -v -s
#
# Run tasks for a specific site:
#   python3 -m pytest eval/tests/test_agent_program_html.py -k "gitlab" -v
#   python3 -m pytest eval/tests/test_agent_program_html.py -k "reddit" -v
#   python3 -m pytest eval/tests/test_agent_program_html.py -k "shopping_admin" -v
#   python3 -m pytest eval/tests/test_agent_program_html.py -k "shopping and not admin" -v
#
# Combine --site and --task-limit (first 5 reddit tasks):
#   python3 -m pytest eval/tests/test_agent_program_html.py --site reddit --task-limit 5 -v
#
# Plug in a custom agent:
#   python3 -m pytest eval/tests/test_agent_program_html.py \
#       --agent-runner my_agent_runner.MyAgentRunner --task-limit 5 -v -s

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TASK_FILE = Path(__file__).parent / "raw_webarena_tasks_no_map.json"

#: Task IDs excluded from the test run (incomplete support, unsupported, or
#: intentionally skipped by the benchmark).
EXCLUDED_TASK_IDS: frozenset = frozenset({
    118,                        # excluded individually
    528, 529, 530, 531, 532,    # 528–532
    585, 586, 587, 588, 589,    # 585–589
})


# ---------------------------------------------------------------------------
# Task loading (runs once at import time)
# ---------------------------------------------------------------------------

def _load_program_html_tasks() -> List[Dict[str, Any]]:
    """Load and filter program_html tasks, excluding the specified IDs."""
    with open(TASK_FILE) as f:
        all_tasks = json.load(f)
    return [
        t for t in all_tasks
        if "program_html" in t.get("eval", {}).get("eval_types", [])
        and t["task_id"] not in EXCLUDED_TASK_IDS
    ]


def _get_tasks(config=None) -> List[Dict[str, Any]]:
    """Return tasks, optionally filtered by --site then capped by --task-limit."""
    tasks = _load_program_html_tasks()
    if config is not None:
        site = config.getoption("--site", default=None)
        if site:
            tasks = [t for t in tasks if site in t.get("sites", [])]
        limit = config.getoption("--task-limit", default=None)
        if limit is not None:
            tasks = tasks[:limit]
    return tasks


# Loaded at collection time (no config available yet — full list).
# The actual parametrize list is rebuilt in pytest_generate_tests below.
PROGRAM_HTML_TASKS: List[Dict[str, Any]] = _load_program_html_tasks()


# session_event_loop and agent_runner fixtures are defined in conftest.py
# and shared across all agent test files. Use --agent-runner MODULE.CLASS
# to plug in a custom BaseAgentRunner subclass.

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_failure_message(
    task: Dict[str, Any],
    html_detail: Optional[Dict[str, Any]],
) -> str:
    """Build a multi-line failure message with per-check details."""
    lines = [
        f"Task {task['task_id']} FAILED",
        f"  intent : {task['intent']}",
        f"  sites  : {task.get('sites', [])}",
        f"  start  : {task.get('start_url', '')}",
    ]

    if not html_detail:
        return "\n".join(lines)

    top_error = html_detail.get("error")
    checks = html_detail.get("checks", [])

    if top_error and not checks:
        lines.append(f"  error  : {top_error}")
        return "\n".join(lines)

    for i, chk in enumerate(checks, 1):
        status = "PASS" if chk["passed"] else "FAIL"
        lines.append(f"  check {i} [{status}]: {chk.get('raw_url', '')}")
        if not chk["passed"]:
            if chk.get("missing"):
                lines.append(f"    missing        : {chk['missing']}")
            if chk.get("excluded_found"):
                lines.append(f"    excluded_found : {chk['excluded_found']}")
            if chk.get("error"):
                lines.append(f"    error          : {chk['error']}")
            if chk.get("extracted_content") is not None:
                snippet = str(chk["extracted_content"])[:300]
                lines.append(f"    content_snippet: {snippet!r}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Parameterised integration tests — one per task
# ---------------------------------------------------------------------------

def _task_id(task: Dict[str, Any]) -> str:
    """Return a human-readable pytest node ID for a task."""
    site = task.get("sites", ["unknown"])[0]
    return f"task_{task['task_id']}_{site}"


def pytest_generate_tests(metafunc):
    """Dynamically parametrize using --task-limit if provided."""
    if "task" in metafunc.fixturenames:
        tasks = _get_tasks(metafunc.config)
        metafunc.parametrize("task", tasks, ids=[_task_id(t) for t in tasks])


def test_agent_accomplishes_program_html_task(
    agent_runner,
    session_event_loop,
    task: Dict[str, Any],
) -> None:
    """
    Assert the agent correctly accomplishes a single program_html task.

    The agent runs through the full plan-then-execute pipeline
    (``automated=True``, no re-planning). After execution,
    ``ProgramHtmlEvaluator`` opens a fresh authenticated Playwright
    session, navigates to the task's evaluation URL(s), and checks the
    required page content. Both the program_html check and the url_match
    check (for tasks that carry both ``eval_types``) must pass.
    """
    passed, _agent_result, error, html_detail = session_event_loop.run_until_complete(
        agent_runner.run_agent_on_task(task)
    )

    if error:
        pytest.fail(
            f"Task {task['task_id']}: agent returned an error: {error}"
        )

    assert passed, _make_failure_message(task, html_detail)
