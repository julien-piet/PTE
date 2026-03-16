"""
Agent: a thin wrapper around PlanningAgent + ExecutionAgent for single-prompt use.
"""

import asyncio
from typing import Any, Optional

from agent.auth import AuthRegistry
from agent.execution_agent import ExecutionAgent, ExecutionResult
from agent.planning_agent import PlanningAgent


class Agent:
    """
    Plans and executes a single natural language prompt.

    Usage:
        agent = Agent()
        agent.initialize(server="gitlab")
        result = await agent.run_task("Create an issue titled 'dark mode' in project foo/bar")
        print(result.answer)
        print(agent.last_plan_response.plan)  # available after run_task()
    """

    def __init__(
        self,
        env_file: str = "config/.server_env",
        api_dir: str = "api",
        skip_execution: bool = False,
        debug: bool = False,
    ):
        self.env_file = env_file
        self.api_dir = api_dir
        self.skip_execution = skip_execution
        self.debug = debug

        self.planning_agent: Optional[PlanningAgent] = None
        self.execution_agent: Optional[ExecutionAgent] = None
        self.last_plan_response: Optional[Any] = None  # set after each run_task()

    def initialize(self, server: str = "gitlab") -> None:
        self.planning_agent = PlanningAgent(
            api_dir=self.api_dir,
            debug_responses=self.debug,
            debug_prompts=False,
        )

        if not self.skip_execution:
            registry = AuthRegistry.build_default(self.env_file)
            if server not in registry:
                raise ValueError(
                    f"Server {server!r} not found in auth registry. "
                    f"Check that its token is set in {self.env_file!r}."
                )
            self.execution_agent = ExecutionAgent(
                auth=registry.get(server),
                debug=self.debug,
            )

    async def run_task(self, prompt: str) -> ExecutionResult:
        """
        Plan and execute a natural language prompt.

        Args:
            prompt: The user's request (e.g. "Create an issue in project foo/bar").

        Returns:
            ExecutionResult with raw API outputs and a natural language answer.
        """
        if self.planning_agent is None:
            raise RuntimeError("Call initialize() before run_task().")

        plan_response = await asyncio.wait_for(
            self.planning_agent.plan(prompt),
            timeout=120,
        )
        self.last_plan_response = plan_response

        if self.skip_execution:
            return ExecutionResult(outputs={}, answer="(execution skipped)")

        if self.execution_agent is None:
            raise RuntimeError("ExecutionAgent was not initialized (skip_execution=True?).")

        return await asyncio.wait_for(
            self.execution_agent.execute(plan_response, task=prompt),
            timeout=120,
        )
