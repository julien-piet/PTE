"""
Execution agent: takes a ToolBasedResponse plan from planning_agent.py and
executes each step as a real HTTP call via curl (subprocess).

No swagger parsing is needed — all routing information is derived from the
plan itself. Base URL and authentication are injected at construction time.

After all steps complete, an LLM call synthesizes the raw API outputs into
a natural language answer to the user's original request.
"""

import asyncio
import json
import re
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union
from urllib.parse import quote, quote_plus

from pydantic import BaseModel
from pydantic_ai import Agent

from agent.auth import AuthProvider

class _ParsedValue(BaseModel):
    found: bool
    value: Union[str, int, float, bool, list, dict, None] = None
    reason: Optional[str] = None


class _MissingDependency(Exception):
    """Raised when a step cannot run because a dependency produced no extractable value."""

class _HttpError(Exception):
    """Raised when a curl call returns a non-2xx HTTP status."""
from agent.common.configurator import Configurator
from agent.planner import ExecutionContext
from agent.providers.provider import ModelProvider


@dataclass
class ExecutionResult:
    """Returned by ExecutionAgent.execute()."""
    outputs: Dict[str, Any]  # raw curl responses — use for JSON saving / {step_id.result} refs
    answer: str              # LLM-generated natural language answer to the original task


# ──────────────────────────────────────────────────────────────────────────────
# Execution agent
# ──────────────────────────────────────────────────────────────────────────────

