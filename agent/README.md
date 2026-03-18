# /agent

The agent package implements a two-phase **plan → execute** pipeline for completing natural language tasks against web server APIs.

## How it works

1. **PlanningAgent** reads the available API schemas, uses an LLM to select the right endpoints, and produces a structured execution plan.
2. **ExecutionAgent** runs each step in the plan as a real HTTP request (via `curl`), resolves inter-step dependencies, and synthesizes a natural language answer.
3. **Agent** is a thin wrapper that wires both together for single-prompt use.

---

## Top-level files

| File | What it does |
|---|---|
| `agent.py` | High-level entry point. Calls `PlanningAgent.plan()` then `ExecutionAgent.execute()` in sequence. |
| `planning_agent.py` | Selects the right Swagger file(s), parses them with `prance`, picks the minimal set of endpoints via LLM, and returns a validated `ToolBasedResponse` execution plan. |
| `execution_agent.py` | Executes each plan step as a `curl` call. Handles dependency ordering, fan-out (one step called per item in a list), inter-step output parsing, and final LLM answer generation. |
| `planner.py` | Pydantic model factory (`build_agent_models`) that generates runtime-typed `ExecutionStep` / `ToolBasedResponse` classes from the allowed tool list. Also contains `ExecutionContext` (tracks step state) and plan validation / pretty-print helpers. |
| `auth.py` | Authentication providers (`HeaderAuth`, `CookieAuth`, `MultiAuth`, `StaticAuth`) and `AuthRegistry`, which maps server names to their auth strategy. Tokens are read from `config/.server_env`. |
| `prompts.py` | System prompts for the planning and responder LLM calls, plus `build_responder_user_prompt()`. |

---

## `common/` — shared utilities

| File | What it does |
|---|---|
| `configurator.py` | Loads `config.yaml` and `.env` files into a typed config object used by the rest of the agent. |
| `api_parser.py` | Parses Playwright-style API files (AST-based) into structured `EndpointDescription` / `APISpecification` models. Used when building tool descriptions from the `api/` index. |
| `tool_manager.py` | Converts MCP tool definitions into Pydantic tool classes usable by `pydantic-ai`. |
| `token_manager.py` | Handles reading and writing auth tokens (e.g. refreshing a session token back to `.server_env`). |
| `agent_state.py` | `AgentState` TypedDict — shared state schema passed between agent steps. |
| `types.py` | Core shared types: `ChatMessage`, `ChatModel` protocol. |
| `utils.py` | Logging helpers, `get_llm()` / `get_llm_signature()` factory shortcuts, and `compare_dicts()`. |
| `requirement_models.py` | Pydantic models for structured requirement analysis results. |
| `mcp_client.py` | MCP client wrapper for connecting to and calling MCP tool servers. |

---

## `providers/` — LLM backends

| File | What it does |
|---|---|
| `provider.py` | `ModelProvider` — reads `agent_llm_provider` / `agent_llm_model` from config and dynamically imports the right backend class. Supported: `openai`, `anthropic`, `google` / `google-gla`. |
| `openai.py` | OpenAI backend (wraps `pydantic-ai` OpenAI model). |
| `anthropic.py` | Anthropic backend (wraps `pydantic-ai` Anthropic model). |
| `google.py` | Google Gemini backend (wraps `pydantic-ai` Google model). |
