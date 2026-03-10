"""
Batch task runner using PlanningAgent: parse tasks from a JSON file, run each
through the planning agent, and save the resulting execution plans to a JSON file.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from agent.planning_agent import PlanningAgent
from agent.planner import pretty_print_plan


class PlanningBatchRunner:
    """Runs multiple tasks through PlanningAgent and collects the resulting plans."""

    def __init__(
        self,
        tasks_file: str,
        output_file: str,
        api_dir: str = "api",
        start: int = 0,
        limit: Optional[int] = None,
        task_ids: Optional[List[int]] = None,
        dryrun: bool = False,
    ):
        self.tasks_file = Path(tasks_file)
        self.output_file = Path(output_file)
        self.api_dir = api_dir
        self.start = max(0, start)
        self.limit = limit
        self.task_ids = task_ids
        self.dryrun = dryrun
        self.agent: Optional[PlanningAgent] = None
        self.results: List[Dict[str, Any]] = []

    def initialize(self):
        """Initialize the PlanningAgent (reads config internally)."""
        print("Initializing PlanningAgent...")
        self.agent = PlanningAgent(api_dir=self.api_dir, debug_responses=True, debug_prompts=False)
        print("PlanningAgent initialized successfully\n")

    def load_tasks(self) -> List[Dict[str, Any]]:
        """Load tasks from the tasks JSON file with start, limit, or task_ids applied."""
        if not self.tasks_file.exists():
            raise FileNotFoundError(f"Tasks file not found: {self.tasks_file}")

        with open(self.tasks_file) as f:
            all_tasks = json.load(f)

        if self.task_ids is not None:
            id_set = set(self.task_ids)
            tasks = [t for t in all_tasks if t.get("task_id") in id_set]
            # Preserve the order specified in task_ids
            id_order = {tid: i for i, tid in enumerate(self.task_ids)}
            tasks.sort(key=lambda t: id_order.get(t.get("task_id"), 0))
            missing = id_set - {t.get("task_id") for t in tasks}
            if missing:
                print(f"  Warning: task IDs not found: {sorted(missing)}")
            print(f"Loaded {len(tasks)} tasks from {self.tasks_file}")
            print(f"  Filtering by task IDs: {self.task_ids}")
        else:
            end_index = self.start + self.limit if self.limit else len(all_tasks)
            tasks = all_tasks[self.start:end_index]
            print(f"Loaded {len(tasks)} tasks from {self.tasks_file}")
            if self.start > 0:
                print(f"  Starting from task index: {self.start}")
            if self.limit:
                print(f"  Limiting to: {self.limit} tasks")
            print(f"  Running tasks {self.start} to {self.start + len(tasks) - 1} (out of {len(all_tasks)} total)")

        return tasks

    async def run_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Run a single task through PlanningAgent and return its plan."""
        task_id = task.get("task_id", "unknown")
        intent = task.get("intent", "")

        # Enrich the prompt with repo context from start_url when present
        start_url = task.get("start_url", "")
        repo_path = start_url.replace("__GITLAB__", "").replace("__SHOPPING__", "").strip("/")
        prompt = f"Project path: {repo_path}\n\nTask: {intent}" if repo_path else intent

        print(f"\n{'='*70}")
        print(f"Task {task_id} — prompt sent to planning agent:")
        print(f"{'-'*70}")
        print(prompt)
        print(f"{'='*70}\n")

        if self.dryrun:
            return {"task_id": task_id, "intent": intent, "prompt": prompt, "status": "dryrun"}

        try:
            plan_response = await asyncio.wait_for(
                self.agent.plan(prompt),
                timeout=120  # 2 minute timeout per task
            )

            # Serialize plan steps to dicts for JSON output
            plan_steps = [
                {
                    "step_id": step.step_id,
                    "tool_name": step.tool_name.value if hasattr(step.tool_name, "value") else str(step.tool_name),
                    "arguments": [
                        {"name": a.name, "value": a.value, "value_type": a.value_type}
                        for a in (step.arguments or [])
                    ],
                    "depends_on": step.depends_on or [],
                    "hints": step.hints or "",
                }
                for step in plan_response.plan
            ]

            print(pretty_print_plan(plan_response.plan))
            print(f"✅ Task {task_id} — plan generated ({len(plan_steps)} steps)")

            return {
                "task_id": task_id,
                "intent": intent,
                "status": "success",
                "plan": plan_steps,
                "plan_step_count": len(plan_steps),
            }

        except asyncio.TimeoutError:
            print(f"⏱ Task {task_id} timed out")
            return {
                "task_id": task_id,
                "intent": intent,
                "status": "failed",
                "error": "timeout",
                "plan": None,
            }
        except Exception as e:
            print(f"❌ Task {task_id} failed: {e}")
            return {
                "task_id": task_id,
                "intent": intent,
                "status": "failed",
                "error": str(e),
                "plan": None,
            }

    async def run_all_tasks(self):
        """Run all tasks sequentially and collect results."""
        tasks = self.load_tasks()
        print(f"Starting batch planning of {len(tasks)} tasks\n")
        print("=" * 70)

        for i, task in enumerate(tasks, 1):
            print(f"\n[{i}/{len(tasks)}]", end=" ")
            result = await self.run_task(task)
            self.results.append(result)

        print("\n" + "=" * 70)
        print(f"\nCompleted {len(self.results)} tasks")

    def save_results(self):
        """Save results to output JSON file and print summary."""
        self.output_file.parent.mkdir(parents=True, exist_ok=True)

        successful = [r for r in self.results if r.get("status") == "success"]
        failed = [r for r in self.results if r.get("status") == "failed"]

        output_data = {
            "timestamp": datetime.now().isoformat(),
            "total_tasks": len(self.results),
            "successful_tasks": len(successful),
            "failed_tasks": len(failed),
            "tasks": self.results,
        }

        with open(self.output_file, "w") as f:
            json.dump(output_data, f, indent=2, default=str)

        print(f"\n✅ Results saved to {self.output_file}")
        print("\n" + "=" * 70)
        print("PLANNING SUMMARY")
        print("=" * 70)
        print(f"\nTotal tasks:  {output_data['total_tasks']}")
        print(f"Successful:   {output_data['successful_tasks']}")
        print(f"Failed:       {output_data['failed_tasks']}")
        rate = (len(successful) / len(self.results) * 100) if self.results else 0
        print(f"Success rate: {rate:.1f}%")

        if failed:
            print("\n" + "-" * 70)
            print(f"FAILED TASKS ({len(failed)})")
            print("-" * 70)
            for r in failed:
                print(f"\n  ❌ Task ID: {r.get('task_id', 'unknown')}")
                print(f"     Intent:  {r.get('intent', 'N/A')[:80]}")
                if r.get("error"):
                    print(f"     Error:   {r['error'][:150]}")

        if successful:
            print("\n" + "-" * 70)
            print(f"PLANNED TASKS ({len(successful)})")
            print("-" * 70)
            for r in successful:
                print(f"\n  ✅ Task ID: {r.get('task_id', 'unknown')}")
                print(f"     Intent:  {r.get('intent', 'N/A')[:80]}")
                print(f"     Steps:   {r.get('plan_step_count', 0)}")

        print("\n" + "=" * 70)


