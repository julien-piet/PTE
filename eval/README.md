# eval/

Benchmark evaluation harness for the PTE agent. Runs the agent on tasks from the [WebArena](https://webarena.dev/) benchmark across four simulated websites: GitLab, Reddit, Shopping, and Shopping Admin.

All commands below should be run from the **project root** (`PTE/`).

---

## How it works

Each benchmark task is a natural-language instruction (e.g. *"Post 'lgtm' on the merge request related to the semantic HTML post"*). The agent attempts to complete it, and the harness checks whether it succeeded.

There are three ways success is measured, depending on the task type:

| Eval type | How it is checked | Example task |
|---|---|---|
| `program_html` (~371 tasks) | A Playwright browser navigates to a verification URL and checks the actual page content after the agent runs | Post a comment, create an issue, fill a form |
| `url_match` (71 tasks) | The agent's reported `final_url` is compared against a reference URL | Navigate to a specific settings page |
| `string_match` (241 tasks) | The agent's text answer is checked for required and forbidden substrings | "What is the top-selling product?" |

---

## Directory layout

```
eval/
├── run_program_html_benchmark.py   # Core engine. Orchestrates task execution and
│                                   # evaluation for all three eval types.
│                                   # Also defines BaseAgentRunner (the abstract
│                                   # interface any agent must implement) and
│                                   # AgentRunner (the default PTE implementation).
│
├── program_html_evaluator.py       # Used by the engine for program_html tasks.
│                                   # Opens a Playwright browser, logs in, navigates
│                                   # to the eval URL, and checks DOM content.
│
├── url_match_evaluator.py          # Used by the engine for url_match tasks.
│                                   # Compares the agent's final URL against the
│                                   # reference URL (exact, prefix, or substring match).
│
├── gitlab_state_reset.py           # Used by the engine before each GitLab task.
│                                   # Deletes comments/forks left by previous runs
│                                   # so each task starts from a clean state.
│
├── agent_runner_template.py        # Copy this to plug in a custom agent.
│                                   # Subclass BaseAgentRunner and fill in two methods:
│                                   # _init_agent() and _run_task(). See below.
│
└── tests/
    ├── conftest.py                  # Shared pytest setup. Provides the agent_runner
    │                                # fixture (initialised once per session) and
    │                                # CLI options: --task-limit, --site, --agent-runner,
    │                                # --server.
    │
    ├── test_agent_program_html.py   # 371 integration tests, one per program_html task.
    │                                # Runs the agent, then opens a fresh browser to
    │                                # verify the result on the actual page.
    │
    ├── test_agent_url_match.py      # 71 integration tests, one per url_match task.
    │                                # Checks that the agent's final_url matches
    │                                # the expected URL.
    │
    ├── test_agent_string_match.py   # 241 integration tests, one per string_match task.
    │                                # Checks that the agent's answer contains all
    │                                # required substrings and none of the forbidden ones.
    │
    └── raw_webarena_tasks_no_map.json   # Master task file. 683 tasks from the WebArena
                                         # benchmark. All three test files load from this
                                         # single source and filter by eval type at runtime.
                                         # Do not delete or rename this file.
```

---

## Prerequisites

Before running any tests, you need three things set up:

### 1. WebArena containers running

The agent connects to local instances of the benchmark websites:

| Site | URL |
|---|---|
| GitLab | `http://localhost:8023` |
| Reddit | `http://localhost:9999` |
| Shopping | `http://ec2-18-218-205-96.us-east-2.compute.amazonaws.com:8082` |
| Shopping Admin | `http://ec2-18-218-205-96.us-east-2.compute.amazonaws.com:8082/admin` |

### 2. LLM API key in `config/.env`

Set the key for whichever provider is configured in `config/config.yaml`:

```
OPENAI_API_KEY=sk-proj-...
```

See `config/README.md` for other providers (Anthropic, Google).

### 3. GitLab server token in `config/.server_env`

The agent makes direct REST API calls to GitLab using a Personal Access Token (PAT).
This file is **not committed** — each person creates it once locally.

```
GITLAB_TOKEN=glpat-xxxxxxxxxxxxxxxxxxxx
```

To create a token: go to `http://localhost:8023/-/user_settings/personal_access_tokens`,
log in as `byteblaze` / `hello1234`, create a token with the `api` scope, and copy the `glpat-...` value.

> Note: if the GitLab Docker container is wiped and reset, you will need to create a new token.

---

## Running tests

### Default: use the PTE agent

```bash
# Smoke test — 2 tasks, verbose output
python3 -m pytest eval/tests/test_agent_program_html.py --task-limit 2 -v -s

# Run all program_html tasks (~371)
python3 -m pytest eval/tests/test_agent_program_html.py -v

# Run all url_match tasks (71)
python3 -m pytest eval/tests/test_agent_url_match.py -v

# Run all string_match tasks (241)
python3 -m pytest eval/tests/test_agent_string_match.py -v

# Run everything (683 tasks total)
python3 -m pytest eval/tests/ -v
```

### Filter by site

```bash
python3 -m pytest eval/tests/ -k "gitlab" -v
python3 -m pytest eval/tests/ -k "reddit" -v
python3 -m pytest eval/tests/ -k "shopping_admin" -v
python3 -m pytest eval/tests/ -k "shopping and not admin" -v
```

### Run a single task by ID

```bash
python3 -m pytest eval/tests/ -k "task_389" -v -s
```

### Limit to the first N tasks

```bash
python3 -m pytest eval/tests/test_agent_program_html.py --task-limit 10 -v
```

### Combine filters

```bash
# First 5 reddit tasks
python3 -m pytest eval/tests/test_agent_program_html.py --site reddit --task-limit 5 -v -s
```

### Save output to a file

```bash
python3 -m pytest eval/tests/ -v 2>&1 | tee my_results.txt
```

---

## Plugging in a custom agent

Any agent can be evaluated using `--agent-runner`. You implement two methods and the harness handles the rest.

### Step 1 — Copy the template

```bash
cp eval/agent_runner_template.py my_agent_runner.py
```

### Step 2 — Fill in two methods

```python
from eval.run_program_html_benchmark import BaseAgentRunner

class MyAgentRunner(BaseAgentRunner):

    async def _init_agent(self) -> None:
        # Called once at the start of the test session.
        # Set up your agent, load models, connect to APIs, etc.
        self.agent = MyAgent(api_key="...")

    async def _run_task(self, task: dict) -> dict:
        # Called once per task. Run your agent and return its result.
        result = await self.agent.run(task["intent"])
        return {
            "final_url": result.url,    # str | None  (needed for url_match tasks)
            "answer":    result.answer, # str | None  (needed for string_match tasks)
        }
        # To signal a hard failure: return {"success": False, "error": "what went wrong"}
```

The `task` dict has these fields if your agent needs context beyond the instruction:

| Field | Example value | Description |
|---|---|---|
| `task["intent"]` | `"Post 'lgtm' on the MR..."` | The natural-language instruction to your agent |
| `task["task_id"]` | `389` | Unique integer ID |
| `task["sites"]` | `["gitlab"]` | Which website(s) are involved |
| `task["start_url"]` | `"__GITLAB__/primer/design/-/merge_requests"` | Starting page (`__GITLAB__` etc. are placeholder tokens) |
| `task["eval"]` | `{...}` | Evaluation config — you can ignore this |

Base URLs for the placeholder tokens:

| Token | URL |
|---|---|
| `__GITLAB__` | `http://localhost:8023` |
| `__REDDIT__` | `http://localhost:9999` |
| `__SHOPPING__` | `http://ec2-18-218-205-96.us-east-2.compute.amazonaws.com:8082` |
| `__SHOPPING_ADMIN__` | `http://ec2-18-218-205-96.us-east-2.compute.amazonaws.com:8082/admin` |

### Step 3 — Smoke test

```bash
python3 -m pytest eval/tests/test_agent_program_html.py \
    --agent-runner my_agent_runner.MyAgentRunner \
    --task-limit 2 -v -s
```

### Step 4 — Full run

```bash
python3 -m pytest eval/tests/ \
    --agent-runner my_agent_runner.MyAgentRunner -v \
    2>&1 | tee my_results.txt
```

---

## Scoring

```
Overall score          = total passed / 683
program_html accuracy  = passed / 371
url_match accuracy     = passed / 71
string_match accuracy  = passed / 241
```

Excluded task IDs (unsupported by benchmark): `118`, `528–532`, `585–589`

---

## GitLab state reset

Before each GitLab task, the harness automatically resets relevant state:
- Deletes any MR comments posted by `byteblaze` in previous runs (so the agent's comment will appear as the most recent one when evaluated)
- Deletes any forks created by `byteblaze` (so the agent can re-create them cleanly)

This is always on when running via `pytest`. The state reset uses the GitLab REST API — it is fast, quiet, and will not abort a task if it fails.

---

## Common failures

| Error | Cause |
|---|---|
| `Server 'gitlab' not found in auth registry` | `config/.server_env` is missing or `GITLAB_TOKEN` is not set. Create a PAT at `http://localhost:8023/-/user_settings/personal_access_tokens`. |
| `step_N produced no extractable value` | The agent's execution plan failed to chain API call results. Agent bug in `execution_agent.py`. |
| `HTTP 404` on an API call | The agent resolved the wrong project ID or MR IID. Agent planning/execution bug. |
| `Task timed out` | Agent is too slow or stuck in a loop. |
| `actual_url is None or empty` | `_run_task()` did not populate `"final_url"`. Required for url_match tasks. |
| `missing: ['some text']` | Agent completed the task but got a detail wrong (wrong wording, wrong item). |
| `Login failed` | Site credentials are wrong or the WebArena container is not running. |
| `answer: (empty)` | `_run_task()` returned `None` or `""` for `"answer"`. Required for string_match tasks. |
