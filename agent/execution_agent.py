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
from typing import Any, Dict, List, Optional
from urllib.parse import quote, quote_plus

from pydantic_ai import Agent

from agent.auth import AuthProvider
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

        config = Configurator()
        config.load_all_env()
        provider = ModelProvider(config)
        self.llm = provider.get_llm_model_provider()

    def _debug(self, msg: str) -> None:
        if self.debug:
            print(f"[ExecutionAgent][DEBUG] {msg}")

    # ── Reference resolution ────────────────────────────────────────────────

    def _resolve(self, value: Any, outputs: Dict[str, Any]) -> Any:
        """
        Recursively replace {step_id.result} placeholders with prior outputs.

        Matches any {step_id.result...} expression regardless of accessor chain
        (e.g. {step_1.result}, {step_1.result[0].id}, {step_1.result.path}).
        The accessor chain is intentionally ignored because _parse_step_output
        already extracted the correct scalar/value and stored it in outputs.
        """
        if isinstance(value, str):
            def _sub(m: re.Match) -> str:
                out = outputs.get(m.group(1))
                if out is None:
                    return m.group(0)  # leave unchanged if step not found
                return json.dumps(out) if isinstance(out, (dict, list)) else str(out)
            return re.sub(r"\{(\w+)\.result[^}]*\}", _sub, value)
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

        if not (200 <= status_code < 300):
            raise RuntimeError(
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

        # Describe what each dependent step needs from this result
        needs = []
        for ds in dependent_steps:
            ds_tool = ds.tool_name.value if hasattr(ds.tool_name, "value") else str(ds.tool_name)
            ref_args = [
                f"  - argument '{a.name}' (value: {a.value!r})"
                for a in (ds.arguments or [])
                if isinstance(a.value, str) and step.step_id in a.value
            ]
            hint = getattr(ds, "hints", "") or ""
            dep_desc = f"Step {ds.step_id} ({ds_tool}):"
            if ref_args:
                dep_desc += "\n" + "\n".join(ref_args)
            if hint:
                dep_desc += f"\n  Hint: {hint}"
            needs.append(dep_desc)

        prompt = (
            f"An API call just completed:\n"
            f"  {tool_name}\n\n"
            f"Raw response:\n{json.dumps(raw_output, indent=2) if isinstance(raw_output, (dict, list)) else raw_output}\n\n"
            f"The following steps depend on this result:\n" + "\n\n".join(needs) + "\n\n"
            f"Extract the value(s) from the response that should be substituted for "
            f"{{{step.step_id}.result}} in the dependent steps above.\n"
            f"Rules:\n"
            f"- If a single scalar is needed (e.g. a project ID, a number), return just that value as plain text.\n"
            f"- If the dependent step needs a structured sub-object, return it as compact JSON.\n"
            f"- If the dependent step uses the value as a path parameter (e.g. /projects/{{id}}) and multiple values "
            f"are needed, return a JSON array (e.g. [1, 2, 3]). The engine will call the step once per item.\n"
            f"- If the response is a list and only one specific item is needed, extract only that item or field.\n"
            f"- Do NOT return the entire raw response. Return only the extracted value.\n"
            f"- Do NOT include any explanation."
        )
        self._debug(f"Parsing output of {step.step_id}:\n{prompt}")
        agent = Agent(self.llm, output_type=str)
        result = await agent.run(prompt)
        parsed = result.output.strip()
        self._debug(f"Parsed value for {step.step_id}: {parsed!r}")

        # Try to parse as JSON so structured values resolve cleanly
        try:
            return json.loads(parsed)
        except (json.JSONDecodeError, ValueError):
            return parsed

    async def _execute_step(self, step, ctx: ExecutionContext, plan: list, raw_outputs: Dict[str, Any]) -> None:
        tool_name = (
            step.tool_name.value
            if hasattr(step.tool_name, "value")
            else str(step.tool_name)
        )
        print(f"[ExecutionAgent] → {step.step_id}: {tool_name}")
        try:
            loop = asyncio.get_event_loop()

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
                print(f"[ExecutionAgent] Fan-out detected for {step.step_id}: {len(fan_out_values)} item(s)")
                all_results = []
                for item in fan_out_values:
                    modified_outputs = dict(ctx.step_outputs)
                    if fan_out_ref_step:
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
                print(f"[ExecutionAgent] Parsing {step.step_id} output for {len(dependent_steps)} dependent step(s)...")
                parsed = await self._parse_step_output(step, raw, dependent_steps)
                ctx.mark_completed(step.step_id, parsed)
            else:
                ctx.mark_completed(step.step_id, raw)

            print(f"[ExecutionAgent] ✓ {step.step_id} done")
        except Exception as e:
            ctx.mark_failed(step.step_id, str(e))
            print(f"[ExecutionAgent] ✗ {step.step_id} failed: {e}")
            raise

    # ── LLM answer generation ────────────────────────────────────────────────

    async def _generate_answer(self, task: str, plan, outputs: Dict[str, Any]) -> str:
        """
        Ask the LLM to answer the original task based on what was executed and returned.
        """
        steps_summary = []
        for step in plan:
            sid = step.step_id
            tool_name = step.tool_name.value if hasattr(step.tool_name, "value") else str(step.tool_name)
            output = outputs.get(sid, "no output")
            steps_summary.append(
                f"Step {sid} ({tool_name}):\n{json.dumps(output, indent=2) if isinstance(output, (dict, list)) else output}"
            )

        prompt = (
            f"The user asked: {task}\n\n"
            f"The following API calls were made to fulfill this request:\n\n"
            + "\n\n".join(steps_summary)
            + "\n\nBased on the API responses above, provide a concise answer to the user's original request. "
            "Focus on what was accomplished or what information was retrieved. "
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
        raw_outputs: Dict[str, Any] = {}  # unmodified curl responses, used for final answer

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
            await asyncio.gather(*[
                self._execute_step(s, ctx, plan, raw_outputs) for s in steps_to_run
            ])

        print("[ExecutionAgent] Generating answer...")
        answer = await self._generate_answer(task, plan, raw_outputs)
        return ExecutionResult(outputs=raw_outputs, answer=answer)
