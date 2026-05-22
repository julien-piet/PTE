# /agent

The agent package implements a two-phase **plan → execute** pipeline for completing natural language tasks against web server APIs.

## How it works

1. **PlanningAgent** reads the available Swagger/OpenAPI schemas from `api/`, uses an LLM to select the right endpoints, and produces a validated execution plan.
2. **ExecutionAgent** runs each step in the plan as a real HTTP request (via `curl`), resolves inter-step dependencies, handles foreach/fan-out, and synthesises a natural language answer.
3. **Agent** is a thin wrapper that wires both together for single-prompt use.

---

## Top-level files

| File | What it does |
|---|---|
| `agent.py` | High-level entry point. Calls `PlanningAgent.plan()` then `ExecutionAgent.execute()` in sequence. Injects runtime base URLs into the plan via `_inject_base_urls`. |
| `planning_agent.py` | Multi-step LLM pipeline: selects Swagger files from `api/index.json`, parses them with `prance`, excludes unrelated endpoints, builds a backward-chained execution plan, and validates it. Server-agnostic — all platform hints live in `api/`. |
| `execution_agent.py` | Executes each plan step as a `curl` call. Handles dependency ordering, `foreach` iteration, fan-out (one call per item in a list), LLM-based inter-step output parsing, and final answer generation. Routes arguments to path/query/body via `param_in` on each `Argument`. |
| `planner.py` | Pydantic model factory (`build_agent_models`) that generates runtime-typed `Argument` / `ExecutionStep` / `ConditionalStep` / `ToolBasedResponse` classes from the allowed tool list. Also contains `ExecutionContext` (tracks step state) and plan validation / pretty-print helpers. |
| `auth.py` | Authentication providers (`HeaderAuth`, `CookieAuth`, `MultiAuth`, `StaticAuth`) and `AuthRegistry`, which maps server names to their auth strategy. Tokens are read from `config/.server_env`. To add a new server: add its token key to `.server_env` and register it in `AuthRegistry.build_default()`. |
| `planning_agent_old.py` | Legacy planning agent (MCP tool-based). Superseded by `planning_agent.py`. Not used in the current pipeline. |
| `prompts.py` | Unused legacy prompt strings. Not imported anywhere. |

---

## `common/` — shared utilities

| File | What it does |
|---|---|
| `configurator.py` | Reads `config/config.yaml` and the three `.env` files (client, shared, server) into a typed config object. Used by `planning_agent.py`, `execution_agent.py`, and `providers/`. |
| `types.py` | Core shared types: `ChatMessage` Pydantic model and `ChatModel` protocol. |
| `utils.py` | `get_mcp_logger` — sets up a file-based logger for MCP servers. |
| `tool_manager.py` | MCP tool infrastructure: `ToolDefinition` model and `build_pydantic_tools_from_mcp`. Not used by the current curl-based pipeline. |
| `mcp_client.py` | Async MCP client (via `fastmcp`) for calling MCP tool servers. Not used by the current pipeline. |
| `token_manager.py` | `TokenStore` — loads and stores auth tokens for MCP tool authentication. Not used by the current pipeline. |

---

## `providers/` — LLM backends

| File | What it does |
|---|---|
| `provider.py` | `ModelProvider` — reads `agent_llm_provider` / `agent_llm_model` from config and dynamically imports the right backend. Supported: `openai`, `anthropic`, `google` / `google-gla`. |
| `openai.py` | OpenAI backend (wraps `pydantic-ai` OpenAI model). |
| `anthropic.py` | Anthropic backend (wraps `pydantic-ai` Anthropic model). |
| `google.py` | Google Gemini backend (wraps `pydantic-ai` Google model). |

---

## Server-agnostic configuration

Runtime server hints live outside the agent code so adding a new server never requires editing agent source:

| File | Purpose |
|---|---|
| `api/index.json` | Maps Swagger filenames to short descriptions — used by the LLM to select which schema files to load. |
| `api/api_hints.json` + `api/api_server_prompts.py` | Per-schema prompt hints injected into planning steps to guide the LLM on API-specific conventions. |
| `config/servers.py` | Canonical server definitions (URL, label, username env var). User context for planning is derived from here; add a new server entry to support its user context automatically. |
| `config/.server_env` | Auth tokens for all servers. Read by `AuthRegistry.build_default()`. |
