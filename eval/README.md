# PTE Evaluation

Evaluates an agent on WebArena tasks using two evaluation types:

- **`string_match`** — agent returns a text answer, compared against a reference answer
- **`program_html`** — after the agent finishes, Playwright navigates to a URL and checks the page content

---

## Task files

Verified task files live in `tests/test_files/`:

| File | Tasks | Site | Eval type |
|------|-------|------|-----------|
| `gitlab_verified_program_html.json` | 117 | GitLab | program_html |
| `gitlab_verified_string_match.json` | 68 | GitLab | string_match |
| `reddit_verified_program_html.json` | 95 | Reddit | program_html |
| `reddit_verified_string_match.json` | 11 | Reddit | string_match |
| `shopping_program_html_verified.json` | 51 | Shopping | program_html |
| `shopping_verified_string_match.json` | 130 | Shopping | string_match |
| `raw_webarena_tasks_no_map.json` | 684 | All | all (unverified) |

---

## Running the evaluation

### GitLab (117 program_html tasks)

```bash
# Run all tasks
python3 -m pytest eval/tests/test_agent_verified_all_gitlab.py -v

# Save results to a JSON log
python3 -m pytest eval/tests/test_agent_verified_all_gitlab.py -v --output gitlab_results.json

# Smoke test — first 5 tasks only
python3 -m pytest eval/tests/test_agent_verified_all_gitlab.py --task-limit 5 -v -s

# Single task by ID
python3 -m pytest eval/tests/test_agent_verified_all_gitlab.py --task-id 389 -v -s

# Force-reset GitLab state before every task (use after a partial run leaves dirty state)
python3 -m pytest eval/tests/test_agent_verified_all_gitlab.py -v --force-reset

# Resume an interrupted run
python3 -m pytest eval/tests/test_agent_verified_all_gitlab.py -v --output gitlab_results.json --resume
```

### Reddit

```bash
# program_html tasks (95 tasks)
python3 -m pytest eval/tests/test_agent_verified_reddit_program_html.py -v

# string_match tasks (11 tasks)
python3 -m pytest eval/tests/test_agent_verified_reddit_string_match.py -v --server reddit

# Single task by ID
python3 -m pytest eval/tests/test_agent_verified_reddit_program_html.py --task-id 465 -v -s
python3 -m pytest eval/tests/test_agent_verified_reddit_string_match.py --task-id 389 -v -s --server reddit

# Resume an interrupted run
python3 -m pytest eval/tests/test_agent_verified_reddit_program_html.py -v --output reddit_program_html_results.json --resume
```

### Shopping

```bash
# program_html tasks (51 tasks)
python3 -m pytest eval/tests/test_agent_verified_shopping_program_html.py -v

# string_match tasks (130 tasks)
python3 -m pytest eval/tests/test_agent_verified_shopping_string_match.py -v --server shopping

# Single task by ID
python3 -m pytest eval/tests/test_agent_verified_shopping_program_html.py --task-id 465 -v -s
python3 -m pytest eval/tests/test_agent_verified_shopping_string_match.py --task-id 21 -v -s --server shopping

# Resume an interrupted run
python3 -m pytest eval/tests/test_agent_verified_shopping_program_html.py -v --output shopping_program_html_results.json --resume
python3 -m pytest eval/tests/test_agent_verified_shopping_string_match.py -v --server shopping --output shopping_string_match_results.json --resume
```

---

## Plugging in a custom agent

The default agent is `AgentRunner` (PTE ToolCallAgent + MCP tools) defined in `agent_runner.py`. To use a different agent, subclass `BaseAgentRunner` from `run_program_html_benchmark.py` and pass the class via `--agent-runner`:

```bash
python3 -m pytest eval/tests/test_agent_verified_all_gitlab.py \
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
| `--task-id ID[,ID,...]` | Run only the specified task ID(s), comma-separated |
| `--output FILENAME` | Write results JSON to `tests/logs/<FILENAME>` |
| `--resume` | Skip tasks already recorded in the `--output` file |
| `--force-reset` | Reset server state before every task (ignores `require_reset` field) |
| `--server SERVER` | Site the agent authenticates against (`gitlab`, `reddit`, `shopping`). Default: `gitlab` |
| `--base-url URL` | Override the default base URL for the target server |
| `--agent-runner MODULE.CLASS` | Use a custom agent runner instead of the default |
| `--multi-docker` | Use the remote multi-docker worker pool (GitLab only) |

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
├── agent_runner.py                      # Default AgentRunner implementation (PTE agent)
├── gitlab_state_reset.py                # Resets GitLab to a known state before write tasks
├── program_html_evaluator.py            # ProgramHtmlEvaluator — Playwright-based checker
├── run_program_html_benchmark.py        # BaseAgentRunner, AgentRunner, BaselineRunner
├── url_match_evaluator.py               # UrlMatchEvaluator — used internally by the runner
└── tests/
    ├── conftest.py                                      # Shared pytest fixtures and CLI options
    ├── agent_test_utils.py                              # Shared utilities (extract_agent_details, task_status)
    ├── test_agent_verified_all_gitlab.py                # 117 GitLab program_html tasks
    ├── test_agent_verified_reddit_program_html.py       # 95 Reddit program_html tasks
    ├── test_agent_verified_reddit_string_match.py       # 11 Reddit string_match tasks
    ├── test_agent_verified_shopping_program_html.py     # 51 Shopping program_html tasks
    ├── test_agent_verified_shopping_string_match.py     # 130 Shopping string_match tasks
    ├── logs/                                            # Output JSON files from test runs
    └── test_files/
        ├── gitlab_verified_program_html.json            # 117 verified GitLab program_html tasks
        ├── gitlab_verified_string_match.json            # 68 verified GitLab string_match tasks
        ├── reddit_verified_program_html.json            # 95 verified Reddit program_html tasks
        ├── reddit_verified_string_match.json            # 11 verified Reddit string_match tasks
        ├── shopping_program_html_verified.json          # 51 verified Shopping program_html tasks
        ├── shopping_verified_string_match.json          # 130 verified Shopping string_match tasks
        └── raw_webarena_tasks_no_map.json               # 684 all-site tasks (unverified)
```
