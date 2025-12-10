"""
LangGraph Agent with planner, interceptor, executor, argument mapper, and responder nodes.
"""

import argparse
import asyncio
import re
import time
from collections import defaultdict




from typing import TypedDict, Annotated, List, Dict, Any, Callable, Optional
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from pydantic_ai import Agent, ModelSettings
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, UserPromptPart, TextPart, ToolCallPart, ToolReturnPart

# miniscope
from agent.common.configurator import Configurator
from agent.providers.provider import ModelProvider
from agent.common.mcp_client import call_tool_with_token, list_tools

# demo utils
# from demo.utils.planner import validate_plan, pretty_print_plan, ExecutionContext, build_agent_models
from agent.prompts import planner_prompt, responder_prompt

from agent.planner import ExecutionContext  # no validate_plan, no build_agent_models
# from agent.app_permissions.app_permissions_handler import ApplicationPermissons
from agent.strict_planner import (
    gather_specs_from_tool_definitions,
    build_planning_models_from_mcp_specs,
    build_planning_agent,
    validate_plan, 
    pretty_print_plan
)


permissions_handler = None
# Define the state structure for the graph
class AgentState(TypedDict):
    """State passed between nodes in the graph."""
    messages: Annotated[list, add_messages]
    plan: Optional[List[Any]] 
    intercepted: bool
    execution_context: ExecutionContext  # Encapsulates all execution state
    execution_result: dict
    mapped_arguments: dict
    response: str
    global_message_history: List[ModelMessage]


# Tool definition for Pydantic-friendly structure
class ToolDefinition(BaseModel):
    """Pydantic model for tool definition"""
    name: str = Field(description="Full tool name (server_tool_name)")
    original_name: str = Field(description="Original tool name without server prefix")
    server: str = Field(description="MCP server name")
    description: str = Field(description="Tool description")
    input_schema: Dict[str, Any] = Field(description="Input schema for the tool")
    execute: Callable = Field(description="Async function to execute the tool")

    class Config:
        arbitrary_types_allowed = True

def normalize_tool_name(tool_name: str) -> str:
    """
    Normalize the tool name by removing the server prefix.
    """
    # return tool_name.replace("functions.", "")
    return tool_name

def build_pydantic_tools_from_mcp(tools_specs, token: str, server_name: str) -> List[ToolDefinition]:
    """
    Build Pydantic-friendly tool definitions from MCP tool specifications.

    Args:
        tools_specs: List of tool specifications from MCP server
        token: Authentication token for MCP calls
        server_name: Name of the MCP server

    Returns:
        List of ToolDefinition objects
    """
    tools = []

    for spec in tools_specs:
        original_name = spec.name
        server = spec.server
        description = spec.description
        full_name = f"{server_name}-{spec.name}"  
        input_schema = spec.inputSchema if hasattr(spec, 'inputSchema') else {}

        # Create async execution function with closure
        def make_execute(tool_name: str, server_name: str, token: str):
            async def execute(**kwargs):
                result = await call_tool_with_token(server_name, token, tool_name, kwargs)
                # print("233,", result.model_dump())
                return result
            return execute

        tool_def = ToolDefinition(
            name=full_name,
            original_name=original_name,
            server=server,
            description=description,
            input_schema=input_schema,
            execute=make_execute(original_name, server, token)
        )

        tools.append(tool_def)

    return tools


async def initialize_tools(config, token: str = None) -> Dict[str, ToolDefinition]:
    """
    Initialize tools from MCP servers in a Pydantic-friendly way.

    Args:
        config: Configurator instance with MCP server configurations
        token: Optional authentication token (if None, will need to be provided later)

    Returns:
        Dictionary mapping tool names to ToolDefinition objects
    """
    mcp_servers = config.get_mcp_servers()
    print(f"Initializing tools from {len(mcp_servers)} MCP servers...")

    tools_dict = {}

    for mcp in mcp_servers:
        server_name = mcp['name']
        server_url = mcp['url']

        try:
            # List tools from the MCP server
            res = await list_tools(server_url)

            if res is not None:
                # Build Pydantic-friendly tools
                server_token = token if token else "default_token"
                tool_definitions = build_pydantic_tools_from_mcp(res, server_token, server_name)

                # Add to dictionary
                for tool_def in tool_definitions:
                    tools_dict[tool_def.name] = tool_def

                print(f"  ✓ Loaded {len(tool_definitions)} tools from {server_name}")
            else:
                print(f"  ✗ Failed to load tools from {server_name}")

        except Exception as e:
            print(f"  ✗ Error loading tools from {server_name}: {e}")

    print(f"Total tools available: {len(tools_dict)}")
    return tools_dict


