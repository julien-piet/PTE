"""
LangGraph Agent with planner, interceptor, executor, argument mapper, and responder nodes.
"""

import argparse
import asyncio
import re
import time
import ast
import json
import textwrap
from collections import defaultdict
from pathlib import Path
from dataclasses import dataclass, field




from typing import TypedDict, Annotated, List, Dict, Any, Callable, Optional, Sequence, Tuple, Literal, Union
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

# Import ChatMessage from shared types
from agent.common.types import ChatMessage

# API routing and parsing utilities
REPO_ROOT = Path(__file__).resolve().parent.parent
API_DIR = REPO_ROOT / "api"
API_INDEX_FILE = API_DIR / "index.json"
DEFAULT_API_MODULE = "api"

permissions_handler = None

# ============================================================================
# API Parsing and Routing Models (from agent.py)
# ============================================================================

class ParameterDescription(BaseModel):
    """Metadata describing a single endpoint parameter."""
    name: str
    kind: str = Field(description="Parameter kind")
    annotation: Optional[str] = None
    default: Optional[str] = None


class EndpointDescription(BaseModel):
    """Metadata describing an API endpoint."""
    name: str
    section: Optional[str] = None
    summary: str = ""
    docstring: str = ""
    parameters: List[ParameterDescription] = Field(default_factory=list)
    return_annotation: Optional[str] = None


class TypeDescription(BaseModel):
    """Metadata describing a Pydantic BaseModel subclass."""
    name: str
    bases: List[str] = Field(default_factory=list)
    docstring: str = ""
    fields: List[Dict[str, Any]] = Field(default_factory=list)


class APISpecification(BaseModel):
    """Structured description of the API surface for prompting."""
    path: Path
    endpoints: List[EndpointDescription] = Field(default_factory=list)
    types: List[TypeDescription] = Field(default_factory=list)

    @classmethod
    def from_file(cls, api_file: Path) -> "APISpecification":
        endpoints, types = _parse_api_file(api_file)
        return cls(path=api_file, endpoints=endpoints, types=types)

    def as_prompt_block(self, prefix: Optional[str] = None) -> str:
        """Render the specification as a markdown-friendly prompt block."""
        display_prefix = f"{prefix}." if prefix else ""
        lines: List[str] = ["Endpoints:"]
        for endpoint in self.endpoints:
            header = f"- {display_prefix}{endpoint.name}("
            params = []
            for param in endpoint.parameters:
                param_repr = param.name
                if param.annotation:
                    param_repr += f": {param.annotation}"
                if param.default is not None:
                    param_repr += f" = {param.default}"
                params.append(param_repr)
            header += ", ".join(params) + ")"
            header += f" -> {endpoint.return_annotation or 'None'}"
            if endpoint.section:
                header += f"  [{endpoint.section}]"
            lines.append(header)
            if endpoint.summary:
                lines.append(f"  Summary: {endpoint.summary}")
            for param in endpoint.parameters:
                details = f"    - {param.kind}: {param.name}"
                if param.annotation:
                    details += f" ({param.annotation})"
                if param.default is not None:
                    details += f", default={param.default}"
                lines.append(details)
        if self.types:
            lines.append("")
            lines.append("Type Definitions:")
            for type_desc in self.types:
                bases = f"({', '.join(type_desc.bases)})" if type_desc.bases else ""
                lines.append(f"- class {display_prefix}{type_desc.name}{bases}")
                if type_desc.docstring:
                    lines.append("  Docstring:")
                    for doc_line in type_desc.docstring.strip().splitlines():
                        lines.append(f"    {doc_line}")
                if type_desc.fields:
                    lines.append("  Fields:")
                    for field in type_desc.fields:
                        field_line = f"    - {field.get('name', '')}"
                        if field.get('annotation'):
                            field_line += f": {field.get('annotation')}"
                        if field.get('default'):
                            field_line += f" = {field.get('default')}"
                        lines.append(field_line)
        return "\n".join(lines)