class ExecutionAgent:
    """
    Executes a ToolBasedResponse plan step by step using curl.

    Steps that share no dependencies are run concurrently.
    Outputs from prior steps are substituted into later step arguments via
    {step_id.result} placeholders.

    After execution, an LLM synthesizes all API outputs into a final answer
    to the user's original task.

    Usage:
        registry = AuthRegistry.build_default("config/.server_env")
        agent = ExecutionAgent(auth=registry.get("gitlab"))
        result = await agent.execute(plan_response, task="Open an issue about dark mode")
        print(result.answer)
    """

    def __init__(self, auth: AuthProvider, base_url: str = "", debug: bool = False) -> None:
        self.base_url = base_url.rstrip("/")  # fallback if step has no base_url
        self.auth = auth
        self.debug = debug
        self.task_id: str = ""

        config = Configurator()
        config.load_all_env()
        provider = ModelProvider(config)
        self.llm = provider.get_llm_model_provider()

    def _debug(self, msg: str) -> None:
        if self.debug:
            print(f"[ExecutionAgent][DEBUG] {msg}")

    # ── Reference resolution ────────────────────────────────────────────────

    @staticmethod
    def _follow_accessor(obj: Any, accessor: str) -> Any:
        """Navigate a dot/bracket accessor chain into obj, e.g. '.default_branch' or '[0].id'."""
        for dot_key, bracket_idx in re.findall(r'\.(\w+)|\[(\d+)\]', accessor):
            if dot_key:
                if not isinstance(obj, dict):
                    return None
                obj = obj.get(dot_key)
            elif bracket_idx:
                if not isinstance(obj, list):
                    return None
                obj = obj[int(bracket_idx)]
            if obj is None:
                return None
        return obj

    def _resolve(self, value: Any, outputs: Dict[str, Any]) -> Any:
        """
        Recursively replace {step_id.result} placeholders with prior outputs.

        Follows any accessor chain after .result (e.g. {step_1.result.default_branch})
        by navigating into the stored value. Falls back to the stored value as-is if
        navigation fails or no accessor is present.
        """
        if isinstance(value, str):
            def _sub(m: re.Match) -> str:
                step_id, accessor = m.group(1), m.group(2)
                out = outputs.get(step_id)
                if out is None:
                    return m.group(0)  # leave unchanged if step not found
                # Follow accessor chain if present and the stored value is navigable
                if accessor and isinstance(out, (dict, list)):
                    navigated = self._follow_accessor(out, accessor)
                    if navigated is not None:
                        out = navigated
                return json.dumps(out) if isinstance(out, (dict, list)) else str(out)
            return re.sub(r"\{(\w+)\.result([^}]*)\}", _sub, value)
        if isinstance(value, dict):
            return {k: self._resolve(v, outputs) for k, v in value.items()}
        if isinstance(value, list):
            return [self._resolve(v, outputs) for v in value]
        return value

    # ── Curl command construction ────────────────────────────────────────────

    def _build_cmd(self, step, outputs: Dict[str, Any]) -> List[str]:
        tool_name = (
            step.tool_name.value
            if hasattr(step.tool_name, "value")
            else str(step.tool_name)
        )
        method, path_template = tool_name.split(" ", 1)
        method = method.upper()

        # Resolve all argument values (substituting {step_id.result} references)
        args: Dict[str, Any] = {
            arg.name: self._resolve(arg.value, outputs)
            for arg in step.arguments
        }

        # Detect path parameters from {name} tokens in the URL template
        path_param_names = set(re.findall(r"\{(\w+)\}", path_template))

        path_params: Dict[str, str] = {}
        query_params: Dict[str, Any] = {}
        body: Optional[Any] = None

        for name, value in args.items():
            if name in path_param_names:
                path_params[name] = str(value)
            elif name == "body" and isinstance(value, dict):
                # Explicit body object — use as-is
                body = value
            elif method in ("POST", "PUT", "PATCH"):
                # Non-path args for mutating methods → merge into JSON body
                if body is None:
                    body = {}
                if isinstance(body, dict):
                    body[name] = value
            else:
                # GET / DELETE → query string
                query_params[name] = value

        # Build final URL — step.base_url wins, fall back to init-time base_url
        step_base_url = getattr(step, "base_url", "").rstrip("/") or self.base_url
        path = path_template
        for pname, pval in path_params.items():
            path = path.replace(f"{{{pname}}}", quote(pval, safe=""))
        url = step_base_url + path
        if query_params:
            qs = "&".join(f"{k}={quote_plus(str(v))}" for k, v in query_params.items())
            url = f"{url}?{qs}"

        # Assemble curl command
        cmd = ["curl", "-s", "-X", method, "-H", "Content-Type: application/json"]
        for hname, hval in self.auth.get_headers().items():
            cmd += ["-H", f"{hname}: {hval}"]
        if body is not None:
            cmd += ["-d", json.dumps(body)]
        cmd.append(url)
        return cmd

    # ── Curl execution (blocking, runs in executor) ──────────────────────────

    def _run_curl(self, cmd: List[str]) -> Any:
        # Append -w "\n%{http_code}" so the status code appears on the last line
        cmd = cmd[:-1] + ["-w", "\n%{http_code}", cmd[-1]]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        output = result.stdout
        # Split off the status code line appended by -w
        *body_lines, status_line = output.rsplit("\n", 1)
        raw = "\n".join(body_lines).strip()
        status_code = int(status_line.strip()) if status_line.strip().isdigit() else 0

        try:
            body = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            body = raw

        # 304 Not Modified is treated as success: the resource is already in the
        # desired state (e.g. project already starred), so the operation is idempotent.
        if not (200 <= status_code < 300) and status_code != 304:
            raise _HttpError(
                f"HTTP {status_code}: {json.dumps(body) if isinstance(body, dict) else body}"
            )
        return body

    # ── Inter-step output parsing ────────────────────────────────────────────

    async def _parse_step_output(self, step, raw_output: Any, dependent_steps: list) -> Any:
        """
        After a step completes, ask the LLM to extract the specific value(s)
        that downstream steps actually need from the raw curl response.

        The parsed value is stored in ctx.step_outputs and is what gets
        substituted when downstream steps reference {step_id.result}.
        The full raw response is preserved separately for final answer generation.
        """
        tool_name = step.tool_name.value if hasattr(step.tool_name, "value") else str(step.tool_name)

        # Collect all {step_id.result...} accessor patterns used across dependent steps
        all_accessors: list[str] = []
        for ds in dependent_steps:
            for a in (ds.arguments or []):
                serialized = json.dumps(a.value) if isinstance(a.value, (dict, list)) else (a.value if isinstance(a.value, str) else "")
                all_accessors += re.findall(r"\{" + step.step_id + r"\.result[^}]*\}", serialized)

        # Describe what each dependent step needs from this result
        needs = []
        for ds in dependent_steps:
            ds_tool = ds.tool_name.value if hasattr(ds.tool_name, "value") else str(ds.tool_name)
            ref_args = [
                f"  - argument '{a.name}' (value: {json.dumps(a.value) if isinstance(a.value, (dict, list)) else a.value!r})"
                for a in (ds.arguments or [])
                if step.step_id in (json.dumps(a.value) if isinstance(a.value, (dict, list)) else (a.value if isinstance(a.value, str) else ""))
            ]
            hint = getattr(ds, "hints", "") or ""
            dep_desc = f"Step {ds.step_id} ({ds_tool}):"
            if ref_args:
                dep_desc += "\n" + "\n".join(ref_args)
            if hint:
                dep_desc += f"\n  Hint: {hint}"
            needs.append(dep_desc)

        # Build accessor guidance: tell the LLM exactly which field(s) to extract
        accessor_guidance = ""
        unique_accessors = list(dict.fromkeys(all_accessors))
        if unique_accessors:
            lines = []
            for acc in unique_accessors:
                # Extract the field path after .result (e.g. ".default_branch" → "default_branch")
                m = re.match(r"\{" + step.step_id + r"\.result\.?(.*)\}", acc)
                field_path = m.group(1) if m and m.group(1) else None
                if field_path:
                    lines.append(f"  '{acc}' → extract the value at field '{field_path}' (must be a scalar string/number, not an object)")
                else:
                    lines.append(f"  '{acc}' → extract the full value")
            accessor_guidance = "Accessor patterns used by dependent steps:\n" + "\n".join(lines) + "\n\n"

        prompt = (
            f"An API call just completed:\n"
            f"  {tool_name}\n\n"
            f"Raw response:\n{json.dumps(raw_output, indent=2) if isinstance(raw_output, (dict, list)) else raw_output}\n\n"
            f"The following steps depend on this result:\n" + "\n\n".join(needs) + "\n\n"
            + accessor_guidance
            + f"Extract the value(s) from the response that should be substituted for "
            f"{{{step.step_id}.result}} in the dependent steps above.\n\n"
            f"Rules:\n"
            f"- Always extract the most specific, deeply-nested scalar (string, number) when that is what the dependent step needs. Never return a wrapper object when a plain value suffices.\n"
            f"- If the dependent step needs a structured sub-object, return that object.\n"
            f"- If the dependent step uses the value as a path parameter and multiple values are needed, return a JSON array. The engine will call the step once per item.\n"
            f"- If the response is a list and only one specific item is needed, extract only that item or field.\n"
            f"- Set found=false only if the required value is genuinely absent from the response."
        )
        self._debug(f"Parsing output of {step.step_id}:\n{prompt}")
        agent = Agent(self.llm, output_type=_ParsedValue)
        try:
            result = await agent.run(prompt)
        except Exception as e:
            print(f"[ExecutionAgent] ✗ _parse_step_output LLM call failed for {step.step_id}: {type(e).__name__}: {e}")
            raise
        envelope = result.output
        self._debug(f"Parsed value for {step.step_id}: found={envelope.found} value={envelope.value!r}")

        if not envelope.found:
            self._debug(f"No value found for {step.step_id}: {envelope.reason} — storing None")
            return None

        return envelope.value

    async def _execute_step(self, step, ctx: ExecutionContext, plan: list, raw_outputs: Dict[str, Any]) -> None:
        tool_name = (
            step.tool_name.value
            if hasattr(step.tool_name, "value")
            else str(step.tool_name)
        )
        prefix = f"[task {self.task_id}]" if self.task_id else "[ExecutionAgent]"
        print(f"{prefix} → {step.step_id}: {tool_name}")
        try:
            loop = asyncio.get_event_loop()

            # Guard: if any argument references a prior step's output that could
            # not be extracted (stored as None), abort before making any curl call.
            for arg in (step.arguments or []):
                m = re.search(r"\{(\w+)\.result", str(arg.value))
                if m:
                    ref_id = m.group(1)
                    if ref_id in ctx.step_outputs and ctx.step_outputs[ref_id] is None:
                        raise _MissingDependency(
                            f"step '{ref_id}' produced no extractable value for argument '{arg.name}'"
                        )

            # Detect fan-out: if a path parameter resolves to a list, call the
            # step once per item and collect all results into a list.
            _, path_template = tool_name.split(" ", 1)
            path_param_names = set(re.findall(r"\{(\w+)\}", path_template))

            fan_out_ref_step: Optional[str] = None
            fan_out_values: Optional[List[Any]] = None
            for arg in (step.arguments or []):
                if arg.name in path_param_names:
                    # Check the raw stored output (not _resolve, which stringifies lists)
                    m = re.search(r"\{(\w+)\.result", str(arg.value))
                    ref_step_id = m.group(1) if m else None
                    raw_val = ctx.step_outputs.get(ref_step_id) if ref_step_id else None
                    if isinstance(raw_val, list):
                        fan_out_ref_step = ref_step_id
                        fan_out_values = raw_val
                        break

            if fan_out_values is not None:
                # Detect if multiple steps share the same fan-out source.
                # If so, distribute one item per step rather than each step
                # iterating all items independently.
                def _references_same_source(s) -> bool:
                    _, pt = (s.tool_name.value if hasattr(s.tool_name, "value") else str(s.tool_name)).split(" ", 1)
                    pp = set(re.findall(r"\{(\w+)\}", pt))
                    return any(
                        arg.name in pp and
                        re.search(r"\{(\w+)\.result", str(arg.value)) and
                        re.search(r"\{(\w+)\.result", str(arg.value)).group(1) == fan_out_ref_step
                        for arg in (s.arguments or [])
                    )

                fan_out_group = [s for s in plan if _references_same_source(s)]

                if len(fan_out_group) > 1:
                    # Distributed mode: this step handles exactly one item.
                    step_index = next(
                        (i for i, s in enumerate(fan_out_group) if s.step_id == step.step_id), 0
                    )
                    item = fan_out_values[step_index] if step_index < len(fan_out_values) else fan_out_values[-1]
                    print(f"[ExecutionAgent] Fan-out distributed for {step.step_id}: item {step_index + 1}/{len(fan_out_values)} (value={item})")
                    modified_outputs = dict(ctx.step_outputs)
                    modified_outputs[fan_out_ref_step] = item
                    cmd = self._build_cmd(step, modified_outputs)
                    self._debug(f"{step.step_id} curl command (item={item}):\n  " + " ".join(
                        f"'{p}'" if " " in p else p for p in cmd
                    ))
                    raw = await loop.run_in_executor(None, self._run_curl, cmd)
                else:
                    # Single fan-out step: iterate all items and collect results.
                    print(f"[ExecutionAgent] Fan-out detected for {step.step_id}: {len(fan_out_values)} item(s)")
                    all_results = []
                    for item in fan_out_values:
                        modified_outputs = dict(ctx.step_outputs)
                        modified_outputs[fan_out_ref_step] = item
                        cmd = self._build_cmd(step, modified_outputs)
                        self._debug(f"{step.step_id} curl command (item={item}):\n  " + " ".join(
                            f"'{p}'" if " " in p else p for p in cmd
                        ))
                        result = await loop.run_in_executor(None, self._run_curl, cmd)
                        all_results.append(result)
                    raw = all_results
            else:
                cmd = self._build_cmd(step, ctx.step_outputs)
                self._debug(f"{step.step_id} curl command:\n  " + " ".join(
                    f"'{p}'" if " " in p else p for p in cmd
                ))
                raw = await loop.run_in_executor(None, self._run_curl, cmd)

            self._debug(f"{step.step_id} response (2xx OK): {json.dumps(raw, indent=2) if isinstance(raw, (dict, list)) else raw}")

            # Always preserve the full raw response for final answer generation
            raw_outputs[step.step_id] = raw

            # If downstream steps reference this result, parse it down to what they need
            dependent_steps = [s for s in plan if step.step_id in (getattr(s, "depends_on", []) or [])]
            if dependent_steps:
                print(f"{prefix} Parsing {step.step_id} output for {len(dependent_steps)} dependent step(s)...")
                parsed = await self._parse_step_output(step, raw, dependent_steps)
                # Explicitly store None so the downstream guard can detect parse failure.
                ctx.step_outputs[step.step_id] = parsed
                ctx.mark_completed(step.step_id, parsed)
            else:
                ctx.mark_completed(step.step_id, raw)

            print(f"{prefix} ✓ {step.step_id} done")
        except _MissingDependency as e:
            ctx.mark_failed(step.step_id, str(e))
            print(f"{prefix} ✗ {step.step_id} skipped: {e}")
            raise
        except _HttpError as e:
            ctx.mark_failed(step.step_id, str(e))
            raw_outputs[step.step_id] = str(e)
            print(f"{prefix} ✗ {step.step_id} failed: {e}")
            raise
        except Exception as e:
            ctx.mark_failed(step.step_id, str(e))
            print(f"{prefix} ✗ {step.step_id} failed: {e}")
            raise

    # ── LLM answer generation ────────────────────────────────────────────────

    async def _generate_answer(self, task: str, plan, outputs: Dict[str, Any]) -> str:
        """
        Ask the LLM to answer the original task based on what was executed and returned.
        """
        steps_summary = []
        skipped_steps = []
        for step in plan:
            sid = step.step_id
            tool_name = step.tool_name.value if hasattr(step.tool_name, "value") else str(step.tool_name)
            if sid not in outputs:
                skipped_steps.append(f"Step {sid} ({tool_name}): skipped — earlier step failed")
            else:
                output = outputs[sid]
                steps_summary.append(
                    f"Step {sid} ({tool_name}):\n{json.dumps(output, indent=2) if isinstance(output, (dict, list)) else output}"
                )

        skipped_note = ""
        if skipped_steps:
            skipped_note = (
                "\n\nThe following steps did not complete (API error, missing resource, or unextractable upstream value):\n"
                + "\n".join(skipped_steps)
                + "\n"
            )

        prompt = (
            f"The user asked: {task}\n\n"
            f"The following API calls were made to fulfill this request:\n\n"
            + "\n\n".join(steps_summary or ["(no steps completed)"])
            + skipped_note
            + "\n\nBased on the above, provide a concise answer to the user's original request. "
            "If some steps were skipped, explain what could not be completed and why. "
            "Do not repeat raw JSON — describe the result in plain language."
        )
        self._debug(f"Answer generation prompt:\n{prompt}")
        agent = Agent(self.llm, output_type=str)
        result = await agent.run(prompt)
        answer = result.output
        self._debug(f"Answer: {answer}")
        return answer

    # ── Public entry point ───────────────────────────────────────────────────

    async def execute(self, plan_response, task: str = "") -> ExecutionResult:
        """
        Execute a ToolBasedResponse plan and generate a natural language answer.

        Args:
            plan_response: ToolBasedResponse returned by PlanningAgent.plan()
            task:          The original user request, used by the LLM to frame its answer.

        Returns:
            ExecutionResult with raw outputs (for saving/reference resolution)
            and a natural language answer to the original task.
        """
        plan = plan_response.plan
        ctx = ExecutionContext(plan)
        self.last_ctx = ctx
        self.last_raw_outputs: Dict[str, Any] = {}  # unmodified curl responses, used for final answer
        self.last_answer: str = ""
        raw_outputs = self.last_raw_outputs

        while not ctx.is_complete():
            ready = ctx.get_ready_steps()
            if not ready:
                remaining = [
                    s.step_id for s in plan if s.step_id not in ctx.completed_steps
                ]
                raise RuntimeError(
                    f"Plan stuck — no ready steps. Remaining: {remaining}"
                )

            for step_id in ready:
                ctx.mark_executing(step_id)

            steps_to_run = [s for s in plan if s.step_id in ready]
            try:
                await asyncio.gather(*[
                    self._execute_step(s, ctx, plan, raw_outputs) for s in steps_to_run
                ])
            except (_MissingDependency, _HttpError):
                # A step couldn't run (missing dependency or HTTP error).
                # Mark all remaining unstarted steps as skipped and stop here.
                tag = f"[task {self.task_id}]" if self.task_id else "[ExecutionAgent]"
                for s in plan:
                    if s.step_id not in ctx.completed_steps and s.step_id not in ctx.failed_steps:
                        ctx.mark_failed(s.step_id, "skipped due to earlier step failure")
                        print(f"{tag} ✗ {s.step_id} skipped (earlier step failed)")
                break

        tag = f"[task {self.task_id}]" if self.task_id else "[ExecutionAgent]"
        print(f"{tag} Generating answer...")
        answer = await self._generate_answer(task, plan, raw_outputs)
        self.last_answer = answer
        return ExecutionResult(outputs=raw_outputs, answer=answer)
