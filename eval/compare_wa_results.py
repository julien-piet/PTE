#!/usr/bin/env python3
"""
Compare PTE and WebArena-Verified evaluation results, with an OR merge.

Usage:
    # Run WA eval on all tasks then combine:
    python eval/compare_wa_results.py \\
        --output-dir wa_react_web_api_output \\
        --config /path/to/config.example.json

    # Run WA eval on just 2 re-run tasks, then combine with ALL existing results:
    python eval/compare_wa_results.py \\
        --output-dir wa_react_web_api_output \\
        --config /path/to/config.example.json \\
        --task-ids 105,445

    # Skip running the WA evaluator (compare existing results only):
    python eval/compare_wa_results.py --output-dir wa_react_web_api_output --skip-eval

A task is considered PASS if EITHER:
  - PTE eval says correct=true  (string_match / program_html, from *_detailed.jsonl)
  - WA eval  says score=1.0     (NetworkEventEvaluator, from {task_id}/eval_result.json)

Multiple *_detailed.jsonl files are merged: later files (by filename sort) override earlier
ones for the same task_id, so re-running a subset picks up the fresh PTE results for those
tasks while keeping old results for everything else.
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent
_PTE_TEST_FILES = [
    "gitlab_verified_string_match.json",
    "gitlab_verified_program_html.json",
]


def _load_gitlab_pte_ids() -> set[int]:
    """Return the 185 task_ids that have PTE counterparts in the two gitlab verified files."""
    test_files = Path(__file__).parent / "tests" / "test_files"
    ids: set[int] = set()
    for fname in _PTE_TEST_FILES:
        fp = test_files / fname
        if fp.exists():
            for t in json.loads(fp.read_text()):
                ids.add(int(t["task_id"]))
        else:
            print(f"⚠️  PTE file not found: {fp}")
    return ids


def _run_wa_eval(
    output_dir: Path,
    config_path: Path,
    wa_dir: Path,
    task_ids: list[int] | None,
) -> None:
    """Run the webarena-verified eval-tasks subprocess."""
    cmd = [
        "uvx", "--from", ".", "webarena-verified", "eval-tasks",
        "--output-dir", str(output_dir.resolve()),
        "--config", str(config_path),
    ]
    if task_ids:
        cmd += ["--task-ids", ",".join(str(t) for t in task_ids)]
    print(f"\nRunning WA evaluator from {wa_dir}")
    print(f"  Command: {' '.join(cmd)}\n")
    result = subprocess.run(cmd, cwd=str(wa_dir), check=False)
    if result.returncode != 0:
        print(f"\n⚠️  WA evaluator exited with code {result.returncode} — continuing with comparison")


def _read_pte_results(output_dir: Path) -> dict[int, bool]:
    """Merge all *_detailed.jsonl files in output_dir into task_id → correct.

    Files are processed in filename order (ascending), so later filenames
    (higher timestamps) override earlier ones for the same task_id.
    """
    jsonl_files = sorted(output_dir.glob("*_detailed.jsonl"))
    if not jsonl_files:
        print(f"⚠️  No *_detailed.jsonl found in {output_dir} — PTE results will all be False")
        return {}

    pte: dict[int, bool] = {}
    for jsonl_path in jsonl_files:
        count_before = len(pte)
        for line in jsonl_path.read_text().splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                pte[int(row["task_id"])] = bool(row.get("correct", False))
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
        added = len(pte) - count_before
        print(f"  PTE: {jsonl_path.name}  (+{added} tasks, {len(pte)} total)")

    return pte


def _read_wa_results(output_dir: Path) -> dict[int, bool]:
    """Read task_id → passed from per-task eval_result.json files."""
    wa: dict[int, bool] = {}
    for task_dir in sorted(output_dir.iterdir()):
        if not task_dir.is_dir() or not task_dir.name.isdigit():
            continue
        result_file = task_dir / "eval_result.json"
        if not result_file.exists():
            continue
        try:
            data = json.loads(result_file.read_text())
            wa[int(task_dir.name)] = (data.get("score", 0.0) == 1.0)
        except (json.JSONDecodeError, ValueError):
            continue
    return wa


def _print_table(rows: list[dict]) -> None:
    """Print a formatted table of per-task results."""
    col_w = {"task_id": 8, "pte": 6, "wa": 6, "combined": 8}
    header = (
        f"{'task_id':<{col_w['task_id']}}  {'pte':<{col_w['pte']}}  "
        f"{'wa':<{col_w['wa']}}  {'combined':<{col_w['combined']}}"
    )
    print(header)
    print("-" * len(header))
    for row in rows:
        pte_s = "PASS" if row["pte"] else "FAIL"
        wa_s = "PASS" if row["wa"] else "FAIL"
        combined_s = "PASS" if row["combined"] else "FAIL"
        print(
            f"{row['task_id']:<{col_w['task_id']}}  {pte_s:<{col_w['pte']}}  "
            f"{wa_s:<{col_w['wa']}}  {combined_s:<{col_w['combined']}}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run WA eval and merge with PTE results")
    parser.add_argument(
        "--output-dir", default="wa_react_web_api_output",
        help="Directory with agent run outputs (default: wa_react_web_api_output)",
    )
    parser.add_argument(
        "--config", default=None,
        help="Path to webarena-verified config JSON (required unless --skip-eval)",
    )
    parser.add_argument(
        "--wa-dir", default=None,
        help="Path to webarena-verified source dir (default: <project-root>/../webarena-verified)",
    )
    parser.add_argument(
        "--task-ids", default=None,
        help="Comma-separated task IDs to (re-)evaluate with WA evaluator. "
             "PTE results are still merged from ALL jsonl files regardless.",
    )
    parser.add_argument(
        "--skip-eval", action="store_true",
        help="Skip running the WA evaluator; just compare existing results",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = _PROJECT_ROOT / output_dir
    if not output_dir.exists():
        print(f"ERROR: output directory not found: {output_dir}")
        sys.exit(1)

    task_ids: list[int] | None = None
    if args.task_ids:
        try:
            task_ids = [int(t.strip()) for t in args.task_ids.split(",") if t.strip()]
        except ValueError:
            print(f"ERROR: invalid --task-ids value: {args.task_ids}")
            sys.exit(1)

    wa_dir = Path(args.wa_dir) if args.wa_dir else (_PROJECT_ROOT.parent.parent / "webarena-verified")

    if not args.skip_eval:
        if not args.config:
            parser.error("--config is required unless --skip-eval is set")
        config_path = Path(args.config)
        if not config_path.is_absolute():
            config_path = wa_dir / config_path
        if not config_path.exists():
            print(f"ERROR: config file not found: {config_path}")
            sys.exit(1)
        if not wa_dir.exists():
            print(f"ERROR: webarena-verified directory not found: {wa_dir}")
            sys.exit(1)
        _run_wa_eval(output_dir, config_path, wa_dir, task_ids)

    # --- Load results ---
    print()
    pte = _read_pte_results(output_dir)
    wa  = _read_wa_results(output_dir)
    print(f"  WA:  {len(wa)} tasks have eval_result.json\n")

    if not pte and not wa:
        print("ERROR: No results found in output directory")
        sys.exit(1)

    # --- Merge ---
    all_ids = sorted(set(pte) | set(wa))
    rows = []
    for task_id in all_ids:
        pte_pass = pte.get(task_id, False)
        wa_pass  = wa.get(task_id, False)
        rows.append({
            "task_id":  task_id,
            "pte":      pte_pass,
            "wa":       wa_pass,
            "combined": pte_pass or wa_pass,
        })

    # --- Print table ---
    print(f"{'='*52}")
    print("Combined Evaluation Results  (PASS = either eval passes)")
    print(f"{'='*52}")
    _print_table(rows)

    # --- Summary ---
    total      = len(rows)
    pte_n      = sum(1 for r in rows if r["pte"])
    wa_n       = sum(1 for r in rows if r["wa"])
    combined_n = sum(1 for r in rows if r["combined"])

    def _pct(n: int) -> str:
        return f"{100 * n / total:.0f}%" if total else "n/a"

    print(f"\n{'='*52}")
    print("Summary")
    print(f"{'='*52}")
    print(f"  Total tasks    : {total}")
    print(f"  PTE passed     : {pte_n} / {total}  ({_pct(pte_n)})")
    print(f"  WA  passed     : {wa_n} / {total}  ({_pct(wa_n)})")
    print(f"  Combined PASS  : {combined_n} / {total}  ({_pct(combined_n)})  ← OR of both evals")
    print()

    # --- Write combined_results.json ---
    out_file = output_dir / "combined_results.json"
    combined_data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total": total,
            "pte_passed": pte_n,
            "wa_passed": wa_n,
            "combined_passed": combined_n,
        },
        "results": rows,
    }
    out_file.write_text(json.dumps(combined_data, indent=2))
    print(f"  Written: {out_file}")

    # --- Write gitlab_only_results.json (185 PTE tasks only) ---
    pte_ids = _load_gitlab_pte_ids()
    gitlab_rows = [r for r in rows if r["task_id"] in pte_ids]
    # Include PTE tasks that weren't run yet (show as all-FAIL)
    run_ids = {r["task_id"] for r in rows}
    for missing_id in sorted(pte_ids - run_ids):
        gitlab_rows.append({"task_id": missing_id, "pte": False, "wa": False, "combined": False})
    gitlab_rows.sort(key=lambda r: r["task_id"])

    g_total = len(gitlab_rows)
    g_pte_n = sum(1 for r in gitlab_rows if r["pte"])
    g_wa_n  = sum(1 for r in gitlab_rows if r["wa"])
    g_comb_n = sum(1 for r in gitlab_rows if r["combined"])

    def _pct_g(n: int) -> str:
        return f"{100 * n / g_total:.0f}%" if g_total else "n/a"

    gitlab_out = output_dir / "gitlab_only_results.json"
    gitlab_data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "description": "Results filtered to the 185 GitLab tasks with PTE counterparts",
        "summary": {
            "total": g_total,
            "run": len(run_ids & pte_ids),
            "not_run": len(pte_ids - run_ids),
            "pte_passed": g_pte_n,
            "wa_passed": g_wa_n,
            "combined_passed": g_comb_n,
        },
        "results": gitlab_rows,
    }
    gitlab_out.write_text(json.dumps(gitlab_data, indent=2))
    print(f"  Written: {gitlab_out}")

    print(f"\n{'='*52}")
    print("GitLab-only Summary  (185 PTE tasks)")
    print(f"{'='*52}")
    print(f"  Total PTE tasks : {g_total}")
    print(f"  Run             : {gitlab_data['summary']['run']}")
    print(f"  Not run yet     : {gitlab_data['summary']['not_run']}")
    print(f"  PTE passed      : {g_pte_n} / {g_total}  ({_pct_g(g_pte_n)})")
    print(f"  WA  passed      : {g_wa_n} / {g_total}  ({_pct_g(g_wa_n)})")
    print(f"  Combined PASS   : {g_comb_n} / {g_total}  ({_pct_g(g_comb_n)})  ← OR of both evals")
    print()


if __name__ == "__main__":
    main()
