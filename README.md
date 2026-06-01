# PTE (Plan-Then-Execute) Agent

A LangGraph-based agent that plans and executes tasks using direct HTTP API calls against WebArena benchmark websites (GitLab, Reddit, Shopping).

## Prerequisites

1. **Python 3.12+**
2. **Virtual Environment** — already set up in `venv/`; activate it before running anything:
   ```bash
   source venv/bin/activate  # macOS/Linux
   ```
3. **Dependencies**:
   ```bash
   pip install -r config/pip_requirements.txt
   ```
4. **WebArena Setup**:
see https://github.com/ServiceNow/webarena-verified
---

## Configuration

### 1. LLM provider — `config/config.yaml`

Set the provider and model you want the agent to use:

```yaml
agent_llm_provider: openai        # Options: openai, anthropic, google, google-gla
agent_llm_model: gpt-4.1          # Must match a model listed under the provider
```

### 2. API keys, credentials, and auth tokens — `config/.env` / `config/.server_env`

See [config/README.md](config/README.md) for full setup instructions, including LLM API keys, site credentials, `REMOTE_HOST`, and server auth tokens.

---

## Initializing the Environment

Before running the agent or any tests, start the supporting services:

```bash
python3 initialize.py username@red5k.cs.berkeley.edu
```

This script:
1. Opens SSH port-forwarding tunnels to the remote worker machine (single-instance and multi-docker).
2. Starts the Shopping Extra API on port 7790.
3. Health-checks all configured servers (GitLab, Shopping, Reddit, Shopping Extra).
4. Stays alive until Ctrl-C, then shuts everything down cleanly.

The remote host can also be set in `config/.env` as `REMOTE_HOST` instead of passing it on the command line.

```bash
# Skip the Shopping Extra API (e.g. for GitLab-only runs):
python3 initialize.py --no-shopping-extra username@red5k.cs.berkeley.edu
```

---

## Running the Agent

The agent makes direct HTTP/REST calls — no MCP servers needed.

```bash
python3 -m agent.agent
```

Or run the full benchmark evaluation suite — see [eval/README.md](eval/README.md) for all options (filtering by site, task ID, custom agents, result logging, and more).

---

## Project Structure

```
PTE/
├── initialize.py               # One-shot env setup: SSH tunnels + Shopping Extra API + health checks
│
├── agent/                      # Plan → execute pipeline (see agent/README.md)
│   ├── agent.py                # Top-level entry point: wires PlanningAgent + ExecutionAgent
│   ├── planning_agent.py       # Selects API endpoints via LLM and builds execution plan
│   ├── execution_agent.py      # Runs each plan step as a curl HTTP request
│   ├── planner.py              # Pydantic models for execution steps and plan validation
│   ├── auth.py                 # Auth providers (header, cookie, token) and AuthRegistry
│   ├── prompts.py              # LLM system prompts
│   ├── common/                 # Shared utilities (config loader, types, token manager, etc.)
│   └── providers/              # LLM backends: openai.py, anthropic.py, google.py
│
├── api/                        # API schemas and server-specific prompts (see api/README.md)
│   ├── schemas/                # Swagger/OpenAPI schema files (GitLab, Shopping, etc.)
│   ├── servers/                # Local API servers (e.g. shopping_extra.py on port 7790)
│   ├── api_server_prompts.py   # Per-server planning hints
│   ├── gitlab_pw/              # Playwright-style API definitions (used by eval)
│   ├── reddit_pw/
│   └── shopping_pw/
│
├── backend/                    # Standalone LLM backend wrappers
│   ├── anthropic_backend.py
│   ├── gemini_backend.py
│   └── openai_backend.py
│
├── config/                     # All configuration files (see config/README.md)
│   ├── config.yaml             # LLM provider/model selection
│   ├── servers.py              # Server URL and credential definitions (SERVERS, SERVER_URLS)
│   ├── .env.example            # Template — copy to .env and fill in keys
│   ├── .env                    # LLM API keys + REMOTE_HOST (not committed)
│   ├── .server_env             # Server auth tokens (not committed)
│   └── init_tokens/            # Token-refresh scripts (GitLab, Shopping)
│
├── eval/                       # Benchmark evaluation harness (see eval/README.md)
│   ├── run_program_html_benchmark.py
│   ├── docker/
│   │   ├── port_forwarding/    # SSH port-forwarding scripts (single + multi-docker)
│   │   └── workers_new.py      # Multi-docker worker pool
│   └── tests/                  # pytest test files (gitlab, shopping, conftest)
│
└── scripts/                    # Utility scripts
    └── run_tasks_batch_new.py  # Run a batch of tasks with plan + execute
```

---

## How to Add a New API

Go to `api/`, duplicate `api/template.py`, and follow the instructions at the top of the file. Do this in a new branch and submit a PR when done.

---

## Documentation

| README | What it covers |
|--------|---------------|
| [agent/README.md](agent/README.md) | How the plan → execute pipeline works; descriptions of every file in `agent/` |
| [config/README.md](config/README.md) | `config.yaml` options, LLM API key setup, and server auth token setup |
| [api/README.md](api/README.md) | API schema files, server-specific prompts, and Playwright API directories |
| [eval/README.md](eval/README.md) | Full benchmark evaluation guide: running tests, filtering, custom agents, scoring, and common failures |
| [eval/docker/port_forwarding/README.md](eval/docker/port_forwarding/README.md) | Running multiple Docker instances: VS Code port config, managing workers, and port forwarding |
