# eval/tests/test_agent_shopping_string_match.py
#
# Integration tests: run the agent on every task in
# shopping_verified_string_match.json (130 verified string_match tasks).
#
# Run all 130 tasks:
#   python3 -m pytest eval/tests/test_agent_shopping_string_match.py -v --server shopping
#
# Smoke test (first 5 tasks):
#   python3 -m pytest eval/tests/test_agent_shopping_string_match.py --task-limit 5 -v -s --server shopping
#
# Single task by ID:
#   python3 -m pytest eval/tests/test_agent_shopping_string_match.py -k "task_21" -v -s --server shopping
#
# Save results to a JSON log:
#   python3 -m pytest eval/tests/test_agent_shopping_string_match.py -v --server shopping --output shopping_string_match_results.json

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from agent.auth import StaticAuth
from config.init_tokens.refresh_shopping_tokens import refresh_tokens as _refresh_shopping_tokens
from config.servers import SERVER_URLS as _SERVER_URLS

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

TASK_FILE = Path(__file__).parent / "shopping_verified_string_match.json"


def _load_tasks() -> List[Dict[str, Any]]:
    with open(TASK_FILE) as f:
        return json.load(f)


def _get_tasks(config=None) -> List[Dict[str, Any]]:
    tasks = _load_tasks()
    if config is not None:
        task_id_opt = config.getoption("--task-id", default=None)
        if task_id_opt:
            ids = {int(x.strip()) for x in task_id_opt.split(",")}
            tasks = [t for t in tasks if t["task_id"] in ids]
        limit = config.getoption("--task-limit", default=None)
        if limit is not None:
            tasks = tasks[:limit]
    return tasks


ALL_TASKS: List[Dict[str, Any]] = _load_tasks()


def _task_id(task: Dict[str, Any]) -> str:
    site = task.get("sites", ["shopping"])[0]
    return f"task_{task['task_id']}_{site}"


def pytest_generate_tests(metafunc):
    if "task" in metafunc.fixturenames:
        tasks = _get_tasks(metafunc.config)
        metafunc.parametrize("task", tasks, ids=[_task_id(t) for t in tasks])


@pytest.fixture(scope="session", autouse=True)
def _inject_shopping_token(agent_runner, request):
    """
    Refresh the Magento admin Bearer token once per session and inject it into
    the shared agent runner.  Without a valid token, shopping REST API calls
    return 401 Unauthorized, causing nearly every task to fail.

    Mirrors the token-refresh logic in test_agent_all_shopping.py.
    """
    base_url = (
        request.config.getoption("--base-url", default=None)
        or getattr(agent_runner, "base_url", None)
        or _SERVER_URLS["shopping"]
    )
    print(f"\nRefreshing shopping admin token from {base_url} ...")
    token = _refresh_shopping_tokens(base_url=base_url)
    if token and agent_runner._agent and agent_runner._agent.execution_agent is not None:
        agent_runner._agent.execution_agent.auth = StaticAuth(
            {"Authorization": f"Bearer {token}"}
        )
        print(f"  Shopping admin token injected (length={len(token)})")
    else:
        print("  WARNING: Could not inject shopping token — execution_agent not available")


def _make_failure_message(
    task: Dict[str, Any],
    agent_result: Optional[Dict[str, Any]],
) -> str:
    ev = task.get("eval", {})
    ra = ev.get("reference_answers", {})
    lines = [
        f"Task {task['task_id']} FAILED",
        f"  intent       : {task['intent']}",
        f"  sites        : {task.get('sites', [])}",
        f"  eval_types   : {ev.get('eval_types', [])}",
    ]
    if ra.get("must_include"):
        lines.append(f"  must_include : {ra['must_include']}")
    if ra.get("must_exclude"):
        lines.append(f"  must_exclude : {ra['must_exclude']}")
    if ra.get("exact_match"):
        lines.append(f"  exact_match  : {ra['exact_match']!r}")
    if ra.get("fuzzy_match"):
        lines.append(f"  fuzzy_match  : {ra['fuzzy_match']!r}")
    if ev.get("string_note"):
        lines.append(f"  string_note  : {ev['string_note']}")
    if agent_result is not None:
        answer = agent_result.get("answer", "")
        snippet = str(answer)[:400] if answer else "(empty)"
        lines.append(f"  agent_answer : {snippet!r}")
        final_url = agent_result.get("final_url")
        if final_url:
            lines.append(f"  final_url    : {final_url}")
        must_include = ra.get("must_include", [])
        if must_include and answer:
            answer_lower = str(answer).lower()
            missing = [item for item in must_include
                       if isinstance(item, str) and item.lower() not in answer_lower]
            if missing:
                lines.append(f"  missing items: {missing}")
    return "\n".join(lines)


def test_agent_produces_correct_answer(
    agent_runner,
    session_event_loop,
    result_log,
    task: Dict[str, Any],
) -> None:
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
        pytest.fail(f"Task {task['task_id']}: agent returned an error: {error}")

    assert passed, _make_failure_message(task, agent_result)
