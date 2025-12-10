# agent_models_and_helpers.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Sequence, Set, Tuple, Union

from typing_extensions import Annotated
from pydantic import BaseModel, Field


# =======================
# Small internal utilities
# =======================
def _tool_name_str(tn: Any) -> str:
    """Return a printable tool name from Enum or str."""
    return tn.value if isinstance(tn, Enum) else str(tn)

def _abbr(v: Any, max_len: int = 50) -> str:
    s = str(v)
    return s if len(s) <= max_len else s[:max_len] + "…"


# =======================
# Public bundle container
# =======================
@dataclass(frozen=True)
class AgentModelBundle:
    """A convenience container for runtime-generated types."""
    Argument: type[BaseModel]
    ExecutionStep: type[BaseModel]
    DirectResponse: type[BaseModel]
    ToolBasedResponse: type[BaseModel]
    AgentResponse: Any  # Annotated[Union[..., ...], Field(discriminator=...)]
    ToolEnum: type[Enum]


# =======================
# Model factory (Option 1)
# =======================
def build_agent_models(allowed_tools: Sequence[str]) -> AgentModelBundle:
    """
    Build a runtime-constrained ToolEnum and the associated Pydantic models.

    Parameters
    ----------
    allowed_tools : Sequence[str]
        The exact set of tool names that are valid at runtime.

    Returns
    -------
    AgentModelBundle
        A bundle containing all generated classes, including ToolEnum and AgentResponse.
    """
    if not allowed_tools:
        raise ValueError("allowed_tools must be a non-empty sequence")

    # Preserve order and uniqueness
    uniq = list(dict.fromkeys(allowed_tools))
    ToolEnum = Enum("ToolEnum", {name: name for name in uniq})

    class Argument(BaseModel):
        name: str = Field(description="Name of the argument parameter")
        value: Union[str, int, float, bool, dict, list] = Field(
            description="Value of the argument. Can be a literal value or placeholder like '{step_1.result}'"
        )
        value_type: str = Field(
            default="literal",
            description="Type of value: 'literal' for direct values, 'reference' for dependency references"
        )

    class ExecutionStep(BaseModel):
        step_id: str = Field(description="Unique identifier for this step")
        tool_name: ToolEnum = Field(description="Name of the tool to execute (one of the allowed tools)")
        arguments: List[Argument] = Field(
            default_factory=list,
            description="List of arguments with name-value mappings",
        )
        depends_on: List[str] = Field(
            default_factory=list,
            description="List of step_ids that must complete before this step. Empty if no dependencies.",
        )
        hints: str = Field(
            default="",
            description="Instructions for how to use outputs from dependent steps to fill arguments during replanning",
        )

    class DirectResponse(BaseModel):
        tool_call_required: Literal[False]
        response: str = Field(min_length=1, description="Direct answer to user query")
        plan: None = None

    class ToolBasedResponse(BaseModel):
        tool_call_required: Literal[True]
        response: Literal[""] = ""  # Must be empty string
        plan: List[ExecutionStep] = Field(
            min_length=1,
            description="Execution plan with at least one step"
        )

    AgentResponse = Annotated[
        Union[DirectResponse, ToolBasedResponse],
        Field(discriminator="tool_call_required")
    ]

    return AgentModelBundle(
        Argument=Argument,
        ExecutionStep=ExecutionStep,
        DirectResponse=DirectResponse,
        ToolBasedResponse=ToolBasedResponse,
        AgentResponse=AgentResponse,
        ToolEnum=ToolEnum,
    )


# ==========================================
# Plan validation, readiness, and pretty-prints
# ==========================================
def explain_plan_errors(plan: List["BaseModel"]) -> Tuple[bool, Optional[str]]:
    """
    Validate the plan and return (ok, error_message).
    error_message is None if ok is True.
    """
    if plan is None:
        return False, "Plan is None"
    if not isinstance(plan, list):
        return False, "Plan must be a list"
    if len(plan) == 0:
        return True, None  # empty plan is allowed

    # Collect IDs and basic checks
    step_ids: List[str] = []
    for idx, step in enumerate(plan):
        sid = getattr(step, "step_id", None)
        if not sid:
            return False, f"Step at index {idx} is missing step_id"
        if not getattr(step, "tool_name", None):
            return False, f"Step '{sid}' missing tool_name"
        step_ids.append(sid)

    # Duplicate step IDs
    seen: Set[str] = set()
    for sid in step_ids:
        if sid in seen:
            return False, f"Duplicate step_id detected: '{sid}'"
        seen.add(sid)

    # Dependency references
    id_set = set(step_ids)
    for step in plan:
        sid = step.step_id
        for dep in getattr(step, "depends_on", []) or []:
            if dep not in id_set:
                return False, f"Step '{sid}' depends on unknown step_id '{dep}'"
            if dep == sid:
                return False, f"Step '{sid}' cannot depend on itself"

    # Cycle detection via DFS
    from collections import defaultdict
    graph = defaultdict(list)
    for step in plan:
        for dep in getattr(step, "depends_on", []) or []:
            graph[dep].append(step.step_id)

    visited: Set[str] = set()
    rec_stack: Set[str] = set()

    def has_cycle(node: str) -> bool:
        if node in rec_stack:
            return True
        if node in visited:
            return False
        visited.add(node)
        rec_stack.add(node)
        for nei in graph.get(node, []):
            if has_cycle(nei):
                return True
        rec_stack.remove(node)
        return False

    for sid in step_ids:
        if sid not in visited and has_cycle(sid):
            return False, "Cycle detected in plan dependencies"

    return True, None


