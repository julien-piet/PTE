"""
Plan-then-execute agent that generates programs using the WebArena API.
"""

from __future__ import annotations

import ast
import asyncio
import contextlib
import importlib
import inspect
import io
import json
import textwrap
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import (
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    Union,
)

from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parent
API_DIR = REPO_ROOT / "api"
API_INDEX_FILE = API_DIR / "index.json"
DEFAULT_API_MODULE = "api"


def _load_api_index(index_path: Path = API_INDEX_FILE) -> Dict[str, str]:
    """Load the API index mapping filenames to descriptions."""
    if not index_path.exists():
        raise FileNotFoundError(f"API index missing at {index_path}")
    data = json.loads(index_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(
            "API index must be a JSON object mapping file names to descriptions."
        )
    return data


def _default_api_file() -> Path:
    """Return the first API file listed in the index."""
    registry = load_api_registry()
    if not registry:
        raise FileNotFoundError("No API files declared in the API index.")
    return registry[0].path


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


def _is_tool_decorated(
    node: Union[ast.AsyncFunctionDef, ast.FunctionDef],
) -> bool:
    """Check if a function node uses the @mcp.tool decorator."""
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Call):
            func = decorator.func
            if isinstance(func, ast.Attribute) and func.attr == "tool":
                return True
    return False

def _is_public_api_function(
    node: Union[ast.AsyncFunctionDef, ast.FunctionDef],
) -> bool:
    """
    Treat top-level async functions without a leading underscore as API endpoints.

    This lets us document client wrapper functions like `search_products`
    in `api/shopping.py`, even if they are not decorated with @mcp.tool.
    """
    # Only consider async functions, and ignore private/internal names
    return isinstance(node, ast.AsyncFunctionDef) and not node.name.startswith("_")


def _infer_section(lines: List[str], lineno: int) -> Optional[str]:
    """Infer the section heading from preceding comment blocks."""
    for index in range(lineno - 2, -1, -1):
        text = lines[index].strip()
        if text.startswith(
            "# ========================================================================="
        ):
            continue
        if text.startswith("# ==="):
            return text.lstrip("# ").strip()
    return None


class ParameterDescription(BaseModel):
    """Metadata describing a single endpoint parameter."""

    name: str
    kind: str = Field(
        description="Parameter kind (positional-only, positional-or-keyword, var-positional, keyword-only, var-keyword)"
    )
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


class ModelFieldDescription(BaseModel):
    """Structured description of a Pydantic model field."""

    name: str
    annotation: Optional[str] = None
    default: Optional[str] = None
    description: Optional[str] = None
    field_info: Optional[str] = None


class TypeDescription(BaseModel):
    """Metadata describing a Pydantic BaseModel subclass."""

    name: str
    bases: List[str] = Field(default_factory=list)
    docstring: str = ""
    fields: List[ModelFieldDescription] = Field(default_factory=list)


class APISpecification(BaseModel):
    """Structured description of the API surface for prompting."""

    path: Path
    endpoints: List[EndpointDescription] = Field(default_factory=list)
    types: List[TypeDescription] = Field(default_factory=list)

    @classmethod
    def from_file(cls, api_file: Optional[Path] = None) -> "APISpecification":
        path = api_file or _default_api_file()
        endpoints, types = _parse_api_file(path)
        return cls(path=path, endpoints=endpoints, types=types)

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
                bases = (
                    f"({', '.join(type_desc.bases)})" if type_desc.bases else ""
                )
                lines.append(f"- class {display_prefix}{type_desc.name}{bases}")
                if type_desc.docstring:
                    lines.append("  Docstring:")
                    for doc_line in type_desc.docstring.strip().splitlines():
                        lines.append(f"    {doc_line}")
                if type_desc.fields:
                    lines.append("  Fields:")
                    for field in type_desc.fields:
                        field_line = f"    - {field.name}"
                        if field.annotation:
                            field_line += f": {field.annotation}"
                        if field.default:
                            field_line += f" = {field.default}"
                        lines.append(field_line)
                        if field.description:
                            lines.append(
                                f"      Description: {field.description}"
                            )
                        if field.field_info and not field.default:
                            lines.append(f"      Field: {field.field_info}")
        return "\n".join(lines)


