# scripts/run_tasks_batch_new.py
#
# Batch task runner for webarena-verified.json format.
# Reads from server-specific subsets of test_files/webarena-verified.json
# (gitlab_tasks_new.json or shopping_tasks_new.json) based on --server.
#
# Run all gitlab tasks (180 tasks):
#   python3 -m scripts.run_tasks_batch_new --server gitlab
#
# Run all shopping tasks (187 tasks):
#   python3 -m scripts.run_tasks_batch_new --server shopping
#
# Smoke test (first 5 tasks):
#   python3 -m scripts.run_tasks_batch_new --server gitlab --limit 5
#
# Single task by ID:
#   python3 -m scripts.run_tasks_batch_new --server gitlab --task-ids 44
#
# Multiple tasks by ID:
#   python3 -m scripts.run_tasks_batch_new --server gitlab --task-ids 44 136 389
#
# Save results to a JSON log:
#   python3 -m scripts.run_tasks_batch_new --server gitlab --output gitlab_results.json
#
# Plan only (skip execution):
#   python3 -m scripts.run_tasks_batch_new --server gitlab --skip-execution
#
# Use multi-docker worker pool:
#   python3 -m scripts.run_tasks_batch_new --server gitlab --multi-docker

import asyncio
import json
import re
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.agent import Agent
from agent.auth import StaticAuth
from agent.planner import pretty_print_plan, pretty_print_execution
from eval.docker import workers_new as _workers_new


from eval.program_html_evaluator import DEFAULT_BASE_URLS as _EVALUATOR_URLS

# Map server names to the same URLs used by the evaluator's placeholder dict.
_DEFAULT_BASE_URLS: dict = {
    "gitlab":         _EVALUATOR_URLS["__GITLAB__"],
    "shopping":       _EVALUATOR_URLS["__SHOPPING__"],
    "shopping_admin": _EVALUATOR_URLS["__SHOPPING_ADMIN__"],
    "reddit":         _EVALUATOR_URLS["__REDDIT__"],
}

_WEBARENA_TASKS_FILE = "test_files/webarena-verified.json"

_DEFAULT_TASK_FILES: dict = {
    "gitlab":   "test_files/gitlab_tasks_new.json",
    "shopping": "test_files/shopping_tasks_new.json",
}


@asynccontextmanager
async def _local_session(server_url: str, glpat: Optional[str]):
    """Stub worker session for a single local server instance."""
    yield {"worker_id": "local", "gitlab_url": server_url, "glpat": glpat}


def _serialize_plan(plan) -> list:
    return [
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
        for step in plan
    ]

