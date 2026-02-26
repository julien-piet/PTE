# demo/utils/strict_planner.py
# -----------------------------------------------------------------------------
# Strict planning models auto-generated from FastMCP tool schemas.
#
# What this gives you:
#   - create_args_model_from_json_schema(): JSON Schema -> Pydantic model
#   - build_planning_models_from_mcp_specs(): ToolStep (discriminated union) + Plan
#   - build_planning_agent(): pydantic_ai.Agent constrained to that Plan schema
#   - gather_specs_from_tool_definitions(): pull specs from your ToolDefinition dict
#   - catalog_text(): concise tool+args catalog for your planner prompt
#
# Integration steps (in your app):
#   tools_dict = await initialize_tools(...)  # you already have this
#   specs = gather_specs_from_tool_definitions(tools_dict)
#   ToolStep, Plan = build_planning_models_from_mcp_specs(specs)
#   planner = build_planning_agent(llm_signature, planner_prompt, specs, Plan)
#   # planner.run(...) returns an object with .output.steps (validated)
# -----------------------------------------------------------------------------

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union, Iterable
from pydantic import BaseModel, Field, create_model, ConfigDict
from typing_extensions import Literal, Annotated
from pydantic_ai import Agent, ModelSettings

from pprint import pprint

# ========= JSON Schema -> Pydantic =========

def _literal_of(values):
    from typing_extensions import Literal as _Lit
    return _Lit.__class_getitem__(tuple(values))

def _schema_to_type(schema: Dict[str, Any]) -> Any:
    if not isinstance(schema, dict):
        return Any
    t = schema.get("type")
    if isinstance(t, list):
        if "null" in t and len(t) == 2:
            other = next(x for x in t if x != "null")
            inner = _schema_to_type({**schema, "type": other})
            from typing import Optional as TypingOptional
            return TypingOptional[inner]
        return Any
    if "enum" in schema and isinstance(schema["enum"], list):
        return _literal_of(schema["enum"])
    if t == "string":
        return str
    if t == "integer":
        return int
    if t == "number":
        return float
    if t == "boolean":
        return bool
    if t == "array":
        items = schema.get("items", {})
        return List[_schema_to_type(items)]
    if t == "object" or "properties" in schema:
        props: Dict[str, Any] = schema.get("properties", {}) or {}
        req = set(schema.get("required", []) or [])
        fields: Dict[str, Tuple[Any, Any]] = {}
        for name, subschema in props.items():
            py_type = _schema_to_type(subschema)
            default = ... if name in req else None
            fields[name] = (py_type, Field(default=default, description=subschema.get("description")))
        submodel = create_model("AnonObj", **fields)
        try:
            submodel.model_config = ConfigDict(extra="forbid")
        except Exception:
            pass
        return submodel
    return Any


def create_args_model_from_json_schema(model_name: str, parameters_schema: Dict[str, Any]) -> type[BaseModel]:
    schema = parameters_schema or {}
    if "parameters" in schema and isinstance(schema["parameters"], dict):
        schema = schema["parameters"]
    if not schema or schema.get("type") not in (None, "object"):
        Model = create_model(model_name)
        Model.model_config = ConfigDict(extra="forbid")
        return Model
    properties: Dict[str, Any] = schema.get("properties", {}) or {}
    required: set[str] = set(schema.get("required", []) or [])
    fields: Dict[str, Tuple[Any, Any]] = {}
    for arg_name, arg_schema in properties.items():
        py_type = _schema_to_type(arg_schema)
        default = ... if arg_name in required else None
        fields[arg_name] = (py_type, Field(default=default, description=arg_schema.get("description")))
    Model = create_model(model_name, **fields)
    Model.model_config = ConfigDict(extra="forbid")
    # pprint(Model.model_json_schema())
    # exit()
    return Model

