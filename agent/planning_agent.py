"""
Planning agent: selects the appropriate swagger file(s), parses them with prance,
identifies the best API endpoints for a given task, and returns a full execution
plan in the planner.py ToolBasedResponse format.
"""

import json
import os
import re
from pathlib import Path
from typing import List

import prance
from pydantic import BaseModel
from pydantic_ai import Agent

from agent.common.configurator import Configurator
from agent.planner import build_agent_models, validate_plan
from agent.providers.provider import ModelProvider

_HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}

class EndpointInfo(BaseModel):
    api: str            # source swagger filename
    method: str         # GET, POST, etc.
    path: str           # /V1/carts/mine
    summary: str
    description: str
    parameters: list    # raw swagger parameter dicts
    response_schema: str = ""  # human-readable description of the 200 response shape
    base_path: str = ""  # swagger basePath (e.g. /api/v4) — path prefix, NOT host


class PlanningAgent:
    """
    Given a natural language task, selects the right swagger file(s) from
    api/index.json, parses them with prance (resolving all $refs),
    chooses the best endpoints via LLM, and builds a full execution plan.

    The LLM backend is resolved from config.yaml (agent_llm_provider /
    agent_llm_model) via ModelProvider, matching the pattern in agent_replan.py.

    Debug flags are auto off by default but can be enabled when initializing the agent to print the full LLM prompts and responses for each step. This is often helpful when developing new tasks or debugging failures.
    """

    def __init__(self, api_dir: str = "api", debug_prompts: bool = False, debug_responses: bool = False) -> None:
        self.api_dir = Path(api_dir)
        self.debug_prompts = debug_prompts
        self.debug_responses = debug_responses

        config = Configurator()
        config.load_all_env()
        provider = ModelProvider(config)
        self.llm = provider.get_llm_model_provider()

    def _debug_print(self, label: str, prompt: str = None, response: str = None) -> None:
        if prompt is not None and self.debug_prompts:
            print("\n" + "="*60)
            print(f"[PlanningAgent] {label} PROMPT:")
            print(prompt)
            print("="*60)
        if response is not None and self.debug_responses:
            print(f"\n[PlanningAgent] {label} RESPONSE:")
            print(response)
            print("="*60 + "\n")

    # ------------------------------------------------------------------
    # Step 1: load swagger index and api hints
    # ------------------------------------------------------------------
    def _load_index(self) -> dict:
        index_path = self.api_dir / "index.json"
        with open(index_path) as f:
            return json.load(f)

    def _load_hints(self) -> dict:
        hints_path = self.api_dir / "api_hints.json"
        if not hints_path.exists():
            return {}
        with open(hints_path) as f:
            raw = json.load(f)
        import importlib.util
        prompts_path = self.api_dir / "api_server_prompts.py"
        spec = importlib.util.spec_from_file_location("api_server_prompts", prompts_path)
        prompts = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(prompts)
        return {
            k: getattr(prompts, v, v)
            for k, v in raw.items()
        }

    # ------------------------------------------------------------------
    # Step 2: LLM picks which swagger file(s) to use
    # ------------------------------------------------------------------
    async def _select_api_files(self, task: str, index: dict) -> List[str]:
        api_list = "\n".join(f"- {fname}: {desc}" for fname, desc in index.items())
        prompt = (
            f'''Task: {task}

            Available API schema files:
            {api_list}

            Your job is to select the API schema file(s) that are most likely needed to complete the task.

            Before choosing files, internally think about:
            - what system the task refers to
            - which APIs would normally support that action
            - which filenames are most likely to contain those APIs

            Important rules:

            1. Do NOT assume the platform or service from the task wording alone.
            Example: "repository" does NOT automatically mean GitHub. It could refer to GitLab, Gitea, Bitbucket, or another system.

            2. Match the task to APIs by meaning, not by exact words.
            Consider synonyms and related concepts. For example:
            - repository ≈ project
            - pull request ≈ merge request
            - user account ≈ profile
            - cart ≈ basket
            - post ≈ submission
            - comment ≈ reply

            3. If the task appears unrelated to the API filenames, still check for conceptual matches.
            Many APIs expose similar functionality under different names.

            4. The concept lists below are high-level summaries and are NOT comprehensive.
            A task may still be supported by a schema even if the exact keywords do not appear.

            Do not reject a file simply because the task wording does not match the listed concepts.
            Match by meaning and related functionality.

            When uncertain, prefer selecting a plausibly relevant file rather than excluding it.
            Only return [] if you are confident that none of the schemas could possibly support the task.

            5. Multiple files may be required to complete the task. Select all that might contain relevant endpoints.

            Output format rules:

            - Respond with ONLY a JSON array of filenames on the first line.
            - Include explanations if no files are selected on the second line.

            Examples:
            ["shopping_api_schema.json"]

            ["gitlab_api_schema.json", "user_api_schema.json"]

            If no file is relevant:
            []
            Reason: The task is about checking the weather, which is unrelated to any of the available API schemas that focus on project management and e-commerce.
            '''
        )
        self._debug_print("_select_api_files", prompt=prompt)
        agent = Agent(self.llm, output_type=str)
        result = await agent.run(prompt)
        response = result.output
        self._debug_print("_select_api_files", response=response)
        match = re.search(r"\[.*?\]", response, re.DOTALL)
        selected: List[str] = json.loads(match.group() if match else response.strip())
        return [f for f in selected if f in index]

    # ------------------------------------------------------------------
    # Step 3: parse swagger file with prance
    # ------------------------------------------------------------------
    def _parse_swagger(self, filename: str) -> dict:
        filepath = (self.api_dir / filename).absolute()
        parser = prance.BaseParser(str(filepath), lazy=False)
        return parser.specification #PRINT

    # ------------------------------------------------------------------
    # Step 4: extract endpoints from resolved spec
    # ------------------------------------------------------------------
    def _extract_response_schema(self, spec: dict, operation: dict) -> str:
        """
        Return a brief human-readable description of the success response shape.
        Performs a single-level $ref lookup into spec["definitions"] to get
        property names — no recursion, so circular refs are not a problem.
        """
        responses = operation.get("responses", {})
        ok = responses.get("200") or responses.get("201")
        if not isinstance(ok, dict):
            return ""

        description = ok.get("description", "")
        schema = ok.get("schema")

        _GENERIC = {"successful", "success", "ok", "200", "201", "no content", "accepted"}

        if not isinstance(schema, dict):
            # No schema — show description only if it's not a generic HTTP phrase
            return description if description.lower().rstrip(".") not in _GENERIC else ""

        def _resolve_ref(ref: str) -> dict:
            if ref.startswith("#/definitions/"):
                def_name = ref.split("/definitions/", 1)[-1]
                return spec.get("definitions", {}).get(def_name, {})
            return {}

        def _collect_props(definition: dict, max_props: int = 12) -> list:
            """Collect property names, including those inside allOf compositions."""
            props = list(definition.get("properties", {}).keys())
            for sub in definition.get("allOf", []):
                if isinstance(sub, dict) and "$ref" not in sub:
                    props.extend(sub.get("properties", {}).keys())
            return props[:max_props]

        def _props_str(schema_obj: dict) -> str:
            """Return 'TypeName{field1, field2, ...}' for a schema object, or '' if unresolvable."""
            ref = schema_obj.get("$ref", "")
            if ref:
                def_name = ref.split("/definitions/", 1)[-1]
                definition = _resolve_ref(ref)
                props = _collect_props(definition)
                return f"{def_name}{{{', '.join(props)}}}" if props else def_name
            if schema_obj.get("type") == "array":
                inner = _props_str(schema_obj.get("items", {}))
                return f"[{inner}]" if inner else ""
            props = _collect_props(schema_obj)
            return f"{{{', '.join(props)}}}" if props else ""

        shape = _props_str(schema)
        if shape:
            return shape
        # Schema present but unresolvable — fall back to description if meaningful
        return description if description.lower().rstrip(".") not in _GENERIC else ""

    def _extract_endpoints(self, spec: dict, api_name: str) -> List[EndpointInfo]:
        base_path = spec.get("basePath", "").rstrip("/")

        endpoints: List[EndpointInfo] = []
        for path, path_item in spec.get("paths", {}).items():
            if not isinstance(path_item, dict):
                continue
            for method, operation in path_item.items():
                if method.lower() not in _HTTP_METHODS:
                    continue
                if not isinstance(operation, dict):
                    continue
                # Filter out any unresolved $ref parameter entries
                raw_params = operation.get("parameters", [])
                params = [p for p in raw_params if isinstance(p, dict) and "$ref" not in p]
                endpoints.append(EndpointInfo(
                    api=api_name,
                    method=method.upper(),
                    path=path,
                    summary=operation.get("summary", ""),
                    description=operation.get("description", ""),
                    parameters=params,
                    response_schema=self._extract_response_schema(spec, operation),
                    base_path=base_path,
                ))
        return endpoints

    # ------------------------------------------------------------------
    # Step 5b: LLM selects the best endpoints for the task
    # Returns (selected_endpoints, capabilities) where capabilities is a
    # list of human-readable strings describing what each endpoint provides.
    # ------------------------------------------------------------------
    async def _select_endpoints(self, task: str, endpoints: List[EndpointInfo]):
        candidates = endpoints
        endpoint_list = "\n".join(
            f"{i}. {ep.method} {ep.path} [{ep.api}] — {ep.summary}"
            for i, ep in enumerate(candidates)
        )

        # Inject per-API hints for whichever schemas are in play
        hints = self._load_hints()
        api_files_used = {ep.api for ep in candidates}
        relevant_hints = [
            f"[ {fname} ]\n{hints[fname]}"
            for fname in api_files_used
            if fname in hints
        ]
        api_hints_section = (
            "\nAPI context (use to understand data models and identifier types):\n"
            + "\n\n".join(relevant_hints) + "\n"
            if relevant_hints else ""
        )

        prompt = (
            f"Task: {task}\n\n"
            f"Available endpoints:\n{endpoint_list}\n\n"
            + api_hints_section + "\n"
            "Select the minimal set of endpoints needed to complete this task.\n\n"
            "Rules:\n"
            "1. Identify the final goal endpoint (the one that performs the task's main action).\n"
            "2. Check what required inputs that endpoint needs.\n"
            "3. If any required input is not directly stated in the task (e.g. a numeric ID when only a name is given), "
            "add a resolver endpoint that can provide it.\n"
            "4. Work backwards until every required input is either from the task or from a prior endpoint's output.\n"
            "5. Do NOT choose a goal endpoint if one of its required inputs still needs a lookup.\n"
            "6. Only include endpoints that are necessary — no extras.\n\n"
            "For each selected endpoint, describe in one sentence what it provides to the chain "
            "(e.g. 'provides numeric project_id needed by the next step').\n\n"
            "Do NOT decide exact argument values or enum choices here — that is handled later.\n\n"
            'Respond with ONLY valid JSON:\n'
            '{"selected_indices": [0, 2], "capabilities": ["resolves username to user_id", "creates the repository"], "reasoning": "brief"}'
        )
        self._debug_print("_select_endpoints", prompt=endpoint_list) #super long list of endpoints
        # self._debug_print("_select_endpoints", prompt=prompt) #super long list of endpoints with prompt
        agent = Agent(self.llm, output_type=str)
        result = await agent.run(prompt)
        response = result.output
        self._debug_print("_select_endpoints", response=response)
        decoder = json.JSONDecoder()
        data = None
        for i, ch in enumerate(response):
            if ch == '{':
                try:
                    data, _ = decoder.raw_decode(response, i)
                    break
                except json.JSONDecodeError:
                    continue
        if data is None:
            data = json.loads(response.strip())
        indices: List[int] = data.get("selected_indices", [])
        capabilities: List[str] = data.get("capabilities", [])
        selected = [candidates[i] for i in indices if 0 <= i < len(candidates)]
        return selected, capabilities

    # ------------------------------------------------------------------
    # Step 5c: Read current-user context from env vars for the APIs in use
    # ------------------------------------------------------------------
    def _get_user_context(self, api_files: set) -> str:
        """
        Return a prompt section describing the current user's identity for each
        API that is in scope.  Values come from env vars already loaded by
        load_all_env() in __init__.
        """
        # Maps a schema filename fragment → (label, list of (var_name, human_label))
        API_ENV_MAP = {
            "gitlab": ("GitLab", [
                # ("GITLAB_DOMAIN",   "server URL"),
                ("GITLAB_USERNAME", "username"),
            ]),
            "reddit": ("Reddit", [
                # ("REDDIT_DOMAIN",   "server URL"),
                ("REDDIT_USERNAME", "username"),
            ]),
            "shopping": ("Shopping", [
            #     ("WEBARENA_BASE_URL", "server URL"),
                ("SHOPPING_USERNAME", "username"),
            ]),
        }

        lines = []
        for fragment, (label, var_defs) in API_ENV_MAP.items():
            if not any(fragment in f.lower() for f in api_files):
                continue
            entries = []
            for var_name, human_label in var_defs:
                val = os.environ.get(var_name)
                if val:
                    entries.append(f"  - {human_label}: {val}")
            if entries:
                lines.append(f"{label}:\n" + "\n".join(entries))

        if not lines:
            return ""
        return (
            "\nCurrent user context (use these values directly (if needed) for tasks that contain me/mine/my etc.):\n"
            + "\n".join(lines) + "\n"
        )

    # ------------------------------------------------------------------
    # Step 6: LLM builds a full execution plan
    # ------------------------------------------------------------------
    async def _build_plan(self, task: str, selected: List[EndpointInfo], capabilities: List[str] = None):
        tool_names = [f"{ep.method} {ep.path}" for ep in selected]
        bundle = build_agent_models(tool_names)

        # Build a detailed endpoint reference including allowed values for params
        details = []
        for ep in selected:
            params = []
            for p in ep.parameters:
                if isinstance(p, dict):
                    pname = p.get("name", "")
                    pin = p.get("in", "")
                    required = p.get("required", False)
                    ptype = p.get("type", "")
                    pdesc = p.get("description", "")
                    enums = p.get("enum", [])
                    line = f"  - {pname} (in={pin}, required={required}, type={ptype})"
                    if enums:
                        line += f", allowed values: {enums}"
                    if pdesc:
                        line += f"\n    description: {pdesc}"
                    params.append(line)
            param_str = "\n".join(params) if params else "  (none)"
            entry = (
                f"{ep.method} {ep.path}\n"
                f"Summary: {ep.summary}\n"
                f"Parameters:\n{param_str}"
            )
            if ep.response_schema:
                entry += f"\nReturns: {ep.response_schema}"
            details.append(entry)
        endpoint_details = "\n\n".join(details)
        schema = json.dumps(bundle.ToolBasedResponse.model_json_schema(), indent=2)

        hints = self._load_hints()
        api_files_used = {ep.api for ep in selected}
        relevant_hints = [
            f"[ {fname} ]\n{hints[fname]}"
            for fname in api_files_used
            if fname in hints
        ]
        api_hints_section = (
            "\nAPI-specific parameter rules (apply these before building the plan):\n"
            + "\n\n".join(relevant_hints) + "\n"
            if relevant_hints else ""
        )

        capabilities_section = ""
        if capabilities:
            cap_lines = "\n".join(
                f"  {i+1}. {tool_names[i] if i < len(tool_names) else '?'}: {cap}"
                for i, cap in enumerate(capabilities)
            )
            capabilities_section = f"\nEndpoint roles in the plan:\n{cap_lines}\n"

        user_context_section = self._get_user_context(api_files_used)

        prompt = (
            f"Task: {task}\n\n"
            f"Available API endpoints:\n{endpoint_details}\n\n"
            + capabilities_section
            + user_context_section
            + api_hints_section + "\n"
            "Build a step-by-step execution plan to complete this task.\n"
            "Steps can depend on each other using depends_on and reference prior outputs with '{step_id.result}'.\n\n"
            f"Respond with ONLY valid JSON matching this schema:\n{schema}\n\n"
            "Rules:\n"
            "- tool_call_required must be true\n"
            '- response must be empty string ""\n'
            '- Each step needs a unique step_id (e.g. "step_1", "step_2")\n'
            f"- tool_name must be EXACTLY one of: {json.dumps(tool_names)}\n"
            "  Do NOT substitute actual IDs or path values into tool_name — keep template placeholders like {{id}} as-is.\n"
            "  Path parameters (e.g. id='a11yproject/myrepo') go in the arguments list, NOT in tool_name.\n"
            "- arguments is a list of {name, value, value_type} objects\n"
            '- value_type is "literal" for known values, "reference" for {step_id.result} placeholders\n'
            "- CRITICAL: argument names must ONLY be parameter names explicitly listed in the endpoint's schema above. "
            "Never invent or guess parameter names. If a parameter name is not in the schema, the task cannot be done with that endpoint.\n\n"
            "Argument sourcing — every argument value must come from exactly one of:\n"
            "  - 'literal': the value is a documented constant for that parameter\n"
            "  - 'reference': the value comes from a prior step's output via {step_id.result}\n\n"
            "Closed-enum rule:\n"
            "- If a parameter lists allowed values (in its description), treat that list as CLOSED.\n"
            "- ONLY use exact listed values — do not invent, paraphrase, or substitute.\n"
            "- If the task requires an operation not expressible with documented values, use the nearest valid value "
            "and add a post_processing instruction on that step to perform the remaining filtering/sorting.\n\n"
            "Free-string parameter rule:\n"
            "- If a parameter is a free string (no enum, no documented example values), do NOT invent a value for it. "
            "Only include it if: (a) the task explicitly states the exact value, or (b) a prior step's output supplies it, or (c) you can look it up via another API endpoint first. "
            "If none of these apply and the parameter is optional, omit it entirely. "
            # "Do not guess values like 'blank', 'html', 'default', etc. for parameters whose valid values are not documented.\n\n"
            "Post-processing:\n"
            "- If the API cannot fully satisfy the task (e.g. unsupported sort order), retrieve with valid params "
            "and describe the remaining client-side operation in the step's post_processing field.\n"
        )
        self._debug_print("_build_plan", prompt=prompt)
        agent = Agent(self.llm, output_type=str)
        result = await agent.run(prompt)
        response = result.output
        self._debug_print("_build_plan", response=response)
        decoder = json.JSONDecoder()
        data = None
        for i, ch in enumerate(response):
            if ch == '{':
                try:
                    data, _ = decoder.raw_decode(response, i)
                    break
                except json.JSONDecodeError:
                    continue
        if data is None:
            data = json.loads(response.strip())
        plan_result = bundle.ToolBasedResponse(**data)
        if not validate_plan(plan_result.plan):
            raise ValueError(f"LLM produced an invalid plan. Raw response:\n{response}")

        # Inject response_schema and api source (used at runtime for base_url routing)
        # into each step using the tool_name → EndpointInfo mapping from the swagger spec.
        # base_url is NOT baked from swagger here — it is injected at runtime by Agent
        # from the servers dict passed to initialize() / run_task().
        endpoint_map = {f"{ep.method} {ep.path}": ep for ep in selected}
        _fallback = EndpointInfo(api="", method="", path="", summary="", description="", parameters=[])
        annotated_steps = [
            step.model_copy(update={
                "returns": endpoint_map.get(
                    step.tool_name.value if hasattr(step.tool_name, "value") else str(step.tool_name),
                    _fallback,
                ).response_schema,
                "base_url": "|".join([
                    endpoint_map.get(
                        step.tool_name.value if hasattr(step.tool_name, "value") else str(step.tool_name),
                        _fallback,
                    ).api,
                    endpoint_map.get(
                        step.tool_name.value if hasattr(step.tool_name, "value") else str(step.tool_name),
                        _fallback,
                    ).base_path,
                ]),  # "api_filename|/base/path" routing tag; replaced with real URL by Agent
            })
            for step in plan_result.plan
        ]
        return plan_result.model_copy(update={"plan": annotated_steps})

    # ------------------------------------------------------------------
    # Step 7: Validate the plan for semantic correctness
    # Checks: reference validity, closed-enum compliance, source provenance
    # ------------------------------------------------------------------
    async def _validate_plan(self, plan_result, selected: List[EndpointInfo]) -> None:
        """
        Validate the produced plan for semantic correctness beyond structural checks.
        Raises ValueError with a description of all violations found.
        """
        plan = plan_result.plan
        endpoint_map = {
            (ep.method + " " + ep.path): ep for ep in selected
        }

        errors = []
        step_ids_seen = []

        for step in plan:
            tool_name = step.tool_name.value if hasattr(step.tool_name, "value") else str(step.tool_name)
            ep = endpoint_map.get(tool_name)
            param_map = {}
            if ep:
                for p in ep.parameters:
                    if isinstance(p, dict) and p.get("name"):
                        param_map[p["name"]] = p

            for arg in (step.arguments or []):
                aname = arg.name
                avalue = arg.value
                atype = arg.value_type

                # 1. Reference validity: {step_id.result} must refer to a prior step
                if atype == "reference":
                    import re as _re
                    refs = _re.findall(r'\{(\w+)\.result\}', str(avalue))
                    for ref_id in refs:
                        if ref_id not in step_ids_seen:
                            errors.append(
                                f"Step '{step.step_id}', arg '{aname}': references '{ref_id}.result' "
                                f"but '{ref_id}' has not appeared yet in the plan."
                            )

                # 2. Closed-enum compliance for literal values
                if atype == "literal" and aname in param_map:
                    param_def = param_map[aname]
                    allowed = param_def.get("enum")
                    if allowed and avalue not in allowed:
                        errors.append(
                            f"Step '{step.step_id}', arg '{aname}': value {avalue!r} is not in "
                            f"the documented allowed values {allowed}."
                        )

            step_ids_seen.append(step.step_id)

        if errors:
            raise ValueError("Plan validation failed:\n" + "\n".join(f"  - {e}" for e in errors))

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    async def plan(self, task: str):
        """
        Given a natural language task, select the appropriate swagger file(s),
        parse them with prance, select the best API endpoints, and return a
        ToolBasedResponse containing a validated execution plan.
        """
        index = self._load_index()

        selected_files = await self._select_api_files(task, index)
        if not selected_files:
            raise ValueError(f"No suitable API file found for task: {task!r}")

        all_endpoints: List[EndpointInfo] = []
        for fname in selected_files:
            spec = self._parse_swagger(fname)
            all_endpoints.extend(self._extract_endpoints(spec, fname))

        if not all_endpoints:
            raise ValueError("No endpoints extracted from selected swagger files.")

        selected_endpoints, capabilities = await self._select_endpoints(task, all_endpoints)
        if not selected_endpoints:
            raise ValueError("LLM selected no endpoints for this task.")

        plan_result = await self._build_plan(task, selected_endpoints, capabilities)

        await self._validate_plan(plan_result, selected_endpoints)

        return plan_result