class TaskBatchRunner:
    """Plans and executes tasks, saving both plan and execution results."""

    def __init__(
        self,
        tasks_file: str,
        output_file: str,
        server: str,
        env_file: str = "config/.server_env",
        api_dir: str = "api",
        start: int = 0,
        limit: Optional[int] = None,
        task_ids: Optional[List[int]] = None,
        skip_execution: bool = False,
        debug: bool = False,
        multi_docker: bool = False,
        base_url: Optional[str] = None,
    ):
        self.tasks_file = Path(tasks_file)
        self.output_file = Path(output_file)
        self.server = server
        self.env_file = env_file
        self.api_dir = api_dir
        self.start = max(0, start)
        self.limit = limit
        self.task_ids = task_ids
        self.skip_execution = skip_execution
        self.debug = debug
        self.multi_docker = multi_docker
        self.base_url = base_url or _DEFAULT_BASE_URLS.get(server, "http://localhost:8023")
        self.num_workers = _workers_new.num_workers() if multi_docker else 1
        self._glpat: Optional[str] = None

        self.results: List[Dict[str, Any]] = []
        self._acquire_lock: asyncio.Lock = asyncio.Lock()

    def initialize(self):
        if not self.multi_docker and self.server == "gitlab":
            from eval.docker.gitlab_init import get_glpat
            self._glpat = get_glpat(self.base_url, "agent-local")
        mode = "multi-docker" if self.multi_docker else f"single ({self.base_url})"
        print(f"Config: server={self.server!r}, workers={self.num_workers}, mode={mode}")
        print("Agent ready\n")

    def load_tasks(self) -> List[Dict[str, Any]]:
        if not self.tasks_file.exists():
            raise FileNotFoundError(f"Tasks file not found: {self.tasks_file}")

        with open(self.tasks_file) as f:
            all_tasks = json.load(f)

        if self.task_ids is not None:
            id_set = set(self.task_ids)
            tasks = [t for t in all_tasks if t.get("task_id") in id_set]
            id_order = {tid: i for i, tid in enumerate(self.task_ids)}
            tasks.sort(key=lambda t: id_order.get(t.get("task_id"), 0))
            missing = id_set - {t.get("task_id") for t in tasks}
            if missing:
                print(f"  Warning: task IDs not found: {sorted(missing)}")
            print(f"Loaded {len(tasks)} tasks (filtered by IDs: {self.task_ids})")
        else:
            end_index = self.start + self.limit if self.limit else len(all_tasks)
            tasks = all_tasks[self.start:end_index]
            print(f"Loaded {len(tasks)} tasks (index {self.start}–{self.start + len(tasks) - 1} of {len(all_tasks)} total)")

        return tasks


    async def run_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        task_id = task.get("task_id", "unknown")
        intent = task.get("intent", "")

        # webarena-verified.json uses `start_urls` (list); fall back to legacy `start_url` (string).
        start_urls = task.get("start_urls") or [task.get("start_url", "")]
        start_url = start_urls[0] if start_urls else ""
        repo_path = re.sub(r"__[A-Z_]+__", "", start_url).strip("/")
        prompt = f"Project path: {repo_path}\n\nTask: {intent}" if repo_path else intent

        print(f"\n{'='*70}")
        print(f"Task {task_id}: {intent}")
        print(f"{'='*70}")

        # Each task gets its own agent to avoid shared mutable state.
        agent = Agent(
            env_file=self.env_file,
            api_dir=self.api_dir,
            skip_execution=self.skip_execution,
            debug=self.debug,
        )
        agent.initialize({self.server: ""})

        task_result: Optional[Dict[str, Any]] = None

        try:
            if self.multi_docker:
                worker_ctx = _workers_new.worker_session(
                    str(task_id),
                    server=self.server,
                    acquire_lock=self._acquire_lock,
                    read_only=True,
                )
            else:
                worker_ctx = _local_session(self.base_url, self._glpat)

            async with worker_ctx as w:
                worker_id = w["worker_id"]
                gitlab_url = w["gitlab_url"]
                glpat = w["glpat"]

                # Inject auth into the execution agent.
                # GitLab uses a dynamically obtained GLPAT; other servers (e.g.
                # shopping) use static tokens already loaded from .server_env.
                if agent.execution_agent is not None:
                    if self.server == "gitlab" and glpat:
                        agent.execution_agent.auth = StaticAuth({"PRIVATE-TOKEN": glpat})
                    agent.execution_agent.task_id = str(task_id)

                # ── Plan + Execute ────────────────────────────────────────────
                execution_result = await agent.run_task(prompt, servers={self.server: gitlab_url})

                plan_response = agent.last_plan_response
                plan_steps = _serialize_plan(plan_response.plan)
                print(pretty_print_plan(plan_response.plan))
                print(f"  ✅ Plan ready ({len(plan_steps)} steps)")

                if self.skip_execution:
                    task_result = {
                        "task_id": task_id,
                        "intent": intent,
                        "status": "execution_failed",
                        "error": "execution skipped (--skip-execution flag)",
                        "plan": plan_steps,
                        "plan_step_count": len(plan_steps),
                        "execution": None,
                        "worker_id": worker_id,
                    }
                else:
                    print(pretty_print_execution(plan_response.plan, execution_result.answer))
                    print(f"  ✅ Execution complete ({len(execution_result.outputs)} steps)")
                    parsed_outputs = (
                        agent.execution_agent.last_ctx.step_outputs
                        if agent.execution_agent is not None
                        else None
                    )
                    task_result = {
                        "task_id": task_id,
                        "intent": intent,
                        "status": "success",
                        "plan": plan_steps,
                        "plan_step_count": len(plan_steps),
                        "execution": execution_result.outputs,
                        "parsed_outputs": parsed_outputs,
                        "answer": execution_result.answer,
                        "worker_id": worker_id,
                    }

        except asyncio.TimeoutError:
            timed_out_during = "planning" if agent.last_plan_response is None else "execution"
            print(f"  ⏱ {timed_out_during.capitalize()} timed out")
            ea = agent.execution_agent
            plan_steps = _serialize_plan(agent.last_plan_response.plan) if agent.last_plan_response else None
            partial_outputs = ea.last_raw_outputs if ea is not None and hasattr(ea, "last_raw_outputs") else None
            partial_parsed = ea.last_ctx.step_outputs if ea is not None and hasattr(ea, "last_ctx") else None
            task_result = {
                "task_id": task_id,
                "intent": intent,
                "status": "failed" if timed_out_during == "planning" else "execution_failed",
                "error": f"{timed_out_during} timeout",
                "plan": plan_steps,
                "plan_step_count": len(plan_steps) if plan_steps else None,
                "execution": partial_outputs or None,
                "parsed_outputs": partial_parsed or None,
                "answer": None,
                "worker_id": None,
            }

        except Exception as e:
            if agent.last_plan_response is None:
                print(f"  ❌ Planning failed: {e}")
                task_result = {
                    "task_id": task_id,
                    "intent": intent,
                    "status": "failed",
                    "error": str(e),
                    "plan": None,
                    "execution": None,
                    "worker_id": None,
                }
            else:
                print(f"  ❌ Execution failed: {e}")
                plan_response = agent.last_plan_response
                plan_steps = _serialize_plan(plan_response.plan)
                ea = agent.execution_agent
                partial_outputs = ea.last_raw_outputs if ea is not None else None
                partial_parsed = ea.last_ctx.step_outputs if ea is not None and hasattr(ea, "last_ctx") else None
                partial_answer = ea.last_answer if ea is not None and hasattr(ea, "last_answer") and ea.last_answer else None
                task_result = {
                    "task_id": task_id,
                    "intent": intent,
                    "status": "execution_failed",
                    "error": str(e),
                    "plan": plan_steps,
                    "plan_step_count": len(plan_steps),
                    "execution": partial_outputs or None,
                    "parsed_outputs": partial_parsed or None,
                    "answer": partial_answer,
                    "worker_id": None,
                }

        return task_result

    async def run_all(self):
        tasks = self.load_tasks()
        print(f"\nStarting batch run of {len(tasks)} tasks ({self.num_workers} workers)\n" + "=" * 70)

        sem = asyncio.Semaphore(self.num_workers)
        remaining = len(tasks)
        remaining_lock = asyncio.Lock()

        async def run_with_sem(task):
            async with sem:
                result = await self.run_task(task)
            async with remaining_lock:
                nonlocal remaining
                remaining -= 1
                status = result.get("status", "unknown")
                print(f"\n[{remaining} tasks remaining] Task {result.get('task_id')} done ({status})")
            return result

        futures = [asyncio.ensure_future(run_with_sem(t)) for t in tasks]
        try:
            self.results = list(await asyncio.gather(*futures))
        except BaseException:
            # Cancel all outstanding tasks so their finally blocks fire and
            # release any acquired workers before we propagate the exception.
            for f in futures:
                f.cancel()
            await asyncio.gather(*futures, return_exceptions=True)
            raise

        print("\n" + "=" * 70)

    def save_results(self):
        self.output_file.parent.mkdir(parents=True, exist_ok=True)

        successful  = [r for r in self.results if r.get("status") == "success"]
        planned     = [r for r in self.results if r.get("status") == "planned"]
        exec_failed = [r for r in self.results if r.get("status") == "execution_failed"]
        failed      = [r for r in self.results if r.get("status") == "failed"]

        output_data = {
            "timestamp": datetime.now().isoformat(),
            "server": self.server,
            "total_tasks": len(self.results),
            "successful": len(successful),
            "planned_only": len(planned),
            "execution_failed": len(exec_failed),
            "planning_failed": len(failed),
            "tasks": self.results,
        }

        with open(self.output_file, "w") as f:
            json.dump(output_data, f, indent=2, default=str)

        print(f"\n📄 Results saved to {self.output_file}")
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"  Total tasks:       {output_data['total_tasks']}")
        print(f"  ✅ Success:        {output_data['successful']}")
        if planned:
            print(f"  📋 Planned only:   {output_data['planned_only']}")
        print(f"  ❌ Exec failed:    {output_data['execution_failed']}")
        print(f"  ❌ Plan failed:    {output_data['planning_failed']}")

        if failed or exec_failed:
            print("\n" + "-" * 70)
            print("FAILURES")
            print("-" * 70)
            for r in failed + exec_failed:
                print(f"\n  Task {r.get('task_id')}: {r.get('intent', '')[:70]}")
                print(f"    Status: {r.get('status')}  |  Error: {r.get('error', '')[:100]}")

        print("\n" + "=" * 70)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Plan and execute webarena-verified.json tasks using PlanningAgent + ExecutionAgent"
    )
    parser.add_argument(
        "--tasks-file", default=None,
        help="Path to tasks JSON file. Defaults per --server: gitlab→gitlab_tasks_new.json, shopping→shopping_tasks_new.json, else webarena-verified.json."
    )
    parser.add_argument(
        "--output", "-o", dest="output_file", default="logs/task_results.json",
        help="Path to save results JSON file (default: task_results.json)"
    )
    parser.add_argument(
        "--server", default="shopping_admin",
        help="Auth server to use from .server_env (default: shopping_admin)"
    )
    parser.add_argument(
        "--env-file", default="config/.server_env",
        help="Path to .env file containing auth tokens (default: config/.server_env)"
    )
    parser.add_argument(
        "--api-dir", default="api",
        help="Directory containing swagger files (default: api)"
    )
    parser.add_argument(
        "--start", type=int, default=0,
        help="Start index for tasks (default: 0)"
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Max number of tasks to run (default: all)"
    )
    parser.add_argument(
        "--task-ids", nargs="+", type=int, default=None, metavar="ID",
        help="Specific task IDs to run. Overrides --start and --limit."
    )
    parser.add_argument(
        "--skip-execution", action="store_true",
        help="Plan only, do not execute (equivalent to run_planning_batch.py)"
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Print curl commands and raw responses for each step"
    )
    parser.add_argument(
        "--multi-docker", action="store_true", default=False,
        help=(
            "Use the remote multi-docker worker pool via the SSH orchestrator. "
            "When omitted (default), tasks run against a single server at --base-url."
        ),
    )
    parser.add_argument(
        "--base-url", default=None,
        help=(
            "Base URL of the server (ignored when --multi-docker is set). "
            "Defaults are pulled from DEFAULT_BASE_URLS in eval/program_html_evaluator.py "
            "so you only need this flag to override them."
        ),
    )
    args = parser.parse_args()
    tasks_file = args.tasks_file or _DEFAULT_TASK_FILES.get(args.server, _WEBARENA_TASKS_FILE)

    try:
        runner = TaskBatchRunner(
            tasks_file=tasks_file,
            output_file=args.output_file,
            server=args.server,
            env_file=args.env_file,
            api_dir=args.api_dir,
            start=args.start,
            limit=args.limit,
            task_ids=args.task_ids,
            skip_execution=args.skip_execution,
            debug=args.debug,
            multi_docker=args.multi_docker,
            base_url=args.base_url,
        )
        runner.initialize()  # sync — must run before the event loop starts
        asyncio.run(_run_async(runner))

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Batch run failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


async def _run_async(runner: TaskBatchRunner):
    await runner.run_all()
    runner.save_results()
    print("\n✅ Batch run completed successfully!")


if __name__ == "__main__":
    main()
