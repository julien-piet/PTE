#!/usr/bin/env python3
"""
Run ReactAgentRunner on WebArena-Verified tasks and save output files for evaluation.

Each completed task produces:
    {output_dir}/{task_id}/agent_response.json   — structured JSON answer
    {output_dir}/{task_id}/network.zip           — Playwright network trace

Usage:
    # Run all GitLab tasks (single worker)
    python eval/run_webarena_verified.py --site gitlab --output-dir wa_output

    # Run specific task IDs
    python eval/run_webarena_verified.py --task-ids 44 108 --output-dir wa_output

    # Cap to first 10 tasks
    python eval/run_webarena_verified.py --site gitlab --task-limit 10 --output-dir wa_output

    # Multi-docker (parallel remote workers)
    python eval/run_webarena_verified.py --site gitlab --multi-docker --output-dir wa_output

    # Run and then evaluate with webarena-verified CLI
    python eval/run_webarena_verified.py --site gitlab --output-dir wa_output \\
        --evaluate --config examples/configs/config.example.json
"""

import argparse
import asyncio
import json
import subprocess
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_DEFAULT_DATASET = _PROJECT_ROOT / "eval" / "tests" / "test_files" / "webarena-verified.json"

from config.servers import SERVER_URLS as _SERVER_URLS
from eval.docker import workers_new as _workers_new
from eval.tests.agent_test_utils import build_detailed_entry, flush_detailed_jsonl, get_model_id
from react_agent.react_agent_runner import ReactAgentRunner


# ---------------------------------------------------------------------------
# Local (single-worker) session — mirrors test_react_agent_gitlab.py
# ---------------------------------------------------------------------------

@asynccontextmanager
async def _local_session(base_url: str, glpat=None):
    yield {"worker_id": "local", "server_url": base_url, "gitlab_url": base_url, "glpat": glpat}


# ---------------------------------------------------------------------------
# PTE task index — site → task_id → task dict with real eval criteria
# ---------------------------------------------------------------------------

_PTE_FILES: dict[str, list[str]] = {
    "gitlab": [
        "gitlab_verified_string_match.json",
        "gitlab_verified_program_html.json",
    ],
    # future: "shopping": [...], "reddit": [...], etc.
}


def _build_pte_index() -> dict[str, dict[int, dict]]:
    """Load PTE task files and index them by site → task_id."""
    index: dict[str, dict[int, dict]] = {}
    test_files_dir = _PROJECT_ROOT / "eval" / "tests" / "test_files"
    for site, fnames in _PTE_FILES.items():
        site_tasks: dict[int, dict] = {}
        for fname in fnames:
            fp = test_files_dir / fname
            if fp.exists():
                for t in json.loads(fp.read_text()):
                    site_tasks[t["task_id"]] = t
            else:
                print(f"  ⚠️  PTE task file not found: {fp}")
        index[site] = site_tasks
    return index


# ---------------------------------------------------------------------------
# Task format normalization
# ---------------------------------------------------------------------------

def _normalize_task(task: dict, pte_index: dict[str, dict[int, dict]]) -> dict:
    """Convert WA-Verified task format to what BaseAgentRunner.run_agent_on_task expects.

    Uses real PTE eval criteria (string_match / program_html) when a counterpart
    exists in the PTE task files; falls back to an empty string_match otherwise.

    WA-Verified differences from PTE format:
      - eval: list of evaluator dicts  →  dict with eval_types/reference_answers
      - start_urls: list               →  start_url: str
    """
    t = dict(task)
    # start_url
    if "start_url" not in t:
        urls = t.get("start_urls") or []
        t["start_url"] = urls[0] if urls else "__GITLAB__"
    # eval — prefer PTE criteria when available
    task_id = t.get("task_id")
    task_site = (t.get("sites") or ["gitlab"])[0]
    pte_task = pte_index.get(task_site, {}).get(task_id)
    if pte_task and isinstance(pte_task.get("eval"), dict):
        t["eval"] = pte_task["eval"]
    elif isinstance(t.get("eval"), list):
        t["eval"] = {
            "eval_types": ["string_match"],
            "reference_answers": {},
            "reference_url": "",
            "program_html": [],
        }
    return t


# ---------------------------------------------------------------------------
# Task loading
# ---------------------------------------------------------------------------

def _load_tasks(
    dataset_path: Path,
    site: str | None,
    task_ids: list[int] | None,
    task_limit: int | None,
    start_id: int | None = None,
) -> list[dict]:
    tasks = json.loads(dataset_path.read_text())

    if task_ids:
        id_set = set(task_ids)
        tasks = [t for t in tasks if t.get("task_id") in id_set]
        if not tasks:
            print(f"ERROR: No tasks found for task IDs {task_ids}")
            sys.exit(1)
    elif site:
        tasks = [t for t in tasks if site in (t.get("sites") or [])]
        if not tasks:
            print(f"ERROR: No tasks found for site '{site}'")
            sys.exit(1)

    if start_id is not None:
        tasks = [t for t in tasks if t.get("task_id") >= start_id]
        if not tasks:
            print(f"ERROR: No tasks found with task_id >= {start_id}")
            sys.exit(1)

    if task_limit is not None:
        tasks = tasks[:task_limit]

    return tasks


