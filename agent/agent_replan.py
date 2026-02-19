"""
LangGraph Agent with planner, interceptor, executor, argument mapper, and responder nodes.
"""

import argparse
import asyncio
import re
import json
from collections import defaultdict
from pathlib import Path


from typing import TypedDict, Annotated, List, Dict, Any, Callable, Optional, Sequence, Tuple, Literal, Union
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from pydantic_ai import Agent, ModelSettings
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, UserPromptPart, TextPart, ToolCallPart, ToolReturnPart

# Common imports
from agent.common.configurator import Configurator
from agent.common.api_parser import (
    WebsiteAPI,
    load_api_registry,
    API_INDEX_FILE
)
from agent.common.requirement_models import (
    RequirementDetail,
    RequirementAnalysisResult,
    _ensure_str,
    _normalize_resolution
)
from agent.common.agent_state import AgentState
from agent.common.tool_manager import ToolDefinition, initialize_tools
from agent.common.token_manager import TokenStore, setup_authentication

# Agent imports
from agent.providers.provider import ModelProvider
from agent.prompts import planner_prompt, responder_prompt
from agent.planner import ExecutionContext
from agent.strict_planner import (
    gather_specs_from_tool_definitions,
    build_planning_models_from_mcp_specs,
    build_planning_agent,
    validate_plan, 
    pretty_print_plan
)

# Utility functions for JSON parsing
def _load_json_from_text(text: str) -> Optional[object]:
    """Attempt to parse the first JSON payload embedded in text."""
    cleaned = text.strip()
    if not cleaned:
        return None

    candidates = [cleaned]
    for opener, closer in (("{", "}"), ("[", "]")):
        start = cleaned.find(opener)
        end = cleaned.rfind(closer)
        if 0 <= start < end:
            snippet = cleaned[start : end + 1]
            candidates.append(snippet)

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences from model output."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        fence = lines[0]
        cleaned = "\n".join(lines[1:])
        if cleaned.endswith("```"):
            cleaned = "\n".join(cleaned.splitlines()[:-1])
    return cleaned.strip()


def _extract_text_from_review(text: str) -> str:
    """Extract text explanation from review output, removing JSON code blocks."""
    # Find the position of the first code fence (```json or ```)
    # This handles the case where JSON is in a code block
    code_fence_pattern = r'```(?:json)?\s*\n'
    match = re.search(code_fence_pattern, text, re.IGNORECASE)
    
    if match:
        # Extract everything before the code fence
        text = text[:match.start()].strip()
    
    # Also handle standalone JSON blocks (without code fences)
    # Look for lines that start with { and contain JSON structure indicators
    lines = text.splitlines()
    filtered_lines = []
    
    for line in lines:
        stripped = line.strip()
        # Stop at lines that look like the start of a JSON block
        # Check for common JSON structure indicators
        if stripped.startswith('{') and (
            'steps' in stripped.lower() or 
            'step_id' in stripped.lower() or 
            '"step_id"' in stripped or
            len(stripped) < 50  # Short line starting with { is likely JSON start
        ):
            break  # Stop processing at the first JSON block
        filtered_lines.append(line)
    
    result = '\n'.join(filtered_lines).strip()
    
    # Final cleanup: remove any remaining JSON artifacts
    # Remove patterns like single-line JSON objects
    result = re.sub(r'\s*\{[^}]*"[^"]*"\s*:\s*"[^"]*"[^}]*\}\s*', '', result)
    
    return result.strip()


