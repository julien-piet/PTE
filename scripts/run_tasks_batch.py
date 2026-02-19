"""
Batch task runner script: Parse tasks from gitlab_tasks.json and run them through agent_replan.
Outputs results to a JSON file.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

# Imports from the agent
from agent.common.configurator import Configurator
from agent.common.tool_manager import initialize_tools
from agent.providers.provider import ModelProvider
from agent.agent_replan import ToolCallAgent


class TaskBatchRunner:
    """Runs multiple tasks through the agent and collects results."""

    def __init__(self, tasks_file: str, output_file: str, start: int = 0, limit: Optional[int] = None):
        """
        Initialize the batch runner.

        Args:
            tasks_file: Path to gitlab_tasks.json
            output_file: Path to save results JSON
            start: Index to start from (default: 0)
            limit: Maximum number of tasks to run (None = all)
        """
        self.tasks_file = Path(tasks_file)
        self.output_file = Path(output_file)
        self.start = max(0, start)  # Ensure non-negative
        self.limit = limit
        self.agent = None
        self.tools = None
        self.token_store = None
        self.results = []

    async def initialize(self):
        """Initialize the agent, tools, and LLM."""
        print("Initializing agent...")

        # Load configuration
        config = Configurator()
        config.load_all_env()
        config.check_llm_env_vars()
        config.get_mcp_servers()

        # Initialize model
        provider = ModelProvider(config)
        print(f"Using model: {provider.llm_provider}:{provider.model_name}")
        llm_signature = provider.llm_provider + ":" + provider.model_name

        # Initialize tools from MCP servers
        self.tools, self.token_store = await initialize_tools(config)

        print(f"Loaded {len(self.tools)} tools")

        # Create agent
        self.agent = ToolCallAgent(
            llm=llm_signature,
            miniscope=False,
            tools=self.tools,
            token_store=self.token_store
        )

        print("Agent initialized successfully\n")

    def load_tasks(self) -> List[Dict[str, Any]]:
        """Load tasks from gitlab_tasks.json with start and limit."""
        if not self.tasks_file.exists():
            raise FileNotFoundError(f"Tasks file not found: {self.tasks_file}")

        with open(self.tasks_file, 'r') as f:
            all_tasks = json.load(f)

        # Apply start and limit
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
        """
        Run a single task through the agent.

        Args:
            task: Task dictionary from gitlab_tasks.json

        Returns:
            Result dictionary with task info and agent output
        """
        task_id = task.get("task_id", "unknown")
        intent = task.get("intent", "")

        print(f"Running task {task_id}: {intent[:60]}...")

        try:
            # Prepare state for agent
            state = {
                "messages": [
                    {"role": "user", "content": intent}
                ],
                "plan": None,
                "intercepted": False,
                "execution_result": {},
                "mapped_arguments": {},
                "response": "",
                "global_message_history": [{"role": "user", "content": intent}],
                "routed_websites": None,
                "api_context": None,
                "requirements_context": None,
                "model_decisions": None,
                "defaults_used": None,
                "user_inputs": None,
                "auth_requirements": None,
            }

            # Run agent with timeout
            try:
                result_state = await asyncio.wait_for(
                    self.agent.invoke(state),
                    timeout=300  # 5 minute timeout per task
                )
            except asyncio.TimeoutError:
                result_state = {
                    "response": "Task execution timed out after 5 minutes",
                    "error": "timeout"
                }

            # Extract response
            response = result_state.get("response", "No response")
            plan = result_state.get("plan")
            error = result_state.get("error")

            # Determine status based on whether an error occurred
            status = "failed" if error else "success"

            result = {
                "task_id": task_id,
                "intent": intent,
                "status": status,
                "response": response,
                "plan_generated": plan is not None,
                "execution_context": result_state.get("execution_context"),
            }

            # Add error if present
            if error:
                result["error"] = error

            # Add optional fields if they exist
            if result_state.get("routed_websites"):
                result["routed_websites"] = [w.name for w in result_state["routed_websites"]]
            if result_state.get("user_inputs"):
                result["user_inputs"] = result_state["user_inputs"]

            if status == "success":
                print(f"✅ Task {task_id} completed")
            else:
                print(f"❌ Task {task_id} failed: {error}")
            return result

        except Exception as e:
            print(f"❌ Task {task_id} failed: {str(e)}")
            return {
                "task_id": task_id,
                "intent": intent,
                "status": "failed",
                "error": str(e),
                "response": None,
                "plan_generated": False,
            }

    async def run_all_tasks(self):
        """Run all tasks and collect results."""
        # Load tasks
        tasks = self.load_tasks()

        print(f"Starting batch execution of {len(tasks)} tasks\n")
        print("=" * 70)

        # Run tasks sequentially (change to concurrent if needed)
        for i, task in enumerate(tasks, 1):
            print(f"\n[{i}/{len(tasks)}]", end=" ")
            result = await self.run_task(task)
            self.results.append(result)

        print("\n" + "=" * 70)
        print(f"\nCompleted {len(self.results)} tasks")

    def save_results(self):
        """Save results to output JSON file and print detailed summary."""
        # Create output directory if it doesn't exist
        self.output_file.parent.mkdir(parents=True, exist_ok=True)

        # Separate successful and failed tasks
        successful_tasks = [r for r in self.results if r.get("status") == "success"]
        failed_tasks = [r for r in self.results if r.get("status") == "failed"]

        # Prepare output data
        output_data = {
            "timestamp": datetime.now().isoformat(),
            "total_tasks": len(self.results),
            "successful_tasks": len(successful_tasks),
            "failed_tasks": len(failed_tasks),
            "tasks": self.results
        }

        # Save to file
        with open(self.output_file, 'w') as f:
            json.dump(output_data, f, indent=2, default=str)

        print(f"\n✅ Results saved to {self.output_file}")

        # Print detailed summary
        print("\n" + "=" * 70)
        print("EXECUTION SUMMARY")
        print("=" * 70)
        print(f"\nTotal tasks: {output_data['total_tasks']}")
        print(f"Successful: {output_data['successful_tasks']}")
        print(f"Failed: {output_data['failed_tasks']}")
        success_rate = (output_data['successful_tasks'] / output_data['total_tasks'] * 100) if output_data['total_tasks'] > 0 else 0
        print(f"Success rate: {success_rate:.1f}%")

        # Show failed tasks with details
        if failed_tasks:
            print("\n" + "-" * 70)
            print(f"FAILED TASKS ({len(failed_tasks)})")
            print("-" * 70)
            for task in failed_tasks:
                print(f"\n  ❌ Task ID: {task.get('task_id', 'unknown')}")
                print(f"     Intent: {task.get('intent', 'N/A')[:80]}...")
                if task.get('error'):
                    print(f"     Error: {task.get('error')[:150]}")

        # Show passed tasks summary
        if successful_tasks:
            print("\n" + "-" * 70)
            print(f"PASSED TASKS ({len(successful_tasks)})")
            print("-" * 70)
            for task in successful_tasks:
                plan_info = "✓ Plan generated" if task.get('plan_generated') else "✗ No plan"
                print(f"\n  ✅ Task ID: {task.get('task_id', 'unknown')}")
                print(f"     Intent: {task.get('intent', 'N/A')[:80]}...")
                print(f"     {plan_info}")
                if task.get('routed_websites'):
                    print(f"     Routed to: {', '.join(task['routed_websites'])}")

        print("\n" + "=" * 70)


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Run batch tasks from gitlab_tasks.json through agent_replan"
    )
    parser.add_argument(
        "--tasks-file",
        default="gitlab_tasks.json",
        help="Path to tasks JSON file (default: gitlab_tasks.json)"
    )
    parser.add_argument(
        "--output", "-o",
        dest="output_file",
        default="task_results.json",
        help="Path to save results JSON file (default: task_results.json)"
    )
    parser.add_argument(
        "--start",
        type=int,
        default=0,
        help="Start index for tasks to run (default: 0)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of tasks to run (default: all)"
    )

    args = parser.parse_args()

    try:
        # Create runner
        runner = TaskBatchRunner(
            tasks_file=args.tasks_file,
            output_file=args.output_file,
            start=args.start,
            limit=args.limit
        )

        # Initialize
        await runner.initialize()

        # Run all tasks
        await runner.run_all_tasks()

        # Save results
        runner.save_results()

        print("\n✅ Batch execution completed successfully!")

    except KeyboardInterrupt:
        print("\n\n⚠️  Batch execution interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Batch execution failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