@dataclass
class WebsiteAPI:
    """Metadata and helpers for a website-specific API module."""
    name: str
    file_name: str
    description: str
    base_dir: Path = field(repr=False)
    _spec: Optional[APISpecification] = field(default=None, init=False, repr=False)

    @property
    def path(self) -> Path:
        return self.base_dir / self.file_name

    def load_spec(self) -> APISpecification:
        if self._spec is None:
            self._spec = APISpecification.from_file(self.path)
        return self._spec


class RequirementDetail(BaseModel):
    """Missing requirement discovered during spec analysis."""
    name: str
    description: Optional[str] = None
    resolution: Literal["model_decision", "default", "user_input"] = "user_input"
    model_decision_instructions: Optional[str] = None
    default_instructions: Optional[str] = None
    prompt: Optional[str] = None


class RequirementAnalysisResult(BaseModel):
    """Outcome of the requirement analysis."""
    requirements: List[RequirementDetail] = Field(default_factory=list)
    notes: Optional[str] = None


# ============================================================================
# API Parsing Functions (from agent.py)
# ============================================================================

def _load_api_index(index_path: Path = API_INDEX_FILE) -> Dict[str, str]:
    """Load the API index mapping filenames to descriptions."""
    if not index_path.exists():
        raise FileNotFoundError(f"API index missing at {index_path}")
    data = json.loads(index_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("API index must be a JSON object mapping file names to descriptions.")
    return data


def load_api_registry(index_path: Path = API_INDEX_FILE) -> List[WebsiteAPI]:
    """Load all website APIs described in the JSON index."""
    entries = _load_api_index(index_path)
    registry: List[WebsiteAPI] = []
    for file_name, description in entries.items():
        path = index_path.parent / file_name
        if not path.exists():
            raise FileNotFoundError(f"API file {file_name} referenced in index but missing at {path}")
        registry.append(
            WebsiteAPI(
                name=Path(file_name).stem,
                file_name=file_name,
                description=description,
                base_dir=index_path.parent,
            )
        )
    return registry


def _unparse(node: Optional[ast.AST]) -> Optional[str]:
    """Convert an AST node to source if possible."""
    if node is None:
        return None
    if hasattr(ast, "unparse"):
        try:
            return ast.unparse(node)
        except Exception:
            pass
    return ast.dump(node)


def _is_tool_decorated(node: Union[ast.AsyncFunctionDef, ast.FunctionDef]) -> bool:
    """Check if a function node uses the @mcp.tool decorator."""
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Call):
            func = decorator.func
            if isinstance(func, ast.Attribute) and func.attr == "tool":
                return True
    return False


def _is_public_api_function(node: Union[ast.AsyncFunctionDef, ast.FunctionDef]) -> bool:
    """Treat top-level async functions without a leading underscore as API endpoints."""
    return isinstance(node, ast.AsyncFunctionDef) and not node.name.startswith("_")


def _infer_section(lines: List[str], lineno: int) -> Optional[str]:
    """Infer the section heading from preceding comment blocks."""
    for index in range(lineno - 2, -1, -1):
        text = lines[index].strip()
        if text.startswith("# ========================================================================="):
            continue
        if text.startswith("# ==="):
            return text.lstrip("# ").strip()
    return None


def _is_pydantic_model(node: ast.ClassDef) -> bool:
    """Determine whether a class definition derives from pydantic BaseModel."""
    for base in node.bases:
        base_text = _unparse(base)
        if "BaseModel" in base_text:
            return True
    return False


def _build_type_description(node: ast.ClassDef) -> TypeDescription:
    """Create a TypeDescription from a class definition."""
    docstring = textwrap.dedent(ast.get_docstring(node) or "")
    fields: List[Dict[str, Any]] = []

    for statement in node.body:
        if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            name = statement.target.id
            annotation = _unparse(statement.annotation)
            default_text: Optional[str] = None
            description_text: Optional[str] = None

            value = statement.value
            if isinstance(value, ast.Call) and _is_field_call(value):
                if value.args:
                    default_text = _unparse(value.args[0])
                description_text = _extract_field_description(value)
            elif value is not None:
                default_text = _unparse(value)

            fields.append({
                "name": name,
                "annotation": annotation,
                "default": default_text,
                "description": description_text,
            })

    bases = [_unparse(base) for base in node.bases]
    return TypeDescription(name=node.name, bases=bases, docstring=docstring, fields=fields)


