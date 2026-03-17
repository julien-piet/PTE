# eval/

Benchmark evaluation harness for the PTE agent, using tasks from the WebArena benchmark across four simulated sites: GitLab, Reddit, Shopping, and Shopping Admin.

All commands below should be run from the **project root** (`PTE/`).

---

## Directory layout

```
eval/
├── run_program_html_benchmark.py   # Core benchmark engine + CLI entry point
├── agent_runner_template.py        # Template for plugging in a custom agent
├── program_html_evaluator.py       # Evaluates program_html tasks via Playwright DOM checks
├── url_match_evaluator.py          # Evaluates url_match tasks by comparing URLs
├── gitlab_state_reset.py           # Pre-task state cleanup for GitLab tasks
└── tests/
    ├── conftest.py                       # Shared pytest config, fixtures, CLI options
    ├── test_agent_program_html.py        # Integration tests: program_html tasks (~371)
    ├── test_agent_string_match.py        # Integration tests: string_match tasks (241)
    ├── test_agent_url_match.py           # Integration tests: url_match tasks (71)
    ├── test_program_html_evaluator.py    # Unit tests for the program_html evaluator
    ├── test_url_match_evaluator.py       # Unit tests for the url_match evaluator
    ├── raw_webarena_tasks_no_map.json    # Main task file (683 tasks)
    └── *.json                            # Filtered subsets of tasks
```
<!-- 
---

## Prerequisites

<!-- 1. **WebArena containers** must be running:

   | Site | URL |
   |---|---|
   | GitLab | `http://localhost:8023` |
   | Reddit | `http://localhost:9999` |
   | Shopping | `http://ec2-18-218-205-96.us-east-2.compute.amazonaws.com:8082` |
   | Shopping Admin | `http://ec2-18-218-205-96.us-east-2.compute.amazonaws.com:8082/admin` |

2. **MCP servers** running in separate terminals (from `PTE/`):

   ```bash
   python3 -m servers.gitlab_server   # → port 8001
   python3 -m servers.reddit_server   # → port 8002
   ```

   > The warning about port 8000 (webarena) on startup is normal — ignore it. -->

<!-- 3. **LLM API key** set as an environment variable:

   ```bash
   export YOUR_API_KEY="..."
   ``` -->

--- -->

## Test files

There are three integration test files, one per evaluation type:

| File | Tasks | What is evaluated |
|---|---|---|
| `tests/test_agent_program_html.py` | ~371 | Agent must mutate page state (post comment, create issue, fill form, etc.). A fresh Playwright browser verifies the result by checking the actual page after the agent runs. |
| `tests/test_agent_url_match.py` | 71 | Agent must navigate to the correct URL. The agent's `final_url` is compared against the reference URL. |
| `tests/test_agent_string_match.py` | 241 | Agent must return a correct text answer. Checked for required (`must_include`) and forbidden (`must_exclude`) substrings. |

**Excluded task IDs** (across all test files): `118`, `528–532`, `585–589`

Unit tests for evaluator logic:
- `tests/test_program_html_evaluator.py`
- `tests/test_url_match_evaluator.py`

---

## Plugging in a custom agent

The test suite accepts any agent via `--agent-runner`. The value is a dotted `MODULE.CLASS` path importable from the project root.

### Step 1 — Copy the template

```bash
cp eval/agent_runner_template.py agent_runner.py
```

### Step 2 — Fill in two methods

```python
from eval.run_program_html_benchmark import BaseAgentRunner

class MyAgentRunner(BaseAgentRunner):

    async def _init_agent(self) -> None:
        # Called once at the start of the test session.
        # Initialise your agent, API clients, etc. here.
        self.agent = MyAgent(api_key="...")

    async def _run_task(self, task: dict) -> dict:
        # Called once per task. task["intent"] is the natural-language instruction.
        result = await self.agent.run(task["intent"])
        return {
            "final_url": result.url,     # str | None — required for url_match tasks
            "answer":    result.answer,  # str | None — required for string_match tasks
        }
        # On hard failure: return {"success": False, "error": "description"}
```

Other available fields in `task` if your agent needs context:

| Field | Description |
|---|---|
| `task["task_id"]` | Unique integer ID |
| `task["sites"]` | e.g. `["gitlab"]` |
| `task["start_url"]` | Starting page (may contain `__GITLAB__` placeholder) |
| `task["eval"]` | Evaluation config (you can ignore this) |

### Step 3 — Smoke test

```bash
python3 -m pytest eval/tests/test_agent_program_html.py \
    --agent-runner agent_runner.MyAgentRunner \
    --task-limit 2 -v -s
```

---

## Running tests

Replace `agent_runner.MyAgentRunner` with your module name and class name throughout.

### Full run by eval type

```bash
python3 -m pytest eval/tests/test_agent_program_html.py \
    --agent-runner agent_runner.MyAgentRunner -v

python3 -m pytest eval/tests/test_agent_url_match.py \
    --agent-runner agent_runner.MyAgentRunner -v

python3 -m pytest eval/tests/test_agent_string_match.py \
    --agent-runner agent_runner.MyAgentRunner -v
```

### Filter by site

```bash
python3 -m pytest eval/tests/ \
    --agent-runner agent_runner.MyAgentRunner \
    -k "gitlab" -v

python3 -m pytest eval/tests/ \
    --agent-runner agent_runner.MyAgentRunner \
    -k "reddit" -v

python3 -m pytest eval/tests/ \
    --agent-runner agent_runner.MyAgentRunner \
    -k "shopping" -v
```

### Limit number of tasks

```bash
python3 -m pytest eval/tests/ \
    --agent-runner agent_runner.MyAgentRunner \
    --task-limit 10 -v
```

### Run a single task by ID

```bash
python3 -m pytest eval/tests/ \
    --agent-runner agent_runner.MyAgentRunner \
    -k "task_389" -v -s
```

### Save output to a file

```bash
python3 -m pytest eval/tests/test_agent_program_html.py \
    --agent-runner agent_runner.MyAgentRunner -v \
    2>&1 | tee my_results.txt
```

---

## Calculating utility numbers

```
Overall utility         = total passed / 683
program_html accuracy   = passed / ~371
url_match accuracy      = passed / 71
string_match accuracy   = passed / 241
```

---

## GitLab state reset

For certain GitLab tasks, the benchmark automatically resets GitLab to a known-good state before the agent runs (deletes MR comments left by `byteblaze`, removes forks so the agent can re-create them). This is always enabled when running via `pytest`.

To disable for the CLI runner (faster, but results may not be reproducible):

```bash
python3 eval/run_program_html_benchmark.py --no-reset
```

---

## Common failures

| Error message | Cause |
|---|---|
| `Task timed out after 90 seconds` | Agent is too slow or stuck in a loop. |
| `actual_url is None or empty` | `_run_task()` didn't populate `"final_url"`. |
| `missing: ['some text', ...]` | Agent did the right thing but got a detail wrong (wrong wording, wrong item). |
| `Login failed` | Site credentials issue or WebArena container not running. |
| `answer: (empty)` | `_run_task()` returned `None` or `""` for `"answer"` on a string_match task. |