@dataclass
class WebsiteAPI:
    """Metadata and helpers for a website-specific API module."""

    name: str
    file_name: str
    description: str
    base_dir: Path = field(repr=False)
    _spec: Optional[APISpecification] = field(
        default=None, init=False, repr=False
    )

    @property
    def path(self) -> Path:
        return self.base_dir / self.file_name

    def load_spec(self) -> APISpecification:
        if self._spec is None:
            self._spec = APISpecification.from_file(self.path)
        return self._spec


def load_api_registry(index_path: Path = API_INDEX_FILE) -> List[WebsiteAPI]:
    """Load all website APIs described in the JSON index."""
    entries = _load_api_index(index_path)
    registry: List[WebsiteAPI] = []
    for file_name, description in entries.items():
        path = index_path.parent / file_name
        if not path.exists():
            raise FileNotFoundError(
                f"API file {file_name} referenced in index but missing at {path}"
            )
        registry.append(
            WebsiteAPI(
                name=Path(file_name).stem,
                file_name=file_name,
                description=description,
                base_dir=index_path.parent,
            )
        )
    return registry


def extract_api_descriptions(
    api_file: Optional[Path] = None,
) -> List[EndpointDescription]:
    """Backward-compatible helper returning only endpoint descriptions."""
    path = api_file or _default_api_file()
    endpoints, _ = _parse_api_file(path)
    return endpoints


def _parse_api_file(
    api_file: Path,
) -> Tuple[List[EndpointDescription], List[TypeDescription]]:
    """
    Parse an API module file and return structured descriptions for each MCP tool endpoint and related types.
    """
    source = api_file.read_text(encoding="utf-8")
    module_ast = ast.parse(source)
    lines = source.splitlines()
    endpoints: List[EndpointDescription] = []
    types: List[TypeDescription] = []

    for node in module_ast.body:
        if isinstance(node, ast.ClassDef) and _is_pydantic_model(node):
            types.append(_build_type_description(node))
        # elif isinstance(
        #     node, (ast.FunctionDef, ast.AsyncFunctionDef)
        # ) and _is_tool_decorated(node):
        #     endpoints.append(_build_endpoint_description(node, lines))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
            _is_tool_decorated(node) or _is_public_api_function(node)
        ):
            endpoints.append(_build_endpoint_description(node, lines))

    endpoints.sort(key=lambda endpoint: (endpoint.section or "", endpoint.name))
    types.sort(key=lambda type_desc: type_desc.name)
    return endpoints, types




class ChatMessage(BaseModel):
    """Minimal chat message schema for LLM clients."""

    role: Literal["system", "user", "assistant"]
    content: str


class StepLog(BaseModel):
    """Captured prompt/response pair for logging."""

    step: str
    prompt: List[ChatMessage] = Field(default_factory=list)
    response: str


class RequirementDetail(BaseModel):
    """Missing requirement discovered during spec analysis."""

    name: str
    description: Optional[str] = None
    resolution: Literal["model_decision", "default", "user_input"] = (
        "user_input"
    )
    model_decision_instructions: Optional[str] = None
    default_instructions: Optional[str] = None
    prompt: Optional[str] = None


class RequirementAnalysisResult(BaseModel):
    """Outcome of the requirement analysis."""

    requirements: List[RequirementDetail] = Field(default_factory=list)
    notes: Optional[str] = None


class ChatModel(Protocol):
    """Simple protocol an LLM client must satisfy."""

    def complete(self, messages: Sequence[ChatMessage]) -> str: ...