def validate_plan(plan: List["BaseModel"]) -> bool:
    """Boolean wrapper around explain_plan_errors."""
    ok, _ = explain_plan_errors(plan)
    return ok


def get_ready_steps(
    plan: List["BaseModel"], 
    completed_steps: Set[str], 
    executing_steps: Set[str]
) -> List[str]:
    """
    Return step_ids that are ready to execute (all deps completed, not done/executing).
    """
    ready = []
    for step in plan:
        sid = step.step_id
        if sid in completed_steps or sid in executing_steps:
            continue
        deps = getattr(step, "depends_on", []) or []
        if all(dep in completed_steps for dep in deps):
            ready.append(sid)
    return ready


def pretty_print_plan(
    plan: List["BaseModel"],
    *,
    show_hints: bool = True,
    max_value_len: int = 50,
    header: bool = True
) -> str:
    """Human-friendly rendering of a plan; supports Enum tool_name."""
    if not plan:
        return "No execution steps in plan"

    lines: List[str] = []
    if header:
        lines.append("\n" + "=" * 60)
        lines.append("EXECUTION PLAN")
        lines.append("=" * 60)

    for i, step in enumerate(plan, 1):
        tn = _tool_name_str(getattr(step, "tool_name", ""))
        lines.append(f"\nStep {i}: {step.step_id}")
        lines.append(f"  Tool: {tn}")

        # Arguments
        args = getattr(step, "arguments", []) or []
        if args:
            lines.append("  Arguments:")
            for arg in args:
                name = getattr(arg, "name", "<unnamed>")
                v = getattr(arg, "value", None)
                vt = getattr(arg, "value_type", "literal")
                lines.append(f"    - {name}: {_abbr(v, max_value_len)} ({vt})")
        else:
            lines.append("  Arguments: None")

        # Dependencies
        deps = getattr(step, "depends_on", []) or []
        if deps:
            lines.append("  Depends on: " + ", ".join(deps))
        else:
            lines.append("  Depends on: None (can execute immediately)")

        # Hints
        hints = getattr(step, "hints", "")
        if show_hints and hints:
            lines.append(f"  Hints: {hints}")

    if header:
        lines.append("=" * 60 + "\n")

    return "\n".join(lines)


def pretty_print_layers(plan: List["BaseModel"]) -> str:
    """
    Show parallelizable 'layers' using Kahn's algorithm (topological levels).
    """
    if not plan:
        return "No execution steps in plan"

    from collections import defaultdict, deque

    indeg = {s.step_id: 0 for s in plan}
    adj = defaultdict(list)
    by_id = {s.step_id: s for s in plan}

    for s in plan:
        for d in getattr(s, "depends_on", []) or []:
            adj[d].append(s.step_id)
            indeg[s.step_id] += 1

    q = deque([sid for sid, d in indeg.items() if d == 0])
    layers: List[List[str]] = []
    while q:
        layer = list(q)
        layers.append(layer)
        for _ in range(len(layer)):
            u = q.popleft()
            for v in adj[u]:
                indeg[v] -= 1
                if indeg[v] == 0:
                    q.append(v)

    out = ["\nExecution Layers (parallelizable groups):"]
    for i, layer in enumerate(layers, 1):
        out.append(f"\nLayer {i}:")
        for sid in layer:
            tn = _tool_name_str(getattr(by_id[sid], "tool_name", ""))
            out.append(f"  - {sid}  [{tn}]")
    return "\n".join(out)


# =======================
# ExecutionContext (Enum-safe)
# =======================
class ExecutionContext:
    """
    Encapsulates execution state tracking for a plan.
    Manages completed steps, executing steps, outputs, and summaries.
    """

    def __init__(self, plan: List["BaseModel"]):
        self.plan = plan
        self.completed_steps: Set[str] = set()
        self.executing_steps: Set[str] = set()
        self.step_outputs: Dict[str, Any] = {}
        self.tool_summaries: List[str] = []

    def mark_executing(self, step_id: str) -> None:
        self.executing_steps.add(step_id)

    def mark_completed(self, step_id: str, output: Any = None) -> None:
        self.executing_steps.discard(step_id)
        self.completed_steps.add(step_id)
        if output is not None:
            self.step_outputs[step_id] = output

    def mark_failed(self, step_id: str, error: str) -> None:
        self.executing_steps.discard(step_id)
        # self.completed_steps.add(step_id)
        self.step_outputs[step_id] = f"Error: {error}"

    def add_summary(self, summary: str) -> None:
        self.tool_summaries.append(summary)

    def get_ready_steps(self) -> List[str]:
        ready = []
        for step in self.plan:
            sid = step.step_id
            if sid in self.completed_steps or sid in self.executing_steps:
                continue
            deps = getattr(step, "depends_on", []) or []
            if all(dep in self.completed_steps for dep in deps):
                ready.append(sid)
        return ready

    def get_step_output(self, step_id: str) -> Any:
        return self.step_outputs.get(step_id)

    def is_complete(self) -> bool:
        return len(self.completed_steps) == len(self.plan)

    def get_progress(self) -> str:
        total = len(self.plan)
        completed = len(self.completed_steps)
        executing = len(self.executing_steps)
        return f"{completed}/{total} completed, {executing} executing"