# eval/tests/test_agent_reddit_string_match.py
#
# Integration tests: run the agent on every task in
# reddit_verified_string_match.json (string_match eval type).
#
# Run all tasks:
#   python3 -m pytest eval/tests/test_agent_reddit_string_match.py -v
#
# Smoke test (first 5 tasks):
#   python3 -m pytest eval/tests/test_agent_reddit_string_match.py --task-limit 5 -v -s
#
# Single task by ID:
#   python3 -m pytest eval/tests/test_agent_reddit_string_match.py --task-id 389 -v -s
#
# Multiple tasks by ID:
#   python3 -m pytest eval/tests/test_agent_reddit_string_match.py --task-id 389,412 -v -s
#
# Save results to a JSON log:
#   python3 -m pytest eval/tests/test_agent_reddit_string_match.py -v --output reddit_string_match_results.json
#
# Force-reset Reddit state before every task:
#   python3 -m pytest eval/tests/test_agent_reddit_string_match.py -v --force-reset

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from agent.auth import StaticAuth
from config.init_tokens.refresh_reddit_session import refresh_session as _refresh_reddit_session
from config.servers import SERVER_URLS as _SERVER_URLS

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

TASK_FILE = Path(__file__).parent / "test_files" / "reddit_verified_string_match.json"
LOGS_DIR = Path(__file__).parent / "logs"


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
        else:
            resume = config.getoption("--resume", default=False)
            output_name = config.getoption("--output", default=None)
            if resume and output_name:
                out_path = LOGS_DIR / output_name
                if out_path.exists():
                    prior = json.loads(out_path.read_text())
                    done_ids = {r["task_id"] for r in prior.get("results", [])}
                    before = len(tasks)
                    tasks = [t for t in tasks if t["task_id"] not in done_ids]
                    print(f"\n--resume: skipping {before - len(tasks)} already-completed tasks, {len(tasks)} remaining")
            limit = config.getoption("--task-limit", default=None)
            if limit is not None:
                tasks = tasks[:limit]
    return tasks


ALL_TASKS: List[Dict[str, Any]] = _load_tasks()


def _task_id(task: Dict[str, Any]) -> str:
    site = task.get("sites", ["reddit"])[0]
    return f"task_{task['task_id']}_{site}"


def pytest_generate_tests(metafunc):
    if "task" in metafunc.fixturenames:
        tasks = _get_tasks(metafunc.config)
        metafunc.parametrize("task", tasks, ids=[_task_id(t) for t in tasks])


@pytest.fixture(scope="session", autouse=True)
def _inject_reddit_token(agent_runner, request):
    """
    Fetch a fresh Reddit PHPSESSID once at session start and inject it into
    the shared agent runner as a StaticAuth cookie header.

    The Postmill Reddit clone uses cookie-based session auth (PHPSESSID).
    All API calls also need the X-Experimental-API header to access the
    JSON API endpoints used by the MCP server.
    """
    base_url = (
        request.config.getoption("--base-url", default=None)
        or getattr(agent_runner, "base_url", None)
        or _SERVER_URLS["reddit"]
    )
    if agent_runner._agent is None or agent_runner._agent.execution_agent is None:
        raise RuntimeError(
            "execution_agent is not initialised — cannot inject Reddit token. "
            "Ensure _init_agent() completed successfully before this fixture runs."
        )
    print(f"\nRefreshing Reddit session from {base_url} ...")
    phpsessid = _refresh_reddit_session(base_url=base_url)
    agent_runner._agent.execution_agent.auth = StaticAuth({
        "Cookie": f"PHPSESSID={phpsessid}",
        "X-Experimental-API": "1",
    })
    agent_runner.server = "reddit"
    agent_runner.base_url = base_url
    print(f"  Reddit PHPSESSID injected (prefix={phpsessid[:8]}...)")


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


def _flush_result(out_path: Path, entry: dict) -> None:
    """Append a single completed task result to the output file immediately."""
    import os
    import tempfile
    from datetime import datetime, timezone

    out_path.parent.mkdir(exist_ok=True)

    summary = {"results": []}
    if out_path.exists():
        try:
            summary = json.loads(out_path.read_text())
        except Exception:
            pass

    results = summary.get("results", [])
    results = [r for r in results if r.get("task_id") != entry["task_id"]]
    results.append(entry)

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total":  len(results),
        "passed": sum(1 for r in results if r.get("passed")),
        "failed": sum(1 for r in results if not r.get("passed")),
        "results": results,
    }

    tmp_fd, tmp_path = tempfile.mkstemp(dir=out_path.parent, suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w") as f:
            json.dump(summary, f, indent=2)
        os.replace(tmp_path, out_path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def test_agent_produces_correct_answer(
    agent_runner,
    session_event_loop,
    result_log,
    request,
    task: Dict[str, Any],
) -> None:
    output_name = request.config.getoption("--output", default=None)
    if not output_name:
        output_name = "reddit_string_match_results.json"
    out_path = LOGS_DIR / output_name

    passed, agent_result, error, _html_detail = session_event_loop.run_until_complete(
        agent_runner.run_agent_on_task(task)
    )

    entry = {
        "task_id":    task["task_id"],
        "intent":     task.get("intent", ""),
        "sites":      task.get("sites", []),
        "eval_types": task.get("eval", {}).get("eval_types", []),
        "passed":     passed and not error,
        "answer":     agent_result.get("answer") if agent_result else None,
        "error":      error,
    }
    result_log.append(entry)
    _flush_result(out_path, entry)

    if error:
        pytest.fail(f"Task {task['task_id']}: agent returned an error: {error}")

    assert passed, _make_failure_message(task, agent_result)
