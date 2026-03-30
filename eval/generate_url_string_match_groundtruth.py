#!/usr/bin/env python3
"""
generate_url_string_match_groundtruth.py

Generates string_match ground truth for GitLab url_match tasks by:
  1. Logging in to GitLab
  2. Navigating directly to each task's reference_url (the known-correct destination)
  3. Capturing the page title, heading, and visible text
  4. Asking Claude to pick the best stable string match from that page
  5. Patching raw_webarena_tasks_url_as_string_match.json incrementally (saved after
     every task so a crash doesn't lose progress)

Task phases
-----------
  Phase 1 — pure url_match tasks (21 tasks): no program_html, no agent needed
  Phase 2 — url_match + string_match combos (10 tasks, tasks 173-182):
             original reference_answers are copied directly — no navigation needed
  Phase 3 — url_match + program_html tasks (26 tasks): skip (require agent run)

Usage
-----
  # Dry-run: navigate and capture pages, print what would be sent to Claude
  python3 eval/generate_url_string_match_groundtruth.py --dry-run

  # Process all Phase 1 tasks (browser visible so you can watch)
  python3 eval/generate_url_string_match_groundtruth.py

  # Process a single task
  python3 eval/generate_url_string_match_groundtruth.py --task-id 44

  # Run headless
  python3 eval/generate_url_string_match_groundtruth.py --headless

  # Also do Phase 2 (copy existing string_match answers)
  python3 eval/generate_url_string_match_groundtruth.py --phase 2

  # Reprocess tasks that already have answers (re-visit and re-ask Claude)
  python3 eval/generate_url_string_match_groundtruth.py --reprocess
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Path setup — allow running from project root or eval/
# ---------------------------------------------------------------------------
EVAL_DIR = Path(__file__).parent
PROJECT_ROOT = EVAL_DIR.parent
for _p in [str(PROJECT_ROOT), str(EVAL_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, Page
from api import gitlab_pw
from eval.program_html_evaluator import DEFAULT_BASE_URLS
from eval.gitlab_state_reset import GitLabStateReset
from eval.url_match_evaluator import UrlMatchEvaluator

# Load API keys from config/.env (same pattern as run_program_html_benchmark.py)
_env_path = PROJECT_ROOT / "config" / ".env"
if _env_path.exists():
    load_dotenv(dotenv_path=_env_path, override=False)

# ---------------------------------------------------------------------------
# File paths
# ---------------------------------------------------------------------------
TARGET_FILE = EVAL_DIR / "tests" / "raw_webarena_tasks_url_as_string_match.json"
SOURCE_FILE = EVAL_DIR / "tests" / "raw_webarena_tasks_no_map.json"

PLACEHOLDER = "PLACEHOLDER_NEW_GROUND_TRUTH"

# Shared evaluator instance — used for URL parsing (|OR| splits, placeholder
# resolution) so navigation uses the same logic as the url_match eval itself.
_url_evaluator = UrlMatchEvaluator()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve(url: str) -> str:
    """Replace __PLACEHOLDER__ tokens with real base URLs."""
    for token, base in DEFAULT_BASE_URLS.items():
        url = url.replace(token, base)
    return url


def _resolve_nav_url(source_task: Dict) -> Optional[str]:
    """
    Return the best single URL to navigate to for ground truth capture.

    Uses UrlMatchEvaluator's own placeholder resolution and |OR| parsing so
    the URL we visit is always valid and consistent with how the evaluator
    interprets reference_url.

    For tasks with multiple |OR| alternatives, the first resolvable URL is
    used (they all lead to equivalent pages for content capture purposes).

    Returns None if no reference_url is set.
    """
    raw = source_task.get("eval", {}).get("reference_url", "") or ""
    if not raw:
        return None
    # Split on |OR| the same way UrlMatchEvaluator does
    alternatives = [
        _url_evaluator._resolve_placeholder(alt.strip())
        for alt in raw.split(" |OR| ")
        if alt.strip()
    ]
    return alternatives[0] if alternatives else None


def _load_data() -> Tuple[List[Dict], Dict[int, Dict]]:
    """
    Returns:
        target_tasks  — list of tasks from the file we're patching
        source_by_id  — dict[task_id -> task] from the original benchmark file
                        (used to look up reference_url and original eval data)
    """
    with open(TARGET_FILE) as f:
        target_tasks = json.load(f)
    with open(SOURCE_FILE) as f:
        source_tasks = json.load(f)
    source_by_id = {t["task_id"]: t for t in source_tasks}
    return target_tasks, source_by_id


def _save(tasks: List[Dict]) -> None:
    """Write the patched task list back to disk (pretty-printed, 2-space indent)."""
    with open(TARGET_FILE, "w") as f:
        json.dump(tasks, f, indent=2)


def _original_eval_types(tid: int, source_by_id: Dict[int, Dict]) -> List[str]:
    return source_by_id.get(tid, {}).get("eval", {}).get("eval_types", [])


# ---------------------------------------------------------------------------
# Page capture
# ---------------------------------------------------------------------------

def _capture_page_context(page: Page, url: str) -> Dict[str, str]:
    """
    Navigate to url and capture text signals useful for choosing a string match.

    Returns a dict with keys: url, title, heading, active_nav, filters,
    body_snippet.  All values are strings; missing keys are omitted.
    """
    page.goto(url, wait_until="networkidle", timeout=20000)
    ctx: Dict[str, str] = {
        "url": page.url,
        "title": page.title(),
    }

    # Main heading — skip GitLab's mobile-nav "Menu" h1 which appears on
    # every list page and is not meaningful as a page identifier.
    _SKIP_HEADINGS = {"menu", ""}
    for sel in [
        ".page-title",           # GitLab list page title (breadcrumb area)
        ".gl-heading-1",
        "h1.title",
        "h2.title",
        "h1",                    # fallback — filtered below
        "h2",
    ]:
        loc = page.locator(sel)
        if loc.count() > 0:
            text = loc.first.inner_text().strip()
            if text.lower() not in _SKIP_HEADINGS:
                ctx["heading"] = text
                break

    # Active filter tokens (label chips, assignee, milestone, sort) —
    # most useful signal on filtered issue / MR list pages.
    filter_parts: List[str] = []
    for sel in [
        ".filtered-search-token .value",          # classic filter tokens
        ".gl-filtered-search-token-data-content",  # newer GitLab filter UI
        ".active-filters .gl-label-text",
        ".filtered-search-box .token-container",
    ]:
        locs = page.locator(sel)
        n = locs.count()
        for j in range(min(n, 6)):
            t = locs.nth(j).inner_text().strip()
            if t:
                filter_parts.append(t)
        if filter_parts:
            break
    if filter_parts:
        ctx["filters"] = ", ".join(filter_parts)

    # Sort control text — useful for "most recent / oldest" tasks
    for sel in [
        ".sort-dropdown-button",
        "[data-testid='sort-by-button']",
        ".gl-dropdown-toggle .gl-button-text",
    ]:
        loc = page.locator(sel)
        if loc.count() > 0:
            text = loc.first.inner_text().strip()
            if text and text.lower() not in {"sort by", ""}:
                ctx["sort"] = text
                break

    # Active navigation tab (Open/Closed/All) — skip pure-number badges and
    # strip embedded count badges that appear on a second line (e.g. "Open\n40")
    for sel in [
        ".gl-tab-nav-item--active",
        ".nav-link.active",
        "[aria-current='page']",
        ".breadcrumbs-list li:last-child a",
    ]:
        loc = page.locator(sel)
        if loc.count() > 0:
            # Take only the first line to drop embedded count badges ("Open\n40" → "Open")
            text = loc.first.inner_text().strip().splitlines()[0].strip()
            # Skip if the text is just a number (issue count badge)
            if text and not text.isdigit():
                ctx["active_nav"] = text
                break

    # Breadcrumb — gives project context on list pages
    crumb_loc = page.locator(".breadcrumbs-list li")
    n = crumb_loc.count()
    if n > 0:
        parts = [crumb_loc.nth(i).inner_text().strip() for i in range(n)]
        parts = [p for p in parts if p and p != "/"]
        if parts:
            ctx["breadcrumb"] = " / ".join(parts)

    # Visible body text — trimmed to keep Claude prompt manageable
    try:
        body_text = page.inner_text("main, #content-body, body")
        ctx["body_snippet"] = body_text[:3000].strip()
    except Exception:
        pass

    return ctx


# ---------------------------------------------------------------------------
# Claude API call
# ---------------------------------------------------------------------------

def _ask_claude(intent: str, ctx: Dict[str, str], reference_url: str) -> str:
    """
    Ask the LLM to choose the best stable string_match ground truth for this task.

    Sends the task intent, reference URL, and captured page context.
    Returns the chosen string (stripped of surrounding quotes/whitespace).
    """
    import openai
    client = openai.OpenAI()

    prompt = f"""You are building a benchmark evaluation dataset for a web-browsing AI agent.