# ---------------------------------------------------------------------------
# Evaluator call
# ---------------------------------------------------------------------------

def _run_evaluator(output_dir: Path, task_ids: list[int], config_path: str) -> None:
    cmd = [
        "webarena-verified", "eval-tasks",
        "--task-ids", *[str(i) for i in task_ids],
        "--output-dir", str(output_dir),
        "--config", config_path,
    ]
    print(f"\n{'='*60}")
    print("Running WebArena-Verified evaluator...")
    print(f"  Command: {' '.join(cmd)}")
    print(f"{'='*60}\n")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"\nWARNING: evaluator exited with code {result.returncode}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run ReactAgent on WebArena-Verified tasks and save evaluation artifacts"
    )
    parser.add_argument(
        "--site",
        help="Filter tasks by site (gitlab, shopping, shopping_admin, reddit, wikipedia, map)",
    )
    parser.add_argument(
        "--task-ids",
        nargs="+",
        type=int,
        metavar="ID",
        help="Specific task IDs to run (overrides --site)",
    )
    parser.add_argument(
        "--task-limit",
        type=int,
        default=None,
        metavar="N",
        help="Cap the number of tasks to run (applied after --site / --task-ids filtering)",
    )
    parser.add_argument(
        "--start-id",
        type=int,
        default=None,
        metavar="ID",
        help="Skip all tasks with task_id < ID (resume from a specific task onwards)",
    )
    parser.add_argument(
        "--output-dir",
        default="wa_output",
        help="Directory to write per-task output files (default: wa_output)",
    )
    parser.add_argument(
        "--dataset",
        default=str(_DEFAULT_DATASET),
        help=f"Path to webarena-verified.json (default: {_DEFAULT_DATASET})",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Override the site base URL (e.g. http://localhost:8024 for gitlab)",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=30,
        help="Max ReAct loop iterations per task (default: 30)",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run browser in headed (visible) mode",
    )
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="Disable pre-task state reset",
    )
    parser.add_argument(
        "--force-reset",
        action="store_true",
        help="Force state reset before every task regardless of require_reset flag",
    )
    parser.add_argument(
        "--multi-docker",
        action="store_true",
        help="Use remote multi-docker worker pool (requires REMOTE_HOST in config/.env)",
    )
    parser.add_argument(
        "--evaluate",
        action="store_true",
        help="Run webarena-verified eval-tasks after all tasks finish",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to webarena-verified config JSON (required with --evaluate)",
    )
    args = parser.parse_args()

    if args.evaluate and not args.config:
        parser.error("--config is required when --evaluate is set")

    pte_index = _build_pte_index()

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"ERROR: Dataset not found: {dataset_path}")
        sys.exit(1)

    tasks = _load_tasks(dataset_path, args.site, args.task_ids, args.task_limit, args.start_id)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # site/base_url used for display and local-mode fallback only.
    # In multi-docker mode each task resolves its own site from task["sites"][0].
    display_site = args.site or (tasks[0]["sites"][0] if tasks else "gitlab")
    default_base_url = args.base_url or _SERVER_URLS.get(display_site, _SERVER_URLS.get("gitlab", ""))

    if args.multi_docker:
        n_workers = _workers_new.num_workers()
    else:
        n_workers = 1

    pte_site_tasks = pte_index.get(display_site, {})
    pte_coverage = sum(1 for t in tasks if t.get("task_id") in pte_site_tasks)

    print(f"\n{'='*60}")
    print(f"WebArena-Verified Run")
    print(f"  Site        : {display_site}")
    print(f"  Tasks       : {len(tasks)}")
    print(f"  Workers     : {n_workers} ({'multi-docker' if args.multi_docker else 'local'})")
    print(f"  Output dir  : {output_dir.resolve()}")
    print(f"  Iterations  : {args.max_iterations}")
    print(f"  PTE eval    : {pte_coverage}/{len(tasks)} tasks have PTE counterpart (string_match/program_html)")
    print(f"{'='*60}\n")

    run_ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    detailed_path = output_dir / f"run_summary_{run_ts}_detailed.jsonl"

    sem = asyncio.Semaphore(n_workers)
    acquire_lock = asyncio.Lock()
    remaining = len(tasks)
    record_lock = asyncio.Lock()
    results: list[dict] = []

    async def run_one(task: dict) -> dict:
        nonlocal remaining
        task_id = task.get("task_id")
        read_only = task.get("read_only", False)
        task_site = (task.get("sites") or [display_site])[0]
        pte_task = pte_index.get(task_site, {}).get(task_id)
        if pte_task:
            pte_eval_types = pte_task.get("eval", {}).get("eval_types", [])
            eval_source = "pte_" + (pte_eval_types[0] if pte_eval_types else "unknown")
        else:
            eval_source = "wa_only"

        async with sem:
            if args.multi_docker:
                worker_ctx = _workers_new.worker_session(
                    str(task_id),
                    server=task_site,
                    acquire_lock=acquire_lock,
                    read_only=read_only,
                )
            else:
                task_base_url = args.base_url or _SERVER_URLS.get(task_site, default_base_url)
                worker_ctx = _local_session(task_base_url)

            async with worker_ctx as w:
                base_url = w.get("server_url") or w.get("gitlab_url") or default_base_url
                runner = ReactAgentRunner(
                    headless=not args.headed,
                    enable_reset=not args.no_reset,
                    force_reset=args.force_reset,
                    gitlab_base_url=base_url,
                    max_iterations=args.max_iterations,
                    webarena_output_dir=str(output_dir),
                    wa_dataset_path=str(dataset_path),
                )
                runner.server = task_site
                runner.base_url = base_url
                if w.get("glpat"):
                    runner.glpat = w["glpat"]

                await runner._init_agent()

                start = datetime.now(timezone.utc)
                _task_timeout = args.max_iterations * 200  # ~3.3 min/iter max
                try:
                    passed, agent_result, error, _ = await asyncio.wait_for(
                        runner.run_agent_on_task(_normalize_task(task, pte_index)),
                        timeout=_task_timeout,
                    )
                except asyncio.TimeoutError:
                    passed, agent_result, error = False, None, f"task_timeout: exceeded {_task_timeout}s wall-clock limit"
                    print(f"  ⚠️  Task {task_id} timed out after {_task_timeout}s")
                except Exception as exc:
                    passed, agent_result, error = False, None, str(exc)
                end = datetime.now(timezone.utc)

                llm = getattr(getattr(runner, "_react_agent", None), "llm", None)
                task_cost = getattr(llm, "total_cost", None)
                costs = [task_cost] if task_cost is not None else []

        correct = passed and not error
        outcome = "PASS" if correct else ("ERROR" if error else "FAIL")
        entry = {
            "task_id": task_id,
            "intent": task.get("intent", ""),
            "passed": correct,
            "eval_source": eval_source,
            "error": error,
            "answer": (agent_result or {}).get("answer"),
            "worker_id": w["worker_id"],
            "duration_s": (end - start).seconds,
        }

        det_entry = build_detailed_entry(
            task=task,
            agent_result=agent_result,
            error=error,
            correct=correct,
            start_time=start,
            end_time=end,
            eval_output_dir=str(output_dir),
            costs=costs,
        )

        # Append result summary to the per-task log file (runner already closed it).
        _task_log_path = output_dir / str(task_id) / "agent.log"
        try:
            with open(_task_log_path, "a") as _lf:
                _lf.write(f"\n[Result] {outcome} [{eval_source}] | duration={entry['duration_s']}s\n")
                if error:
                    _lf.write(f"[Error] {error}\n")
        except OSError:
            pass

        async with record_lock:
            remaining -= 1
            results.append(entry)
            flush_detailed_jsonl(detailed_path, det_entry)
            print(f"\n[{remaining} remaining] Task {task_id} → {outcome} [{eval_source}] ({entry['duration_s']}s)")
            if error:
                print(f"  Error: {error}")

        return entry

    futures = [asyncio.ensure_future(run_one(t)) for t in tasks]
    try:
        await asyncio.gather(*futures)
    except KeyboardInterrupt:
        print("\nInterrupted — cancelling remaining tasks...")
        for f in futures:
            f.cancel()
        await asyncio.gather(*futures, return_exceptions=True)

    # Write summary
    summary_path = output_dir / f"run_summary_{run_ts}.json"
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": get_model_id(),
        "site": display_site,
        "multi_docker": args.multi_docker,
        "total": len(results),
        "passed": sum(1 for r in results if r["passed"]),
        "failed": sum(1 for r in results if not r["passed"]),
        "pte_eval_count": sum(1 for r in results if r.get("eval_source", "").startswith("pte_")),
        "wa_only_count": sum(1 for r in results if r.get("eval_source") == "wa_only"),
        "results": results,
    }
    summary_path.write_text(json.dumps(summary, indent=2))

    total = len(results)
    passed_count = summary["passed"]
    print(f"\n{'='*60}")
    print(f"Done: {passed_count}/{total} tasks produced output files")
    print(f"Summary : {summary_path}")
    print(f"Detailed: {detailed_path}")
    print(f"{'='*60}\n")

    if args.evaluate:
        completed_ids = [r["task_id"] for r in results if r["task_id"] is not None]
        _run_evaluator(output_dir, completed_ids, args.config)


if __name__ == "__main__":
    asyncio.run(main())
