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

---

## Configuration

### 1. LLM provider — `config/config.yaml`

Set the provider and model you want the agent to use:

```yaml
agent_llm_provider: openai        # Options: openai, anthropic, google, google-gla
agent_llm_model: gpt-4.1          # Must match a model listed under the provider
```

### 2. API keys — `config/.env`

Copy the example file and fill in the key for your active provider:

```bash
cp config/.env.example config/.env
```

```
OPENAI_API_KEY=sk-proj-...       # if using openai
ANTHROPIC_API_KEY=sk-ant-...     # if using anthropic
GEMINI_API_KEY=AIza...           # if using google-gla
```

### 3. Server auth tokens — `config/.server_env`

Required for the agent to make authenticated API calls to the benchmark servers. This file is **not committed** — create it once locally:

```
GITLAB_TOKEN=glpat-xxxxxxxxxxxxxxxxxxxx
CUSTOMER_AUTH_TOKEN=<customer JWT>
ADMIN_AUTH_TOKEN=<admin JWT>
```

To get a GitLab token: go to `http://localhost:8023/-/user_settings/personal_access_tokens`, log in as `byteblaze` / `hello1234`, and create a token with the `api` scope.

> Note: if the GitLab Docker container is reset, you will need to create a new token.

---

## Running the Agent

The agent makes direct HTTP/REST calls — no MCP servers needed.

```bash
python3 -m agent.agent
```

Or run a batch of tasks:

```bash
python3 scripts/run_tasks_batch.py
```

---

## Project Structure

```
PTE/
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
│   ├── index.json              # Agent's initial lookup to find relevant API files
│   ├── gitlab_api_schema.json  # Swagger 2.0 schema for GitLab
│   ├── shopping_api_schema.json
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
│   ├── .env.example            # Template — copy to .env and fill in keys
│   ├── .env                    # LLM API keys (not committed)
│   └── .server_env             # Server auth tokens (not committed)
│
├── eval/                       # Benchmark evaluation harness (see eval/README.md)
│   ├── run_program_html_benchmark.py
│   ├── agent_runner.py / agent_runner_template.py
│   ├── docker/                 # Worker management for parallel Docker eval runs
│   └── tests/                  # pytest test files for all three eval types
│
└── scripts/                    # Utility scripts
    ├── run_tasks_batch.py       # Run a batch of tasks with plan + execute
    ├── run_planning_batch.py    # Planning only (no execution)
    └── docker_parallel/         # Multi-Docker setup guide (see docker_parallel/README.md)
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
| [scripts/docker_parallel/README.md](scripts/docker_parallel/README.md) | Running multiple Docker instances: VS Code port config, managing workers, and port forwarding |
