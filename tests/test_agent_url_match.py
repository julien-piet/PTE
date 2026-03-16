# tests/test_agent_url_match.py
#
# Integration tests: verify the agent navigates to the correct URL for every
# url_match task from raw_webarena_tasks_no_map.json that does NOT also
# require a program_html check (those are already covered by
# test_agent_program_html.py).
#
# Eval-type breakdown covered here:
#   - url_match (alone)          — 71 tasks: 26 GitLab, 3 Shopping Admin, 42 Shopping
#
# Tasks that carry BOTH program_html + url_match are handled inside
# test_agent_program_html.py and are therefore excluded here.
#
# Excluded task IDs: 118, 528-532, 585-589
#
# Run all url_match tasks:
#   cd "/Users/sylvie/Desktop/API Research/PTE"
#   python3 -m pytest tests/test_agent_url_match.py -v
#
# Run with --site / --task-limit filters (same as test_agent_program_html.py):
#   python3 -m pytest tests/test_agent_url_match.py -k "gitlab" -v
#   python3 -m pytest tests/test_agent_url_match.py -k "shopping" -v
#   python3 -m pytest tests/test_agent_url_match.py --task-limit 10 -v
#
# Run a single task by ID:
#   python3 -m pytest tests/test_agent_url_match.py -k "task_44" -v
#
# Run with a visible browser (for debugging):
#   python3 -m pytest tests/test_agent_url_match.py -k "task_44" -v -s

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

#: Task IDs excluded from the test run (same exclusion set as the rest of the
#: benchmark suite).
EXCLUDED_TASK_IDS: frozenset = frozenset({
    118,                        # excluded individually
    528, 529, 530, 531, 532,    # 528–532
    585, 586, 587, 588, 589,    # 585–589
})


# ---------------------------------------------------------------------------
# Task loading
# ---------------------------------------------------------------------------

def _load_url_match_only_tasks() -> List[Dict[str, Any]]:
    """
    Load tasks that have url_match as an eval type but do NOT require
    program_html (which is handled by test_agent_program_html.py).
    """
    with open(TASK_FILE) as f:
        all_tasks = json.load(f)
    return [
        t for t in all_tasks
        if "url_match" in t.get("eval", {}).get("eval_types", [])
        and "program_html" not in t.get("eval", {}).get("eval_types", [])
        and t["task_id"] not in EXCLUDED_TASK_IDS
    ]


def _get_tasks(config=None) -> List[Dict[str, Any]]:
    """Return tasks, optionally filtered by --site then capped by --task-limit."""
    tasks = _load_url_match_only_tasks()
    if config is not None:
        site = config.getoption("--site", default=None)
        if site:
            tasks = [t for t in tasks if site in t.get("sites", [])]
        limit = config.getoption("--task-limit", default=None)
        if limit is not None:
            tasks = tasks[:limit]
    return tasks


# Loaded at collection time for the parametrize list.
URL_MATCH_TASKS: List[Dict[str, Any]] = _load_url_match_only_tasks()


# session_event_loop and agent_runner fixtures are defined in conftest.py
# and shared across all agent test files. Use --agent-runner MODULE.CLASS
# to plug in a custom BaseAgentRunner subclass.

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_failure_message(
    task: Dict[str, Any],
    agent_result: Optional[Dict[str, Any]],
) -> str:
    """Build a multi-line failure message for a url_match failure."""
    ev = task.get("eval", {})
    lines = [
        f"Task {task['task_id']} FAILED",
        f"  intent   : {task['intent']}",
        f"  sites    : {task.get('sites', [])}",
        f"  url_note : {ev.get('url_note', '')}",
        f"  expected : {ev.get('reference_url', '')}",
    ]
    if agent_result is not None:
        lines.append(f"  actual   : {agent_result.get('final_url', '(no final_url)')}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Parameterised integration tests — one per task
# ---------------------------------------------------------------------------

def _task_id(task: Dict[str, Any]) -> str:
    """Return a human-readable pytest node ID for a task."""
    site = task.get("sites", ["unknown"])[0]
    return f"task_{task['task_id']}_{site}"


def pytest_generate_tests(metafunc):
    """Dynamically parametrize, respecting --task-limit and --site."""
    if "task" in metafunc.fixturenames:
        tasks = _get_tasks(metafunc.config)
        metafunc.parametrize("task", tasks, ids=[_task_id(t) for t in tasks])


def test_agent_navigates_to_correct_url(
    agent_runner,
    session_event_loop,
    task: Dict[str, Any],
) -> None:
    """
    Assert the agent ends on the correct URL for a url_match task.

    The agent runs through the full plan-then-execute pipeline
    (``automated=True``, no re-planning). After execution, the agent's
    reported ``final_url`` is compared against the task's reference URL
    using ``UrlMatchEvaluator``.

    For tasks with both ``string_match`` and ``url_match`` eval types
    (but no ``program_html``), both checks must pass.
    """
    passed, agent_result, error, _html_detail = session_event_loop.run_until_complete(
        agent_runner.run_agent_on_task(task)
    )

    if error:
        pytest.fail(
            f"Task {task['task_id']}: agent returned an error: {error}"
        )

    assert passed, _make_failure_message(task, agent_result)
