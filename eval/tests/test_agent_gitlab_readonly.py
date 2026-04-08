# eval/tests/test_agent_gitlab_readonly.py
#
# Integration tests: verify the agent produces correct answers for all
# read-only GitLab tasks (66 tasks, all string_match).
#
# Source file: raw_webarena_tasks_gitlab_readonly.json
#
# Task breakdown
# ──────────────
#   Phase 1 (16 tasks) — navigation / "show me" tasks
#     Originally pure url_match; converted to string_match with must_include
#     strings derived by live inspection of the seeded GitLab environment.
#     Examples: "Check out my todos", "List issues with label X",
#               "See all public projects", "Checkout MRs assigned to me"
#
#   Phase 2 (10 tasks) — issue open/closed status
#     Tasks 173–182: "Open my latest updated/created issue with keyword X —
#     is it closed?" Simplified from string_match+url_match to string_match;
#     reference_answers check the correct issue title + open/closed status.
#
#   Phase 3 (40 tasks) — information retrieval
#     Pure string_match lookups: commit counts, top contributors, SSH clone
#     commands, repo membership, RSS token, contributor email/stats.
#
# All tasks have require_reset=True — a GitLab state reset runs before each
# task to ensure a clean container state.
#
# Run all 66 tasks:
#   python3 -m pytest eval/tests/test_agent_gitlab_readonly.py -v
#
# Run a single phase:
#   python3 -m pytest eval/tests/test_agent_gitlab_readonly.py -k "task_44 or task_45 or task_46" -v -s
#
# Run by task ID:
#   python3 -m pytest eval/tests/test_agent_gitlab_readonly.py -k "task_173" -v -s
#
# Run first N tasks (smoke test):
#   python3 -m pytest eval/tests/test_agent_gitlab_readonly.py --task-limit 5 -v -s
#
# Save output to log:
#   python3 -m pytest eval/tests/test_agent_gitlab_readonly.py -v -s \
#       --output readonly_run.json 2>&1 | tee /tmp/readonly_run.log

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

TASK_FILE = Path(__file__).parent / "raw_webarena_tasks_gitlab_readonly.json"

PHASE1_IDS = frozenset({
    44, 45, 46, 102, 103, 104, 105, 106,
    156, 258, 339, 340, 341, 342, 343, 357,
})
PHASE2_IDS = frozenset(range(173, 183))  # 173–182


# ---------------------------------------------------------------------------
# Task loading
# ---------------------------------------------------------------------------

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


READONLY_TASKS: List[Dict[str, Any]] = _load_tasks()


# session_event_loop, agent_runner, and result_log fixtures are defined in
# conftest.py and shared across all agent test files.

# ---------------------------------------------------------------------------
# Failure message helper
# ---------------------------------------------------------------------------

def _make_failure_message(
    task: Dict[str, Any],
    agent_result: Optional[Dict[str, Any]],
) -> str:
    ev = task.get("eval", {})
    ra = ev.get("reference_answers", {})
    tid = task["task_id"]

    phase = (
        "Phase 1 (navigation)" if tid in PHASE1_IDS else
        "Phase 2 (issue status)" if tid in PHASE2_IDS else
        "Phase 3 (info retrieval)"
    )

    lines = [
        f"Task {tid} FAILED  [{phase}]",
        f"  intent      : {task['intent']}",
        f"  sites       : {task.get('sites', [])}",
    ]

    if ra.get("must_include"):
        lines.append(f"  must_include: {ra['must_include']}")
    if ra.get("must_exclude"):
        lines.append(f"  must_exclude: {ra['must_exclude']}")
    if ra.get("exact_match") is not None:
        lines.append(f"  exact_match : {ra['exact_match']!r}")
    if ra.get("fuzzy_match") is not None:
        lines.append(f"  fuzzy_match : {ra['fuzzy_match']!r}")
    if ev.get("string_note"):
        lines.append(f"  string_note : {ev['string_note']}")

    if agent_result is not None:
        answer = agent_result.get("answer", "")
        snippet = str(answer)[:400] if answer else "(empty)"
        lines.append(f"  agent_answer: {snippet!r}")

        must_include = ra.get("must_include", [])
        if must_include and answer:
            answer_lower = str(answer).lower()
            missing = [
                item for item in must_include
                if isinstance(item, str) and item.lower() not in answer_lower
            ]
            if missing:
                lines.append(f"  missing     : {missing}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Parameterised integration tests — one per task
# ---------------------------------------------------------------------------

def _task_id(task: Dict[str, Any]) -> str:
    site = task.get("sites", ["unknown"])[0]
    return f"task_{task['task_id']}_{site}"


def pytest_generate_tests(metafunc):
    if "task" in metafunc.fixturenames:
        tasks = _get_tasks(metafunc.config)
        metafunc.parametrize("task", tasks, ids=[_task_id(t) for t in tasks])


def test_agent_produces_correct_answer(
    agent_runner,
    session_event_loop,
    result_log,
    task: Dict[str, Any],
) -> None:
    """
    Assert the agent returns a correct answer for a read-only GitLab task.

    All tasks use string_match evaluation:
      - must_include : every listed string must appear in the answer
                       (case-insensitive substring match)
      - must_exclude : no listed string may appear in the answer
      - exact_match  : answer must equal reference after whitespace
                       normalisation and case-folding
      - fuzzy_match  : each reference item must appear approximately
                       (sliding-window SequenceMatcher ratio >= 0.8)

    All tasks have require_reset=True — a GitLab state reset runs before each task.
    """
    passed, agent_result, error, _html_detail = session_event_loop.run_until_complete(
        agent_runner.run_agent_on_task(task)
    )

    result_log.append({
        "task_id":    task["task_id"],
        "intent":     task.get("intent", ""),
        "sites":      task.get("sites", []),
        "eval_types": task.get("eval", {}).get("eval_types", []),
        "passed":     passed and not error,
        "answer":     agent_result.get("answer") if agent_result else None,
        "error":      error,
    })

    if error:
        pytest.fail(
            f"Task {task['task_id']}: agent returned an error: {error}"
        )

    assert passed, _make_failure_message(task, agent_result)