def _is_field_call(call: ast.Call) -> bool:
    """Check whether the call is to pydantic Field."""
    func = call.func
    if isinstance(func, ast.Name):
        return func.id == "Field"
    if isinstance(func, ast.Attribute):
        return func.attr == "Field"
    return False


def _extract_field_description(call: ast.Call) -> Optional[str]:
    """Attempt to extract the description argument from a Field call."""
    for keyword in call.keywords:
        if keyword.arg == "description":
            literal = _literal_eval(keyword.value)
            if isinstance(literal, str):
                return literal
            return _unparse(keyword.value)
    return None


def _literal_eval(node: ast.AST) -> Optional[object]:
    """Safely evaluate an AST literal node."""
    try:
        return ast.literal_eval(node)
    except Exception:
        return None


def _build_endpoint_description(
    node: Union[ast.FunctionDef, ast.AsyncFunctionDef],
    lines: List[str],
) -> EndpointDescription:
    """Create an EndpointDescription from a function definition."""
    docstring = ast.get_docstring(node) or ""
    summary = docstring.strip().splitlines()[0] if docstring else ""
    parameters: List[ParameterDescription] = []

    positional_nodes = list(getattr(node.args, "posonlyargs", [])) + list(node.args.args)
    defaults = list(node.args.defaults)
    default_offset = len(positional_nodes) - len(defaults)

    for index, arg in enumerate(positional_nodes):
        default_node = defaults[index - default_offset] if index >= default_offset else None
        kind = "positional-only" if index < len(getattr(node.args, "posonlyargs", [])) else "positional-or-keyword"
        parameters.append(
            ParameterDescription(
                name=arg.arg,
                kind=kind,
                annotation=_unparse(arg.annotation),
                default=_unparse(default_node),
            )
        )

    if node.args.vararg:
        parameters.append(
            ParameterDescription(
                name=node.args.vararg.arg,
                kind="var-positional",
                annotation=_unparse(node.args.vararg.annotation),
            )
        )

    for kw_arg, default_node in zip(node.args.kwonlyargs, node.args.kw_defaults):
        parameters.append(
            ParameterDescription(
                name=kw_arg.arg,
                kind="keyword-only",
                annotation=_unparse(kw_arg.annotation),
                default=_unparse(default_node),
            )
        )

    if node.args.kwarg:
        parameters.append(
            ParameterDescription(
                name=node.args.kwarg.arg,
                kind="var-keyword",
                annotation=_unparse(node.args.kwarg.annotation),
            )
        )

    return EndpointDescription(
        name=node.name,
        section=_infer_section(lines, node.lineno),
        summary=summary,
        docstring=textwrap.dedent(docstring),
        parameters=parameters,
        return_annotation=_unparse(node.returns),
    )


def _parse_api_file(api_file: Path) -> Tuple[List[EndpointDescription], List[TypeDescription]]:
    """Parse an API module file and return structured descriptions."""
    source = api_file.read_text(encoding="utf-8")
    module_ast = ast.parse(source)
    lines = source.splitlines()
    endpoints: List[EndpointDescription] = []
    types: List[TypeDescription] = []

    for node in module_ast.body:
        if isinstance(node, ast.ClassDef) and _is_pydantic_model(node):
            types.append(_build_type_description(node))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
            _is_tool_decorated(node) or _is_public_api_function(node)
        ):
            endpoints.append(_build_endpoint_description(node, lines))

    endpoints.sort(key=lambda endpoint: (endpoint.section or "", endpoint.name))
    types.sort(key=lambda type_desc: type_desc.name)
    return endpoints, types


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


def _ensure_str(value: Optional[object]) -> Optional[str]:
    """Return the input as a stripped string if possible."""
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return None