def build_planning_models_from_mcp_specs(mcp_specs: List[Dict[str, Any]]):
    variants = []
    for spec in mcp_specs:
        tool_name: str = spec["full_name"]
        description: str = spec.get("description", "") or ""
        input_schema: Dict[str, Any] = spec.get("input_schema") or {}

        ArgsModel = create_args_model_from_json_schema(
            model_name=f"{tool_name.replace(':','_').replace('.','_')}_Args",
            parameters_schema=input_schema,
        )

        StepCls = create_model(
            f"{tool_name.replace(':','_').replace('.','_').title()}Step",
            tool=(Literal[tool_name], Field(description=description)),
            args=(ArgsModel, Field(..., description="Arguments for this tool")),
            step_id=(str, Field(description="Unique id within the plan")),
            depends_on=(List[str], Field(default_factory=list, description="List of step_ids")),
            hints=(str, Field(default="", description="Free-form hint for replanning/execution")),
            __base__=BaseModel,
        )
        variants.append(StepCls)

    if not variants:
        NoTool = create_model(
            "NoToolStep",
            # tool=(Literal.__class_getitem__(("no_tools_available",)), Field()),
            tool=(Literal["no_tools_available"], Field()),
            args=(Dict[str, Any], Field(default_factory=dict)),
            step_id=(str, Field()),
            depends_on=(List[str], Field(default_factory=list)),
            hints=(str, Field(default="")),
            __base__=BaseModel,
        )
        variants = [NoTool]

    ToolStep = Annotated[Union[tuple(variants)], Field(discriminator="tool")]

    class Plan(BaseModel):
        steps: List[ToolStep] = Field(min_length=1, description="Ordered execution steps")

    return ToolStep, Plan


# ========= Prompt helpers =========

def catalog_text(mcp_specs: List[Dict[str, Any]]) -> str:
    """
    Make a concise catalog string with just tool names (no args).
    Saves 5k-15k tokens since full schemas are already in the discriminated union.
    """
    return "\n".join([f"- {s['full_name']}" for s in mcp_specs])


def build_planning_agent(
    llm_signature: str,
    planner_prompt: str,
    mcp_specs: List[Dict[str, Any]],
    PlanModel: type[BaseModel] | None = None
) -> Agent:
    """
    Construct a pydantic_ai.Agent that outputs a validated Plan.

    If PlanModel is None, we first build ToolStep+Plan internally from mcp_specs.
    """
    if PlanModel is None:
        _, PlanModel = build_planning_models_from_mcp_specs(mcp_specs)

    sys = f"""{planner_prompt}

Use only the tools listed below. Do NOT invent tool names or argument keys.
Return a JSON object that conforms to the exact schema for Plan(steps).

Available tools:
{catalog_text(mcp_specs)}
"""
    agent = Agent(
        llm_signature,
        output_type=PlanModel,
        system_prompt=sys,
        retries=3,
        model_settings=ModelSettings(temperature=0.0)
    )
    return agent


# ========= Extract specs from your ToolDefinition dict =========

