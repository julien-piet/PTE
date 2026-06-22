#!/usr/bin/env python3
"""
Compare PTE and WebArena-Verified evaluation results, with an OR merge.

Usage:
    python eval/compare_wa_results.py \\
        --output-dir wa_react_web_api_output \\
        --config /Users/annabella/Downloads/AIAgent/webarena-verified/examples/configs/config.example.json

    # Skip running the WA evaluator (compare existing eval_result.json files only):
    python eval/compare_wa_results.py --output-dir wa_react_web_api_output --skip-eval

A task is considered PASS if EITHER:
  - PTE eval says correct=true  (string_match / program_html, from *_detailed.jsonl)
  - WA eval  says score=1.0     (NetworkEventEvaluator, from {task_id}/eval_result.json)
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent


def _run_wa_eval(output_dir: Path, config_path: Path, wa_dir: Path) -> None:
    """Run the webarena-verified eval-tasks subprocess."""
    cmd = [
        "uvx", "--from", ".", "webarena-verified", "eval-tasks",
        "--output-dir", str(output_dir.resolve()),
        "--config", str(config_path),
    ]
    print(f"\nRunning WA evaluator from {wa_dir}")
    print(f"  Command: {' '.join(cmd)}\n")
    result = subprocess.run(cmd, cwd=str(wa_dir), check=False)
    if result.returncode != 0:
        print(f"\n⚠️  WA evaluator exited with code {result.returncode} — continuing with comparison")


def _find_latest_detailed_jsonl(output_dir: Path) -> Path | None:
    """Return the most recently modified *_detailed.jsonl in output_dir."""
    candidates = list(output_dir.glob("*_detailed.jsonl"))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _read_pte_results(output_dir: Path) -> dict[int, bool]:
    """Read task_id → correct from the most recent *_detailed.jsonl."""
    jsonl_path = _find_latest_detailed_jsonl(output_dir)
    if jsonl_path is None:
        print(f"⚠️  No *_detailed.jsonl found in {output_dir} — PTE results will all be False")
        return {}
    print(f"Reading PTE results from: {jsonl_path.name}")
    pte: dict[int, bool] = {}
    for line in jsonl_path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            pte[int(row["task_id"])] = bool(row.get("correct", False))
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
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
    header = f"{'task_id':<{col_w['task_id']}}  {'pte':<{col_w['pte']}}  {'wa':<{col_w['wa']}}  {'combined':<{col_w['combined']}}"
    sep = "-" * len(header)
    print(header)
    print(sep)
    for row in rows:
        pte_s = "PASS" if row["pte"] else "FAIL"
        wa_s = "PASS" if row["wa"] else "FAIL"
        combined_s = "PASS" if row["combined"] else "FAIL"
        print(f"{row['task_id']:<{col_w['task_id']}}  {pte_s:<{col_w['pte']}}  {wa_s:<{col_w['wa']}}  {combined_s:<{col_w['combined']}}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run WA eval and merge with PTE results")
    parser.add_argument("--output-dir", default="wa_react_web_api_output",
                        help="Directory with agent run outputs (default: wa_react_web_api_output)")
    parser.add_argument("--config", default=None,
                        help="Path to webarena-verified config JSON (required unless --skip-eval)")
    parser.add_argument("--wa-dir", default=None,
                        help="Path to webarena-verified source dir (default: <project-root>/../webarena-verified)")
    parser.add_argument("--skip-eval", action="store_true",
                        help="Skip running the WA evaluator subprocess; just compare existing results")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = _PROJECT_ROOT / output_dir
    if not output_dir.exists():
        print(f"ERROR: output directory not found: {output_dir}")
        sys.exit(1)

    wa_dir = Path(args.wa_dir) if args.wa_dir else (_PROJECT_ROOT.parent / "webarena-verified")

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
        _run_wa_eval(output_dir, config_path, wa_dir)

    # --- Load results ---
    pte = _read_pte_results(output_dir)
    wa  = _read_wa_results(output_dir)

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
    print(f"\n{'='*52}")
    print("Combined Evaluation Results  (PASS = either eval passes)")
    print(f"{'='*52}")
    _print_table(rows)

    # --- Summary ---
    total    = len(rows)
    pte_n    = sum(1 for r in rows if r["pte"])
    wa_n     = sum(1 for r in rows if r["wa"])
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
    if pte_n == 0:
        print("\n  Note: PTE results are all FAIL — either this is an old run (before PTE eval fix)")
        print("  or the agent didn't produce correct answers per string_match/program_html criteria.")
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


if __name__ == "__main__":
    main()