def _normalize_resolution(value: Optional[object]) -> Literal["model_decision", "default", "user_input"]:
    """Normalize resolution labels coming from the requirement checker."""
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"model", "model_decision", "model-choice", "model_choice"}:
            return "model_decision"
        if lowered in {"default", "platform_default"}:
            return "default"
    return "user_input"


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
    # New fields for routing and requirements
    routed_websites: Optional[List[WebsiteAPI]]
    api_context: Optional[str]
    requirements_context: Optional[str]
    model_decisions: Optional[List[str]]
    defaults_used: Optional[List[str]]
    user_inputs: Optional[Dict[str, str]]
    auth_requirements: Optional[Dict[str, Any]]


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

    def __init__(self, llm=None, miniscope=False, tools=None, api_index_path: Optional[Path] = None):
        """
        Initialize the ToolCallAgent.

        Args:
            llm: Language model instance for making LLM calls in nodes.
            miniscope: If True, include interceptor node in the graph. If False, skip interceptor.
            tools: Dictionary of available tools (tool_name -> ToolDefinition).
            api_index_path: Path to API index.json file.
        """
        if not llm:
            raise ValueError("LLM instance is required for ToolCallAgent")

        self.llm = llm
        self.miniscope = miniscope
        self.tools = tools or {}
        self.api_index_path = api_index_path or API_INDEX_FILE
        
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

        # Routing agent for website selection
        self.routing_system_prompt = (
            "You decide which website APIs are relevant to a user task. "
            "Select only the websites that provide information or capabilities required to complete the task. "
            "If none are relevant, choose an empty set."
        )

        # Pre-planning requirement check (authentication and prerequisites)
        self.pre_planning_requirement_prompt_template = (
            "Task:\n{task}\n\n"
            "Draft Plan (tools to be called):\n{plan}\n\n"
            "API reference:\n{api_context}\n\n"
            "Analyze the tools in the draft plan and identify authentication or prerequisite requirements.\n"
            "Check if any tools require:\n"
            "- Admin login (tools that modify products, orders, customers, etc. or use 'use_admin=True')\n"
            "- Customer login (tools that access customer-specific data like cart, orders, account)\n"
            "- Guest authentication (for guest cart operations)\n"
            "- Any other prerequisites that must be handled BEFORE executing the plan\n\n"
            "For each authentication requirement, decide one of:\n"
            '1. "model_decision" – use default/test credentials or skip if not critical\n'
            '2. "default" – authentication is optional or has defaults\n'
            '3. "user_input" – user must provide credentials (include a prompt)\n'
            "Respond with JSON:\n"
            '{{"requirements": ['
            '{{"name": "auth_type", "description": "admin_login|customer_login|guest_login", "resolution": "model_decision|default|user_input", '
            '"model_decision_instructions": "...", "default_instructions": "...", "prompt": "..."}}'
            '], "notes": "optional context"}}.\n'
            "Only include authentication requirements. If no authentication is needed, return an empty requirements list."
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

    def _extract_tools_from_plan(self, plan: List[Any]) -> List[str]:
        """Extract tool names from the plan steps."""
        tools = []
        for step in plan:
            if hasattr(step, 'tool'):
                tools.append(step.tool)
        return tools

    def _check_auth_requirements(self, tools: List[str]) -> Dict[str, bool]:
        """Check which authentication types are needed based on tool names."""
        needs_admin = False
        needs_customer = False
        needs_guest = False

        for tool in tools:
            tool_lower = tool.lower()
            # Check for admin tools (typically have 'admin' in name or modify data)
            if any(keyword in tool_lower for keyword in ['admin', 'create_product', 'update_product', 
                    'delete_product', 'create_category', 'update_customer', 'delete_customer',
                    'create_invoice', 'create_shipment', 'cancel_order']):
                needs_admin = True
            # Check for customer tools
            if any(keyword in tool_lower for keyword in ['customer_login', 'get_current_customer',
                    'get_cart', 'get_orders', 'get_customer', 'add_to_cart', 'place_order']):
                needs_customer = True
            # Check for guest tools
            if any(keyword in tool_lower for keyword in ['guest_cart', 'create_guest_cart']):
                needs_guest = True

        return {
            'admin': needs_admin,
            'customer': needs_customer,
            'guest': needs_guest
        }

    async def _analyze_pre_planning_requirements(
        self,
        task: str,
        plan_str: str,
        api_context: str,
    ) -> RequirementAnalysisResult:
        """Identify authentication and prerequisite requirements before finalizing plan."""
        requirement_agent = Agent(
            self.llm if isinstance(self.llm, str) else str(self.llm),
            output_type=str,
            system_prompt="You are an expert at analyzing tool requirements and identifying authentication needs."
        )

        prompt = self.pre_planning_requirement_prompt_template.format(
            task=task,
            plan=plan_str,
            api_context=api_context,
        )

        try:
            result = await requirement_agent.run(prompt)
            response = result.output
        except Exception as e:
            print(f"Pre-planning requirement analysis LLM error: {e}")
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

    async def _handle_authentication(self, auth_requirements: List[RequirementDetail], plan: List[Any]) -> Tuple[List[Any], Dict[str, str]]:
        """Handle authentication requirements by adding login steps to the plan if needed."""
        auth_inputs: Dict[str, str] = {}
        updated_plan = list(plan)  # Copy the plan
        
        for req in auth_requirements:
            auth_type = req.description or req.name
            auth_type_lower = auth_type.lower()
            
            # Determine which login tool to use
            login_tool = None
            if 'admin' in auth_type_lower:
                login_tool = f"{self._get_server_name()}-admin_login"
            elif 'customer' in auth_type_lower:
                login_tool = f"{self._get_server_name()}-customer_login"
            elif 'guest' in auth_type_lower:
                # Guest doesn't need login, just create guest cart
                continue
            
            if not login_tool or login_tool not in self.tools:
                continue
            
            # Check if login step already exists in plan
            has_login = any(
                hasattr(step, 'tool') and step.tool == login_tool 
                for step in updated_plan
            )
            
            if not has_login:
                # Collect credentials if needed
                if req.resolution == "user_input":
                    prompt_text = req.prompt or f"Enter credentials for {auth_type}"
                    email = input(f"Email for {auth_type}: ").strip()
                    password = input(f"Password for {auth_type}: ").strip()
                    auth_inputs[f"{auth_type}_email"] = email
                    auth_inputs[f"{auth_type}_password"] = password
                    
                    # Create login step (we'll need to add it to the plan)
                    # For now, we'll store the credentials and let the planner add the step
                    print(f"🔐 Credentials collected for {auth_type}")
                elif req.resolution == "model_decision":
                    # Use default/test credentials
                    print(f"🔐 Using default credentials for {auth_type}")
                    auth_inputs[f"{auth_type}_email"] = "admin@example.com"  # Default
                    auth_inputs[f"{auth_type}_password"] = "admin123"  # Default
        
        return updated_plan, auth_inputs

    def _get_server_name(self) -> str:
        """Get the server name from available tools (e.g., 'shopping')."""
        if not self.tools:
            return "shopping"  # Default
        # Get first tool's server name
        try:
            first_tool = next(iter(self.tools.values()))
            if hasattr(first_tool, 'server'):
                return first_tool.server
            # Try to extract from tool name (format: "server-toolname")
            first_tool_name = next(iter(self.tools.keys()))
            if '-' in first_tool_name:
                return first_tool_name.split('-')[0]
        except (StopIteration, AttributeError):
            pass
        return "shopping"  # Default fallback

    async def pre_planning_requirement_analyzer(self, state: AgentState) -> AgentState:
        """
        Pre-Planning Requirement Analyzer: Assumes authentication is available for all tool calls.
        Authentication is handled automatically by the MCP tools/token system.
        """
        plan = state.get("plan")
        if not plan:
            state["auth_requirements"] = {
                "needs_admin": False,
                "needs_customer": False,
                "needs_guest": False,
                "auth_inputs": {},
                "requirements": []
            }
            return state

        # Assume authentication is available - no checks or prompts needed
        # The MCP tools will handle authentication using the provided token
        state["auth_requirements"] = {
            "needs_admin": False,
            "needs_customer": False,
            "needs_guest": False,
            "auth_inputs": {},
            "requirements": [],
        }

        return state

    async def requirement_analyzer(self, state: AgentState) -> AgentState:
        """
        Requirement Analyzer: Checks if task description is enough to execute.
        Identifies missing arguments (address, payment, etc).
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

            # Collect user inputs if needed
            user_inputs: Dict[str, str] = {}
            if user_inputs_needed:
                print("\n📋 Missing information required to complete the task:")
                for req in user_inputs_needed:
                    print(f"  - {req.name}: {req.description or req.prompt or 'No description'}")
                user_inputs = await self._collect_user_inputs(user_inputs_needed)

            # Format requirements context
            requirements_context = self._format_requirement_context(
                model_decisions, defaults, user_inputs, analysis.notes
            )

            state["requirements_context"] = requirements_context
            state["model_decisions"] = [r.name for r in model_decisions]
            state["defaults_used"] = [r.name for r in defaults]
            state["user_inputs"] = user_inputs

            if model_decisions or defaults or user_inputs:
                print(f"\n✅ Requirement analysis complete:")
                if model_decisions:
                    print(f"  Model decisions: {[r.name for r in model_decisions]}")
                if defaults:
                    print(f"  Using defaults: {[r.name for r in defaults]}")
                if user_inputs:
                    print(f"  User provided: {list(user_inputs.keys())}")

        except Exception as e:
            print(f"Requirement analysis error: {e}")
            state["requirements_context"] = "No additional requirement notes."
            state["model_decisions"] = []
            state["defaults_used"] = []
            state["user_inputs"] = {}

        return state

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
        api_context = state.get("api_context", "")
        if api_context:
            # Add API context to the planning prompt
            enhanced_query = f"{user_query}\n\nAvailable APIs:\n{api_context}"
        else:
            enhanced_query = user_query

        try:
            message_history = self.get_message_history(state)
            result = await self.planning_agent.run(
                enhanced_query,
                message_history=message_history,
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
        if ctx is None:
            return "responder"
        
        denial_message = "Insufficient permissions to execute this function"
        summaries = ctx.tool_summaries if hasattr(ctx, 'tool_summaries') else []
        
        if not ctx.is_complete() and all([denial_message not in str(summary) for summary in summaries]):
            print("Replanning...")
            return "planner"
        else:
            return "responder" # previous plan is complete, so we can respond

    
    def _create_graph(self):
        """
        Creates and returns the LangGraph workflow with all nodes connected.
        Enhanced with routing and requirement analysis nodes.
        """
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("router", self.router)  # Routing node
        workflow.add_node("planner", self.planner)  # Creates draft plan with tool selection
        workflow.add_node("pre_planning_requirement_analyzer", self.pre_planning_requirement_analyzer)  # Checks auth needs
        workflow.add_node("requirement_analyzer", self.requirement_analyzer)  # Checks other requirements
        workflow.add_node("argument_mapper", self.argument_mapper)
        workflow.add_node("executor", self.executor)
        workflow.add_node("responder", self.responder)


        # Define edges
        workflow.set_entry_point("router")  # Start with routing
        workflow.add_edge("router", "planner")  # Route -> Plan (draft with tool selection)
        workflow.add_edge("planner", "pre_planning_requirement_analyzer")  # Plan -> Check Auth Requirements
        workflow.add_edge("pre_planning_requirement_analyzer", "requirement_analyzer")  # Auth Check -> Check Other Requirements
        workflow.add_edge("requirement_analyzer", "executor")  # Requirements -> Execute

        workflow.add_conditional_edges("executor", self.replanning, { ##replanning React might need to remove
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
            permissions_handler.permission_manager.cleanup_session()
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
            # Run router
            state = await agent.router(state)
            
            # Run planner
            state = await agent.planner(state)
            
            # Run pre-planning requirement analyzer
            state = await agent.pre_planning_requirement_analyzer(state)# Run requirement analyzer
            state = await agent.requirement_analyzer(state)
            
            print("\r" + " " * 60 + "\r", end="")  # Clear the "Processing..." message
            
            # Display results
            plan = state.get("plan")
            if plan:
                print("\n=== Generated Plan ===")
                try:
                    print(pretty_print_plan(plan))
                except Exception:
                    print(plan)
                
               
                
                req_context = state.get("requirements_context")
                if req_context and req_context != "No additional requirement notes.":
                    print("\n=== Requirement Analysis ===")
                    print(req_context)
                
                print("\n✅ Plan and requirements ready. Execution stopped before running tools.")
            else:
                print("No plan generated.")
                
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
    args = parser.parse_args()
    
    # Load configuration
    config = Configurator()
    config.load_client_env()
    config.load_shared_env()
    config.check_llm_env_vars()
    config.get_mcp_servers()
    

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