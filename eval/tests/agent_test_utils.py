# eval/tests/agent_test_utils.py
#
# Shared utilities for agent integration tests (gitlab, shopping, and future servers).

from typing import Any, Dict, Optional


def serialize_plan(plan) -> list:
    """Serialize a plan to a JSON-serializable list of step dicts."""
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


def extract_agent_details(runner) -> Dict[str, Any]:
    """
    Extract plan, execution, and logging details from an AgentRunner instance.

    Returns a dict with keys:
        plan_steps      — serialized plan steps, or None
        parsed_outputs  — step_outputs from execution context, or None
        raw_execution   — last_raw_outputs from execution agent, or None
        planning_log    — last_run_log from planning agent, or None
    """
    plan_steps = None
    parsed_outputs = None
    raw_execution = None
    planning_log = None

    _agent = getattr(runner, "_agent", None)
    if _agent is not None:
        pr = getattr(_agent, "last_plan_response", None)
        if pr is not None:
            plan_steps = serialize_plan(pr.plan)
        pa = getattr(_agent, "planning_agent", None)
        if pa is not None:
            planning_log = getattr(pa, "last_run_log", None)
        ea = getattr(_agent, "execution_agent", None)
        if ea is not None:
            raw_execution = getattr(ea, "last_raw_outputs", None)
            ctx = getattr(ea, "last_ctx", None)
            if ctx is not None:
                parsed_outputs = getattr(ctx, "step_outputs", None)

    return {
        "plan_steps": plan_steps,
        "parsed_outputs": parsed_outputs,
        "raw_execution": raw_execution,
        "planning_log": planning_log,
    }


def task_status(passed: bool, error: Optional[str], plan_steps: Optional[list]) -> str:
    """Derive a status string consistent across all server test files."""
    if error:
        return "failed" if plan_steps is None else "execution_failed"
    if passed:
        return "success"
    return "execution_failed"
