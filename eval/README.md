# PTE Evaluation

Evaluates an agent on WebArena tasks using two evaluation types:

- **`string_match`** — agent returns a text answer, compared against a reference answer
- **`program_html`** — after the agent finishes, Playwright navigates to a URL and checks the page content

---

## Task files

| File | Tasks | Description |
|------|-------|-------------|
| `tests/raw_webarena_tasks_all_gitlab.json` | 186 | All GitLab tasks (string_match + program_html) |
| `tests/raw_webarena_tasks_no_map.json` | 684 | All WebArena tasks across all sites |

---

## Running the evaluation

### GitLab tasks only (recommended starting point)

```bash
# Run all 186 GitLab tasks
python3 -m pytest eval/tests/test_agent_all_gitlab.py -v

# Save results to a JSON log
python3 -m pytest eval/tests/test_agent_all_gitlab.py -v --output gitlab_results.json

# Smoke test — first 5 tasks only
python3 -m pytest eval/tests/test_agent_all_gitlab.py --task-limit 5 -v -s

# Single task by ID
python3 -m pytest eval/tests/test_agent_all_gitlab.py -k "task_389" -v -s

# Force-reset GitLab state before every task (use after a partial run leaves dirty state)
python3 -m pytest eval/tests/test_agent_all_gitlab.py -v --force-reset
```

### All WebArena tasks

```bash
# program_html tasks (~371 tasks across all sites)
python3 -m pytest eval/tests/test_agent_program_html.py -v

# string_match tasks (~241 tasks across all sites)
python3 -m pytest eval/tests/test_agent_string_match.py -v

# Both together
python3 -m pytest eval/tests/ -v

# Filter by site
python3 -m pytest eval/tests/test_agent_program_html.py -k "gitlab" -v
python3 -m pytest eval/tests/test_agent_program_html.py -k "shopping_admin" -v
```

---

## Plugging in a custom agent

The default agent is `AgentRunner` (PTE ToolCallAgent + MCP tools) defined in `agent_runner.py`. To use a different agent, subclass `BaseAgentRunner` from `run_program_html_benchmark.py` and pass the class via `--agent-runner`:

```bash
python3 -m pytest eval/tests/test_agent_all_gitlab.py \
    --agent-runner my_module.MyAgentRunner -v -s
```

Your subclass must implement two methods:

```python
from eval.run_program_html_benchmark import BaseAgentRunner

class MyAgentRunner(BaseAgentRunner):

    async def _init_agent(self) -> None:
        # Called once at the start of the session.
        # Initialise your agent, API clients, etc.
        self.agent = MyAgent(...)

    async def _run_task(self, task: dict) -> dict:
        # Called once per task. Run your agent on task["intent"].
        # Return:
        #   {"final_url": str | None, "answer": str | None}  on success
        #   {"success": False, "error": "description"}        on failure
        result = await self.agent.run(task["intent"])
        return {"final_url": result.url, "answer": result.answer}
```

- `answer` is required for `string_match` tasks
- `final_url` is required for `program_html` tasks where `url` is `"last"` and there is no `reference_url` fallback

---

## CLI options reference

| Option | Description |
|--------|-------------|
| `--task-limit N` | Only run the first N tasks |
| `--output FILENAME` | Write results JSON to `tests/logs/<FILENAME>` |
| `--force-reset` | Reset GitLab state before every task (ignores `require_reset` field) |
| `--agent-runner MODULE.CLASS` | Use a custom agent runner instead of the default |
| `--server SERVER` | Site the agent authenticates against (`gitlab`, `reddit`, `shopping`). Default: `gitlab` |

---

## Eval logic

### `string_match`

The agent's `answer` is checked against `reference_answers` in the task:

| Key | Check |
|-----|-------|
| `must_include` | Every item must appear in the answer (case-insensitive) |
| `must_exclude` | No item may appear in the answer (case-insensitive) |
| `exact_match` | Answer must equal the reference after whitespace normalisation |
| `fuzzy_match` | Each item must appear approximately (SequenceMatcher ratio ≥ 0.8) |
| `fuzzy_match: "N/A"` | Task is impossible — always passes |

A `must_include` item that is itself a list `["A", "B"]` means **at least one** of the alternatives must be present (OR logic).

### `program_html`

After the agent finishes, for each entry in `program_html`:

1. **Navigate** to the entry's `url`:
   - A literal URL (e.g. `__GITLAB__/byteblaze/dotfiles/-/project_members`) → navigate there directly
   - `"last"` → use the agent's `final_url`; falls back to `reference_url` if `final_url` is `None`
2. **Extract** content using the `locator` (a JS expression evaluated in the page context). Empty locator falls back to `document.body.outerText`.
3. **Check** the extracted content against `required_contents` (`must_include`, `exact_match`, `must_exclude`).

All entries must pass for the task to pass.

---

## File structure

```
eval/
├── agent_runner.py              # Default AgentRunner implementation (PTE agent)
├── docker_worker_pool.py        # Parallel worker pool for multi-worker runs
├── gitlab_state_reset.py        # Resets GitLab to a known state before write tasks
├── program_html_evaluator.py    # ProgramHtmlEvaluator — Playwright-based checker
├── run_program_html_benchmark.py# BaseAgentRunner, AgentRunner, BaselineRunner
├── url_match_evaluator.py       # UrlMatchEvaluator — used internally by the runner
└── tests/
    ├── conftest.py                          # Shared pytest fixtures and CLI options
    ├── raw_webarena_tasks_all_gitlab.json   # 186 GitLab tasks
    ├── raw_webarena_tasks_no_map.json       # 684 all-site WebArena tasks
    ├── test_agent_all_gitlab.py             # Runs all 186 GitLab tasks
    ├── test_agent_program_html.py           # Runs all program_html tasks (all sites)
    └── test_agent_string_match.py           # Runs all string_match tasks (all sites)
```