async def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Run batch tasks through PlanningAgent and save plans to JSON"
    )
    parser.add_argument(
        "--tasks-file", default="gitlab_tasks.json",
        help="Path to tasks JSON file (default: gitlab_tasks.json)"
    )
    parser.add_argument(
        "--output", "-o", dest="output_file", default="planning_results.json",
        help="Path to save results JSON file (default: planning_results.json)"
    )
    parser.add_argument(
        "--api-dir", default="api",
        help="Directory containing swagger files and swagger_index.json (default: api)"
    )
    parser.add_argument(
        "--start", type=int, default=0,
        help="Start index for tasks (default: 0)"
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Maximum number of tasks to run (default: all)"
    )
    parser.add_argument(
        "--task-ids", nargs="+", type=int, default=None, metavar="ID",
        help="Specific task IDs to run (e.g. --task-ids 123 142 156). Overrides --start and --limit."
    )
    parser.add_argument(
        "--dryrun", action="store_true",
        help="Print prompts only without running the agent"
    )

    args = parser.parse_args()

    try:
        runner = PlanningBatchRunner(
            tasks_file=args.tasks_file,
            output_file=args.output_file,
            api_dir=args.api_dir,
            start=args.start,
            limit=args.limit,
            task_ids=args.task_ids,
            dryrun=args.dryrun,
        )

        if not args.dryrun:
            runner.initialize()

        await runner.run_all_tasks()
        runner.save_results()
        print("\n✅ Batch planning completed successfully!")

    except KeyboardInterrupt:
        print("\n\n⚠️  Batch planning interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Batch planning failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