class AgentConfig(BaseModel):
    """Configuration for the plan-then-execute agent."""

    max_attempts: int = Field(default=3, ge=1)
    system_prompt: str = Field(
        default="You are an expert website automation agent. Plan carefully and write precise Python programs that call only the provided website APIs via the shared `api` package."
    )
    plan_prompt_template: str = Field(
        default=(
            "You can access curated website APIs. Each endpoint name already includes the website prefix you must use when calling it (e.g., `api.<website>.<endpoint>`).\n"
            "Available endpoints:\n"
            "{api_context}\n\n"
            "Task: {task}\n"
            "Return a concise, numbered list of high-level steps before coding."
        )
    )
    program_prompt_template: str = Field(
        default=(
            "You must write a Python program that fulfils the task using only the endpoints listed below.\n"
            "Do not include explanations.\n"
            "Rules:\n"
            "1. Import from the shared `api` package; do not redefine endpoints.\n"
            "2. Call endpoints via their website namespace exactly as shown (e.g., `await api.webarena.customer_login(...)`).\n"
            "3. Define `async def main()` as the entry point.\n"
            "4. Use `await` for API calls and `asyncio.gather` if parallelism is required.\n"
            "5. Do not include `if __name__ == '__main__':` guards; the runtime will invoke `main()`.\n"
            "6. Return a structured dictionary summarising the result from `main()`.\n"
            "7. When handling errors, re-raise informative exceptions.\n\n"
            "High-level plan:\n{plan}\n\n"
            "{retry_block}"
            "Requirement notes:\n{requirements_context}\n\n"
            "Task: {task}\n"
            "API reference:\n{api_context}\n"
            "Write only valid Python code."
        )
    )
    fix_prompt_template: str = Field(
        default=(
            "The previous program failed with the error below. Update the program to fix the issue while adhering to all rules.\n"
            "Error:\n{error}\n"
            "Previous code:\n{code}\n"
        )
    )
    requirement_check_prompt_template: str = Field(
        default=(
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
    )
    routing_system_prompt: str = Field(
        default=(
            "You decide which website APIs are relevant to a user task. "
            "Select only the websites that provide information or capabilities required to complete the task. "
            "If none are relevant, choose an empty set."
        )
    )
    routing_prompt_template: str = Field(
        default=(
            "Task:\n{task}\n\n"
            "Available website APIs:\n{api_inventory}\n\n"
            "Respond with a JSON object of the form "
            '{{"websites": ["name1", "name2"], "reason": "short justification"}} using the website identifiers. '
            "Return an empty `websites` list if the task cannot be served by the available APIs."
        )
    )


class ExecutionResult(BaseModel):
    """Outcome of running a generated program."""

    success: bool
    attempt: int
    code: str
    output: str = ""
    error: Optional[str] = None
    return_value: Optional[object] = None


class AgentRunResult(BaseModel):
    """Summary of an agent run across multiple attempts."""

    success: bool
    task: str
    plan: Optional[str]
    attempts: List[ExecutionResult] = Field(default_factory=list)
    routed_websites: List[str] = Field(default_factory=list)
    message: Optional[str] = None
    execution_result: Optional[ExecutionResult] = None
    logs: List[StepLog] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    defaults_used: List[str] = Field(default_factory=list)
    model_decisions: List[str] = Field(default_factory=list)
    user_inputs: Dict[str, str] = Field(default_factory=dict)

    @property
    def final_code(self) -> Optional[str]:
        if not self.attempts:
            return None
        return self.attempts[-1].code

    @property
    def last_error(self) -> Optional[str]:
        if not self.attempts:
            return None
        return self.attempts[-1].error


def _ensure_fastmcp_stub() -> None:
    """Provide a minimal FastMCP stub if the package is unavailable."""
    try:
        import fastmcp  # type: ignore  # noqa: F401
    except ModuleNotFoundError:
        import sys
        import types

        module = types.ModuleType("fastmcp")

        class FastMCP:  # pylint: disable=too-few-public-methods
            def __init__(self, *args, **kwargs) -> None:
                self.args = args
                self.kwargs = kwargs

            def tool(self, *args, **kwargs):
                def decorator(func):
                    return func

                return decorator

            def run(self) -> None:
                raise RuntimeError("FastMCP stub cannot run the MCP server.")

        module.FastMCP = FastMCP  # type: ignore[attr-defined]
        sys.modules["fastmcp"] = module


class PlanThenExecuteAgent:
    """Agent that plans, writes code, executes it, and retries on failure."""

    def __init__(
        self,
        llm: ChatModel,
        config: Optional[AgentConfig] = None,
        api_index_path: Optional[Path] = None,
        user_input_provider: Optional[
            Callable[[RequirementDetail], str]
        ] = None,
    ) -> None:
        self.llm = llm
        self.config = config or AgentConfig()
        self.api_index_path = api_index_path or API_INDEX_FILE
        self.api_registry = load_api_registry(self.api_index_path)
        if not self.api_registry:
            raise ValueError(
                "No website APIs configured; check api/index.json."
            )
        self._registry_lookup = {api.name: api for api in self.api_registry}
        self._registry_lookup_lower = {
            api.name.lower(): api for api in self.api_registry
        }
        self.api_module_name = DEFAULT_API_MODULE
        self._api_module: Optional[ModuleType] = None
        self._inventory_text = self._format_api_inventory()
        self._user_input_provider = user_input_provider

    def run(self, task: str, *, dry_run: bool = False) -> AgentRunResult:
        """Execute the full route-plan-code loop."""
        logs: List[StepLog] = []
        websites = self._route_task(task, logs)
        if not websites:
            message = "The available website APIs cannot satisfy this request."
            return AgentRunResult(
                success=False,
                task=task,
                plan=None,
                attempts=[],
                routed_websites=[],
                message=message,
                execution_result=None,
                logs=logs,
            )

        routed_names = [site.name for site in websites]
        api_context = self._build_api_context(websites)
        plan = self._create_plan(task, api_context, logs)
        analysis = self._analyze_requirements(task, plan, api_context, logs)
        (
            model_decisions,
            defaults_to_use,
            inputs_needed,
        ) = self._partition_requirements(analysis.requirements)

        warnings: List[str] = []
        defaults_used: List[str] = []
        model_decision_notes: List[str] = []

        if defaults_to_use:
            for requirement in defaults_to_use:
                description = (
                    requirement.default_instructions
                    or f"Use platform default for {requirement.name}"
                )
                defaults_used.append(description)
            warnings.append(
                "Using documented platform defaults for: "
                + ", ".join(detail.name for detail in defaults_to_use)
            )

        if model_decisions:
            for requirement in model_decisions:
                instruction = (
                    requirement.model_decision_instructions
                    or "Choose any reasonable value."
                )
                model_decision_notes.append(
                    f"{requirement.name}: {instruction}"
                )

        user_inputs: Dict[str, str] = {}
        if inputs_needed:
            user_inputs = self._collect_user_inputs(inputs_needed)

        requirements_context = self._format_requirement_context(
            model_decisions,
            defaults_to_use,
            user_inputs,
            analysis.notes,
        )

        attempts: List[ExecutionResult] = []
        previous_error: Optional[str] = None
        previous_code: Optional[str] = None

        for attempt in range(1, self.config.max_attempts + 1):
            program = self._draft_program(
                task=task,
                plan=plan,
                attempt=attempt,
                previous_error=previous_error,
                previous_code=previous_code,
                api_context=api_context,
                requirements_context=requirements_context,
                logs=logs,
            )
            if dry_run:
                execution = ExecutionResult(
                    success=False,
                    attempt=attempt,
                    code=program,
                    output="",
                    error="Dry run: execution skipped.",
                )
                attempts.append(execution)
                return AgentRunResult(
                    success=False,
                    task=task,
                    plan=plan,
                    attempts=attempts,
                    routed_websites=routed_names,
                    message="Dry run: execution skipped.",
                    execution_result=execution,
                    logs=logs,
                    warnings=warnings,
                    defaults_used=defaults_used,
                    model_decisions=model_decision_notes,
                    user_inputs=user_inputs,
                )

            execution = self._execute_program(program, attempt=attempt)
            attempts.append(execution)

            if execution.success:
                return AgentRunResult(
                    success=True,
                    task=task,
                    plan=plan,
                    attempts=attempts,
                    routed_websites=routed_names,
                    execution_result=execution,
                    logs=logs,
                    warnings=warnings,
                    defaults_used=defaults_used,
                    model_decisions=model_decision_notes,
                    user_inputs=user_inputs,
                )

            previous_error = execution.error
            previous_code = program

        return AgentRunResult(
            success=False,
            task=task,
            plan=plan,
            attempts=attempts,
            routed_websites=routed_names,
            execution_result=attempts[-1] if attempts else None,
            logs=logs,
            warnings=warnings,
            defaults_used=defaults_used,
            model_decisions=model_decision_notes,
            user_inputs=user_inputs,
        )

    def _create_plan(
        self, task: str, api_context: str, logs: List[StepLog]
    ) -> str:
        """Ask the LLM for a high-level execution plan."""
        messages = [
            ChatMessage(role="system", content=self.config.system_prompt),
            ChatMessage(
                role="user",
                content=self.config.plan_prompt_template.format(
                    api_context=api_context,
                    task=task,
                ),
            ),
        ]
        response = self._complete_with_logging(messages, "plan", logs)
        return response.strip()

    def _draft_program(
        self,
        task: str,
        plan: str,
        attempt: int,
        previous_error: Optional[str],
        previous_code: Optional[str],
        api_context: str,
        requirements_context: str,
        logs: List[StepLog],
    ) -> str:
        """Request program synthesis from the LLM."""
        retry_block = ""
        if attempt > 1 and previous_error:
            retry_block = self.config.fix_prompt_template.format(
                error=previous_error, code=previous_code or ""
            )

        messages = [
            ChatMessage(role="system", content=self.config.system_prompt),
            ChatMessage(
                role="assistant",
                content=plan,
            ),
            ChatMessage(
                role="user",
                content=self.config.program_prompt_template.format(
                    plan=plan,
                    task=task,
                    api_context=api_context,
                    requirements_context=requirements_context,
                    retry_block=retry_block,
                ),
            ),
        ]
        response = self._complete_with_logging(
            messages, f"program_attempt_{attempt}", logs
        )
        return _strip_code_fences(response)

    def _analyze_requirements(
        self,
        task: str,
        plan: str,
        api_context: str,
        logs: List[StepLog],
    ) -> RequirementAnalysisResult:
        """Identify missing arguments and how to resolve them."""
        messages = [
            ChatMessage(role="system", content=self.config.system_prompt),
            ChatMessage(
                role="user",
                content=self.config.requirement_check_prompt_template.format(
                    task=task,
                    plan=plan,
                    api_context=api_context,
                ),
            ),
        ]
        response = self._complete_with_logging(
            messages, "requirement_check", logs
        )
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
                            name=str(entry.get("name", "") or "").strip()
                            or "unspecified_field",
                            description=_ensure_str(entry.get("description")),
                            resolution=_normalize_resolution(
                                entry.get("resolution")
                            ),
                            model_decision_instructions=_ensure_str(
                                entry.get("model_decision_instructions")
                            ),
                            default_instructions=_ensure_str(
                                entry.get("default_instructions")
                            ),
                            prompt=_ensure_str(entry.get("prompt")),
                        )
                    )
        notes = _ensure_str(data.get("notes"))
        return RequirementAnalysisResult(requirements=parsed, notes=notes)

    def _partition_requirements(
        self, requirements: Sequence[RequirementDetail]
    ) -> Tuple[
        List[RequirementDetail],
        List[RequirementDetail],
        List[RequirementDetail],
    ]:
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

    def _collect_user_inputs(
        self, requirements: Sequence[RequirementDetail]
    ) -> Dict[str, str]:
        """Prompt the user for missing argument values."""
        values: Dict[str, str] = {}
        for requirement in requirements:
            value = self._prompt_user_for_requirement(requirement)
            values[requirement.name] = value
        return values

    def _prompt_user_for_requirement(
        self, requirement: RequirementDetail
    ) -> str:
        """Collect input for a missing requirement via callback or stdin."""
        if self._user_input_provider is not None:
            return self._user_input_provider(requirement)

        prompt_text = (
            requirement.prompt or requirement.description or requirement.name
        )
        message = f"Provide a value for '{requirement.name}' ({prompt_text}): "
        while True:
            try:
                value = input(message).strip()
            except EOFError as exc:
                raise RuntimeError(
                    f"Missing value for {requirement.name} and stdin is closed."
                ) from exc
            if value:
                return value
            print("Value cannot be empty. Please enter a valid value.")

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
                instruction = (
                    requirement.model_decision_instructions
                    or "Choose any reasonable value."
                )
                lines.append(f"- {requirement.name}: {instruction}")
            sections.append("\n".join(lines))
        if defaults:
            lines = ["Defaults to use:"]
            for requirement in defaults:
                details = (
                    requirement.default_instructions or "Use platform default."
                )
                lines.append(f"- {requirement.name}: {details}")
            sections.append("\n".join(lines))
        if user_inputs:
            lines = ["User-provided values:"]
            for name, value in user_inputs.items():
                lines.append(f"- {name}: {value}")
            sections.append("\n".join(lines))
        if notes:
            sections.append(f"Additional notes: {notes}")
        return (
            "\n\n".join(sections)
            if sections
            else "No additional requirement notes."
        )

    def _complete_with_logging(
        self,
        messages: Sequence[ChatMessage],
        step: str,
        logs: List[StepLog],
    ) -> str:
        """Send a prompt to the LLM and capture the interaction in the run log."""
        response = self.llm.complete(messages)
        logs.append(
            StepLog(step=step, prompt=list(messages), response=response)
        )
        return response

    def _route_task(self, task: str, logs: List[StepLog]) -> List[WebsiteAPI]:
        """Ask the routing sub-agent which website APIs are relevant."""
        inventory = self._inventory_text or self._format_api_inventory()
        messages = [
            ChatMessage(
                role="system", content=self.config.routing_system_prompt
            ),
            ChatMessage(
                role="user",
                content=self.config.routing_prompt_template.format(
                    task=task,
                    api_inventory=inventory,
                ),
            ),
        ]
        response = self._complete_with_logging(messages, "routing", logs)
        selection = self._parse_routing_response(response)
        if selection is None:
            return list(self.api_registry)
        resolved = self._resolve_websites(selection)
        if not resolved and selection:
            return list(self.api_registry)
        return resolved

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

    def _format_api_inventory(self) -> str:
        """Format website inventory for routing prompt consumption."""
        return "\n".join(
            f"- {site.name}: {site.description}" for site in self.api_registry
        )

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
            site = self._registry_lookup.get(
                key
            ) or self._registry_lookup_lower.get(key.lower())
            if site and site not in resolved:
                resolved.append(site)
        return resolved

    def _execute_program(self, code: str, attempt: int) -> ExecutionResult:
        """Run the generated program in a controlled context."""
        stdout = io.StringIO()

        try:
            api_module = self._load_api_module()
        except Exception:
            return ExecutionResult(
                success=False,
                attempt=attempt,
                code=code,
                error=traceback.format_exc(),
            )

        exec_globals = {
            "__name__": "__agent_runtime__",
            "api": api_module,
            "asyncio": asyncio,
        }

        try:
            compiled = compile(code, "<agent-program>", "exec")
            with contextlib.redirect_stdout(stdout):
                exec(compiled, exec_globals)

            main_fn = exec_globals.get("main")
            if main_fn is None:
                raise RuntimeError(
                    "Generated program must define an async function named `main`."
                )

            if asyncio.iscoroutinefunction(main_fn):
                result_value = asyncio.run(main_fn())
            else:
                outcome = main_fn()
                if asyncio.iscoroutine(outcome):
                    result_value = asyncio.run(outcome)
                else:
                    result_value = outcome

        except Exception:
            return ExecutionResult(
                success=False,
                attempt=attempt,
                code=code,
                output=stdout.getvalue(),
                error=traceback.format_exc(),
            )

        return ExecutionResult(
            success=True,
            attempt=attempt,
            code=code,
            output=stdout.getvalue(),
            return_value=result_value,
        )

    def _load_api_module(self) -> ModuleType:
        """Dynamically import the API module, inserting a FastMCP stub if needed."""
        if self._api_module is not None:
            return self._api_module

        _ensure_fastmcp_stub()
        try:
            self._api_module = importlib.import_module(self.api_module_name)
        except ModuleNotFoundError as exc:
            raise ImportError(
                f"Unable to load API package '{self.api_module_name}'."
            ) from exc

        return self._api_module


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences from model output."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        fence = lines[0]
        cleaned = "\n".join(lines[1:])
        if cleaned.endswith("```"):
            cleaned = "\n".join(cleaned.splitlines()[:-1])
        if fence.startswith("```python"):
            cleaned = cleaned
    return cleaned.strip()


