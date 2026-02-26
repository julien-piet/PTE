#!/usr/bin/env python3
"""
Filter tasks from webarena_tasks.json that have "gitlab" in their sites list.
Creates a new file called gitlab_tasks.json with only gitlab tasks.
"""

import json
from pathlib import Path

def filter_gitlab_tasks():
    input_file = Path(__file__).parent / "webarena_tasks.json"
    output_file = Path(__file__).parent / "gitlab_tasks.json"

    # Read the original tasks
    with open(input_file, 'r') as f:
        all_tasks = json.load(f)

    # Filter for gitlab tasks
    gitlab_tasks = [task for task in all_tasks if "gitlab" in task.get("sites", [])]

    # Write to new file
    with open(output_file, 'w') as f:
        json.dump(gitlab_tasks, f, indent=2)

    print(f"✓ Filtered {len(gitlab_tasks)} gitlab tasks from {len(all_tasks)} total tasks")
    print(f"✓ Saved to: {output_file}")

if __name__ == "__main__":
    filter_gitlab_tasks()