def gather_specs_from_tool_definitions(tools: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Your initialize_tools() returns Dict[str, ToolDefinition].
    This converts that dict to the 'mcp_specs' list consumed by builders above.

    Expected ToolDefinition attributes (as per your code):
      - name: str  (we use this as 'full_name')
      - description: str
      - input_schema: Dict[str, Any]  (either already parameters schema or contains 'parameters')
    """
    specs: List[Dict[str, Any]] = []
    for tool_name, tool_def in tools.items():
        schema = getattr(tool_def, "input_schema", {}) or {}
        desc = getattr(tool_def, "description", "") or ""
        specs.append({
            "full_name": tool_name,         # IMPORTANT: must match the name your planner will emit
            "description": desc,
            "input_schema": schema,
        })
    return specs


# ========= Optional: plan validation helpers (acyclic deps, etc.) =========

def explain_plan_errors(plan: Any) -> Tuple[bool, Optional[str]]:
    """
    Validate basic structural properties of the plan (beyond Pydantic typing):
      - steps is list, non-empty
      - unique step_id
      - depends_on references known steps
      - no self-dependency
      - cycle detection
    """
    if plan is None:
        return False, "Plan is None"
    steps = getattr(plan, "steps", None)
    if not isinstance(steps, list) or len(steps) == 0:
        return False, "Plan must contain at least one step"

    # Collect IDs
    ids = []
    for i, s in enumerate(steps):
        sid = getattr(s, "step_id", None)
        if not sid:
            return False, f"Step at index {i} missing step_id"
        ids.append(sid)

    # Uniqueness
    seen = set()
    for sid in ids:
        if sid in seen:
            return False, f"Duplicate step_id: {sid}"
        seen.add(sid)

    idset = set(ids)
    # References and self-edges
    for s in steps:
        sid = s.step_id
        for dep in getattr(s, "depends_on", []) or []:
            if dep not in idset:
                return False, f"Step '{sid}' depends on unknown step_id '{dep}'"
            if dep == sid:
                return False, f"Step '{sid}' cannot depend on itself"

    # Cycle detection
    from collections import defaultdict

    g = defaultdict(list)
    for s in steps:
        for d in getattr(s, "depends_on", []) or []:
            g[d].append(s.step_id)

    visited: set[str] = set()
    stack: set[str] = set()

    def dfs(u: str) -> bool:
        if u in stack:
            return True
        if u in visited:
            return False
        visited.add(u)
        stack.add(u)
        for v in g.get(u, []):
            if dfs(v):
                return True
        stack.remove(u)
        return False

    for sid in ids:
        if sid not in visited and dfs(sid):
            return False, "Cycle detected in plan"
    return True, None


def validate_plan(plan: Any) -> bool:
    ok, _ = explain_plan_errors(plan)
    return ok

def _abbr(v: Any, max_len: int = 80) -> str:
    """Compact, single-line preview of a value."""
    try:
        s = (
            v if isinstance(v, str)
            else v.model_dump_json() if isinstance(v, BaseModel)
            else str(v)
        )
    except Exception:
        s = str(v)
    s = s.replace("\n", " ").replace("\r", " ")
    return s if len(s) <= max_len else s[:max_len] + "…"

def _render_args(args_model: BaseModel, max_value_len: int) -> List[str]:
    """Render args with required-first ordering and compact values."""
    fields = args_model.model_fields  # {name: FieldInfo}
    data = args_model.model_dump()

    # required first, then lexicographic
    def sort_key(name: str):
        required = getattr(fields[name], "is_required", None)
        is_req = bool(required() if callable(required) else fields[name].is_required)
        return (0 if is_req else 1, name)

    lines = []
    for name in sorted(data.keys(), key=sort_key):
        fi = fields.get(name)
        required = False
        if fi is not None:
            req_attr = getattr(fi, "is_required", None)
            required = bool(req_attr() if callable(req_attr) else fi.is_required)
        val = data[name]
        suffix = " (req)" if required else ""
        lines.append(f"    - {name}{suffix}: {_abbr(val, max_value_len)}")
    if not lines:
        lines.append("    (no arguments)")
    return lines

def pretty_print_plan(
    steps: Iterable[Any],
    *,
    show_hints: bool = True,
    max_value_len: int = 80,
    header: bool = True,
) -> str:
    """
    Pretty print a strict-plan steps iterable (each step has:
    step_id: str, tool: str, args: BaseModel, depends_on: List[str], hints: str).
    """
    steps = list(steps)
    if not steps:
        return "No execution steps in plan"

    out: List[str] = []
    if header:
        out += ["", "=" * 60, "EXECUTION PLAN", "=" * 60]

    for i, step in enumerate(steps, 1):
        out.append(f"\nStep {i}: {step.step_id}")
        out.append(f"  Tool: {step.tool}")

        # Arguments
        out.append("  Arguments:")
        try:
            out.extend(_render_args(step.args, max_value_len))
        except Exception:
            # Fallback if args isn't a BaseModel for some reason
            args_dump = getattr(step.args, "model_dump", lambda: step.args)()
            if isinstance(args_dump, dict):
                for k, v in sorted(args_dump.items()):
                    out.append(f"    - {k}: {_abbr(v, max_value_len)}")
            else:
                out.append(f"    {_abbr(args_dump, max_value_len)}")

        # Dependencies
        deps = getattr(step, "depends_on", []) or []
        if deps:
            out.append("  Depends on: " + ", ".join(deps))
        else:
            out.append("  Depends on: None (can execute immediately)")

        # Hints
        if show_hints:
            hints = getattr(step, "hints", "") or ""
            if hints.strip():
                out.append(f"  Hints: {hints}")

    if header:
        out.append("=" * 60 + "")

    return "\n".join(out)


# ========= Example wiring (reference) =========
# Use this in your app code — shown here for completeness only.
#
# from miniscope.common.configurator import Configurator
# from miniscope.providers.provider import ModelProvider
# from .strict_planner import (
#     gather_specs_from_tool_definitions,
#     build_planning_models_from_mcp_specs,
#     build_planning_agent,
# )
#
# config = Configurator()
# config.load_client_env(); config.load_shared_env(); config.check_llm_env_vars()
# provider = ModelProvider(config)
# llm_signature = provider.llm_provider + ":" + provider.model_name
#
# tools_dict = await initialize_tools(config, token="session_token")  # your function
# specs = gather_specs_from_tool_definitions(tools_dict)
# ToolStep, Plan = build_planning_models_from_mcp_specs(specs)
# planner = build_planning_agent(llm_signature, planner_prompt, specs, Plan)
#
# result = await planner.run("Find this week’s calendar events and recent important emails.")
# print(result.output.model_dump_json(indent=2))
# assert validate_plan(result.output), "Plan failed structural validation"
