#!/usr/bin/env python3
"""
run_readonly_benchmark.py

Evaluate the 66 read-only GitLab tasks without pytest.

Single-worker mode (default):
    Runs tasks sequentially against the existing localhost:8023 tunnel.
    No orchestrator needed.

Multi-worker mode (--num-workers N --remote-host user@red5k):
    Distributes tasks across N Docker containers managed by the WebArena
    orchestrator.  Each worker runs on its own port (localhost:8024, 8025,
    8026, ...) via port_forwarding.sh.  Before each task with
    require_reset=True the worker's container is released and reinitialized
    via SSH, giving a fully clean GitLab state.

Prerequisites for multi-worker mode:
    1. SSH port forwarding running in a separate terminal:
           cd PTE/scripts/docker_parallel
           ./port_forwarding.sh sylvie@red5k.cs.berkeley.edu <N>
    2. Workers initialized on red5k:
           ssh sylvie@red5k.cs.berkeley.edu \\
               'python3 /scr2/webagent/webarena_orchestrator/orchestrator.py \\
                init --num-workers <N>'

Usage (from project root):
    # Single-worker, all 66 tasks:
    python3 eval/run_readonly_benchmark.py

    # Single-worker, subset:
    python3 eval/run_readonly_benchmark.py --limit 10
    python3 eval/run_readonly_benchmark.py --task-ids 293 294 295 296

    # Multi-worker (3 parallel Docker containers, full reset per task):
    python3 eval/run_readonly_benchmark.py \\
        --num-workers 3 \\
        --remote-host sylvie@red5k.cs.berkeley.edu

    # Save to a named file:
    python3 eval/run_readonly_benchmark.py --output after_fix.json

Output:
    eval/tests/logs/<output>.json  (default: readonly_<timestamp>.json)

Task breakdown (raw_webarena_tasks_gitlab_readonly.json — 66 tasks):
    Phase 1 (16):  Navigation / "show me" tasks
    Phase 2 (10):  Issue open/closed status (IDs 173-182)
    Phase 3 (40):  Information retrieval (commits, contributors, SSH, tokens)

All tasks have require_reset=True.  In single-worker mode this runs the
targeted GitLabStateReset cleanup.  In multi-worker mode it triggers a full
Docker container reset via the orchestrator.
"""

import asyncio
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

TASK_FILE = Path(__file__).parent / "tests" / "raw_webarena_tasks_gitlab_readonly.json"
LOGS_DIR  = Path(__file__).parent / "tests" / "logs"

PHASE1_IDS = frozenset({44, 45, 46, 102, 103, 104, 105, 106, 156, 258, 339, 340, 341, 342, 343, 357})
PHASE2_IDS = frozenset(range(173, 183))


# ---------------------------------------------------------------------------
# Task loading / filtering
# ---------------------------------------------------------------------------

