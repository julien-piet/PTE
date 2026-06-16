# eval/tests/test_agent_reddit_program_html.py
#
# Integration tests: run the agent on every Reddit program_html task in
# reddit_verified_program_html.json.
#
# Run all tasks:
#   python3 -m pytest eval/tests/test_agent_reddit_program_html.py -v
#
# Smoke test (first 5 tasks):
#   python3 -m pytest eval/tests/test_agent_reddit_program_html.py --task-limit 5 -v -s
#
# Single task by ID:
#   python3 -m pytest eval/tests/test_agent_reddit_program_html.py --task-id 465 -v -s
#
# Multiple tasks by ID:
#   python3 -m pytest eval/tests/test_agent_reddit_program_html.py --task-id 465,521 -v -s
#
# Save results to a JSON log:
#   python3 -m pytest eval/tests/test_agent_reddit_program_html.py -v --output reddit_program_html_results.json
#
# Force-reset Reddit state before every task:
#   python3 -m pytest eval/tests/test_agent_reddit_program_html.py -v --force-reset
#
# Resume a previous run:
#   python3 -m pytest eval/tests/test_agent_reddit_program_html.py -v --output reddit_program_html_results.json --resume

import asyncio
import json
import os
import sys
import tempfile
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
from dotenv import dotenv_values as _dotenv_values

from agent.auth import StaticAuth
from config.init_tokens.refresh_reddit_session import refresh_session as _refresh_reddit_session
from config.servers import SERVER_URLS as _SERVER_URLS
from eval.run_program_html_benchmark import AgentRunner
from eval.tests.agent_test_utils import extract_agent_details, task_status

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

TASK_FILE = Path(__file__).parent / "test_files" / "reddit_verified_program_html.json"
LOGS_DIR = Path(__file__).parent / "logs"

_ENV_FILE = Path(__file__).parent.parent.parent / "config" / ".env"
_REDDIT_USERNAME: str = _dotenv_values(_ENV_FILE).get("REDDIT_USERNAME", "MarvelsGrantMan136")

# Task IDs whose mutations conflict with other tasks in this suite.
BIO_TASK_IDS: frozenset = frozenset({399, 400, 401, 402, 403})
HREKIRES_TASK_IDS: frozenset = frozenset({724, 730})

# The 10 posts shared by tasks 724 (like-all) and 730 (dislike-all).
_HREKIRES_POST_PATHS = [
    "/f/news/129816/gov-whitmer-signs-bills-to-repeal-right-to-work-restore",
    "/f/news/129808/disney-world-deal-with-union-will-raise-minimum-wage-to-18",
    "/f/news/129794/judge-halts-wyoming-abortion-ban-days-after-it-took-effect",
    "/f/news/129783/don-t-say-gay-lawmaker-pleads-guilty-to-covid-relief-fraud",
    "/f/news/129594/arizona-gov-katie-hobbs-refuses-to-proceed-with-execution",
    "/f/news/129508/tennessee-governor-oks-bill-to-cut-nashville-council-in-half",
    "/f/news/43839/philadelphia-da-larry-krasner-impeached-by-pa-house",
    "/f/news/43781/crypto-giant-ftx-to-file-for-bankruptcy-ceo-sam-bankman",
    "/f/news/43572/sec-doj-investigating-crypto-platform-ftx",
    "/f/news/43558/kansas-gov-laura-kelly-wins-re-election-defeating-gop",
]


@asynccontextmanager
async def _local_session(reddit_url: str):
    """Stub worker session for a single local Reddit instance."""
    yield {"worker_id": "local", "reddit_url": reddit_url}


