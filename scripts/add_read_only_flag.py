"""
Copies the read_only flag from test_files/gitlab_tasks.json into a target
tasks file, matching by task_id. Tasks with no matching task_id are left
unchanged (e.g. non-GitLab tasks in mixed-site files).

Updates the target file in-place. Prints a summary of changes.

Usage:
    python scripts/add_read_only_flag.py [TARGET_FILE]

    TARGET_FILE defaults to eval/tests/raw_webarena_tasks_all_gitlab.json
"""

import json
import sys
from pathlib import Path

SOURCE_FILE = Path("test_files/gitlab_tasks.json")
DEFAULT_TARGET = Path("eval/tests/raw_webarena_tasks_all_gitlab.json")


def main():
    target_file = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_TARGET

    if not target_file.exists():
        sys.exit(f"File not found: {target_file}")
    if not SOURCE_FILE.exists():
        sys.exit(f"File not found: {SOURCE_FILE}")

    with open(SOURCE_FILE) as f:
        source_tasks = json.load(f)
    with open(target_file) as f:
        raw_tasks = json.load(f)

    read_only_map = {t["task_id"]: t.get("read_only", False) for t in source_tasks}

    updated = skipped = 0
    for task in raw_tasks:
        tid = task["task_id"]
        if tid not in read_only_map:
            skipped += 1
            continue
        task["read_only"] = read_only_map[tid]
        updated += 1

    with open(target_file, "w") as f:
        json.dump(raw_tasks, f, indent=2)
        f.write("\n")

    print(f"Updated {updated} tasks in {target_file}")
    if skipped:
        print(f"Skipped {skipped} tasks (no matching task_id in source — non-GitLab tasks)")


if __name__ == "__main__":
    main()