class ToolCallAgent:
    """
    LangGraph-based agent with planner, interceptor, executor, argument mapper, and responder nodes.
    """

    def __init__(self, llm=None, miniscope=False, tools=None):
        """
        Initialize the ToolCallAgent.

        Args:
            llm: Language model instance for making LLM calls in nodes.
            miniscope: If True, include interceptor node in the graph. If False, skip interceptor.
            tools: Dictionary of available tools (tool_name -> ToolDefinition).
        """
        if not llm:
            raise ValueError("LLM instance is required for ToolCallAgent")

        self.llm = llm
        self.miniscope = miniscope
        self.tools = tools or {}
        self.graph = self._create_graph()

        # # Build tool descriptions for the system prompt
        # tool_descriptions = []
        # tool_names = []
        # for tool_name, tool_def in self.tools.items():
        #     tool_desc = f"- {tool_name}: {tool_def.description}"
        #     if tool_def.input_schema:
        #         tool_desc += f"Parameters: {tool_def.input_schema} \n"
        #     tool_descriptions.append(tool_desc)
        #     tool_names.append(tool_name)

        # tools_context = "\n".join(tool_descriptions) if tool_descriptions else "No tools available"

        # # Augment the planning prompt with available tools
        # self.augmented_planner_prompt = f"{planner_prompt}\n\n## Available Tools:\n{tools_context}"
        # # self.augmented_planner_prompt = planner_prompt
        # self.tools_context = f"## Available Tools:\n{tools_context}"
        # Models = build_agent_models(tool_names)

        # # Create a planning agent with structured output (no toolset - just context)
        # self.planning_agent = Agent(
        #     self.llm if isinstance(self.llm, str) else str(self.llm),
        #     output_type=Models.AgentResponse,
        #     system_prompt=self.augmented_planner_prompt
        # )

        specs = gather_specs_from_tool_definitions(self.tools)
        _, Plan = build_planning_models_from_mcp_specs(specs)
        self.planning_agent = build_planning_agent(
            self.llm if isinstance(self.llm, str) else str(self.llm),
            planner_prompt,
            specs,
            PlanModel=Plan,   # explicit
        )

        self.responder_agent = Agent(
            self.llm if isinstance(self.llm, str) else str(self.llm),
            output_type=str,
            system_prompt=responder_prompt
        )

    async def planner(self, state: AgentState) -> AgentState:
        """
        Planner node: Creates a plan based on the input.
        Takes the user prompt and uses pydantic_ai to invoke the LLM to generate a tool call plan.
        """
        # Extract the latest user message
        messages = state.get("messages", [])
        if not messages:
            state["plan"] = None
            state["response"] = "No user input provided"
            return state

        # Get the last user message
        user_query = ""
        for msg in reversed(messages):
            # Handle both dict and LangGraph message object formats
            if isinstance(msg, dict):
                if msg.get("role") == "user":
                    user_query = msg.get("content", "")
                    break
            elif hasattr(msg, 'content'):
                # LangGraph message object (HumanMessage, etc.)
                if (hasattr(msg, 'type') and msg.type == "human") or \
                   (hasattr(msg, '__class__') and msg.__class__.__name__ == "HumanMessage"):
                    user_query = msg.content
                    break

        if not user_query:
            state["plan"] = None
            state["response"] = "No user query found"
            return state

        try:
            # Run the planning agent (tools are provided in system prompt context)
      
            message_history = self.get_message_history(state)
            # print(message_history)

            # print(f"Message history: {message_history}")

            # user_query += self.tools_context
            result = await self.planning_agent.run(user_query,message_history=message_history,model_settings=ModelSettings(temperature=0.0))
            plan_model = result.output

            # Optional: structural validation (acyclic deps, etc.)
            if not validate_plan(plan_model):
                state["plan"] = None
                state["response"] = "Invalid execution plan: detected cycle or missing dependencies"
                return state

            # Store the plan (use list for your ExecutionContext)
            state["plan"] = plan_model.steps
            state["response"] = ""

            # Pretty print (minor tweak: your pretty printer expects list-like)
            print(pretty_print_plan(state["plan"]))

        except Exception as e:
            # Handle errors gracefully
            print("Planning error: ", str(e))
            state["plan"] = None
            state["response"] = f"Error during planning: {str(e)}"

        return state

    # async def interceptor(self, state: AgentState) -> AgentState:
    #     """
    #     Interceptor node: Intercepts and validates the plan.
    #     """
    #     # TODO: Implement interceptor logic
    #     plan = state.get("plan")
    #     steps = list(plan)

    #     # TODO: Add potential invalid plan detection
    #     # Build required scopes per application and prompt for any missing ones
    #     missing_by_app: Dict[str, List[str]] = {}
    #     app_tools = defaultdict(list)
    #     for step in steps:
    #         tool_name = step.tool
    #         app_tools[tool_name.split('-')[0]].append(tool_name.split('-')[1])
        
    #      # For each application, analyze permissions and prompt user as needed
    #     for app_name in app_tools.keys():
    #         # Determine scopes required for this app given the plan
    #         required_scopes = await analyze_and_solve_permissions(
    #             [s for s in plan if s.tool.startswith(f"{app_name}-")], 
    #             permissions_handler
    #         )
    #         print(f"required_scopes: {required_scopes}")
    #         # Identify scopes not yet granted
    #         extra_scopes = [
    #             scope for scope in required_scopes
    #             if not permissions_handler.permission_manager.is_scope_granted(app_name, scope)
    #         ]
    #         if extra_scopes:
    #             user_decisions = prompt_user_for_permissions(app_name, extra_scopes, permissions_handler)
    #             print(f"🔐 User decisions for {app_name}: {user_decisions}")

    #         # Re-check after prompting to see if anything remains denied
    #         still_missing = [
    #             scope for scope in required_scopes
    #             if not permissions_handler.permission_manager.is_scope_granted(app_name, scope)
    #         ]
    #         if still_missing:
    #             missing_by_app[app_name] = still_missing
            
    #     if missing_by_app:
    #         state["permission_denied"] = {"apps": missing_by_app}
    #         return state
    #     else:
    #         state["permission_denied"] = None
    #         return state

    def argument_mapper(self, state: AgentState) -> AgentState:
        """
        Argument Mapper node: Maps arguments for execution.
        """
        # TODO: Implement argument mapper logic
        return state

    async def executor(self, state: AgentState) -> AgentState:
        """
        Executor node: Executes the planned actions.
        Executes all ready steps (with dependencies met) in parallel.
        Uses ExecutionContext to manage execution state cleanly.
        """
        plan = state.get("plan")
        if not plan:
            return state

        # Initialize execution context if not present
        
        # if "execution_context" not in state or state["execution_context"] is None:
        #     state["execution_context"] = ExecutionContext(plan)
        state["execution_context"] = ExecutionContext(plan)
        ctx = state["execution_context"]

        # Get steps ready to execute (all dependencies completed)
        ready_steps = ctx.get_ready_steps()

        if not ready_steps:
            # Check if execution is complete
            if ctx.is_complete():
                print(f"\n✅ All steps completed! {ctx.get_progress()}")
            return state  # All done or waiting for dependencies

        print(f"\n🚀 Executing steps in parallel: {ready_steps}")
        print(f"   Progress: {ctx.get_progress()}")

        # Mark steps as executing
        for step_id in ready_steps:
            ctx.mark_executing(step_id)

        # Execute ready steps in parallel
        async def execute_single_step(step_id: str):
            # Find step definition
            step = next(s for s in plan if s.step_id == step_id)

            # NEW: exact tool name and typed args
            tool_name = step.tool                       # Literal[...] string
            args = step.args.model_dump(exclude_none=True, exclude_unset=True)

            # Execute
            # if tool_name not in self.tools:
            #     raise ValueError(f"Tool '{tool_name}' not found in available tools")
            
            # tool_def = self.tools[tool_name]
            # result = await tool_def.execute(**args)

            # # Mark as completed in context
            # ctx.mark_completed(step_id, result)
            # ctx.add_summary(f"{step_id}({tool_name}) => {result}")
            # print(f"✅ Completed: {step_id}")

            # return step_id, result

            try:
                # Execute
                if tool_name not in self.tools:
                    raise ValueError(f"Tool '{tool_name}' not found in available tools")
                
                tool_def = self.tools[tool_name]
                result = await tool_def.execute(**args)

                # Mark as completed in context
                ctx.mark_completed(step_id, result)
                # print("added summary: ", f"{step_id}({tool_name}) => {result}")
                ctx.add_summary(f"{step_id}({tool_name}) => {result}")
                if "Insufficient permissions to execute this function" in result:
                    print("❌ Permission denied for this tool call.")
                else:
                    print(f"✅ Completed: {step_id}")

                return step_id, result

            except Exception as e:
                print(f"❌ Failed: {step_id} - {e}")
                error_msg = str(e)

                # Mark as failed in context
                ctx.mark_failed(step_id, error_msg)
                ctx.add_summary(f"{step_id}({tool_name}) => ERROR: {error_msg}")

                return step_id, f"Error: {error_msg}"

        # Run all ready steps concurrently
        tasks = [execute_single_step(step_id) for step_id in ready_steps]
        await asyncio.gather(*tasks, return_exceptions=True)

        return state

    def get_message_history(self, state: AgentState) -> List[ModelMessage]:
        """
        Message history node: Builds the message history for the responder based on current state and execution context.
        """
        messages = state.get("messages", [])
        ctx = state.get("execution_context")

        # Build prior history (exclude the last user message; we pass a fresh prompt below)
        message_history: List[ModelMessage] = []
        for msg in messages[:-1]:
            if isinstance(msg, dict):
                role = msg.get("role")
                content = msg.get("content", "")
                if role == "user":
                    message_history.append(ModelRequest(parts=[UserPromptPart(content=content)]))
                elif role == "assistant":
                    message_history.append(ModelResponse(parts=[TextPart(content=content)]))

        # Append tool traces from THIS turn, in the right sequence:
        #  ModelResponse(tool call) -> ModelRequest(tool return) for each executed step
        if ctx and getattr(ctx, "plan", None):
            for step in ctx.plan:
                step_id = step.step_id
                tool_name = step.tool  # new shape

                if hasattr(ctx, "completed_steps") and step_id in ctx.completed_steps:
                    # tool call trace
                    args_dict = step.args.model_dump()
                    message_history.append(
                        ModelResponse(parts=[
                            ToolCallPart(tool_name=tool_name, args=args_dict, tool_call_id=step_id)
                        ])
                    )
                    # tool return trace
                    output = ctx.get_step_output(step_id)
                    message_history.append(
                        ModelRequest(parts=[
                            ToolReturnPart(tool_name=tool_name, content=output, tool_call_id=step_id)
                        ])
                    )

                elif hasattr(ctx, "failed_steps") and step_id in ctx.failed_steps:
                    err = ctx.get_step_error(step_id) if hasattr(ctx, "get_step_error") else "error"
                    message_history.append(
                        ModelResponse(parts=[
                            ToolCallPart(tool_name=tool_name, args={"__omitted__": True}, tool_call_id=step_id)
                        ])
                    )
                    message_history.append(
                        ModelRequest(parts=[
                            ToolReturnPart(tool_name=tool_name, content={"error": str(err)}, tool_call_id=step_id)
                        ])
                    )
        if state.get('global_message_history') is None:
            state['global_message_history'] = message_history
        for msg in message_history:
            if msg not in state['global_message_history']:
                state['global_message_history'].append(msg)
        return state['global_message_history']

    async def responder(self, state: AgentState) -> AgentState:
        """
        Responder node: Generates the final response.
        """
        # If planner already produced a direct response (no tools), keep it
        if state.get("response"):
            return state

        messages = state.get("messages", [])
        message_history = self.get_message_history(state)
        # print(f"Message history: {message_history}")

        # Current user query (last message)
        user_query = ""
        for msg in reversed(messages):
            # Handle both dict and LangGraph message object formats
            if isinstance(msg, dict):
                if msg.get("role") == "user":
                    user_query = msg.get("content", "")
                    break
            elif hasattr(msg, 'content'):
                # LangGraph message object (HumanMessage, etc.)
                if (hasattr(msg, 'type') and msg.type == "human") or \
                   (hasattr(msg, '__class__') and msg.__class__.__name__ == "HumanMessage"):
                    user_query = msg.content
                    break

        # current_prompt = (
        #     f'User asked: "{user_query}"\n\n'
        #     "Please produce a clear, helpful response using the tool results. "
        #     # "If any tools failed, explain briefly and suggest next steps. "
        #     # "Do not propose new tool calls."
        # )
        current_prompt = f"User query: {user_query} please produce a response based on the tool results."

        try:
            result = await self.responder_agent.run(
                current_prompt,
                message_history=message_history if message_history else None,
            )
            state["response"] = result.output  # guaranteed str when output_type=str
            # append the response to the global message history
            state['global_message_history'].append({"role": "assistant", "content": state["response"]})
        except Exception as e:
            print(f"Responder error: {e}")
            state["response"] = f"I encountered an error while generating the response: {e}"


        state['plan'] = None # reset the plan
        return state
    
    def replanning(self, state: AgentState) -> str:
        """
        Replanning: Replans the state if the previous plan is not complete.
        """
        ctx = state.get('execution_context')
        denial_message = "Insufficient permissions to execute this function"
        summaries = ctx.tool_summaries
        if ctx is not None and ctx.is_complete() ==False and all([denial_message not in summary for summary in summaries]):
            print("Replanning...")
            return "planner"
        else:
            return "responder" # previous plan is complete, so we can respond

    
    def _create_graph(self):
        """
        Creates and returns the LangGraph workflow with all nodes connected.
        If miniscope flag is True, includes interceptor node in the pipeline.
        Otherwise, planner connects directly to argument_mapper.
        """
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("planner", self.planner)
        workflow.add_node("argument_mapper", self.argument_mapper)
        workflow.add_node("executor", self.executor)
        workflow.add_node("responder", self.responder)

        # Conditionally add interceptor node
        if self.miniscope:
            workflow.add_node("interceptor", self.interceptor)

        # Define edges (node connections)
        workflow.set_entry_point("planner")

        if self.miniscope:
            # With interceptor: planner -> interceptor -> argument_mapper
            workflow.add_edge("planner", "interceptor")
            workflow.add_edge("interceptor", "executor")
        else:
            # Without interceptor: planner -> argument_mapper directly
            workflow.add_edge("planner", "executor")

        # workflow.add_edge("argument_mapper", "executor")
        # workflow.add_edge("executor", "responder")
        workflow.add_conditional_edges("executor", self.replanning, {
            "responder": "responder",
            "planner": "planner",
        })
        workflow.add_edge("responder", END)

        # Compile the graph
        app = workflow.compile()

        return app

    async def invoke(self, state: dict) -> dict:
        """
        Invoke the agent with the given state (async).

        Args:
            state: Initial state dictionary.

        Returns:
            Final state after graph execution.
        """
        return await self.graph.ainvoke(state)


