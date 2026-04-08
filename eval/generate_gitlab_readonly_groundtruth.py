#!/usr/bin/env python3
"""
generate_gitlab_readonly_groundtruth.py

Builds eval/tests/raw_webarena_tasks_gitlab_readonly.json — a consolidated
benchmark of all read-only GitLab tasks (66 total, all string_match).

Sources
───────
  Phase 1 (16 tasks — navigation):
    raw_webarena_tasks_url_as_html_match.json
    Tasks 44, 45, 46, 102–106, 156, 258, 339–343, 357.
    reference_answers were derived by live inspection of the seeded environment
    (see eval/inspect_navigation_groundtruth.py).

  Phase 2 (10 tasks — issue open/closed status):
    raw_webarena_tasks_no_map.json
    Tasks 173–182.  eval_types simplified from [string_match, url_match] to
    [string_match]; reference_answers updated to must_include the correct issue
    title + open/closed status keyword.

  Phase 3 (40 tasks — information retrieval):
    raw_webarena_tasks_no_map.json
    Pure string_match read-only tasks: commit counts, contributor stats, SSH
    clone commands, repo membership, RSS token, etc.
    Excludes state-modifying tasks 783 (add maintainer) and 789 (create issue).
    Excludes task 307 (broken: "Nic" author does not exist in the seeded April
    2021 data — all authors that month were Eric Bailey, Jason Webb, etc.).

Usage
─────
  python3 eval/generate_gitlab_readonly_groundtruth.py
"""

import json
from pathlib import Path

EVAL_DIR    = Path(__file__).parent
OUTPUT_FILE = EVAL_DIR / "tests" / "raw_webarena_tasks_gitlab_readonly.json"
HTML_FILE   = EVAL_DIR / "tests" / "raw_webarena_tasks_url_as_html_match.json"
NO_MAP_FILE = EVAL_DIR / "tests" / "raw_webarena_tasks_no_map.json"

EXCLUDED_IDS    = {118, 528, 529, 530, 531, 532, 585, 586, 587, 588, 589}
STATE_MODIFYING = {783, 789}
BROKEN_TASKS    = {307}   # task 307: "Nic" author absent from seeded April 2021 data

# Phase 1 IDs — sourced from html_match file (have live-inspected must_include)
PHASE1_IDS = {44, 45, 46, 102, 103, 104, 105, 106, 156, 258, 339, 340, 341, 342, 343, 357}


def generate() -> None:
    with open(HTML_FILE) as f:
        html_tasks = {t["task_id"]: t for t in json.load(f)}

    with open(NO_MAP_FILE) as f:
        no_map_tasks = {t["task_id"]: t for t in json.load(f)}

    tasks_out = []

    # Phase 1: navigation tasks from html_match (already correct string_match format)
    for tid in sorted(PHASE1_IDS):
        t = html_tasks.get(tid)
        if t is None:
            print(f"⚠️  Phase 1 task {tid} not found in html_match file — skipping")
            continue
        assert t["eval"]["eval_types"] == ["string_match"], \
            f"Task {tid} unexpectedly not string_match: {t['eval']['eval_types']}"
        tasks_out.append(t)

    # Phase 2 + Phase 3: read-only string_match from no_map
    for tid, t in sorted(no_map_tasks.items()):
        if tid in PHASE1_IDS:
            continue  # already added from html_match
        if t.get("sites") != ["gitlab"]:
            continue
        if "string_match" not in t["eval"]["eval_types"]:
            continue
        if "program_html" in t["eval"]["eval_types"]:
            continue
        if tid in EXCLUDED_IDS or tid in STATE_MODIFYING or tid in BROKEN_TASKS:
            continue
        # Ensure eval_types is pure string_match (drops url_match if lingering)
        t = dict(t)
        t["eval"] = dict(t["eval"], eval_types=["string_match"])
        tasks_out.append(t)

    tasks_out.sort(key=lambda t: t["task_id"])

    with open(OUTPUT_FILE, "w") as f:
        json.dump(tasks_out, f, indent=2)
        f.write("\n")

    p1 = sum(1 for t in tasks_out if t["task_id"] in PHASE1_IDS)
    p2 = sum(1 for t in tasks_out if 173 <= t["task_id"] <= 182)
    p3 = len(tasks_out) - p1 - p2
    print(f"Written {len(tasks_out)} tasks → {OUTPUT_FILE}")
    print(f"  Phase 1 (navigation):        {p1}")
    print(f"  Phase 2 (issue open/closed): {p2}")
    print(f"  Phase 3 (info retrieval):    {p3}")


if __name__ == "__main__":
    generate()