The agent's task was: "{intent}"
The correct destination URL is: {reference_url}

After navigating to that URL, the page shows:
  Page title   : {ctx.get('title', 'N/A')}
  Main heading : {ctx.get('heading', 'N/A')}
  Breadcrumb   : {ctx.get('breadcrumb', 'N/A')}
  Active filter: {ctx.get('filters', 'N/A')}
  Sort control : {ctx.get('sort', 'N/A')}
  Active nav   : {ctx.get('active_nav', 'N/A')}
  Body text (first 1500 chars):
---
{ctx.get('body_snippet', 'N/A')[:1500]}
---

Choose a short, stable string from this page to use as an exact_match ground truth.

Selection rules:
1. VISIBLE on this page — must appear in the body text or heading shown above
2. SPECIFIC — confirms the right page/view/state (not just "GitLab" or "Dashboard")
3. STABLE — never changes across resets; avoid counts ("3 issues"), dates, usernames
4. SHORT — prefer page headings, tab names, filter labels, breadcrumbs (under 80 chars)
5. UNIQUE to this view — should not appear on unrelated GitLab pages

Return ONLY the string itself. No explanation, no quotes, no punctuation around it."""

    response = client.chat.completions.create(
        model="gpt-4.1",
        max_tokens=150,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.choices[0].message.content.strip()
    # Strip any surrounding quotes the model might add despite the instruction
    return raw.strip('"').strip("'").strip()


# ---------------------------------------------------------------------------
# Phase 2: copy existing string_match answers
# ---------------------------------------------------------------------------

def _apply_phase2(
    target_tasks: List[Dict],
    source_by_id: Dict[int, Dict],
    reprocess: bool,
) -> int:
    """
    Tasks 173-182 originally had both string_match + url_match eval types.
    Their reference_answers already exist in the source file — copy them over
    rather than re-navigating.

    Returns the number of tasks updated.
    """
    updated = 0
    for task in target_tasks:
        tid = task["task_id"]
        orig_types = _original_eval_types(tid, source_by_id)
        if "string_match" not in orig_types or "url_match" not in orig_types:
            continue
        # Skip tasks that are already done (unless reprocessing)
        current = task["eval"]["reference_answers"].get("exact_match", "")
        if current != PLACEHOLDER and not reprocess:
            continue
        src = source_by_id.get(tid, {})
        orig_answers = src.get("eval", {}).get("reference_answers") or {}
        if not orig_answers:
            print(f"   ⚠️  Task {tid}: no reference_answers in source — skipping")
            continue
        task["eval"]["reference_answers"] = orig_answers
        print(f"   ✅ Task {tid}: copied original reference_answers → {orig_answers}")
        updated += 1
    return updated


# ---------------------------------------------------------------------------
# Main processing loop
# ---------------------------------------------------------------------------

def process(
    task_ids: Optional[List[int]] = None,
    headless: bool = False,
    dry_run: bool = False,
    phase: int = 1,
    reprocess: bool = False,
) -> None:
    target_tasks, source_by_id = _load_data()

    # ── Phase 2: copy answers without browser ──────────────────────────────
    if phase == 2:
        print("\nPhase 2: copying existing string_match answers (tasks 173–182)\n")
        n = _apply_phase2(target_tasks, source_by_id, reprocess)
        if not dry_run:
            _save(target_tasks)
            print(f"\nSaved {n} updates to {TARGET_FILE}")
        else:
            print(f"\n[dry-run] Would save {n} updates")
        return

    # ── Phase 1: direct navigation + Claude ───────────────────────────────
    # Select eligible tasks: have a PLACEHOLDER and fit the phase criteria
    def _is_eligible(task: Dict) -> bool:
        orig_types = _original_eval_types(task["task_id"], source_by_id)
        if phase == 1:
            # Phase 1 = pure url_match only.
            # Exclude tasks that also had program_html (Phase 3 — needs agent)
            # or that already had string_match (Phase 2 — copy existing answers).
            if "program_html" in orig_types or "string_match" in orig_types:
                return False
        current = task["eval"]["reference_answers"].get("exact_match", "")
        return current == PLACEHOLDER or reprocess

    eligible = [t for t in target_tasks if _is_eligible(t)]
    if task_ids:
        eligible = [t for t in eligible if t["task_id"] in task_ids]

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Phase {phase}: {len(eligible)} tasks to process\n")
    if not eligible:
        print("Nothing to do — all tasks already have ground truth values.")
        print("Use --reprocess to re-visit and regenerate existing answers.")
        return

    resetter = GitLabStateReset()
    updated = 0
    errors = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        page = browser.new_page()
        page.set_viewport_size({"width": 1280, "height": 900})

        # ── Log in ────────────────────────────────────────────────────────
        print("🔐 Logging in to GitLab...")
        username, password = gitlab_pw.get_default_gitlab_credentials()
        login_result = None
        for attempt in range(3):
            login_result = gitlab_pw.login_user(page, username, password)
            if login_result.success:
                break
            time.sleep(2 ** attempt)

        if not login_result or not login_result.success:
            print(f"❌ Login failed: {login_result.error_message if login_result else 'unknown'}")
            browser.close()
            return
        print(f"✅ Logged in as {username}\n")

        # ── Process each task ─────────────────────────────────────────────
        for i, task in enumerate(eligible, 1):
            tid = task["task_id"]
            intent = task["intent"]
            src = source_by_id.get(tid, {})
            ref_url = _resolve_nav_url(src)

            print(f"[{i}/{len(eligible)}] Task {tid}: {intent[:70]}")
            print(f"   ref_url : {ref_url}")

            if not ref_url:
                msg = f"No reference_url found in source for task {tid}"
                print(f"   ⚠️  {msg} — skipping")
                errors.append((tid, msg))
                continue

            # State reset if required
            if task.get("require_reset"):
                print("   🔄 Resetting GitLab state...")
                resetter.reset_for_task(task)

            # Navigate and capture
            try:
                ctx = _capture_page_context(page, ref_url)
            except Exception as e:
                msg = f"Navigation error: {e}"
                print(f"   ❌ {msg}")
                errors.append((tid, msg))
                continue

            print(f"   title      : {ctx.get('title', '—')}")
            print(f"   heading    : {ctx.get('heading', '—')}")
            print(f"   breadcrumb : {ctx.get('breadcrumb', '—')}")
            print(f"   filters    : {ctx.get('filters', '—')}")
            print(f"   sort       : {ctx.get('sort', '—')}")
            print(f"   active_nav : {ctx.get('active_nav', '—')}")

            if dry_run:
                snippet = ctx.get("body_snippet", "")
                if snippet:
                    preview = snippet[:400].replace("\n", " ↵ ")
                    print(f"   body[400]  : {preview}")
                print("   [dry-run] Skipping Claude call\n")
                continue

            # Ask Claude
            try:
                chosen = _ask_claude(intent, ctx, ref_url)
            except Exception as e:
                msg = f"Claude API error: {e}"
                print(f"   ❌ {msg}")
                errors.append((tid, msg))
                continue

            print(f"   ✅ Ground truth: {chosen!r}\n")

            # Patch task in memory
            for t in target_tasks:
                if t["task_id"] == tid:
                    t["eval"]["reference_answers"]["exact_match"] = chosen
                    break

            # Incremental save — safe against crashes mid-run
            _save(target_tasks)
            updated += 1

        browser.close()

    # ── Summary ──────────────────────────────────────────────────────────
    print("=" * 60)
    print(f"Done.  Updated: {updated}/{len(eligible)} tasks")
    if errors:
        print(f"Errors ({len(errors)}):")
        for tid, msg in errors:
            print(f"  Task {tid}: {msg}")
    if not dry_run:
        print(f"Output: {TARGET_FILE}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate string_match ground truth for GitLab url_match tasks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 eval/generate_url_string_match_groundtruth.py --dry-run
  python3 eval/generate_url_string_match_groundtruth.py --task-id 44 45 46
  python3 eval/generate_url_string_match_groundtruth.py --headless
  python3 eval/generate_url_string_match_groundtruth.py --phase 2
        """,
    )
    parser.add_argument(
        "--task-id", type=int, nargs="+", metavar="ID",
        help="Only process specific task ID(s) (space-separated)",
    )
    parser.add_argument(
        "--headless", action="store_true", default=False,
        help="Run browser headless (default: visible so you can watch)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Navigate and capture pages but skip Claude calls and file writes",
    )
    parser.add_argument(
        "--phase", type=int, default=1, choices=[1, 2],
        help=(
            "Task phase: "
            "1 = pure url_match tasks (navigate + Claude); "
            "2 = url_match+string_match combos (copy existing answers). "
            "Default: 1"
        ),
    )
    parser.add_argument(
        "--reprocess", action="store_true",
        help="Re-visit and regenerate answers even for tasks that already have one",
    )
    args = parser.parse_args()

    process(
        task_ids=args.task_id,
        headless=args.headless,
        dry_run=args.dry_run,
        phase=args.phase,
        reprocess=args.reprocess,
    )


if __name__ == "__main__":
    main()
