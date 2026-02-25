#!/usr/bin/env python3
"""
Agent Task Runner - Extension for ToolCallAgent

Adds run_single_task() capability to test agent on WebArena tasks.
"""

import sys
from pathlib import Path
from typing import Dict, Any, Optional
import asyncio

# Add project root
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


class AgentTaskRunner:
    """Wrapper to run agent on individual tasks programmatically."""

    def __init__(self, agent):
        """
        Initialize with a ToolCallAgent instance.

        Args:
            agent: Instance of ToolCallAgent from agent_replan.py
        """
        self.agent = agent

    async def run_single_task(
        self,
        task_intent: str,
        task_context: Optional[Dict[str, Any]] = None,
        timeout: int = 60
    ) -> Dict[str, Any]:
        """
        Run agent on a single task and return results.

        Args:
            task_intent: The task description (e.g., "Check out my todos")
            task_context: Optional context from test data (credentials, etc.)
            timeout: Max time in seconds

        Returns:
            {
                "success": bool,
                "plan": Optional[Dict],  # The generated plan
                "final_url": Optional[str],  # Final URL navigated to
                "answer": Optional[str],  # Text answer (for non-navigation tasks)
                "execution_result": Dict,  # Full execution results
                "error": Optional[str]
            }
        """
        try:
            # Prepare state
            state = {
                "messages": [{"role": "user", "content": task_intent}],
                "plan": None,
                "intercepted": False,
                "execution_result": {},
                "mapped_arguments": {},
                "response": "",
                "global_message_history": [{"role": "user", "content": task_intent}],
                "routed_websites": None,
                "api_context": None,
                "requirements_context": None,
                "model_decisions": None,
                "defaults_used": None,
                "user_inputs": None,
                "auth_requirements": None,
            }

            # Add context if provided (credentials, etc.)
            if task_context:
                # Inject context into the task intent
                context_str = self._format_context(task_context)
                if context_str:
                    state["messages"][0]["content"] = f"{task_intent}\n\n{context_str}"

            # Run agent workflow with timeout
            result = await asyncio.wait_for(
                self._run_agent_workflow(state),
                timeout=timeout
            )

            return result

        except asyncio.TimeoutError:
            return {
                "success": False,
                "plan": None,
                "final_url": None,
                "answer": None,
                "execution_result": {},
                "error": f"Task timed out after {timeout} seconds"
            }
        except Exception as e:
            return {
                "success": False,
                "plan": None,
                "final_url": None,
                "answer": None,
                "execution_result": {},
                "error": str(e)
            }

    async def _run_agent_workflow(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Run the full agent workflow: route -> plan -> analyze -> review -> execute."""

        # Step 1: Router
        state = await self.agent.router(state)

        # Step 2: Planner
        state = await self.agent.planner(state)

        # Step 3: Requirement Analyzer
        state = await self.agent.requirement_analyzer(state)

        # Step 4: Plan Reviewer
        state = await self.agent.plan_reviewer(state)

        # Check if plan was generated
        plan = state.get("plan")
        if not plan:
            return {
                "success": False,
                "plan": None,
                "final_url": None,
                "answer": None,
                "execution_result": {},
                "error": "No plan generated"
            }

        # Step 5: Execute the plan — loop until all steps are done or no progress
        try:
            max_waves = len(plan) + 1  # upper bound: one wave per step
            for _ in range(max_waves):
                state = await self.agent.executor(state)
                ctx = state.get("execution_context")
                if ctx is None:
                    break
                if ctx.is_complete():
                    break
                # If no steps are ready and we're not complete, a failed step is
                # blocking its dependents — no further progress is possible.
                if not ctx.get_ready_steps() and ctx.executing_steps == set():
                    print("   ⚠️  Execution stalled: a failed step is blocking dependents.")
                    break
        except Exception as e:
            return {
                "success": False,
                "plan": plan,
                "final_url": None,
                "answer": None,
                "execution_result": {},
                "error": f"Execution error: {str(e)}"
            }

        # Step 6: Responder (format the response)
        try:
            state = await self.agent.responder(state)
        except Exception as e:
            # Responder error is less critical - we still have execution results
            pass

        # Extract results from execution
        execution_result = state.get("execution_result", {})
        response = state.get("response", "")

        # Try to extract final URL or answer
        final_url = None
        answer = None

        # Check if execution produced a URL (for navigation tasks)
        if isinstance(execution_result, dict):
            final_url = execution_result.get("final_url") or execution_result.get("url")

        # Use response as answer (for data extraction tasks)
        if response:
            answer = response

        return {
            "success": True,
            "plan": plan,
            "final_url": final_url,
            "answer": answer,
            "execution_result": execution_result,
            "error": None
        }

    def _format_context(self, context: Dict[str, Any]) -> str:
        """Format context information for injection."""
        parts = []

        if "gitlab_username" in context:
            parts.append(f"GitLab username: {context['gitlab_username']}")
        if "gitlab_password" in context:
            parts.append(f"GitLab password: {context['gitlab_password']}")
        if "namespace" in context:
            parts.append(f"Namespace: {context['namespace']}")
        if "project" in context:
            parts.append(f"Project: {context['project']}")

        if parts:
            return "Context:\n" + "\n".join(f"- {p}" for p in parts)
        return ""


# Example usage
async def test_agent_on_task():
    """Example of how to use AgentTaskRunner."""
    from agent.agent_replan import ToolCallAgent
    from agent.common.configurator import Configurator
    from agent.common.tool_manager import initialize_tools

    # Initialize
    config = Configurator()
    config.load_client_env()

    provider = config.get_key('agent_llm_provider')
    model = config.get_key('agent_llm_model')
    llm_signature = f"{provider}:{model}"

    tools = initialize_tools(config)

    # Create agent
    agent = ToolCallAgent(llm=llm_signature, tools=tools, miniscope=False)

    # Create task runner
    runner = AgentTaskRunner(agent)

    # Run a task
    task_context = {
        "gitlab_username": "byteblaze",
        "gitlab_password": "hello1234"
    }

    result = await runner.run_single_task(
        "Check out my todos",
        task_context=task_context,
        timeout=60
    )

    print(f"Success: {result['success']}")
    print(f"Plan: {result['plan']}")
    print(f"Error: {result['error']}")


if __name__ == "__main__":
    asyncio.run(test_agent_on_task())