async def run_interactive_session(llm=None, miniscope=False, tools=None):
    """
    Runs an interactive command-line session with the agent.

    Args:
        llm: Optional language model instance to pass to the agent.
        miniscope: If True, include interceptor node in the graph.
        tools: Dictionary of available tools.
    """
    agent = ToolCallAgent(llm=llm, miniscope=miniscope, tools=tools)

    print("=" * 60)
    print("MiniScope Agent - Interactive Session")
    print("=" * 60)
    print("Type your prompts below. Type 'exit', 'quit', or press Ctrl+C to stop.")
    print("-" * 60)

    conversation_history = []

    # try:
    while True:
        # Get user input
        user_input = input("\nYou: ").strip()

        # Check for exit commands
        if user_input.lower() in ['exit', 'quit', 'q']:
            print("\nGoodbye!")
            break

        # Skip empty inputs
        if not user_input:
            permissions_handler.permission_manager.cleanup_session()
            break

        # Add user message to conversation history
        conversation_history.append({"role": "user", "content": user_input})

        # Prepare state for agent
        state = {
            "messages": conversation_history.copy(),
            "plan": "",
            "intercepted": False,
            "execution_result": {},
            "mapped_arguments": {},
            "response": "",
            "global_message_history": conversation_history.copy()
        }

        ##UNCOMMENT AFTER TESTING
        # # Invoke the agent (async)
        # print("\nAgent: Processing...", end="", flush=True)
        #     # try:
        # result = await agent.invoke(state)
        # print("\r" + " " * 30 + "\r", end="")  # Clear the "Processing..." message

        # # Display the response
        # response = result.get("response", "No response generated")
        # print(f"Agent: {response}")

        # # Add agent response to conversation history
        # conversation_history.append({"role": "assistant", "content": response})

        # Planner-only mode: run planner and show plan (do not execute)
        print("\nAgent: Planning...", end="", flush=True)
        try:
            planner_res = await asyncio.wait_for(agent.planner(state), timeout=30.0)
        except asyncio.TimeoutError:
            print("\nPlanner timed out after 30s")
            planner_res = {"plan": None, "response": "Planner timed out"}
        except Exception as e:
            print(f"Planner error: {e}")
            planner_res = {"plan": None, "response": f"Planner error: {e}"}

        print("\r" + " " * 30 + "\r", end="")  # Clear the "Planning..." message

        # Display plan output
        plan = planner_res.get("plan")
        if plan:
            print("\n=== Generated Plan ===")
            try:
                print(pretty_print_plan(plan))
            except Exception:
                print(plan)
        else:
            print("No plan generated. Planner response:", planner_res.get("response"))

        # Add planner response to conversation history so the user can see it
        # conversation_history.append({"role": "assistant", "content": planner_res.get("response", "")})

        # Optionally show debug info
        # if result.get("plan"):
        #     print(f"\n[Debug] Plan: {result['plan']}")
        # if result.get("intercepted"):
        #     print(f"[Debug] Intercepted: {result['intercepted']}")

    #         except Exception as e:
    #             print(f"\n\nError processing request: {e}")
    #             print("Please try again.")

    # except KeyboardInterrupt:
    #     print("\n\nSession interrupted. Goodbye!")
    # except EOFError:
    #     print("\n\nSession ended. Goodbye!")


async def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="MiniScope Agent")
    parser.add_argument("--miniscope", action="store_true", default=False,
                        help="Enable miniscope interceptor node (default: False)")
    args = parser.parse_args()
    
    # Load configuration
    config = Configurator()
    config.load_client_env()
    config.load_shared_env()
    config.check_llm_env_vars()
    config.get_mcp_servers()
    
    # global permissions_handler
    # permissions_handler = ApplicationPermissons(config)
    # permissions_handler.initialize_application_permissions_from_active_servers()

    # Initialize model
    provider = ModelProvider(config)
    print(provider.llm_provider + ":" + provider.model_name)
    llm_signature = provider.llm_provider + ":" + provider.model_name

    # Initialize tools from MCP servers
    tools = await initialize_tools(config)

    print(f"\nAvailable tools:")
    for tool_name, tool_def in tools.items():
        print(f"  - {tool_name}: {tool_def.description}")

    # Run interactive session with tools
    await run_interactive_session(llm=llm_signature, miniscope=args.miniscope, tools=tools)


if __name__ == "__main__":
    asyncio.run(main())