def _ensure_str(value: Optional[object]) -> Optional[str]:
    """Return the input as a stripped string if possible."""
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return None


def _normalize_resolution(
    value: Optional[object],
) -> Literal["model_decision", "default", "user_input"]:
    """Normalize resolution labels coming from the requirement checker."""
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {
            "model",
            "model_decision",
            "model-choice",
            "model_choice",
        }:
            return "model_decision"
        if lowered in {"default", "platform_default"}:
            return "default"
    return "user_input"


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
    fields: List[ModelFieldDescription] = []

    for statement in node.body:
        if isinstance(statement, ast.AnnAssign) and isinstance(
            statement.target, ast.Name
        ):
            name = statement.target.id
            annotation = _unparse(statement.annotation)
            default_text: Optional[str] = None
            description_text: Optional[str] = None
            field_info_text: Optional[str] = None

            value = statement.value
            if isinstance(value, ast.Call) and _is_field_call(value):
                if value.args:
                    default_text = _unparse(value.args[0])
                description_text = _extract_field_description(value)
                field_info_text = _unparse(value)
            elif value is not None:
                default_text = _unparse(value)

            fields.append(
                ModelFieldDescription(
                    name=name,
                    annotation=annotation,
                    default=default_text,
                    description=description_text,
                    field_info=field_info_text,
                )
            )

    bases = [_unparse(base) for base in node.bases]
    return TypeDescription(
        name=node.name, bases=bases, docstring=docstring, fields=fields
    )


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

    positional_nodes = list(getattr(node.args, "posonlyargs", [])) + list(
        node.args.args
    )
    defaults = list(node.args.defaults)
    default_offset = len(positional_nodes) - len(defaults)

    for index, arg in enumerate(positional_nodes):
        default_node = (
            defaults[index - default_offset]
            if index >= default_offset
            else None
        )
        kind = (
            "positional-only"
            if index < len(getattr(node.args, "posonlyargs", []))
            else "positional-or-keyword"
        )
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

    for kw_arg, default_node in zip(
        node.args.kwonlyargs, node.args.kw_defaults
    ):
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


