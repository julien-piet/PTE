"""
Planning agent: selects the appropriate swagger file(s), parses them with prance,
identifies the best API endpoints for a given task, and returns a full execution
plan in the planner.py ToolBasedResponse format.
"""

import json
import os
import re
from pathlib import Path
from typing import List, Optional, Union

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


class ChainStep(BaseModel):
    endpoint: EndpointInfo
    capability: str
    satisfies_param: str = ""        # which param in the next chain step this step's output satisfies
    literal_args: dict = {}          # {param_name: value} directly from the task
    foreach: Union[str, List, None] = None  # literal list or "step_N.result[*].field" reference


class PlanningAgent:
    """
    Given a natural language task, selects the right swagger file(s) from
    api/index.json, parses them with prance (resolving all $refs),
    chooses the best endpoints via LLM, and builds a full execution plan.

    The LLM backend is resolved from config.yaml (agent_llm_provider /
    agent_llm_model) via ModelProvider, matching the pattern in agent_replan.py.

    Debug flags are auto off by default but can be enabled when initializing the agent to print
    the full LLM prompts and responses for each step.
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
            print("\n" + "=" * 60)
            print(f"[PlanningAgent] {label} PROMPT:")
            print(prompt)
            print("=" * 60)
        if response is not None and self.debug_responses:
            print(f"\n[PlanningAgent] {label} RESPONSE:")
            print(response)
            print("=" * 60 + "\n")

    async def _run_llm(self, label: str, prompt: str) -> str:
        self._debug_print(label, prompt=prompt)
        if self.debug_prompts or self.debug_responses:
            print(f"[PlanningAgent] {label} calling LLM (prompt length: {len(prompt)} chars)...")
        agent = Agent(self.llm, output_type=str)
        try:
            result = await agent.run(prompt)
        except Exception as exc:
            cause = getattr(exc, "__cause__", None)
            print(f"\n[PlanningAgent] {label} LLM ERROR: {type(exc).__name__}: {exc}"
                  + (f"\n  caused by: {type(cause).__name__}: {cause}" if cause else ""))
            raise
        response = result.output
        self._debug_print(label, response=response)
        return response

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

    def _build_hints_section(self, endpoints: List[EndpointInfo], header: str = "API context") -> str:
        hints = self._load_hints()
        api_files_used = {ep.api for ep in endpoints}
        relevant_hints = [
            f"[ {fname} ]\n{hints[fname]}"
            for fname in api_files_used
            if fname in hints
        ]
        if not relevant_hints:
            return ""
        return f"\n{header}:\n" + "\n\n".join(relevant_hints) + "\n"

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
        response = await self._run_llm("_select_api_files", prompt)
        decoder = json.JSONDecoder()
        selected = None
        for i, ch in enumerate(response):
            if ch == "[":
                try:
                    selected, _ = decoder.raw_decode(response, i)
                    break
                except json.JSONDecodeError:
                    continue
        if selected is None:
            selected = json.loads(response.strip())
        return [f for f in selected if f in index]

    # ------------------------------------------------------------------
    # Step 3: parse swagger file with prance
    # ------------------------------------------------------------------
    def _parse_swagger(self, filename: str) -> dict:
        filepath = (self.api_dir / filename).absolute()
        parser = prance.BaseParser(str(filepath), lazy=False)
        return parser.specification

    # ------------------------------------------------------------------
    # Step 4: extract endpoints from resolved spec
    # ------------------------------------------------------------------
    def _extract_response_schema(self, spec: dict, operation: dict) -> str:
        responses = operation.get("responses", {})
        ok = responses.get("200") or responses.get("201")
        if not isinstance(ok, dict):
            return ""

        description = ok.get("description", "")
        schema = ok.get("schema")

        _GENERIC = {"successful", "success", "ok", "200", "201", "no content", "accepted"}

        if not isinstance(schema, dict):
            return description if description.lower().rstrip(".") not in _GENERIC else ""

        def _resolve_ref(ref: str) -> dict:
            if ref.startswith("#/definitions/"):
                def_name = ref.split("/definitions/", 1)[-1]
                return spec.get("definitions", {}).get(def_name, {})
            return {}

        def _collect_props(definition: dict, max_props: int = 12) -> list:
            props = list(definition.get("properties", {}).keys())
            for sub in definition.get("allOf", []):
                if isinstance(sub, dict) and "$ref" not in sub:
                    props.extend(sub.get("properties", {}).keys())
            return props[:max_props]

        def _props_str(schema_obj: dict) -> str:
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
    # Step 5b: LLM identifies endpoints that are DEFINITELY unrelated
    # ------------------------------------------------------------------
    async def _exclude_unrelated_endpoints(
        self, task: str, endpoints: List[EndpointInfo]
    ) -> List[int]:
        endpoint_list = "\n".join(
            f"{i}. {ep.method} {ep.path} — {ep.summary}"
            for i, ep in enumerate(endpoints)
        )
        api_hints_section = self._build_hints_section(endpoints, header="API context")

        prompt = (
            'Respond with ONLY valid JSON — no explanation, no markdown, no preamble.\n'
            'Format: {"excluded_indices": [3, 7, 15]}\n\n'
            f"Task: {task}\n\n"
            f"Available endpoints:\n{endpoint_list}\n\n"
            + api_hints_section
            + "Identify endpoints that are DEFINITELY UNRELATED to this task.\n\n"
            "Rules:\n"
            "- Only exclude an endpoint if you are confident it has zero possible connection to the task.\n"
            "- When in doubt, do NOT exclude — keeping a marginally relevant endpoint is safer than missing a needed one.\n"
            "- Exclude endpoints that operate on completely different resources or systems.\n"
            "- Do NOT try to pick the best endpoints here — only filter out the obviously irrelevant ones.\n"
        )
        response = await self._run_llm("_exclude_unrelated_endpoints", prompt)

        decoder = json.JSONDecoder()
        data = None
        for i, ch in enumerate(response):
            if ch == "{":
                try:
                    data, _ = decoder.raw_decode(response, i)
                    break
                except json.JSONDecodeError:
                    continue
        if data is None:
            try:
                data = json.loads(response.strip())
            except json.JSONDecodeError:
                data = {"excluded_indices": []}

        excluded = [i for i in data.get("excluded_indices", []) if 0 <= i < len(endpoints)]

        if self.debug_responses:
            kept_count = len(endpoints) - len(excluded)
            # reasoning = data.get("reasoning", "")
            print("\n[PlanningAgent] _exclude_unrelated_endpoints RESULT:")
            # if reasoning:
            #     print(f"  Reasoning: {reasoning}")
            print(f"  Excluded {len(excluded)}, keeping {kept_count} of {len(endpoints)} total")
            print("=" * 60 + "\n")

        return excluded

    # ------------------------------------------------------------------
    # Step 5c: Expand full details for all non-excluded endpoints
    # ------------------------------------------------------------------
    def _expand_endpoint_details(
        self, all_endpoints: List[EndpointInfo], excluded_indices: List[int]
    ) -> tuple:
        excluded_set = set(excluded_indices)
        kept = [ep for i, ep in enumerate(all_endpoints) if i not in excluded_set]
        detailed_list = "\n\n".join(
            f"{i}. {self._format_endpoint_detail(ep)}"
            for i, ep in enumerate(kept)
        )
        return kept, detailed_list

    def _format_endpoint_detail(self, ep: EndpointInfo) -> str:
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
        return entry

    # ------------------------------------------------------------------
    # Step 5d helpers
    # ------------------------------------------------------------------
    def _get_missing_params(self, step: ChainStep, already_satisfied: set) -> List[dict]:
        """Return all required params not covered by literal_args or a prior chain step."""
        missing = []
        seen_names: set = set()

        for p in step.endpoint.parameters:
            if not isinstance(p, dict):
                continue
            name = p.get("name", "")
            if not name or name in seen_names:
                continue
            if not p.get("required", False):
                continue
            if name in step.literal_args or name in already_satisfied:
                continue
            seen_names.add(name)
            missing.append({
                "name": name,
                "in": p.get("in", ""),
                "description": (p.get("description") or "")[:120],
            })

        # Also catch path params via regex — swagger sometimes marks them required=False
        for name in re.findall(r'\{(\w+)\}', step.endpoint.path):
            if name in seen_names:
                continue
            if name in step.literal_args or name in already_satisfied:
                continue
            seen_names.add(name)
            missing.append({"name": name, "in": "path", "description": ""})

        return missing

    async def _pick_goal(
        self,
        task: str,
        kept_endpoints: List[EndpointInfo],
        detailed_list: str,
        api_hints_section: str,
        prior_issues: Optional[list] = None,
    ) -> tuple:
        """Returns (goal_step, required_resolvers).

        When prior_issues is provided the LLM also identifies which resolver
        steps are needed to address the issues — steps the swagger-param-based
        backward chainer cannot detect because they are required by API usage
        rules rather than declared swagger parameters.
        """
        prior_issues_section = (
            "⚠️ REQUIRED CORRECTIONS — a prior attempt failed. Apply these constraints before choosing:\n"
            + "\n".join(f"  - {iss}" for iss in prior_issues) + "\n\n"
            if prior_issues else ""
        )

        prompt = (
            "Respond with ONLY a JSON object — no markdown, no explanation.\n"
            'Format: {"goal_index": <int>, "literal_args": {<param>: <value>, ...}, "foreach": <null|"LOOP_OVER_PRIOR">}\n\n'
            + prior_issues_section
            + f"Task: {task}\n\n"
            + f"Available endpoints:\n{detailed_list}\n\n"
            + api_hints_section
            + "Identify the single goal endpoint — the one whose response directly contains the final answer the task is asking for.\n\n"
            "Rules for choosing the goal:\n"
            "- The goal endpoint is the LAST step to execute. Its output must directly satisfy the task.\n"
            "- If the task asks for specific data about a resource, the goal is the endpoint that fetches "
            "that specific resource, NOT a search or list endpoint.\n"
            "- Search and list endpoints are almost always resolvers (prerequisite steps), not goals. "
            "Only pick a list endpoint as the goal if the task explicitly asks for a list.\n"
            "- Write/mutate endpoints (POST, PUT, DELETE, PATCH) are the goal when the task asks to "
            "create, update, or delete something.\n\n"
            "Also list any literal arguments for the goal that can be filled directly from the task description.\n\n"
            "Foreach (bulk operations only):\n"
            "- If the task requires the SAME operation on MULTIPLE entities resolved from a prior step, "
            "set foreach to the string 'LOOP_OVER_PRIOR' — the exact step reference will be resolved when the full plan is built.\n"
            "- Otherwise set foreach to null.\n\n"
            'Required output — ONLY valid JSON, examples:\n'
            '{"goal_index": 2, "literal_args": {"state": "opened"}, "foreach": null}\n'
            'Bulk: {"goal_index": 5, "literal_args": {}, "foreach": "LOOP_OVER_PRIOR"}'
        )
        response = await self._run_llm("_pick_goal", prompt)

        decoder = json.JSONDecoder()
        data = None
        for i, ch in enumerate(response):
            if ch == "{":
                try:
                    data, _ = decoder.raw_decode(response, i)
                    break
                except json.JSONDecodeError:
                    continue
        if data is None:
            data = json.loads(response.strip())

        goal_index = data.get("goal_index", 0)
        if not (0 <= goal_index < len(kept_endpoints)):
            raise ValueError(
                f"LLM returned goal_index {goal_index} but only {len(kept_endpoints)} endpoints available."
            )
        goal_step = ChainStep(
            endpoint=kept_endpoints[goal_index],
            capability="performs the main action of the task",
            literal_args=data.get("literal_args", {}),
            foreach=data.get("foreach"),
        )

        # Parse required_resolvers (always present, even when no prior_issues)
        required_resolvers: List[ChainStep] = []
        seen_keys = {f"{goal_step.endpoint.method} {goal_step.endpoint.path}"}
        for r in data.get("required_resolvers", []):
            ep_index = r.get("endpoint_index")
            if ep_index is None or not (0 <= ep_index < len(kept_endpoints)):
                continue
            ep = kept_endpoints[ep_index]
            key = f"{ep.method} {ep.path}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            required_resolvers.append(ChainStep(
                endpoint=ep,
                capability=r.get("capability", "provides prerequisite data"),
                satisfies_param=r.get("satisfies_param", ""),
                literal_args=r.get("literal_args", {}),
                foreach=r.get("foreach"),
            ))

        return goal_step, required_resolvers

    async def _find_resolver(
        self,
        task: str,
        missing_params: List[dict],
        kept: List[EndpointInfo],
        detailed_list: str,
        api_hints_section: str,
        chain_so_far: List[ChainStep],
        prior_issues: Optional[list] = None,
    ) -> Optional[ChainStep]:
        """Pick one resolver from the already-filtered endpoint subset."""
        if not kept:
            return None

        param_descriptions = ", ".join(
            f"'{p['name']}' ({p['description']})" if p.get("description") else f"'{p['name']}'"
            for p in missing_params
        )
        chain_keys = {f"{cs.endpoint.method} {cs.endpoint.path}" for cs in chain_so_far}

        prior_issues_section = (
            "⚠️ REQUIRED CORRECTIONS — a prior attempt failed. Apply these constraints before choosing:\n"
            + "\n".join(f"  - {iss}" for iss in prior_issues) + "\n\n"
            if prior_issues else ""
        )

        prompt = (
            prior_issues_section
            + f"Task context: {task}\n\n"
            + f"You need to find ONE endpoint that provides value(s) for: {param_descriptions}\n\n"
            + f"Available endpoints:\n{detailed_list}\n\n"
            + api_hints_section
            + "Rules:\n"
            "- Pick the single best endpoint whose response output can supply the needed parameter value(s).\n"
            "- Prefer endpoints that return the specific resource containing the needed identifier.\n"
            "- Also extract any literal argument values directly from the task description for this resolver.\n"
            "- Specify which parameter name (from the missing list above) this resolver's output will satisfy.\n"
            "- If no endpoint can provide the needed value, return null for endpoint_index.\n\n"
            "Foreach (bulk operations only):\n"
            "- If the task names multiple specific entities that all need this resolver to run once per entity, "
            "set foreach to a list of those names and use {loop_item} as the argument value.\n"
            "- Otherwise set foreach to null.\n\n"
            'Respond with ONLY valid JSON:\n'
            '{"endpoint_index": 3, "satisfies_param": "project_id", "literal_args": {"search": "dotfiles"}, "foreach": null, "capability": "searches for project by name to get its ID"}\n'
            'Bulk example: {"endpoint_index": 2, "satisfies_param": "user_id", "literal_args": {}, "foreach": ["Alice", "Bob", "Carol"], "capability": "looks up each user by name"}\n'
            'Or if nothing fits: {"endpoint_index": null, "satisfies_param": "", "literal_args": {}, "foreach": null, "capability": ""}'
        )
        response = await self._run_llm("_find_resolver", prompt)

        decoder = json.JSONDecoder()
        data = None
        for i, ch in enumerate(response):
            if ch == "{":
                try:
                    data, _ = decoder.raw_decode(response, i)
                    break
                except json.JSONDecodeError:
                    continue
        if data is None:
            data = json.loads(response.strip())

        ep_index = data.get("endpoint_index")
        if ep_index is None or not (0 <= ep_index < len(kept)):
            return None

        chosen_ep = kept[ep_index]
        key = f"{chosen_ep.method} {chosen_ep.path}"
        if key in chain_keys:
            self._debug_print("_find_resolver", response=f"Cycle detected: {key} already in chain, stopping.")
            return None

        return ChainStep(
            endpoint=chosen_ep,
            capability=data.get("capability", "provides prerequisite data"),
            satisfies_param=data.get("satisfies_param", ""),
            literal_args=data.get("literal_args", {}),
            foreach=data.get("foreach"),
        )

    # ------------------------------------------------------------------
    # Step 5d: Build backward chain — goal first, then prepend resolvers
    # Exclusion (5b) and expansion (5c) happen once in plan() and are passed in.
    # ------------------------------------------------------------------
    async def _build_chain_backward(
        self,
        task: str,
        kept: List[EndpointInfo],
        detailed_list: str,
        api_hints_section: str,
        prior_issues: Optional[list] = None,
    ) -> List[ChainStep]:
        MAX_RESOLVER_ITERATIONS = 5

        if not kept:
            raise ValueError("No endpoints available — cannot build a plan.")

        goal_step, _ = await self._pick_goal(
            task, kept, detailed_list, api_hints_section, prior_issues
        )
        chain: List[ChainStep] = [goal_step]

        # Backward chaining: iteratively prepend resolvers for missing params
        for iteration in range(MAX_RESOLVER_ITERATIONS):
            already_satisfied = {cs.satisfies_param for cs in chain if cs.satisfies_param}

            # Find the first chain step (from front) that still has unsatisfied required params
            target_step = None
            missing_params: List[dict] = []
            for cs in chain:
                missing = self._get_missing_params(cs, already_satisfied)
                if missing:
                    target_step = cs
                    missing_params = missing
                    break

            if not target_step:
                break  # all params satisfied

            self._debug_print(
                "_build_chain_backward",
                response=(
                    f"Iteration {iteration + 1}: finding resolver for "
                    f"{[p['name'] for p in missing_params]} "
                    f"needed by {target_step.endpoint.method} {target_step.endpoint.path}"
                ),
            )

            resolver = await self._find_resolver(
                task, missing_params, kept, detailed_list, api_hints_section, chain, prior_issues
            )

            if resolver is None:
                self._debug_print(
                    "_build_chain_backward",
                    response=f"No resolver found for {[p['name'] for p in missing_params]}, proceeding with current chain.",
                )
                break

            chain.insert(0, resolver)

        if self.debug_responses:
            print("\n[PlanningAgent] _build_chain_backward FINAL CHAIN:")
            for i, cs in enumerate(chain):
                print(f"  {i + 1}. {cs.endpoint.method} {cs.endpoint.path} — {cs.capability}")
                if cs.satisfies_param:
                    print(f"     → satisfies_param: {cs.satisfies_param}")
                if cs.literal_args:
                    print(f"     literal_args: {cs.literal_args}")
            print("=" * 60 + "\n")

        return chain

    # ------------------------------------------------------------------
    # Step 5e: Read current-user context from env vars for the APIs in use
    # ------------------------------------------------------------------
    def _get_user_context(self, api_files: set) -> str:
        API_ENV_MAP = {
            "gitlab": ("GitLab", [
                ("GITLAB_USERNAME", "username"),
            ]),
            "reddit": ("Reddit", [
                ("REDDIT_USERNAME", "username"),
            ]),
            "shopping": ("Shopping", [
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
    async def _build_plan(
        self,
        task: str,
        chain_steps: List[ChainStep],
        kept: List[EndpointInfo],
        detailed_list: str,
    ):
        # ToolEnum and endpoint details use ALL kept endpoints so the LLM can
        # pick the best set and the fix step is never blocked by a missing tool.
        tool_names = list(dict.fromkeys(f"{ep.method} {ep.path}" for ep in kept))
        bundle = build_agent_models(tool_names)

        endpoint_details = detailed_list  # pre-formatted full list of kept endpoints
        schema = json.dumps(bundle.ToolBasedResponse.model_json_schema(), indent=2)

        hints = self._load_hints()
        api_files_used = {ep.api for ep in kept}
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

        step_ids = [f"step_{i+1}" for i in range(len(chain_steps))]

        # Build a lookup so each step can find which earlier step provides each param
        param_to_provider: dict = {}  # param_name -> (provider_idx, provider_step_id)
        for i, cs in enumerate(chain_steps):
            if cs.satisfies_param:
                param_to_provider[cs.satisfies_param] = (i, step_ids[i])

        wiring_lines = []
        for i, cs in enumerate(chain_steps):
            sid = step_ids[i]
            lines = [f"  {sid}: {cs.endpoint.method} {cs.endpoint.path} [{cs.capability}]"]
            if cs.foreach is not None:
                lines.append(f"    foreach: {json.dumps(cs.foreach)}")
                lines.append(f"    note: use {{loop_item}} as the argument value for the iterated parameter")
            if cs.literal_args:
                for k, v in cs.literal_args.items():
                    lines.append(f"    literal arg: {k}={v!r}")

            # Wire every parameter this step needs that any earlier step provides.
            # This handles non-adjacent dependencies (e.g. author from step_1 → step_3).
            step_param_names: set = set()
            for p in cs.endpoint.parameters:
                if isinstance(p, dict):
                    pname = p.get("name", "")
                    if pname:
                        step_param_names.add(pname)
            for pname in re.findall(r'\{(\w+)\}', cs.endpoint.path):
                step_param_names.add(pname)

            for pname in sorted(step_param_names):
                if pname in param_to_provider and pname not in cs.literal_args:
                    provider_idx, provider_sid = param_to_provider[pname]
                    if provider_idx < i:
                        lines.append(f"    {pname}: reference {{{provider_sid}.result}}")

            if cs.satisfies_param:
                lines.append(f"    output provides: {cs.satisfies_param}")
            wiring_lines.append("\n".join(lines))
        wiring_section = (
            "\nSuggested execution chain (use as a starting point — you may deviate if a better "
            "wiring or additional endpoint from the list above is needed):\n"
            + "\n\n".join(wiring_lines) + "\n"
        )

        user_context_section = self._get_user_context(api_files_used)

        prompt = (
            f"Task: {task}\n\n"
            f"Available API endpoints:\n{endpoint_details}\n\n"
            + wiring_section
            + user_context_section
            # + api_hints_section + "\n"
            + "Build a complete step-by-step execution plan for the task above.\n"
            "Use any endpoints from the available list that are needed. "
            "The suggested chain above is a starting point — follow it where it is correct, "
            "but deviate if a better wiring or an additional endpoint is required.\n"
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
            "  - 'reference': the value comes from a prior step's output via {step_id.result} or a field accessor like {step_id.result.field_name}\n\n"
            "Reference field accessor rule (CRITICAL):\n"
            "- When a prior step returns a JSON object and you need only one field from it, use dot-notation: {step_id.result.field_name}\n"
            "  Example: if step_1 returns a project object and you need its default_branch, write {step_1.result.default_branch}\n"
            "- Use {step_id.result} (no field) ONLY when the prior step returns a plain scalar (string, number) or you genuinely need the entire object.\n"
            "- Never use {step_id.result} when you need a specific named field — always drill down with .field_name.\n"
            "- For JSON body arguments that embed multiple references (e.g. a body string), use the most specific accessor for each embedded reference.\n\n"
            "Closed-enum rule:\n"
            "- If a parameter lists allowed values (in its description), treat that list as CLOSED.\n"
            "- ONLY use exact listed values — do not invent, paraphrase, or substitute.\n"
            "- If the task requires an operation not expressible with documented values, use the nearest valid value "
            "and add a post_processing instruction on that step to perform the remaining filtering/sorting.\n\n"
            "Free-string parameter rule:\n"
            "- If a parameter is a free string (no enum, no documented example values), do NOT invent a value for it. "
            "Only include it if: (a) the task explicitly states the exact value, or (b) a prior step's output supplies it, or (c) you can look it up via another API endpoint first. \n\n"
            "If none of these apply and the parameter is optional and not necessary for the task, omit it entirely.\n\n"
            
            "Foreach rule:\n"
            "- If a step needs to process each item from a prior step's list output individually "
            "(e.g., fetch details for each ID returned by a search or events step), set foreach to "
            "'step_N.result[*].field_name' where N is the prior step and field_name is the relevant field.\n"
            "- If the wiring shows 'foreach: LOOP_OVER_PRIOR' or 'foreach: [...]' or 'foreach: \"...\"', "
            "resolve or copy that value to the correct step reference.\n"
            "- CRITICAL consistency rule: if any argument value in a step contains '{loop_item}', "
            "that step's foreach field MUST be set. A step with {loop_item} arguments but no foreach is always wrong.\n"
            "- foreach accepts a literal list ([\"Alice\", \"Bob\"]) or a reference string (\"step_1.result[*].id\").\n"
            "- In argument values, use {loop_item} as the placeholder for the current iterated element.\n"
            "- A foreach step runs N times and its output is automatically collected as a list.\n\n"
            "Post-processing:\n"
            "- If the API cannot fully satisfy the task (e.g. unsupported sort order), retrieve with valid params "
            "and describe the remaining client-side operation in the step's post_processing field.\n\n"
        )
        response = await self._run_llm("_build_plan", prompt)

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

        # Annotate each plan step with returns/base_url from the full kept endpoint map
        endpoint_map = {f"{ep.method} {ep.path}": ep for ep in kept}
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
                ]),
            })
            for step in plan_result.plan
        ]
        return plan_result.model_copy(update={"plan": annotated_steps})

    # ------------------------------------------------------------------
    # Step 7: LLM semantic verification + auto-fix loop
    # ------------------------------------------------------------------
    def _plan_context(self, kept: List[EndpointInfo]) -> tuple:
        endpoint_details = "\n\n".join(self._format_endpoint_detail(ep) for ep in kept)
        hints = self._load_hints()
        api_files_used = {ep.api for ep in kept}
        relevant_hints = [
            f"[ {fname} ]\n{hints[fname]}"
            for fname in api_files_used
            if fname in hints
        ]
        api_hints_section = (
            "\nAPI-specific rules:\n"
            + "\n\n".join(relevant_hints) + "\n"
            if relevant_hints else ""
        )
        tool_names = list(dict.fromkeys(f"{ep.method} {ep.path}" for ep in kept))
        bundle = build_agent_models(tool_names)
        return endpoint_details, api_hints_section, tool_names, bundle

    @staticmethod
    def _format_plan_text(plan_result) -> str:
        return "\n\n".join(
            f"  step_id: {step.step_id}\n"
            f"  tool: {step.tool_name.value if hasattr(step.tool_name, 'value') else str(step.tool_name)}\n"
            f"  arguments: {[{'name': a.name, 'value': a.value, 'value_type': a.value_type} for a in (step.arguments or [])]}\n"
            f"  depends_on: {step.depends_on or []}\n"
            f"  hints: {step.hints or ''}"
            for step in plan_result.plan
        )

    async def _check_plan(
        self, task: str, plan_result, kept: List[EndpointInfo]
    ) -> tuple:
        endpoint_details, api_hints_section, _, _ = self._plan_context(kept)
        plan_text = self._format_plan_text(plan_result)

        prompt = (
            f"Task: {task}\n\n"
            f"Endpoint definitions:\n{endpoint_details}\n\n"
            + api_hints_section
            + f"\nGenerated plan:\n{plan_text}\n\n"
            "Review this plan for argument-level correctness. Do NOT flag endpoint selection "
            "or high-level sequencing — focus only on the wiring within the plan as written.\n\n"
            "Check ALL of the following:\n\n"
            "1. Missing required parameters: are any required parameters absent from a step "
            "that cannot be inferred from a prior step or the task description?\n\n"
            "2. Type mismatch in reference wiring: does each {step_N.result} reference supply "
            "the correct resource type for the parameter it feeds? "
            "(e.g., a step returning a user_id list must NOT feed into a project {id} parameter — "
            "only a step returning project data can do that)\n\n"
            "3. Parameter value correctness: are literal argument values valid for their parameter "
            "according to the endpoint description? (wrong enum, wrong format, user display name "
            "used where a machine identifier is needed, etc.)\n\n"
            "4. Task accomplishment: does the plan as a whole accomplish the stated task?\n\n"
            'Respond with ONLY valid JSON:\n'
            '{"issues": ["step_2 arg \'id\' wires step_1.result (user_id) into a project {id} — type mismatch"], "ok": false}\n'
            'If no issues found: {"issues": [], "ok": true}'
        )
        response = await self._run_llm("_check_plan", prompt)

        decoder = json.JSONDecoder()
        data: dict = {}
        for i, ch in enumerate(response):
            if ch == "{":
                try:
                    data, _ = decoder.raw_decode(response, i)
                    break
                except json.JSONDecodeError:
                    continue

        return data.get("issues", []), data.get("ok", True)

    async def _fix_plan(
        self, task: str, plan_result, kept: List[EndpointInfo], issues: list
    ):
        endpoint_details, api_hints_section, tool_names, bundle = self._plan_context(kept)
        plan_text = self._format_plan_text(plan_result)
        schema = json.dumps(bundle.ToolBasedResponse.model_json_schema(), indent=2)
        issues_text = "\n".join(f"  - {iss}" for iss in issues)

        prompt = (
            f"Task: {task}\n\n"
            f"Endpoint definitions:\n{endpoint_details}\n\n"
            + api_hints_section
            + f"\nCurrent plan (has issues):\n{plan_text}\n\n"
            f"Issues to fix:\n{issues_text}\n\n"
            "Produce a corrected plan that resolves all issues above. "
            "Keep steps that are already correct unchanged.\n\n"
            f"tool_name must be EXACTLY one of: {json.dumps(tool_names)}\n"
            "- value_type is 'literal' for known values, 'reference' for {{step_id.result}} placeholders\n"
            "- argument names must ONLY be parameter names explicitly listed in the endpoint schema\n"
            "- If a step has foreach set, preserve it. Use {{loop_item}} as the argument value for the iterated parameter.\n\n"
            f"Respond with ONLY valid JSON matching this schema:\n{schema}"
        )
        response = await self._run_llm("_fix_plan", prompt)

        decoder = json.JSONDecoder()
        data = None
        for i, ch in enumerate(response):
            if ch == "{":
                try:
                    data, _ = decoder.raw_decode(response, i)
                    break
                except json.JSONDecodeError:
                    continue
        if data is None:
            data = json.loads(response.strip())

        fixed = bundle.ToolBasedResponse(**data)
        if not validate_plan(fixed.plan):
            raise ValueError("_fix_plan produced an invalid plan structure.")

        endpoint_map = {f"{ep.method} {ep.path}": ep for ep in kept}
        _fallback = EndpointInfo(api="", method="", path="", summary="", description="", parameters=[])
        annotated = [
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
                ]),
            })
            for step in fixed.plan
        ]
        return fixed.model_copy(update={"plan": annotated})

    async def _check_chain(
        self,
        task: str,
        chain_steps: List[ChainStep],
        api_hints_section: str,
    ) -> tuple:
        """Verify the chain of steps before building the plan.

        Checks logical correctness (goal, ordering, missing prerequisites, data-flow
        mismatches) without needing a fully-built plan.  Returns (issues, ok).
        """
        # Chain text: one line per endpoint showing its role and what data it contributes.
        # No wiring detail — wiring is verified separately after the plan is built.
        chain_text = "\n".join(
            f"  {i + 1}. {cs.endpoint.method} {cs.endpoint.path} — {cs.capability}"
            + (f" | provides: {cs.satisfies_param}" if cs.satisfies_param else "")
            + (f" | foreach: {json.dumps(cs.foreach)}" if cs.foreach is not None else "")
            for i, cs in enumerate(chain_steps)
        )

        prompt = (
            f"Task: {task}\n\n"
            f"Selected endpoints:\n{chain_text}\n\n"
            + api_hints_section
            + "Check that this set of endpoints is COMPLETE and SUFFICIENT to accomplish the task.\n\n"
            "Ask yourself:\n"
            "1. Does the last endpoint produce the final result the task asks for?\n"
            "2. Is there any data or identifier the task needs that NO endpoint in this set can provide? "
            "(e.g. the task asks to filter commits by author but there is no user-lookup endpoint to resolve the author name)\n"
            "3. Is any endpoint clearly wrong or irrelevant for this task?\n"
            "4. Is the execution order conceptually correct?\n\n"
            "IMPORTANT: Do NOT check how arguments are wired between steps, what parameter names are used, "
            "or whether reference values are correct — argument-level wiring is verified in a separate pass "
            "after the plan is built.\n\n"
            'Respond with ONLY valid JSON:\n'
            '{"issues": ["description of gap or problem"], "ok": false}\n'
            'If the endpoint set is complete and correct: {"issues": [], "ok": true}'
        )
        response = await self._run_llm("_check_chain", prompt)

        decoder = json.JSONDecoder()
        data: dict = {}
        for i, ch in enumerate(response):
            if ch == "{":
                try:
                    data, _ = decoder.raw_decode(response, i)
                    break
                except json.JSONDecodeError:
                    continue

        return data.get("issues", []), data.get("ok", True)

    # ------------------------------------------------------------------
    # Step 8: Validate the plan for semantic correctness
    # ------------------------------------------------------------------
    async def _validate_plan(self, plan_result, kept: List[EndpointInfo]) -> None:
        plan = plan_result.plan
        endpoint_map = {(ep.method + " " + ep.path): ep for ep in kept}

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

                if atype == "reference":
                    import re as _re
                    refs = _re.findall(r'\{(\w+)\.result\}', str(avalue))
                    for ref_id in refs:
                        if ref_id not in step_ids_seen:
                            errors.append(
                                f"Step '{step.step_id}', arg '{aname}': references '{ref_id}.result' "
                                f"but '{ref_id}' has not appeared yet in the plan."
                            )

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

        # 5b+5c: exclusion filter and detail expansion happen exactly once here.
        # The resulting kept/detailed_list/api_hints_section are threaded through
        # to _build_chain_backward and _check_chain so rebuilds never re-scan.
        api_hints_section = self._build_hints_section(
            all_endpoints, header="API context (use to understand data models and identifier types)"
        )
        excluded = await self._exclude_unrelated_endpoints(task, all_endpoints)
        kept, detailed_list = self._expand_endpoint_details(all_endpoints, excluded)
        if not kept:
            raise ValueError("All endpoints were excluded — cannot build a plan.")

        chain_steps = await self._build_chain_backward(task, kept, detailed_list, api_hints_section)
        if not chain_steps:
            raise ValueError("No endpoints selected for this task.")

        # Verify chain logic before building the plan so a bad chain never
        # wastes an expensive _build_plan call.
        MAX_CHAIN_ATTEMPTS = 2
        for attempt in range(MAX_CHAIN_ATTEMPTS):
            issues, ok = await self._check_chain(task, chain_steps, api_hints_section)
            if ok or not issues:
                break
            self._debug_print(
                "plan",
                response=f"chain attempt {attempt + 1}: rebuilding due to {len(issues)} issue(s): {issues}",
            )
            chain_steps = await self._build_chain_backward(
                task, kept, detailed_list, api_hints_section, prior_issues=issues
            )
            if not chain_steps:
                raise ValueError("Rebuild produced no chain steps.")
        else:
            issues, ok = await self._check_chain(task, chain_steps, api_hints_section)
            if not ok and issues:
                raise ValueError(
                    f"Chain verification failed after {MAX_CHAIN_ATTEMPTS} rebuild(s):\n"
                    + "\n".join(f"  - {iss}" for iss in issues)
                )

        # Step 1 check passed — build the plan using all kept endpoints so the
        # LLM has full visibility and _fix_plan is never blocked by a missing tool.
        plan_result = await self._build_plan(task, chain_steps, kept, detailed_list)

        # Catch validation errors from the initial build so they feed into the fix loop
        # rather than immediately aborting planning.
        pending_validation_error: Optional[str] = None
        try:
            await self._validate_plan(plan_result, kept)
        except ValueError as exc:
            pending_validation_error = str(exc)

        # Step 2: verify argument-level wiring in the built plan, fix if needed.
        # Validation errors from _validate_plan are merged with _check_plan issues
        # so _fix_plan gets full context in one pass.
        MAX_PLAN_FIX_ATTEMPTS = 2
        for attempt in range(MAX_PLAN_FIX_ATTEMPTS):
            issues, ok = await self._check_plan(task, plan_result, kept)
            all_issues = list(issues)
            if pending_validation_error:
                all_issues.append(pending_validation_error)
            if not all_issues or (ok and not pending_validation_error):
                break
            self._debug_print(
                "plan",
                response=f"plan fix attempt {attempt + 1}: {len(all_issues)} issue(s): {all_issues}",
            )
            plan_result = await self._fix_plan(task, plan_result, kept, all_issues)
            pending_validation_error = None
            try:
                await self._validate_plan(plan_result, kept)
            except ValueError as exc:
                pending_validation_error = str(exc)

        if pending_validation_error:
            raise ValueError(pending_validation_error)

        return plan_result