class ToolCallAgent:
    """
    LangGraph-based agent with planner, interceptor, executor, argument mapper, and responder nodes.
    """

    def __init__(self, llm=None, miniscope=False, tools=None, api_index_path: Optional[Path] = None, token_store: Optional[TokenStore] = None):
        """
        Initialize the ToolCallAgent.

        Args:
            llm: Language model instance for making LLM calls in nodes.
            miniscope: If True, include interceptor node in the graph. If False, skip interceptor.
            tools: Dictionary of available tools (tool_name -> ToolDefinition).
            api_index_path: Path to API index.json file.
            token_store: Optional TokenStore instance for authentication tokens.
        """
        if not llm:
            raise ValueError("LLM instance is required for ToolCallAgent")

        self.llm = llm
        self.miniscope = miniscope
        self.tools = tools or {}
        self.api_index_path = api_index_path or API_INDEX_FILE
        self.token_store = token_store or TokenStore()  # Initialize if not provided
        
        # Load API registry
        try:
            self.api_registry = load_api_registry(self.api_index_path)
            self._registry_lookup = {api.name: api for api in self.api_registry}
            self._registry_lookup_lower = {api.name.lower(): api for api in self.api_registry}
            self._inventory_text = self._format_api_inventory()
        except Exception as e:
            print(f"Warning: Could not load API registry: {e}")
            self.api_registry = []
            self._registry_lookup = {}
            self._registry_lookup_lower = {}
            self._inventory_text = ""

        self.graph = self._create_graph()

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

        # Routing agent for website selection
        self.routing_system_prompt = (
            "You decide which website APIs are relevant to a user task. "
            "Select only the websites that provide information or capabilities required to complete the task. "
            "If none are relevant, choose an empty set."
        )

        # Post-planning requirement check (other missing arguments)
        self.requirement_check_prompt_template = (
            "Task:\n{task}\n\n"
            "Plan:\n{plan}\n\n"
            "API reference:\n{api_context}\n\n"
            "Using only the information above, list the inputs still missing for execution.\n"
            "Infer values whenever a reasonable assumption can be made (e.g., obvious defaults).\n"
            "Only request user input when the value cannot be inferred, selected automatically, or covered by a documented default.\n"
            "For each remaining gap, decide one of:\n"
            '1. "model_decision" – the agent can pick a reasonable value (describe how).\n'
            '2. "default" – the API has a documented default (describe it).\n'
            '3. "user_input" – the user must supply it (include a prompt).\n'
            "Respond with JSON:\n"
            '{{"requirements": ['
            '{{"name": "...", "description": "...", "resolution": "model_decision|default|user_input", '
            '"model_decision_instructions": "...", "default_instructions": "...", "prompt": "..."}}'
            '], "notes": "optional context"}}.\n'
            "Only include arguments that truly need attention."
        )

    def _extract_user_query(self, messages: List) -> str:
        """Extract the latest user message from messages."""
        for msg in reversed(messages):
            if isinstance(msg, dict):
                if msg.get("role") == "user":
                    return msg.get("content", "")
            elif hasattr(msg, 'content'):
                if (hasattr(msg, 'type') and msg.type == "human") or \
                   (hasattr(msg, '__class__') and msg.__class__.__name__ == "HumanMessage"):
                    return msg.content
        return ""

    ## ROUTER NODE##
    def _format_api_inventory(self) -> str:
        """Format website inventory for routing prompt consumption."""
        return "\n".join(f"- {site.name}: {site.description}" for site in self.api_registry)

    def _build_api_context(self, websites: Sequence[WebsiteAPI]) -> str:
        """Construct the API reference block for the selected websites."""
        blocks: List[str] = []
        for site in websites:
            spec_block = site.load_spec().as_prompt_block(prefix=site.name)
            header = [
                f"Website `{site.name}`",
                f"Description: {site.description}",
                f"Usage: import `api` and call `api.{site.name}.<endpoint or model>`.",
            ]
            blocks.append("\n".join(header + ["", spec_block]))
        return "\n\n".join(blocks)

    def _build_api_context_minimal(self, websites: Sequence[WebsiteAPI]) -> str:
        """
        Build minimal API context with just website names and descriptions.
        This saves 20k-40k tokens compared to full API documentation.
        """
        if not websites:
            return ""

        lines = []
        for site in websites:
            lines.append(f"- {site.name}: {site.description}")

        return "\n".join(lines)

    def _parse_routing_response(self, text: str) -> Optional[List[str]]:
        """Parse the routing model response and return a list of website identifiers."""
        data = _load_json_from_text(_strip_code_fences(text))
        if data is None:
            return None

        payload: Optional[Union[str, List[object]]] = None
        if isinstance(data, dict):
            payload = data.get("websites")
        elif isinstance(data, list):
            payload = data
        elif isinstance(data, str):
            payload = data

        if payload is None:
            return []

        if isinstance(payload, str):
            normalized = payload.strip()
            if not normalized or normalized.lower() in {"none", "null"}:
                return []
            return [normalized]

        if isinstance(payload, list):
            selections: List[str] = []
            for entry in payload:
                candidate: Optional[str] = None
                if isinstance(entry, str):
                    candidate = entry.strip()
                elif isinstance(entry, dict):
                    name_value = entry.get("name")
                    if isinstance(name_value, str):
                        candidate = name_value.strip()
                if candidate and candidate.lower() not in {"none", "null"}:
                    selections.append(candidate)
            return selections

        return None

    def _resolve_websites(self, identifiers: Sequence[str]) -> List[WebsiteAPI]:
        """Convert identifier strings into WebsiteAPI objects."""
        resolved: List[WebsiteAPI] = []
        for identifier in identifiers:
            key = identifier.strip()
            if not key:
                continue
            site = self._registry_lookup.get(key) or self._registry_lookup_lower.get(key.lower())
            if site and site not in resolved:
                resolved.append(site)
        return resolved

    async def _call_routing_llm(self, prompt: str) -> str:
        """Call LLM for routing decision."""
        # Create a simple routing agent
        routing_agent = Agent(
            self.llm if isinstance(self.llm, str) else str(self.llm),
            output_type=str,
            system_prompt=self.routing_system_prompt
        )
        
        routing_prompt_template = (
            "Task:\n{task}\n\n"
            "Available website APIs:\n{api_inventory}\n\n"
            "Respond with a JSON object of the form "
            '{{"websites": ["name1", "name2"], "reason": "short justification"}} using the website identifiers. '
            "Return an empty `websites` list if the task cannot be served by the available APIs."
        )
        
        # Extract task from prompt (simplified - you may want to improve this)
        task_match = re.search(r"Task:\n(.*?)\n\n", prompt, re.DOTALL)
        task = task_match.group(1) if task_match else ""
        
        full_prompt = routing_prompt_template.format(
            task=task,
            api_inventory=self._inventory_text
        )
        
        result = await routing_agent.run(full_prompt)
        return result.output

    async def router(self, state: AgentState) -> AgentState:
        """
        Router node: Determines which website APIs are relevant to the task.
        """
        messages = state.get("messages", [])
        user_query = self._extract_user_query(messages)

        if not user_query:
            state["routed_websites"] = []
            state["api_context"] = ""
            return state

        if not self.api_registry:
            # No API registry available, use all tools
            state["routed_websites"] = []
            state["api_context"] = ""
            return state

        try:
            # Use LLM to route
            routing_prompt = f"Task:\n{user_query}\n\nAvailable website APIs:\n{self._inventory_text}\n\n"
            response = await self._call_routing_llm(routing_prompt)
            selection = self._parse_routing_response(response)

            if selection is None:
                # Default to all websites if parsing fails
                selected_websites = list(self.api_registry)
            else:
                resolved = self._resolve_websites(selection)
                if not resolved and selection:
                    # Fallback to all if resolution fails
                    selected_websites = list(self.api_registry)
                else:
                    selected_websites = resolved

            state["routed_websites"] = selected_websites
            state["api_context"] = self._build_api_context(selected_websites) if selected_websites else ""

            print(f"🔀 Routed to websites: {[site.name for site in selected_websites]}")

        except Exception as e:
            print(f"Routing error: {e}")
            # Fallback to all websites
            state["routed_websites"] = list(self.api_registry)
            state["api_context"] = self._build_api_context(self.api_registry) if self.api_registry else ""

        return state

    ## REQUIREMENT ANALYZER NODE##
    async def _analyze_requirements(
        self,
        task: str,
        plan: str,
        api_context: str,
    ) -> RequirementAnalysisResult:
        """Identify missing arguments and how to resolve them."""
        # Create a requirement analysis agent
        requirement_agent = Agent(
            self.llm if isinstance(self.llm, str) else str(self.llm),
            output_type=str,
            system_prompt="You are an expert at analyzing task requirements and identifying missing information."
        )

        prompt = self.requirement_check_prompt_template.format(
            task=task,
            plan=plan,
            api_context=api_context,
        )

        try:
            result = await requirement_agent.run(prompt)
            response = result.output
        except Exception as e:
            print(f"Requirement analysis LLM error: {e}")
            return RequirementAnalysisResult()

        data = _load_json_from_text(_strip_code_fences(response))
        if not isinstance(data, dict):
            return RequirementAnalysisResult()

        raw_requirements = data.get("requirements")
        parsed: List[RequirementDetail] = []
        if isinstance(raw_requirements, list):
            for entry in raw_requirements:
                if isinstance(entry, dict):
                    parsed.append(
                        RequirementDetail(
                            name=str(entry.get("name", "") or "").strip() or "unspecified_field",
                            description=_ensure_str(entry.get("description")),
                            resolution=_normalize_resolution(entry.get("resolution")),
                            model_decision_instructions=_ensure_str(entry.get("model_decision_instructions")),
                            default_instructions=_ensure_str(entry.get("default_instructions")),
                            prompt=_ensure_str(entry.get("prompt")),
                        )
                    )
        notes = _ensure_str(data.get("notes"))
        return RequirementAnalysisResult(requirements=parsed, notes=notes)

    def _partition_requirements(
        self, requirements: Sequence[RequirementDetail]
    ) -> Tuple[List[RequirementDetail], List[RequirementDetail], List[RequirementDetail]]:
        """Split requirements by resolution type."""
        model_decisions: List[RequirementDetail] = []
        defaults: List[RequirementDetail] = []
        needs_input: List[RequirementDetail] = []
        for requirement in requirements:
            resolution = requirement.resolution
            if resolution == "model_decision":
                model_decisions.append(requirement)
            elif resolution == "default":
                defaults.append(requirement)
            else:
                needs_input.append(requirement)
        return model_decisions, defaults, needs_input

    async def _collect_user_inputs(
        self, requirements: Sequence[RequirementDetail]
    ) -> Dict[str, str]:
        """Prompt the user for missing argument values."""
        values: Dict[str, str] = {}
        for requirement in requirements:
            prompt_text = requirement.prompt or requirement.description or requirement.name
            message = f"Provide a value for '{requirement.name}' ({prompt_text}): "
            while True:
                try:
                    value = input(message).strip()
                except EOFError:
                    print(f"Warning: Missing value for {requirement.name}, skipping...")
                    break
                if value:
                    values[requirement.name] = value
                    break
                print("Value cannot be empty. Please enter a valid value.")
        return values

    def _format_requirement_context(
        self,
        model_decisions: Sequence[RequirementDetail],
        defaults: Sequence[RequirementDetail],
        user_inputs: Dict[str, str],
        notes: Optional[str],
    ) -> str:
        """Render notes about defaults and user-provided values for prompting."""
        sections: List[str] = []
        if model_decisions:
            lines = ["Model-decided values:"]
            for requirement in model_decisions:
                instruction = requirement.model_decision_instructions or "Choose any reasonable value."
                lines.append(f"- {requirement.name}: {instruction}")
            sections.append("\n".join(lines))
        if defaults:
            lines = ["Defaults to use:"]
            for requirement in defaults:
                details = requirement.default_instructions or "Use platform default."
                lines.append(f"- {requirement.name}: {details}")
            sections.append("\n".join(lines))
        if user_inputs:
            lines = ["User-provided values:"]
            for name, value in user_inputs.items():
                lines.append(f"- {name}: {value}")
            sections.append("\n".join(lines))
        if notes:
            sections.append(f"Additional notes: {notes}")
        return "\n\n".join(sections) if sections else "No additional requirement notes."


    async def requirement_analyzer(self, state: AgentState) -> AgentState:
        """
        Requirement Analyzer: Checks if task description is enough to execute.
        Identifies missing arguments (address, payment, etc).
        Auto-fills tokens from TokenStore when available.
        """
        plan = state.get("plan")
        if not plan:
            return state

        messages = state.get("messages", [])
        task = self._extract_user_query(messages)
        api_context = state.get("api_context", "")

        if not task:
            return state

        try:
            # Convert plan to string representation
            plan_str = pretty_print_plan(plan) if plan else ""

            # Analyze requirements
            analysis = await self._analyze_requirements(task, plan_str, api_context)

            # Partition requirements
            model_decisions, defaults, user_inputs_needed = self._partition_requirements(
                analysis.requirements
            )

            # Check for tokens in TokenStore and move them from user_inputs_needed to model_decisions
            auto_filled_tokens: Dict[str, str] = {}
            remaining_user_inputs_needed: List[RequirementDetail] = []

            for requirement in user_inputs_needed:
                # Check if this is a token requirement
                if requirement.name.lower() == "token" and plan:
                    # Try to get token from plan (find which server the tools are from)
                    server_name = None
                    for step in plan:
                        if hasattr(step, 'tool'):
                            tool_name = step.tool
                            # Extract server name from tool (e.g., "gitlab-list_issues" -> "gitlab")
                            if "-" in tool_name:
                                server_name = tool_name.split("-")[0]
                                break

                    if server_name:
                        # Try to get token for this server
                        token = self.token_store.get_token_for_tool(server_name, "")
                        if not token:
                            # Fallback: try to get any token type
                            token = (self.token_store.get_token(server_name, "token") or
                                   self.token_store.get_token(server_name, "customer") or
                                   self.token_store.get_token(server_name, "admin"))

                        if token:
                            # We have a token - use it as a model decision instead of asking user
                            auto_filled_tokens[requirement.name] = token
                            model_decisions.append(requirement)
                            continue

                # Not a token or no token found - ask user for it
                remaining_user_inputs_needed.append(requirement)

            # Collect user inputs if needed (excluding auto-filled tokens)
            user_inputs: Dict[str, str] = {}
            if remaining_user_inputs_needed:
                print("\n📋 Missing information required to complete the task:")
                for req in remaining_user_inputs_needed:
                    print(f"  - {req.name}: {req.description or req.prompt or 'No description'}")
                user_inputs = await self._collect_user_inputs(remaining_user_inputs_needed)

            # Combine auto-filled tokens with user inputs
            all_user_inputs = {**auto_filled_tokens, **user_inputs}

            if auto_filled_tokens:
                print("\n✅ Auto-filled tokens from configuration:")
                for name in auto_filled_tokens.keys():
                    print(f"  - {name}: [loaded from config]")

            # Format requirements context
            requirements_context = self._format_requirement_context(
                model_decisions, defaults, all_user_inputs, analysis.notes
            )

            state["requirements_context"] = requirements_context
            state["model_decisions"] = [r.name for r in model_decisions]
            state["defaults_used"] = [r.name for r in defaults]
            state["user_inputs"] = all_user_inputs

            if model_decisions or defaults or all_user_inputs:
                print(f"\n✅ Requirement analysis complete:")
                print(state["requirements_context"])

        except Exception as e:
            print(f"Requirement analysis error: {e}")
            state["requirements_context"] = "No additional requirement notes."
            state["model_decisions"] = []
            state["defaults_used"] = []
            state["user_inputs"] = {}

        return state

    ## REPLANNING NODE##
    async def replanning(self, state: AgentState) -> AgentState:
        """
        Replanning: Reviews the plan after requirement analysis and updates it if needed.
        Checks if the plan is good - if yes, proceeds to executor. If not, replans and then proceeds to executor.
        """
        plan = state.get("plan")
        if not plan:
            return state

        messages = state.get("messages", [])
        task = self._extract_user_query(messages)
        requirements_context = state.get("requirements_context", "")
        user_inputs = state.get("user_inputs", {})

        if not task:
            return state

        # Early exit if no requirements to address (saves 10k-20k tokens)
        if not user_inputs and (not requirements_context or requirements_context == "No additional requirement notes."):
            print("\n✅ No requirements to address, skipping replanning")
            return state

        try:
            # Convert plan to string representation
            plan_str = pretty_print_plan(plan) if plan else ""

            # Create a plan review agent
            review_agent = Agent(
                self.llm if isinstance(self.llm, str) else str(self.llm),
                output_type=str,
                system_prompt=(
                    "You are an expert at reviewing and refining execution plans. "
                    "Review the plan and determine if it needs updates based on the requirements analysis. "
                    "If the plan is good as-is, respond with 'NO_CHANGES_NEEDED'. "
                    "If changes are needed, provide a JSON response with the updated plan structure."
                )
            )

            # Omit API context from review to save tokens (5k-10k savings)
            review_prompt = (
                f"Task: {task}\n\n"
                f"Current Plan:\n{plan_str}\n\n"
                f"Requirements Context:\n{requirements_context}\n\n"
                f"User Inputs Provided: {user_inputs}\n\n"
                "Review this plan and determine if any changes are needed based on the requirements analysis. "
                "Consider:\n"
                "1. Are all required inputs accounted for in the plan?\n"
                "2. Do the tool calls match the requirements context?\n"
                "3. Are there any logical issues or missing steps?\n"
                "4. Should the plan be updated with the user inputs or model decisions?\n\n"
                "If no changes are needed, respond with: 'NO_CHANGES_NEEDED'\n"
                "If changes are needed, provide guidance on what should be updated."
            )

            result = await review_agent.run(review_prompt)
            review_output = result.output.strip()

            if "NO_CHANGES_NEEDED" in review_output.upper():
                print("\n✅ Replanning: Plan is good, no changes needed, proceeding to execution")
                return state

            # Extract text explanation without JSON code blocks
            review_text = _extract_text_from_review(review_output)
            
            # If changes are suggested, re-plan with updated context
            print(f"\n⚠️ Replanning: Plan needs changes:\n{review_text}")
            print("🔄 Re-planning with updated requirements context...")
            
            # Re-run planner with enhanced context including requirements and review feedback
            # Use minimal API context to save tokens
            enhanced_query = f"{task}\n\n"
            if requirements_context and requirements_context != "No additional requirement notes.":
                enhanced_query += f"Requirements Context:\n{requirements_context}\n\n"
            if user_inputs:
                enhanced_query += f"User Provided Values:\n"
                for key, value in user_inputs.items():
                    enhanced_query += f"  - {key}: {value}\n"
                enhanced_query += "\n"
            if review_output:
                enhanced_query += f"Plan Review Feedback:\n{review_output}\n\n"

            # Use minimal API context to save tokens (20k-40k savings)
            routed_websites = state.get("routed_websites", [])
            if routed_websites:
                minimal_api_context = self._build_api_context_minimal(routed_websites)
                enhanced_query += f"Available APIs:\n{minimal_api_context}"

            # Don't pass message_history to save tokens (20-40k savings)
            result = await self.planning_agent.run(
                enhanced_query,
                message_history=None,
                model_settings=ModelSettings(temperature=0.0)
            )
            plan_model = result.output
            
            # Validate the updated plan
            if validate_plan(plan_model):
                state["plan"] = plan_model.steps
                print("✅ Plan updated based on review")
                print(pretty_print_plan(state["plan"]))
            else:
                print("⚠️ Updated plan validation failed, using original plan")

        except Exception as e:
            print(f"Plan review error: {e}")
            # Continue with original plan if review fails

        return state


    ## PLANNER NODE##
    async def planner(self, state: AgentState) -> AgentState:
        """
        Planner node: Creates a plan based on the input.
        Takes the user prompt and uses pydantic_ai to invoke the LLM to generate a tool call plan.
        """
        messages = state.get("messages", [])
        if not messages:
            state["plan"] = None
            state["response"] = "No user input provided"
            return state

        user_query = self._extract_user_query(messages)
        if not user_query:
            state["plan"] = None
            state["response"] = "No user query found"
            return state

        # Enhance query with API context if available
        # Use minimal API context to save tokens (20k-40k token savings)
        routed_websites = state.get("routed_websites", [])
        if routed_websites:
            minimal_api_context = self._build_api_context_minimal(routed_websites)
            enhanced_query = f"{user_query}\n\nAvailable APIs:\n{minimal_api_context}"
        else:
            enhanced_query = user_query

        try:
            # Don't pass message_history to planner to save 20-40k tokens
            # Planner only needs current query, not prior conversation context
            result = await self.planning_agent.run(
                enhanced_query,
                message_history=None,
                model_settings=ModelSettings(temperature=0.0)
            )
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

    ## EXECUTOR NODE##
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
        # CRITICAL: Only create new context if it doesn't exist, otherwise reuse to preserve progress
        if "execution_context" not in state or state["execution_context"] is None:
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

            # exact tool name and typed args
            tool_name = step.tool                       # Literal[...] string
            args = step.args.model_dump(exclude_none=True, exclude_unset=True)

            try:
                # Execute
                if tool_name not in self.tools:
                    raise ValueError(f"Tool '{tool_name}' not found in available tools")
                
                tool_def = self.tools[tool_name]
                result = await tool_def.execute(**args)

                # Mark as completed in context
                ctx.mark_completed(step_id, result)
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

    ## RESPONDER NODE##
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
                    # Convert output to proper format: ensure it's a dict or string, not raw int/other types
                    if output is None:
                        output_dict = None
                    elif isinstance(output, dict):
                        output_dict = output
                    elif isinstance(output, str):
                        # Try to parse as JSON, otherwise use as string
                        try:
                            output_dict = json.loads(output)
                        except (json.JSONDecodeError, TypeError):
                            output_dict = {"result": output}
                    else:
                        # Convert non-dict types (int, list, etc.) to dict
                        output_dict = {"result": str(output)}
                    
                    # Truncate large outputs to prevent token limit issues (keep first 2000 chars)
                    if output_dict and isinstance(output_dict, dict):
                        for key, value in output_dict.items():
                            if isinstance(value, str) and len(value) > 2000:
                                output_dict[key] = value[:2000] + "... [truncated]"
                            elif isinstance(value, (list, dict)) and len(str(value)) > 2000:
                                output_dict[key] = str(value)[:2000] + "... [truncated]"
                    
                    message_history.append(
                        ModelRequest(parts=[
                            ToolReturnPart(tool_name=tool_name, content=output_dict, tool_call_id=step_id)
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

    
    def _create_graph(self):
        """
        Creates and returns the LangGraph workflow with all nodes connected.
        Enhanced with routing and requirement analysis nodes.
        """
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("router", self.router)  # Routing node
        workflow.add_node("planner", self.planner)  # Creates draft plan with tool selection
        workflow.add_node("requirement_analyzer", self.requirement_analyzer)  # Checks other requirements
        # workflow.add_node("argument_mapper", self.argument_mapper)
        workflow.add_node("replanning", self.replanning)  # Reviews plan and replans if needed
        workflow.add_node("executor", self.executor)
        workflow.add_node("responder", self.responder)


        # Define edges
        workflow.set_entry_point("router")  # Start with routing
        workflow.add_edge("router", "planner")  # Route -> Plan
        workflow.add_edge("planner", "requirement_analyzer")  # Plan -> Check Requirements
        workflow.add_edge("requirement_analyzer", "replanning")  # Requirements -> Replanning (conditional)
        workflow.add_edge("replanning", "executor")  # Replanning -> Execute
        
        # Executor can loop back to itself if there are more steps to execute
        # Or go to responder when all steps are complete
        def should_continue_execution(state: AgentState) -> str:
            """Determine if executor should continue or move to responder."""
            ctx = state.get("execution_context")
            if ctx is None:
                return "responder"
            
            # If execution is complete, go to responder
            if ctx.is_complete():
                print(f"\n✅ All steps completed! {ctx.get_progress()}")
                return "responder"
            
            # Check if there are ready steps to execute (dependencies met)
            ready_steps = ctx.get_ready_steps()
            if ready_steps:
                return "executor"  # More steps ready, continue executing
            
            # No ready steps but not complete - could be waiting for dependencies or stuck
            # For now, if no ready steps and not complete, assume we're done (some steps may have failed)
            return "responder"

        workflow.add_conditional_edges(
            "executor",
            should_continue_execution,
            {
                "executor": "executor",  # Loop back to execute more steps
                "responder": "responder",  # All done, generate response
            }
        )
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


async def run_interactive_session(llm=None, miniscope=False, tools=None, planner_only=False, token_store=None):
    """
    Runs an interactive command-line session with the agent.

    Args:
        llm: Optional language model instance to pass to the agent.
        miniscope: If True, include interceptor node in the graph.
        tools: Dictionary of available tools.
        planner_only: If True, only run planning nodes (router, planner, requirement_analyzer, replanning)
                     without executing the plan. If False, run full graph including executor.
        token_store: Optional TokenStore instance for authentication tokens.
    """
    agent = ToolCallAgent(llm=llm, miniscope=miniscope, tools=tools, token_store=token_store)

    print("=" * 60)
    print("Enhanced Agent - Interactive Session")
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
            break

        # Add user message to conversation history
        conversation_history.append({"role": "user", "content": user_input})

        # Prepare state for agent
        state = {
            "messages": conversation_history.copy(),
            "plan": None,
            "intercepted": False,
            "execution_result": {},
            "mapped_arguments": {},
            "response": "",
            "global_message_history": conversation_history.copy(),
            "routed_websites": None,
            "api_context": None,
            "requirements_context": None,
            "model_decisions": None,
            "defaults_used": None,
            "user_inputs": None,
            "auth_requirements": None,
        }

        if planner_only:
        # Planner-only mode: run planner and show plan (do not execute)
            print("\nAgent: Planning...", end="", flush=True)
            try:
                # Run router
                state = await agent.router(state)
                
                # Run planner
                state = await agent.planner(state)
                
                # Run requirement analyzer
                state = await agent.requirement_analyzer(state)
                
                # Run replanning
                state = await agent.replanning(state)
            
                print("\r" + " " * 60 + "\r", end="")  # Clear the "Processing..." message
            
                # Display results
                plan = state.get("plan")
                if plan:
                    print("\n=== Generated Plan ===")
                    try:
                        print(pretty_print_plan(plan))
                    except Exception:
                        print(plan)
                    
                    
                    print("\n✅ Plan and requirements ready. Execution stopped before running tools.")
                else:
                    print("No plan generated.")
                
            except asyncio.TimeoutError:
                print("\nProcessing timed out")
            except Exception as e:
                print(f"\nError: {e}")
                import traceback
                traceback.print_exc()
        else:
            # Executor mode: run full graph including executor
            print("\nAgent: Processing...", end="", flush=True)
            try:
                result = await agent.invoke(state) #invoke runs full graph including executor
                print("\r" + " " * 30 + "\r", end="")  # Clear the "Processing..." message

                # Display the response
                response = result.get("response", "No response generated")
                print(f"Agent: {response}")

                # Add agent response to conversation history
                conversation_history.append({"role": "assistant", "content": response})
                
            except asyncio.TimeoutError:
                print("\nProcessing timed out")
            except Exception as e:
                print(f"\nError: {e}")
                import traceback
                traceback.print_exc()


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
    parser = argparse.ArgumentParser(description="Enhanced Agent with Routing and Requirement Analysis")
    parser.add_argument("--miniscope", action="store_true", default=False,
                        help="Enable miniscope interceptor node (default: False)")
    parser.add_argument("--planner-only", action="store_true", default=False,
                        help="Run in planner-only mode (no execution). If False, runs full graph including executor (default: False)")
    args = parser.parse_args()
    
    # Load configuration
    config = Configurator()
    config.load_all_env()  # Load all env files (client, shared, server)
    config.check_llm_env_vars()
    config.get_mcp_servers()
    

    # Initialize model
    provider = ModelProvider(config)
    llm_signature = provider.get_llm_model_provider()
    print(f"Using model: {llm_signature}")

    # Initialize tools from MCP servers
    tools, token_store = await initialize_tools(config)

    print(f"\nAvailable tools:")
    for tool_name, tool_def in tools.items():
        print(f"  - {tool_name}: {tool_def.description}")

    # Optionally: Authenticate and save tokens to .env file
    # Uncomment the line below to authenticate and save tokens:
    # await setup_authentication(tools, token_store, config)

    # Run interactive session with tools
    await run_interactive_session(llm=llm_signature, miniscope=args.miniscope, tools=tools, planner_only=args.planner_only, token_store=token_store)


if __name__ == "__main__":
    asyncio.run(main())