def test_api_descriptions(
    sample_endpoints: Optional[Sequence[str]] = None,
) -> None:
    """
    Validate the extracted API specification and print a detailed summary.

    If `sample_endpoints` is provided, only those names are checked/printed; otherwise every
    endpoint found in the file is validated.
    """
    specs = [
        APISpecification.from_file(site.path) for site in load_api_registry()
    ]

    errors: List[str] = []
    output_lines: List[str] = []

    for spec in specs:
        module_name = f"{DEFAULT_API_MODULE}.{spec.path.stem}"
        _ensure_fastmcp_stub()
        api_module = importlib.import_module(module_name)

        endpoint_map = {endpoint.name: endpoint for endpoint in spec.endpoints}
        targets = (
            list(sample_endpoints)
            if sample_endpoints
            else sorted(endpoint_map.keys())
        )

        output_lines.append(f"=== Endpoints ({module_name}) ===")

        for name in targets:
            endpoint = endpoint_map.get(name)
            if endpoint is None:
                errors.append(
                    f"[{module_name}] Missing endpoint in spec: {name}"
                )
                continue

            func = getattr(api_module, name, None)
            if func is None:
                errors.append(
                    f"[{module_name}] Endpoint present in spec but not found in module: {name}"
                )
                continue

            signature = inspect.signature(func)
            spec_params = [param.name for param in endpoint.parameters]
            actual_params = list(signature.parameters.keys())

            if spec_params != actual_params:
                errors.append(
                    f"[{module_name}] Parameter mismatch for {name}: spec {spec_params} vs actual {actual_params}"
                )

            output_lines.append(f"{name}(")
            for param in endpoint.parameters:
                line = f"  - {param.name} [{param.kind}]"
                if param.annotation:
                    line += f": {param.annotation}"
                if param.default is not None:
                    line += f" = {param.default}"
                output_lines.append(line)
            output_lines.append(")")
            output_lines.append(
                f"  Returns: {endpoint.return_annotation or 'None'}"
            )
            if endpoint.section:
                output_lines.append(f"  Section: {endpoint.section}")
            if endpoint.summary:
                output_lines.append(f"  Summary: {endpoint.summary}")
            if endpoint.docstring:
                output_lines.append("  Docstring:")
                for doc_line in endpoint.docstring.strip().splitlines():
                    output_lines.append(f"    {doc_line}")
            output_lines.append("")

        if spec.types:
            output_lines.append(f"=== Type Definitions ({module_name}) ===")
            for type_desc in spec.types:
                bases = (
                    f"({', '.join(type_desc.bases)})" if type_desc.bases else ""
                )
                output_lines.append(f"class {type_desc.name}{bases}:")
                if type_desc.docstring:
                    output_lines.append("  Docstring:")
                    for doc_line in type_desc.docstring.strip().splitlines():
                        output_lines.append(f"    {doc_line}")
                if type_desc.fields:
                    output_lines.append("  Fields:")
                    for field in type_desc.fields:
                        field_line = f"    - {field.name}"
                        if field.annotation:
                            field_line += f": {field.annotation}"
                        if field.default:
                            field_line += f" = {field.default}"
                        output_lines.append(field_line)
                        if field.description:
                            output_lines.append(
                                f"      Description: {field.description}"
                            )
                        if field.field_info and not field.default:
                            output_lines.append(
                                f"      Field: {field.field_info}"
                            )
                output_lines.append("")

    if errors:
        raise AssertionError(
            "API description mismatches:\n- " + "\n- ".join(errors)
        )

    print("\n".join(output_lines))
