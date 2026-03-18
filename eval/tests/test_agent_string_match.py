# eval/tests/test_agent_string_match.py
#
# Integration tests: verify the agent produces a correct answer for every
# string_match task from raw_webarena_tasks_no_map.json that does NOT also
# require a program_html check (those are already covered by
# test_agent_program_html.py).
#
# Eval-type breakdown covered here (241 total tasks):
#   - string_match only                — 231 tasks
#   - string_match + url_match         —  10 tasks (both checks must pass)
#
# Tasks that carry program_html (with or without string_match) are handled
# inside test_agent_program_html.py and are therefore excluded here.
#
# Answer format reference
# ───────────────────────
#   must_include  : agent answer must contain every listed substring (case-insensitive)
#   must_exclude  : agent answer must NOT contain any listed substring (case-insensitive)
#   exact_match   : NOTE — AgentRunner._evaluate_string_match does not currently enforce
#                   exact_match; it only checks must_include/must_exclude. Tasks that
#                   carry only exact_match will pass as long as the agent returns any
#                   non-empty answer. This is a known evaluator limitation.
#   fuzzy_match   : Not enforced by AgentRunner._evaluate_string_match; tasks pass as
#                   long as the agent returns any non-empty answer.
#
# Site distribution:
#   shopping_admin : 88
#   shopping       : 88
#   gitlab         : 54
#   reddit         : 12
#
# Excluded task IDs: 118, 528-532, 585-589
#
# Run all string_match tasks (241):
#   python3 -m pytest eval/tests/test_agent_string_match.py -v
#
# Run with --site / --task-limit filters:
#   python3 -m pytest eval/tests/test_agent_string_match.py -k "gitlab" -v
#   python3 -m pytest eval/tests/test_agent_string_match.py -k "shopping_admin" -v
#   python3 -m pytest eval/tests/test_agent_string_match.py -k "reddit" -v
#   python3 -m pytest eval/tests/test_agent_string_match.py --task-limit 10 -v
#
# Run a single task by ID:
#   python3 -m pytest eval/tests/test_agent_string_match.py -k "task_0" -v -s
#
# Plug in a custom agent:
#   python3 -m pytest eval/tests/test_agent_string_match.py \
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

def _load_string_match_tasks() -> List[Dict[str, Any]]:
    """
    Load tasks that have string_match as an eval type but do NOT require
    program_html (which is handled by test_agent_program_html.py).

    Tasks with both string_match and url_match (but no program_html) are
    included — AgentRunner handles both checks in a single run.
    """
    with open(TASK_FILE) as f:
        all_tasks = json.load(f)
    return [
        t for t in all_tasks
        if "string_match" in t.get("eval", {}).get("eval_types", [])
        and "program_html" not in t.get("eval", {}).get("eval_types", [])
        and t["task_id"] not in EXCLUDED_TASK_IDS
    ]


def _get_tasks(config=None) -> List[Dict[str, Any]]:
    """Return tasks, optionally filtered by --site (or --server) then capped by --task-limit."""
    tasks = _load_string_match_tasks()
    if config is not None:
        site = config.getoption("--site", default=None) or config.getoption("--server", default=None)
        if site:
            tasks = [t for t in tasks if site in t.get("sites", [])]
        limit = config.getoption("--task-limit", default=None)
        if limit is not None:
            tasks = tasks[:limit]
    return tasks


# Loaded at collection time for the parametrize list.
STRING_MATCH_TASKS: List[Dict[str, Any]] = _load_string_match_tasks()


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
    """Build a multi-line failure message for a string_match failure."""
    ev = task.get("eval", {})
    ra = ev.get("reference_answers", {})
    lines = [
        f"Task {task['task_id']} FAILED",
        f"  intent       : {task['intent']}",
        f"  sites        : {task.get('sites', [])}",
        f"  eval_types   : {ev.get('eval_types', [])}",
    ]

    # Expected answer breakdown
    if ra.get("must_include"):
        lines.append(f"  must_include : {ra['must_include']}")
    if ra.get("must_exclude"):
        lines.append(f"  must_exclude : {ra['must_exclude']}")
    if ra.get("exact_match"):
        lines.append(f"  exact_match  : {ra['exact_match']!r}  (note: not enforced by evaluator)")
    if ra.get("fuzzy_match"):
        lines.append(f"  fuzzy_match  : {ra['fuzzy_match']!r}  (note: not enforced by evaluator)")
    if ev.get("string_note"):
        lines.append(f"  string_note  : {ev['string_note']}")

    # What the agent actually returned
    if agent_result is not None:
        answer = agent_result.get("answer", "")
        snippet = str(answer)[:400] if answer else "(empty)"
        lines.append(f"  agent_answer : {snippet!r}")
        final_url = agent_result.get("final_url")
        if final_url:
            lines.append(f"  final_url    : {final_url}")

        # For must_include tasks, highlight which items are missing
        must_include = ra.get("must_include", [])
        if must_include and answer:
            answer_lower = str(answer).lower()
            missing = [item for item in must_include
                       if isinstance(item, str) and item.lower() not in answer_lower]
            if missing:
                lines.append(f"  missing items: {missing}")

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


def test_agent_produces_correct_answer(
    agent_runner,
    session_event_loop,
    task: Dict[str, Any],
) -> None:
    """
    Assert the agent returns a correct string answer for a string_match task.

    The agent runs through the full plan-then-execute pipeline
    (``automated=True``, no re-planning). After execution, the agent's
    ``answer`` field is checked against the task's ``reference_answers``:

    - ``must_include`` items must all appear in the answer (case-insensitive).
    - ``must_exclude`` items must not appear in the answer (case-insensitive).
    - ``exact_match`` / ``fuzzy_match`` fields are recorded in the failure
      message for human review but are not currently enforced by the
      evaluator (see AgentRunner._evaluate_string_match).

    For tasks that also carry a ``url_match`` eval type, the agent's
    ``final_url`` is additionally checked against the reference URL.
    """
    passed, agent_result, error, _html_detail = session_event_loop.run_until_complete(
        agent_runner.run_agent_on_task(task)
    )

    if error:
        pytest.fail(
            f"Task {task['task_id']}: agent returned an error: {error}"
        )

    assert passed, _make_failure_message(task, agent_result)
