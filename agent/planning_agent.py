"""
Planning agent: selects the appropriate swagger file(s), parses them with prance,
identifies the best API endpoints for a given task, and returns a full execution
plan in the planner.py ToolBasedResponse format.
"""

import json
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
    base_url: str = ""  # e.g. http://127.0.0.1:8023/api/v4


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
            return json.load(f)

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
        scheme = (spec.get("schemes") or ["http"])[0]
        host = spec.get("host", "localhost")
        base_path = spec.get("basePath", "").rstrip("/")
        base_url = f"{scheme}://{host}{base_path}"

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
                    base_url=base_url,
                ))
        return endpoints

    # ------------------------------------------------------------------
    # Step 5b: LLM selects the best endpoints for the task 
    # ------------------------------------------------------------------
    async def _select_endpoints(self, task: str, endpoints: List[EndpointInfo]) -> List[EndpointInfo]:
        candidates = endpoints #passed in everything
        endpoint_list = "\n".join(
            f"{i}. {ep.method} {ep.path} [{ep.api}] — {ep.summary}"
            for i, ep in enumerate(candidates)
        )

        # Inject per-API hints for whichever schemas are in play
        hints = self._load_hints()
        api_files_used = {ep.api for ep in candidates}
        api_hints_section = ""
        relevant_hints = [
            f"[ {fname} ]\n{hints[fname]}"
            for fname in api_files_used
            if fname in hints
        ]
        if relevant_hints:
            api_hints_section = "\nAPI-specific parameter rules (apply these before deciding):\n" + "\n\n".join(relevant_hints) + "\n"

        # prompt = (
        #     f"Task: {task}\n\n"
        #     f"Available endpoints:\n{endpoint_list}\n\n"
        #     "Select the minimal executable set of endpoints needed to complete this task.\n\n"
        #     "Important rules:\n"
        #     "1. First identify the most likely final goal endpoint.\n"
        #     "2. Then inspect the required parameters for that endpoint.\n"
        #     "3. Compare those required parameters against the information explicitly available in the task/context.\n"
        #     "4. If a required parameter is missing, ambiguous, or in the wrong form, select one or more additional endpoints that can resolve or transform it.\n"
        #     "5. Work backwards from the goal endpoint until every required parameter can be obtained.\n"
        #     "6. Do NOT assume a parameter is directly usable just because it has a similar name.\n"
        #     "   Example: a project name is not always a valid project id or namespaced path.\n"
        #     "7. Prefer a valid multi-step chain over an invalid single-endpoint plan.\n"
        #     "8. Only choose endpoints that are necessary to make the plan executable.\n"
        #     "9. If multiple resolver endpoints are possible, prefer the most direct and reliable one.\n\n"
        #     "When reasoning about parameters, pay attention to:\n"
        #     "- numeric id vs string name vs full path\n"
        #     "- namespace-qualified identifiers\n"
        #     "- search results that must be resolved before use\n"
        #     "- required path parameters vs optional query parameters\n"
        #     "- whether the task provides enough context directly\n"
        #     + api_hints_section + "\n"
        #     "Your goal is not just to pick the endpoint that performs the final action.\n"
        #     "Your goal is to pick the smallest set of endpoints that can actually be executed with the available information.\n\n"
        #     'Respond with ONLY valid JSON in this format: '
        #     '{"selected_indices": [0, 2, 5], "reasoning": "brief explanation"}'
        # )
        prompt = (
            f"Task: {task}\n\n"
            f"Available endpoints:\n{endpoint_list}\n\n"
            "Select the minimal executable set of endpoints needed to complete this task.\n\n"
            "Important rules:\n"
            "1. First identify the most likely final goal endpoint.\n"
            "2. Then inspect the required parameters for that endpoint.\n"
            "3. Compare those required parameters against the information explicitly available in the task/context.\n"
            "4. If a required parameter is missing, ambiguous, or in the wrong form, you MUST add one or more resolver endpoints that can obtain or transform it.\n"
            "5. Work backwards from the goal endpoint until every required parameter is available in a directly usable form.\n"
            "6. Do NOT assume a parameter is directly usable just because it has a similar name.\n"
            "7. Do NOT choose a goal endpoint alone if one of its required parameters still needs to be looked up or transformed.\n"
            "8. Prefer a valid multi-step chain over an invalid single-endpoint plan.\n"
            "9. Only choose endpoints that are necessary to make the plan executable.\n"
            "10. If multiple resolver endpoints are possible, prefer the most direct and reliable one.\n"
            "11. A plan is executable only if every selected endpoint can be called with the task/context plus outputs of earlier selected endpoints.\n"
            "12. Never rely on 'it might work' or speculative identifier guessing. If direct usability is not established, add a resolver endpoint.\n\n"
            "When reasoning about parameters, pay attention to:\n"
            "- numeric id vs string name vs full path\n"
            "- namespace-qualified identifiers\n"
            "- search results that must be resolved before use\n"
            "- required path parameters vs optional query parameters\n"
            "- whether the task provides enough context directly\n"
            + api_hints_section + "\n"
            "Your goal is not just to pick the endpoint that performs the final action.\n"
            "Your goal is to pick the smallest set of endpoints that can actually be executed with the available information.\n\n"
            'Respond with ONLY valid JSON in this format: '
            '{"selected_indices": [0, 2, 5], "reasoning": "brief explanation"}'
        )
        # prompt = (
        #     f"Task: {task}\n\n"
        #     f"Available endpoints:\n{endpoint_list}\n\n"
        #     "Select the minimal executable endpoint chain needed to complete this task.\n\n"
        #     "Planning procedure:\n"
        #     "1. First identify the most likely final goal endpoint.\n"
        #     "2. Inspect the required parameters for that endpoint.\n"
        #     "3. Compare those required parameters against the information explicitly available in the task/context.\n"
        #     "4. If the task/context already provides a parameter in a directly usable form, prefer using it immediately in the goal endpoint.\n"
        #     "5. If a required parameter is missing, ambiguous, or in the wrong form, work backwards and add one or more resolver endpoints that can obtain or transform it.\n"
        #     "6. Continue backward-chaining until every selected endpoint has all required inputs available.\n\n"
        #     "Important rules:\n"
        #     "7. Do NOT assume a parameter is directly usable just because it has a similar name.\n"
        #     "   Example: a project name is not always a valid project id or namespaced path.\n"
        #     "8. Do NOT assume that every path parameter named {id} requires a prior search call.\n"
        #     "   Some APIs accept numeric ids, namespaced paths, slugs, URLs, or other structured identifiers directly.\n"
        #     "9. If the task provides a specific structured identifier (for example a namespaced path, owner/resource path, full slug, URL, numeric id, or other resource-like identifier), prefer using it directly instead of adding an unnecessary lookup step.\n"
        #     "10. Only add search/list/resolver endpoints when the current information is insufficient to execute the goal endpoint directly.\n"
        #     "11. Prefer a valid direct call over an unnecessary lookup chain.\n"
        #     "12. Prefer a valid multi-step chain over an invalid single-endpoint plan.\n"
        #     "13. If multiple resolver endpoints are possible, choose the most direct and reliable one.\n"
        #     "14. Only choose endpoints that are necessary to make the plan executable.\n\n"
        #     "When reasoning about parameters, pay attention to:\n"
        #     "- numeric id vs string name vs full path\n"
        #     "- namespace-qualified or owner-qualified identifiers\n"
        #     "- whether a provided identifier is already highly specific\n"
        #     "- search results that must be resolved before use\n"
        #     "- required path parameters vs optional query parameters\n"
        #     "- whether the task already provides enough context directly\n\n"
        #     "Your goal is not just to pick the endpoint that performs the final action.\n"
        #     "Your goal is to pick the smallest executable chain of endpoints that can actually run with the available information.\n\n"
        #     'Respond with ONLY valid JSON in this format: '
        #     '{"selected_indices": [0, 2, 5], "reasoning": "brief explanation"}'
        # )
        # self._debug_print("_select_endpoints", prompt=prompt) #super long list of endpoints
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
        return [candidates[i] for i in indices if 0 <= i < len(candidates)]

    # ------------------------------------------------------------------
    # Step 6: LLM builds a full execution plan
    # ------------------------------------------------------------------
    async def _build_plan(self, task: str, selected: List[EndpointInfo]):
        tool_names = [f"{ep.method} {ep.path}" for ep in selected]
        bundle = build_agent_models(tool_names)

        # Build a concise endpoint reference for the LLM
        details = []
        for ep in selected:
            params = []
            for p in ep.parameters:
                if isinstance(p, dict):
                    pname = p.get("name", "")
                    pin = p.get("in", "")
                    required = p.get("required", False)
                    params.append(f"  - {pname} (in={pin}, required={required})")
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

        prompt = (
            f"Task: {task}\n\n"
            f"Available API endpoints:\n{endpoint_details}\n\n"
            "Build a step-by-step execution plan to complete this task.\n"
            "Steps can depend on each other using depends_on and reference prior outputs with '{step_id.result}'.\n\n"
            f"Respond with ONLY valid JSON matching this schema:\n{schema}\n\n"
            "Rules:\n"
            "- tool_call_required must be true\n"
            '- response must be empty string ""\n'
            '- Each step needs a unique step_id (e.g. "step_1", "step_2")\n'
            f"- tool_name must be one of: {json.dumps(tool_names)}\n"
            "- arguments is a list of {name, value, value_type} objects\n"
            '- value_type is "literal" for known values, "reference" for {step_id.result} placeholders'
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

        # Inject response_schema and base_url into each step using the
        # tool_name → EndpointInfo mapping we already have from the swagger spec.
        endpoint_map = {f"{ep.method} {ep.path}": ep for ep in selected}
        annotated_steps = [
            step.model_copy(update={
                "returns": endpoint_map.get(
                    step.tool_name.value if hasattr(step.tool_name, "value") else str(step.tool_name),
                    EndpointInfo(api="", method="", path="", summary="", description="", parameters=[])
                ).response_schema,
                "base_url": endpoint_map.get(
                    step.tool_name.value if hasattr(step.tool_name, "value") else str(step.tool_name),
                    EndpointInfo(api="", method="", path="", summary="", description="", parameters=[])
                ).base_url,
            })
            for step in plan_result.plan
        ]
        return plan_result.model_copy(update={"plan": annotated_steps})

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

        selected_endpoints = await self._select_endpoints(task, all_endpoints)
        if not selected_endpoints:
            raise ValueError("LLM selected no endpoints for this task.")

        return await self._build_plan(task, selected_endpoints)