# ---------------------------------------------------------------------------
# Task loading
# ---------------------------------------------------------------------------

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
    return tasks


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_bio(base_url: str, phpsessid: str, username: str) -> str:
    """Return the current value of the user's biography field."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        ctx.add_cookies([{"name": "PHPSESSID", "value": phpsessid, "url": base_url}])
        page = ctx.new_page()
        page.goto(f"{base_url}/user/{username}/edit_biography", wait_until="networkidle")
        bio = page.input_value("#user_biography_biography")
        browser.close()
    return bio


def _restore_bio(base_url: str, phpsessid: str, username: str, bio_value: str) -> None:
    """Reset the user's biography to bio_value via Playwright form submission.

    The bio form's submit button has no type="submit" attribute, so we target
    it via the form name rather than a type selector.
    """
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        ctx.add_cookies([{"name": "PHPSESSID", "value": phpsessid, "url": base_url}])
        page = ctx.new_page()
        page.goto(f"{base_url}/user/{username}/edit_biography", wait_until="networkidle")
        page.fill("#user_biography_biography", bio_value)
        page.locator("form[name='user_biography'] button").click()
        page.wait_for_load_state("networkidle")
        browser.close()
    print(f"  [restore] Bio reset to {bio_value!r}")


def _restore_hrekires_votes(base_url: str, phpsessid: str) -> None:
    """Un-vote any active vote on each Hrekires/news post, returning them to neutral.

    Postmill sets the retract button to value="0" when a vote is active, regardless
    of direction — clicking it un-votes.  In neutral state no value="0" button exists,
    so we skip cleanly.
    """
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        ctx.add_cookies([{"name": "PHPSESSID", "value": phpsessid, "url": base_url}])
        page = ctx.new_page()
        for path in _HREKIRES_POST_PATHS:
            try:
                page.goto(f"{base_url}{path}", wait_until="networkidle", timeout=15000)
                retract = page.locator("div.submission__vote form button[value='0']")
                if retract.count() > 0:
                    retract.first.click()
                    page.wait_for_load_state("networkidle", timeout=8000)
            except Exception as exc:
                print(f"  [restore] Warning: could not restore vote on {path}: {exc}")
        browser.close()
    print("  [restore] Hrekires votes reset to neutral")


def _build_log_entry(r: dict) -> dict:
    task = r["task"]
    return {
        "task_id":         task["task_id"],
        "intent":          task.get("intent", ""),
        "eval_types":      task.get("eval", {}).get("eval_types", []),
        "read_only":       task.get("read_only"),
        "passed":          bool(r["passed"]) and not r["error"],
        "status":          r.get("status"),
        "answer":          r["agent_result"].get("answer") if r["agent_result"] else None,
        "error":           r["error"],
        "worker_id":       r.get("worker_id"),
        "plan":            r.get("plan"),
        "plan_step_count": len(r["plan"]) if r.get("plan") else None,
        "execution":       r.get("execution"),
        "parsed_outputs":  r.get("parsed_outputs"),
        "planning_log":    r.get("planning_log"),
    }


def _flush_result(out_path: Path, entry: dict) -> None:
    """Append a single completed task result to the output file immediately."""
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

def test_agent_accomplishes_reddit_tasks(
    session_event_loop,
    acquire_lock,
    result_log,
    request,
) -> None:
    tasks = _load_tasks(request.config)
    force_reset = request.config.getoption("--force-reset", default=False)
    base_url = request.config.getoption("--base-url") or _SERVER_URLS["reddit"]

    output_name = request.config.getoption("--output", default=None)
    if not output_name:
        output_name = "reddit_program_html_results.json"
    out_path = LOGS_DIR / output_name

    print(f"\nRefreshing Reddit session from {base_url} ...")
    phpsessid = _refresh_reddit_session(base_url=base_url)
    print(f"  PHPSESSID refreshed (prefix={phpsessid[:8]}...)")

    n_workers = 1
    print(f"\nRunning {len(tasks)} tasks with {n_workers} worker")
    print(f"Results written incrementally to {out_path} — safe to Ctrl+C and resume with --resume")

    async def run_all() -> list:
        sem = asyncio.Semaphore(n_workers)
        write_lock = asyncio.Lock()
        remaining = len(tasks)
        remaining_lock = asyncio.Lock()

        # Capture the bio before any bio task can overwrite it so we can restore
        # it after each of tasks 399-403.  Skip if no bio tasks are in this run.
        original_bio: str = ""
        if any(t["task_id"] in BIO_TASK_IDS for t in tasks):
            loop = asyncio.get_event_loop()
            original_bio = await loop.run_in_executor(
                None, _read_bio, base_url, phpsessid, _REDDIT_USERNAME
            )
            print(f"  [restore] Original bio captured: {original_bio!r}")

        async def run_one(task: Dict[str, Any]) -> Dict[str, Any]:
            async with sem:
                try:
                    async with _local_session(base_url) as w:
                        runner = AgentRunner(headless=True, enable_reset=False, force_reset=False)
                        runner.server = "reddit"
                        # The agent's tool calls go to the FastAPI MCP server
                        # (reddit_extra, default 127.0.0.1:7791), NOT to Postmill
                        # itself (reddit, 127.0.0.1:9999, used for login/session
                        # refresh above). Mirrors scripts/run_tasks_batch_new.py
                        # which routes `reddit` calls to reddit_extra's URL.
                        runner.base_url = _SERVER_URLS["reddit_extra"]

                        await runner._init_agent()

                        if runner._agent.execution_agent is not None:
                            runner._agent.execution_agent.auth = StaticAuth({
                                "Cookie": f"PHPSESSID={phpsessid}",
                                "X-Experimental-API": "1",
                            })
                            runner._agent.execution_agent.task_id = str(task["task_id"])

                        run_task = task
                        if force_reset and not task.get("read_only", False):
                            run_task = {**task, "require_reset": True}

                        passed, agent_result, error, html_detail = await runner.run_agent_on_task(run_task)

                        # --- State restoration for conflicting tasks ---
                        # Run after the eval so the agent's mutation is captured,
                        # but before the next task acquires the semaphore.
                        _loop = asyncio.get_event_loop()
                        if task["task_id"] in BIO_TASK_IDS:
                            await _loop.run_in_executor(
                                None, _restore_bio, base_url, phpsessid, _REDDIT_USERNAME, original_bio
                            )
                        elif task["task_id"] in HREKIRES_TASK_IDS:
                            await _loop.run_in_executor(
                                None, _restore_hrekires_votes, base_url, phpsessid
                            )

                        async with remaining_lock:
                            nonlocal remaining
                            remaining -= 1
                            outcome = "PASS" if passed and not error else "FAIL"
                            print(f"\n[{remaining} tasks remaining] Task {task['task_id']} done ({outcome})")

                        details = extract_agent_details(runner)
                        status = task_status(passed, error, details["plan_steps"])

                        result = {
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
                    result = {
                        "task": task,
                        "passed": False,
                        "agent_result": None,
                        "error": str(e),
                        "html_detail": None,
                        "plan": None,
                        "parsed_outputs": None,
                        "execution": None,
                        "planning_log": None,
                        "worker_id": None,
                        "status": "failed",
                    }

                entry = _build_log_entry(result)
                async with write_lock:
                    await asyncio.get_event_loop().run_in_executor(
                        None, _flush_result, out_path, entry
                    )

                return result

        futures = [asyncio.ensure_future(run_one(t)) for t in tasks]
        try:
            return list(await asyncio.gather(*futures))
        except BaseException:
            print("\nInterrupted — cancelling remaining tasks...")
            for f in futures:
                f.cancel()
            all_results = await asyncio.gather(*futures, return_exceptions=True)
            return [r for r in all_results if isinstance(r, dict)]

    try:
        results = session_event_loop.run_until_complete(run_all())
        interrupted = False
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt — completed tasks already saved to disk.")
        interrupted = True
        results = []

    failures = []
    for r in results:
        task = r["task"]
        passed = r["passed"]
        error = r["error"]

        result_log.append(_build_log_entry(r))

        if error:
            failures.append(f"Task {task['task_id']}: agent error: {error}")
        elif not passed:
            failures.append(_make_failure_message(task, r["agent_result"], r["html_detail"]))

    if interrupted:
        print(f"\nResults saved to {out_path} — re-run with --resume to continue.")
        pytest.exit("Interrupted by user", returncode=1)

    total = len(results)
    passed_count = sum(1 for r in results if r["passed"] and not r["error"])
    failed_count = total - passed_count
    print(f"\nResults: {passed_count}/{total} passed, {failed_count}/{total} failed")

    if failures:
        pytest.fail("\n\n".join(failures))