def load_tasks(
    task_ids: Optional[List[int]] = None,
    start: int = 0,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    with open(TASK_FILE) as f:
        all_tasks = json.load(f)

    if task_ids is not None:
        id_set = set(task_ids)
        tasks = [t for t in all_tasks if t["task_id"] in id_set]
        id_order = {tid: i for i, tid in enumerate(task_ids)}
        tasks.sort(key=lambda t: id_order.get(t["task_id"], 0))
        missing = id_set - {t["task_id"] for t in tasks}
        if missing:
            print(f"  ⚠️  Task IDs not found in {TASK_FILE.name}: {sorted(missing)}")
    else:
        end = start + limit if limit else len(all_tasks)
        tasks = all_tasks[start:end]

    return tasks


# ---------------------------------------------------------------------------
# Failure diagnostics
# ---------------------------------------------------------------------------

def _missing_strings(task: Dict[str, Any], answer: Optional[str]) -> List[str]:
    """Return must_include strings absent from the agent's answer."""
    if not answer:
        return task["eval"].get("reference_answers", {}).get("must_include", [])
    ra = task["eval"].get("reference_answers", {})
    must_include = ra.get("must_include", [])
    answer_lower = answer.lower()
    return [
        item for item in must_include
        if isinstance(item, str) and item.lower() not in answer_lower
    ]


def _phase_label(task_id: int) -> str:
    if task_id in PHASE1_IDS:
        return "Phase 1 (navigation)"
    if task_id in PHASE2_IDS:
        return "Phase 2 (issue status)"
    return "Phase 3 (info retrieval)"


def _make_result(task, passed, agent_result, error) -> Dict[str, Any]:
    tid = task["task_id"]
    answer = agent_result.get("answer") if agent_result else None
    missing = _missing_strings(task, answer) if not passed and not error else []
    return {
        "task_id":          tid,
        "phase":            _phase_label(tid),
        "intent":           task.get("intent", ""),
        "sites":            task.get("sites", []),
        "eval_types":       task["eval"].get("eval_types", []),
        "passed":           passed and not error,
        "answer":           answer,
        "error":            error,
        "missing_strings":  missing,
        "reference_answers": task["eval"].get("reference_answers", {}),
    }


def _print_task_result(i: int, total: int, task, result: Dict[str, Any]) -> None:
    tid = task["task_id"]
    phase = result["phase"]
    intent = task.get("intent", "")
    print(f"\n[{i}/{total}] Task {tid} [{phase}]: {intent[:65]}")
    if result["error"]:
        print(f"   ⚠️  ERROR: {result['error'][:120]}")
    elif result["passed"]:
        print("   ✅ PASS")
    else:
        print("   ❌ FAIL")
        if result["missing_strings"]:
            print(f"      missing: {result['missing_strings']}")
        if result["answer"]:
            print(f"      answer : {str(result['answer'])[:200]!r}")


# ---------------------------------------------------------------------------
# Single-worker runner (sequential, uses localhost:8023)
# ---------------------------------------------------------------------------

async def run_sequential(
    tasks: List[Dict[str, Any]],
    server: str = "gitlab",
    force_reset: bool = False,
    enable_reset: bool = True,
) -> List[Dict[str, Any]]:
    """Run tasks one at a time against the default localhost:8023 GitLab."""
    from eval.run_program_html_benchmark import AgentRunner

    runner = AgentRunner(
        headless=True,
        enable_reset=enable_reset,
        force_reset=force_reset,
    )
    runner.server = server
    await runner._init_agent()

    results: List[Dict[str, Any]] = []
    for i, task in enumerate(tasks, 1):
        passed, agent_result, error, _ = await runner.run_agent_on_task(task)
        result = _make_result(task, passed, agent_result, error)
        results.append(result)
        _print_task_result(i, len(tasks), task, result)

    return results


# ---------------------------------------------------------------------------
# Multi-worker runner (parallel, Docker reset via orchestrator)
# ---------------------------------------------------------------------------

async def run_parallel(
    tasks: List[Dict[str, Any]],
    num_workers: int,
    remote_host: str,
    server: str = "gitlab",
    no_reset: bool = False,
) -> List[Dict[str, Any]]:
    """
    Distribute tasks across N Docker workers.

    Each worker:
    - Has its own GitLab container at localhost:{8023+worker_id}
    - Has its own copy of the API schema with the correct port
    - Resets its container via the orchestrator before tasks with require_reset=True
    """
    from eval.run_program_html_benchmark import AgentRunner
    from eval.docker_worker_pool import DockerWorkerPool

    source_api_dir = str(PROJECT_ROOT / "api")

    async with DockerWorkerPool(
        num_workers=num_workers,
        remote_host=remote_host,
        source_api_dir=source_api_dir,
    ) as pool:

        # Initialize one AgentRunner per worker (each uses a patched api dir)
        runners: Dict[int, AgentRunner] = {}
        for wid in range(1, num_workers + 1):
            worker = pool.get_worker(wid)
            runner = AgentRunner(
                headless=True,
                enable_reset=False,        # Docker reset handled by pool below
                api_dir=worker.api_dir,
                env_file=worker.env_file,  # per-worker PAT
                gitlab_base_url=worker.gitlab_base_url,  # for program_html Playwright checks
            )
            runner.server = server
            print(f"🔧 Initializing agent for worker {wid} (port {worker.port})...")
            await runner._init_agent()
            runners[wid] = runner

        # Distribute tasks round-robin across workers
        per_worker: List[List[Dict[str, Any]]] = [[] for _ in range(num_workers)]
        for idx, task in enumerate(tasks):
            per_worker[idx % num_workers].append(task)

        # Shared ordered results list (indexed by original task position)
        all_results: List[Optional[Dict[str, Any]]] = [None] * len(tasks)
        task_positions = {task["task_id"]: i for i, task in enumerate(tasks)}

        async def worker_loop(worker_id: int, worker_tasks: List[Dict[str, Any]]) -> None:
            worker = pool.get_worker(worker_id)
            runner = runners[worker_id]
            for task in worker_tasks:
                tid = task["task_id"]
                pos = task_positions[tid]

                # Full Docker reset before each task that requires it
                if task.get("require_reset") and not no_reset:
                    await pool.reset_worker(worker_id)

                passed, agent_result, error, _ = await runner.run_agent_on_task(task)
                result = _make_result(task, passed, agent_result, error)
                all_results[pos] = result
                _print_task_result(pos + 1, len(tasks), task, result)

        await asyncio.gather(*[
            worker_loop(wid, per_worker[wid - 1])
            for wid in range(1, num_workers + 1)
        ])

    return [r for r in all_results if r is not None]


# ---------------------------------------------------------------------------
# Summary printing
# ---------------------------------------------------------------------------

def print_summary(results: List[Dict[str, Any]], remote_host: Optional[str] = None) -> None:
    total   = len(results)
    passed  = sum(1 for r in results if r["passed"])
    errored = sum(1 for r in results if r["error"])
    failed  = total - passed

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    if remote_host:
        print(f"  Mode:    multi-worker ({remote_host})")
    print(f"  Total:   {total}")
    print(f"  ✅ Pass: {passed}   ({100*passed/total:.1f}%)" if total else "  ✅ Pass: 0")
    print(f"  ❌ Fail: {failed - errored}")
    print(f"  ⚠️  Err: {errored}")

    for phase_label, phase_ids in [
        ("Phase 1 (navigation)",     PHASE1_IDS),
        ("Phase 2 (issue status)",   PHASE2_IDS),
        ("Phase 3 (info retrieval)", None),
    ]:
        phase_results = [
            r for r in results
            if (phase_ids is not None and r["task_id"] in phase_ids)
            or (phase_ids is None
                and r["task_id"] not in PHASE1_IDS
                and r["task_id"] not in PHASE2_IDS)
        ]
        if not phase_results:
            continue
        p = sum(1 for r in phase_results if r["passed"])
        print(f"  {phase_label}: {p}/{len(phase_results)}")

    failures = [r for r in results if not r["passed"]]
    if failures:
        print("\n" + "-" * 70)
        print("FAILURES")
        print("-" * 70)
        for r in failures:
            print(f"\n  Task {r['task_id']}: {r['intent'][:65]}")
            if r.get("error"):
                print(f"    error  : {r['error'][:100]}")
            elif r.get("missing_strings"):
                print(f"    missing: {r['missing_strings']}")

    print("\n" + "=" * 70)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate read-only GitLab tasks (string_match) without pytest.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Task selection
    parser.add_argument(
        "--task-ids", nargs="+", type=int, default=None, metavar="ID",
        help="Run specific task IDs only. Overrides --start / --limit.",
    )
    parser.add_argument(
        "--start", type=int, default=0,
        help="Index of first task to run (default: 0).",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Maximum number of tasks to run (default: all).",
    )

    # Output
    parser.add_argument(
        "--output", type=str, default=None, metavar="FILENAME",
        help=(
            "Write results to eval/tests/logs/<FILENAME>. "
            "Defaults to readonly_<timestamp>.json."
        ),
    )

    # Agent / server
    parser.add_argument(
        "--server", type=str, default="gitlab",
        help="Auth server name from config/.server_env (default: gitlab).",
    )

    # Multi-worker / orchestrator
    parser.add_argument(
        "--num-workers", type=int, default=1, metavar="N",
        help=(
            "Number of parallel Docker workers (default: 1). "
            "When >1, requires --remote-host and port_forwarding.sh to be running."
        ),
    )
    parser.add_argument(
        "--remote-host", type=str, default=None, metavar="USER@HOST",
        help=(
            "SSH target for orchestrator commands, e.g. sylvie@red5k.cs.berkeley.edu. "
            "Required when --num-workers > 1."
        ),
    )

    # Reset control
    parser.add_argument(
        "--force-reset", action="store_true",
        help="(Single-worker) Force GitLab state reset before every task.",
    )
    parser.add_argument(
        "--no-reset", action="store_true",
        help=(
            "Disable state reset entirely. "
            "In single-worker mode skips GitLabStateReset; "
            "in multi-worker mode skips the Docker container release. "
            "Useful when containers are already clean (e.g. freshly init'd)."
        ),
    )

    args = parser.parse_args()

    # Validate multi-worker args
    if args.num_workers > 1 and not args.remote_host and not args.no_reset:
        parser.error("--remote-host is required when --num-workers > 1 (unless --no-reset)")

    tasks = load_tasks(task_ids=args.task_ids, start=args.start, limit=args.limit)
    if not tasks:
        print("No tasks to run.")
        sys.exit(0)

    mode = f"{args.num_workers} worker(s)" + (f" via {args.remote_host}" if args.remote_host else "")
    print(f"Running {len(tasks)} task(s) | mode: {mode} | server: {args.server!r}")
    print(f"Task file: {TASK_FILE}\n")

    # Run
    if args.num_workers > 1:
        results = await run_parallel(
            tasks,
            num_workers=args.num_workers,
            remote_host=args.remote_host,
            server=args.server,
            no_reset=args.no_reset,
        )
    else:
        results = await run_sequential(
            tasks,
            server=args.server,
            force_reset=args.force_reset,
            enable_reset=not args.no_reset,
        )

    print_summary(results, remote_host=args.remote_host if args.num_workers > 1 else None)

    # Save results
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_name = args.output or f"readonly_{ts}.json"
    out_path = LOGS_DIR / out_name

    summary_doc = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode":          f"{args.num_workers}-worker",
        "remote_host":   args.remote_host,
        "server":        args.server,
        "task_file":     str(TASK_FILE),
        "total":         len(results),
        "passed":        sum(1 for r in results if r["passed"]),
        "failed":        sum(1 for r in results if not r["passed"]),
        "results":       results,
    }
    out_path.write_text(json.dumps(summary_doc, indent=2))
    print(f"📄 Results saved → {out_path}\n")


if __name__ == "__main__":
    asyncio.run(main())
