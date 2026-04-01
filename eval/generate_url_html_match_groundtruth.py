#!/usr/bin/env python3
"""
generate_url_html_match_groundtruth.py

Converts all 57 GitLab url_match tasks into program_html tasks and writes
eval/tests/raw_webarena_tasks_url_as_html_match.json.

All non-eval fields are identical to raw_webarena_tasks_no_map.json.

Conversion strategy by phase
─────────────────────────────
  Phase 1 (16 tasks — pure url_match, navigation):
    One program_html check per task.
      url      : "last"   (evaluates wherever the agent ended up)
      locator  : document.querySelector('#content-body').outerText
      contents : must_include list derived from Phase 1 string_match work.
                 exact_match strings are promoted to must_include since
                 #content-body is far too long for exact equality.

  Phase 2 (10 tasks — url_match + string_match, tasks 173-182):
    Two program_html checks per task.
      Check 1 — issue title (confirms agent is on the right issue page):
        locator  : document.querySelector('[data-qa-selector="title_content"]').outerText
        contents : must_include the key title keyword
      Check 2 — issue status (Open / Closed):
        locator  : document.querySelector(
                     '.issuable-status-badge-open, .issuable-status-badge-closed'
                   ).outerText
        contents : must_include ['Open'] or ['Closed']

  Phase 3 (31 tasks — url_match + program_html, action tasks):
    The source file already has authoritative DOM-level program_html checks.
    These are copied verbatim; only eval_types is changed to ['program_html'].

Usage
─────
  python3 eval/generate_url_html_match_groundtruth.py
  python3 eval/generate_url_html_match_groundtruth.py --verify   # navigate & smoke-test selectors
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
EVAL_DIR = Path(__file__).parent
PROJECT_ROOT = EVAL_DIR.parent
for _p in [str(PROJECT_ROOT), str(EVAL_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

SOURCE_FILE = EVAL_DIR / "tests" / "raw_webarena_tasks_no_map.json"
OUTPUT_FILE = EVAL_DIR / "tests" / "raw_webarena_tasks_url_as_html_match.json"

# ---------------------------------------------------------------------------
# Locator constants
# ---------------------------------------------------------------------------
BODY    = "document.querySelector('#content-body').outerText"
TITLE   = "document.querySelector('[data-qa-selector=\"title_content\"]').outerText"
STATUS  = ("document.querySelector("
           "'.issuable-status-badge-open, .issuable-status-badge-closed'"
           ").outerText")

# ---------------------------------------------------------------------------
# Phase 1 — program_html checks derived from string_match ground truth
# One check per task; required_contents uses must_include throughout since
# the #content-body locator captures the full page text.
# ---------------------------------------------------------------------------
PHASE1_CHECKS: Dict[int, List[Dict]] = {
    # Task 44 — Check out my todos
    44: [{"url": "last", "locator": BODY,
          "required_contents": {"must_include": ["To-Do List"]}}],

    # Task 45 — Most recent open issues (a11yproject) — sorted by Created date
    45: [{"url": "last", "locator": BODY,
          "required_contents": {"must_include": ["a11yproject.com / Issues", "Created date"]}}],

    # Task 46 — Most recent open issues (primer/design) — sorted by Created date
    46: [{"url": "last", "locator": BODY,
          "required_contents": {"must_include": ["Primer / design / Issues", "Created date"]}}],

    # Task 102 — Issues labelled "help wanted" in a11y-syntax-highlighting
    102: [{"url": "last", "locator": BODY,
           "required_contents": {"must_include": ["help wanted"]}}],

    # Task 103 — Issues labelled "question" in ffmpeg-python
    103: [{"url": "last", "locator": BODY,
           "required_contents": {"must_include": ["~question"]}}],

    # Task 104 — Issues labelled "flaky-test" in keycloak
    104: [{"url": "last", "locator": BODY,
           "required_contents": {"must_include": ["~flaky-test"]}}],

    # Task 105 — Issues labelled "OpenAPI Generator CLI"
    105: [{"url": "last", "locator": BODY,
           "required_contents": {"must_include": ["~OpenAPI Generator CLI"]}}],

    # Task 106 — Issues labelled "BUG" in AndroidSlidingUpPanel
    106: [{"url": "last", "locator": BODY,
           "required_contents": {"must_include": ["~BUG"]}}],

    # Task 156 — Merge requests assigned to me
    156: [{"url": "last", "locator": BODY,
           "required_contents": {"must_include": ["Assignee", "Byte Blaze"]}}],

    # Task 258 — See all public projects (Explore)
    258: [{"url": "last", "locator": BODY,
           "required_contents": {"must_include": ["Projects", "Explore"]}}],

    # Task 339 — Bug issues in a11yproject
    339: [{"url": "last", "locator": BODY,
           "required_contents": {"must_include": ["~bug"]}}],

    # Task 340 — Bug issues in primer/design
    340: [{"url": "last", "locator": BODY,
           "required_contents": {"must_include": ["~type: bug"]}}],

    # Task 341 — Enhancement (feature request) issues in metaseq
    341: [{"url": "last", "locator": BODY,
           "required_contents": {"must_include": ["~enhancement"]}}],

    # Task 342 — OPT-related question issues in metaseq
    342: [{"url": "last", "locator": BODY,
           "required_contents": {"must_include": ["~question", "OPT"]}}],

    # Task 343 — Issues with no labels in metaseq
    343: [{"url": "last", "locator": BODY,
           "required_contents": {"must_include": ["~None"]}}],

    # Task 357 — Merge requests where I am reviewer
    357: [{"url": "last", "locator": BODY,
           "required_contents": {"must_include": ["Reviewer", "Byte Blaze"]}}],
}

# ---------------------------------------------------------------------------
# Phase 2 — two checks per task (right page + correct open/closed status)
#
# Issue pages verified during benchmark construction:
#   #8    — "Better initial load experience"           → Open   (tasks 173)
#   #71   — "[Feature suggestion] Support linking..."  → Open   (task  174)
#   #18   — "Outdated dependencies"                    → Open   (tasks 175, 180)
#   #1    — "Tm Theme Editor"                          → Open   (tasks 176, 181)
#   #719  — "Rethink the homepage's content"           → Closed (tasks 177, 182)
#   #566  — "Better Event page UX"                     → Closed (task  178)
#   #1517 — "Deprecate GitHub Discussions"             → Closed (task  179)
# ---------------------------------------------------------------------------
def _p2(title_keyword: str, status: str) -> List[Dict]:
    """Return the two-check program_html list for a Phase 2 task."""
    return [
        {
            "url": "last",
            "locator": TITLE,
            "required_contents": {"must_include": [title_keyword]},
        },
        {
            "url": "last",
            "locator": STATUS,
            "required_contents": {"must_include": [status]},
        },
    ]

PHASE2_CHECKS: Dict[int, List[Dict]] = {
    173: _p2("Better initial load",     "Open"),
    174: _p2("Feature suggestion",      "Open"),
    175: _p2("Outdated dependencies",   "Open"),
    176: _p2("Tm Theme Editor",         "Open"),
    177: _p2("Rethink the homepage",    "Closed"),
    178: _p2("Better Event page",       "Closed"),
    179: _p2("Deprecate GitHub",        "Closed"),
    180: _p2("Outdated dependencies",   "Open"),
    181: _p2("Tm Theme Editor",         "Open"),
    182: _p2("Rethink the homepage",    "Closed"),
}

# ---------------------------------------------------------------------------
# Phase membership sets
# ---------------------------------------------------------------------------
PHASE1_IDS = set(PHASE1_CHECKS.keys())
PHASE2_IDS = set(PHASE2_CHECKS.keys())
PHASE3_IDS = {590,591,592,593,594,658,659,660,661,662,663,664,665,666,667,668,
              669,670,681,682,683,684,685,686,687,688,805,806,807,808,809}


# ---------------------------------------------------------------------------
# Build eval dict for a single task
# ---------------------------------------------------------------------------

def _build_eval(task_id: int, original_eval: Dict) -> Dict:
    """
    Construct the new eval dict for a converted task.

    - eval_types  : always ["program_html"]
    - reference_url / url_note : preserved from original (used by evaluator
      to determine navigation fallback and match mode)
    - program_html : phase-specific checks (see module docstring)
    - reference_answers : null  (not used by program_html evaluator)
    """
    if task_id in PHASE1_IDS:
        checks = PHASE1_CHECKS[task_id]
    elif task_id in PHASE2_IDS:
        checks = PHASE2_CHECKS[task_id]
    elif task_id in PHASE3_IDS:
        # Reuse authoritative checks verbatim from source
        checks = original_eval.get("program_html", [])
    else:
        raise ValueError(f"Task {task_id} not in any known phase")

    return {
        "eval_types": ["program_html"],
        "reference_answers": None,
        "reference_url": original_eval.get("reference_url", ""),
        "program_html": checks,
        "url_note": original_eval.get("url_note", ""),
        "string_note": "",
        "reference_answer_raw_annotation": "",
    }


# ---------------------------------------------------------------------------
# Generate the output file
# ---------------------------------------------------------------------------

def generate() -> None:
    with open(SOURCE_FILE) as f:
        all_source = json.load(f)
    source_by_id = {t["task_id"]: t for t in all_source}

    all_phase_ids = PHASE1_IDS | PHASE2_IDS | PHASE3_IDS
    tasks_out = []

    for task_id in sorted(all_phase_ids):
        src = source_by_id.get(task_id)
        if src is None:
            print(f"⚠️  Task {task_id} not found in source — skipping")
            continue

        # Copy all non-eval fields verbatim
        new_task = {k: v for k, v in src.items() if k != "eval"}
        new_task["eval"] = _build_eval(task_id, src["eval"])
        tasks_out.append(new_task)

    with open(OUTPUT_FILE, "w") as f:
        json.dump(tasks_out, f, indent=2)

    print(f"Written {len(tasks_out)} tasks → {OUTPUT_FILE}")
    _print_summary(tasks_out)


def _print_summary(tasks: List[Dict]) -> None:
    p1 = sum(1 for t in tasks if t["task_id"] in PHASE1_IDS)
    p2 = sum(1 for t in tasks if t["task_id"] in PHASE2_IDS)
    p3 = sum(1 for t in tasks if t["task_id"] in PHASE3_IDS)
    total_checks = sum(len(t["eval"]["program_html"]) for t in tasks)
    print(f"  Phase 1 ({p1} tasks): 1 check each")
    print(f"  Phase 2 ({p2} tasks): 2 checks each")
    print(f"  Phase 3 ({p3} tasks): {total_checks - p1 - p2*2} checks total (from source)")
    print(f"  Total program_html checks: {total_checks}")


# ---------------------------------------------------------------------------
# Optional --verify mode: navigate to reference URLs and smoke-test selectors
# ---------------------------------------------------------------------------

def verify() -> None:
    """
    Loads the generated file, navigates to each task's reference_url, and
    runs each program_html locator via JavaScript to confirm it returns a
    non-empty string. Prints pass/fail per check.
    Requires GitLab (and Reddit for Phase 3 cross-site tasks) to be running.
    """
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / "config" / ".env", override=False)

    from playwright.sync_api import sync_playwright
    from api import gitlab_pw
    from eval.url_match_evaluator import UrlMatchEvaluator

    url_eval = UrlMatchEvaluator()

    with open(OUTPUT_FILE) as f:
        tasks = json.load(f)

    with open(SOURCE_FILE) as f:
        source_by_id = {t["task_id"]: t for t in json.load(f)}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_viewport_size({"width": 1280, "height": 900})

        print("🔐 Logging in...")
        gitlab_pw.login_user(page, *gitlab_pw.get_default_gitlab_credentials())
        print("✅ Logged in\n")

        passed = failed = 0
        for task in tasks:
            tid = task["task_id"]
            src = source_by_id[tid]
            raw_ref = src["eval"].get("reference_url", "")
            if not raw_ref:
                continue

            # Use UrlMatchEvaluator to parse |OR| and resolve placeholders
            alternatives = [
                url_eval._resolve_placeholder(a.strip())
                for a in raw_ref.split(" |OR| ") if a.strip()
            ]
            nav_url = alternatives[0]

            # Skip Reddit tasks (need separate server)
            if "localhost:9999" in nav_url:
                print(f"Task {tid:4d}: SKIP (Reddit — needs separate server)")
                continue

            try:
                page.goto(nav_url, wait_until="networkidle", timeout=15000)
            except Exception as e:
                print(f"Task {tid:4d}: ❌ navigation failed — {e}")
                failed += 1
                continue

            checks = task["eval"]["program_html"]
            task_ok = True
            for i, check in enumerate(checks):
                locator_js = check["locator"]
                try:
                    result = page.evaluate(f"() => {{ try {{ return {locator_js}; }} catch(e) {{ return ''; }} }}")
                    ok = bool(result and result.strip())
                except Exception as e:
                    result = ""
                    ok = False

                status = "✅" if ok else "❌"
                if not ok:
                    task_ok = False
                    failed += 1
                    print(f"Task {tid:4d} check[{i}]: {status} locator returned empty")
                    print(f"  locator : {locator_js[:80]}")
                    print(f"  nav_url : {nav_url}")
                else:
                    passed += 1

            if task_ok:
                print(f"Task {tid:4d}: ✅ all {len(checks)} check(s) have non-empty locators")

        browser.close()

    print(f"\n{'='*50}")
    print(f"Selector smoke-test: {passed} passed, {failed} failed")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate raw_webarena_tasks_url_as_html_match.json"
    )
    parser.add_argument(
        "--verify", action="store_true",
        help="After generating, navigate to each task's reference URL and "
             "smoke-test that all locators return non-empty text.",
    )
    args = parser.parse_args()

    generate()
    if args.verify:
        print()
        verify()


if __name__ == "__main__":
    main()
