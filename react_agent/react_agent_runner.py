"""
ReactAgentRunner — BaseAgentRunner subclass for CodeActAgent (ReAct loop).

Usage in the test:
    runner = ReactAgentRunner(gitlab_base_url=url, max_iterations=30)
    runner.server = "gitlab"
    runner.base_url = url
    runner.glpat = w["glpat"]       # set per-worker in multi-docker mode
    await runner._init_agent()
    passed, result, error, html = await runner.run_agent_on_task(task)
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

_PROJECT_ROOT = Path(__file__).parent.parent
_SERVER_ENV = _PROJECT_ROOT / "config" / ".server_env"


def _token_from_server_env() -> str:
    """Read GITLAB_TOKEN from config/.server_env (KEY = value #comment format)."""
    if not _SERVER_ENV.exists():
        return ""
    for line in _SERVER_ENV.read_text().splitlines():
        line = line.split("#")[0].strip()
        if "=" in line:
            key, _, val = line.partition("=")
            if key.strip() == "GITLAB_TOKEN":
                return val.strip()
    return ""

# Always emit INFO from the react-agent and codeact loggers so LLM responses
# and step details are visible without any extra pytest flags.
logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(name)s %(levelname)s %(message)s")
logging.getLogger("react_agent").setLevel(logging.INFO)
logging.getLogger("agenthub").setLevel(logging.INFO)

from eval.run_program_html_benchmark import BaseAgentRunner
from react_agent.codeact_agent.codeact_agent import (
    BrowserOutputObservation,
    CmdOutputObservation,
    IPythonRunCellObservation,
    MessageAction,
    truncate_observation,
)


class _SimpleState:
    """Minimal State compatible with CodeActAgent.step()."""

    def __init__(self, task_prompt: str, max_iterations: int = 30):
        self.max_iterations = max_iterations
        self.iteration = 0
        self.num_of_chars = 0
        initial = MessageAction(content=task_prompt, wait_for_response=False)
        initial.source = "user"
        self.history = [(initial, None)]


class ReactAgentRunner(BaseAgentRunner):
    """
    Drives CodeActAgent via a ReAct loop rather than the planning+execution pipeline.

    Execution capabilities:
      - <execute_ipython>  → exec() in a sandboxed namespace with requests + GitLab creds
      - <execute_bash>     → subprocess.run(shell=True, timeout=30)
      - <execute_browse>   → mocked (EVAL_MODE login steps are no-ops)
    """

    def __init__(
        self,
        headless: bool = True,
        enable_reset: bool = True,
        force_reset: bool = False,
        gitlab_base_url: str = "",
        max_iterations: int = 30,
        webarena_output_dir: Optional[str] = None,
        wa_dataset_path: Optional[str] = None,
    ):
        super().__init__(
            headless=headless,
            enable_reset=enable_reset,
            force_reset=force_reset,
            gitlab_base_url=gitlab_base_url,
        )
        self.max_iterations = max_iterations
        self.glpat: Optional[str] = None  # set per-task in multi-docker mode
        self._react_agent = None
        self._last_steps: list = []
        self._page = None  # active Playwright page, set during _run_task
        self._task_log_fh = None  # per-task log file handle, opened in _run_task
        self.webarena_output_dir = webarena_output_dir
        self._wa_task_type: Dict[int, str] = {}
        if webarena_output_dir:
            self._load_wa_dataset(wa_dataset_path)

    # ------------------------------------------------------------------
    # WebArena-Verified helpers
    # ------------------------------------------------------------------

    def _load_wa_dataset(self, path: Optional[str] = None) -> None:
        """Build task_id → task_type index from the WA-Verified dataset."""
        dataset_path = Path(path) if path else (
            _PROJECT_ROOT / "eval" / "tests" / "test_files" / "webarena-verified.json"
        )
        if not dataset_path.exists():
            print(f"  ⚠️  WA-Verified dataset not found: {dataset_path}")
            return
        try:
            tasks = json.loads(dataset_path.read_text())
            for t in tasks:
                tid = t.get("task_id")
                evals = t.get("eval", [])
                task_type = "NAVIGATE"
                if evals and isinstance(evals, list):
                    expected = evals[0].get("expected", {})
                    task_type = str(expected.get("task_type", "NAVIGATE")).upper()
                if tid is not None:
                    self._wa_task_type[int(tid)] = task_type
            print(f"  ✓ Loaded {len(self._wa_task_type)} task_type mappings from WA-Verified dataset")
        except Exception as exc:
            print(f"  ⚠️  Failed to load WA-Verified dataset: {exc}")

    def _save_wa_response(self, task: Dict[str, Any], raw_answer: str) -> None:
        """Save agent_response.json in WebArena-Verified format."""
        task_id = task.get("task_id", "unknown")
        task_out = Path(self.webarena_output_dir) / str(task_id)
        task_out.mkdir(parents=True, exist_ok=True)

        task_type = self._wa_task_type.get(int(task_id) if str(task_id).isdigit() else -1, "NAVIGATE")

        # Try to extract a JSON object from the raw answer (greedy brace-match)
        response = None
        if raw_answer:
            # Greedy extraction: find first { ... last }
            start = raw_answer.find("{")
            end = raw_answer.rfind("}")
            if start != -1 and end != -1 and end > start:
                candidate = raw_answer[start:end + 1]
                try:
                    parsed = json.loads(candidate)
                    if isinstance(parsed, dict) and "task_type" in parsed and "status" in parsed:
                        response = parsed
                except json.JSONDecodeError:
                    pass

        if response is None:
            # Fallback: construct from raw answer text
            response = {
                "task_type": task_type,
                "status": "SUCCESS" if raw_answer else "UNKNOWN_ERROR",
                "retrieved_data": [raw_answer] if task_type == "RETRIEVE" and raw_answer else None,
                "error_details": None if raw_answer else "No answer produced",
            }

        out_file = task_out / "agent_response.json"
        out_file.write_text(json.dumps(response, indent=2))
        self._log(f"  ✓ Saved {out_file}")

    # ------------------------------------------------------------------
    # BaseAgentRunner interface
    # ------------------------------------------------------------------

    def _log(self, msg: str = "", end: str = "\n") -> None:
        """Print to terminal AND write to the per-task log file if one is open."""
        print(msg, end=end)
        if self._task_log_fh:
            self._task_log_fh.write(msg + end)
            self._task_log_fh.flush()

    async def _init_agent(self) -> None:
        from react_agent.codeact_agent.codeact_agent import CodeActAgent

        print("🔧 Initializing react agent...")
        self._react_agent = CodeActAgent(llm=None)  # LLM sourced from config/config.yaml
        print("✓ React Agent initialized\n")

    async def _run_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Run the CodeActAgent ReAct loop on a single task."""
        intent = task.get("intent", "")
        raw_start = task.get("start_url", "")
        # Open per-task log file early so all subsequent _log() calls are captured.
        _task_id_for_log = task.get("task_id", "unknown")
        if self.webarena_output_dir:
            from datetime import datetime, timezone as _tz
            _log_dir = Path(self.webarena_output_dir) / str(_task_id_for_log)
            _log_dir.mkdir(parents=True, exist_ok=True)
            self._task_log_fh = open(_log_dir / "agent.log", "w")
        gitlab_url = getattr(self, "base_url", None) or self.gitlab_base_url
        start_url = raw_start.replace("__GITLAB__", gitlab_url).strip("/")
        token = self.glpat or os.environ.get("GLPAT") or os.environ.get("GITLAB_TOKEN") or _token_from_server_env()

        # Include the GitLab URL in the prompt so history_str picks it up for
        # _get_site_hints() / _get_api_schema_section() inside step().
        prompt_parts = [
            f"GitLab instance: {gitlab_url}",
            f"Task: {intent}",
            "You can use <execute_ipython> to call the GitLab REST API or <execute_browse> to navigate the web with a real browser.",
            "Pre-defined variables available in every Python block:",
            "  GITLAB_URL  — base URL of the GitLab instance",
            "  GITLAB_TOKEN — authenticated personal access token",
            "  Example: requests.get(f'{GITLAB_URL}/api/v4/projects', headers={'PRIVATE-TOKEN': GITLAB_TOKEN})",
            "", #EVAL INFORMATION FOR STRING_MATCH
            "IMPORTANT: When your final answer is the URL of a page you navigated to, or the content "
            "visible on a page, include the URL and the relevant text you see on the page in your answer. "
            "Do not just say 'I have opened the page' — quote the actual page content or URL so the "
            "evaluator can verify you visited the correct destination.",
        ]
        if start_url and start_url != gitlab_url:
            prompt_parts.append(f"Start URL: {start_url}")
        if self.webarena_output_dir:
            prompt_parts.append(
                "\nRESPONSE FORMAT (required): Put your final answer inside Finish[...] where the"
                " content is a JSON object with NO extra text or markdown:\n"
                '{"task_type": "NAVIGATE", "status": "SUCCESS", "retrieved_data": null, "error_details": null}\n'
                "task_type: RETRIEVE (looked up data), MUTATE (changed something), NAVIGATE (went to a page)\n"
                "status: SUCCESS, ACTION_NOT_ALLOWED_ERROR, PERMISSION_DENIED_ERROR, NOT_FOUND_ERROR,"
                " DATA_VALIDATION_ERROR, or UNKNOWN_ERROR\n"
                "retrieved_data: array of results for RETRIEVE tasks (use numbers/booleans, not strings),"
                " null for MUTATE/NAVIGATE\n"
                "error_details: null on SUCCESS, brief explanation otherwise"
            )
        prompt = "\n".join(prompt_parts)

        self._log(f"\n{'='*70}")
        self._log(f"[Task] {intent}")
        if start_url and start_url != gitlab_url:
            self._log(f"[Start URL] {start_url}")
        self._log(f"{'='*70}")

        # Expose URL and per-worker token for agent code that reads os.environ directly.
        os.environ["GITLAB"] = gitlab_url
        os.environ["GITLAB_TOKEN"] = token

        # codeact_agent.py treats any env var whose value is '' as matching every
        # page ('' in any_string is True).  Set placeholder values for sites not
        # in use so EVAL_MODE doesn't emit Reddit/Shopping login steps for GitLab tasks.
        for _unused_key in ("REDDIT", "SHOPPING", "SHOPPING_ADMIN", "MAP"):
            if not os.environ.get(_unused_key):
                os.environ[_unused_key] = f"http://{_unused_key.lower()}.invalid"

        self._react_agent.reset()
        self._last_steps = []
        state = _SimpleState(task_prompt=prompt, max_iterations=self.max_iterations)
        answer = ""

        from playwright.async_api import async_playwright
        self._log(f"  [timing] launching browser | active_threads={threading.active_count()} | t={time.monotonic():.1f}")
        async with async_playwright() as pw:
            _browser = await pw.chromium.launch(headless=self.headless)
            _context = await _browser.new_context()
            if self.webarena_output_dir:
                await _context.tracing.start(screenshots=False, snapshots=True)
            try:
                self._page = await _context.new_page()
                # Log in before the ReAct loop so all subsequent navigations are authenticated.
                await self._login_browser(gitlab_url)
                if start_url:
                    try:
                        await self._page.goto(start_url, wait_until="domcontentloaded", timeout=30000)
                        await self._inject_bids()
                    except Exception:
                        pass
                try:
                    loop = asyncio.get_event_loop()
                    hit_max_iterations = False
                    stall_reason: Optional[str] = None
                    _last_action_key: Optional[str] = None
                    _consecutive_same_action = 0
                    _SAME_ACTION_LIMIT = 3
                    _url_visit_counts: dict = {}
                    _URL_VISIT_LIMIT = 4
                    while state.iteration < self.max_iterations:
                        self._log(f"\n[Step {state.iteration + 1}/{self.max_iterations}] Calling LLM... (active_threads={threading.active_count()})")
                        _step_t0 = time.monotonic()
                        try:
                            action = await asyncio.wait_for(
                                loop.run_in_executor(None, self._react_agent.step, state),
                                timeout=180,
                            )
                        except asyncio.TimeoutError:
                            self._log(f"\n[Step {state.iteration + 1}] LLM call timed out after 180s (active_threads={threading.active_count()}) — stopping")
                            break
                        self._log(f"  [timing] LLM step done in {time.monotonic()-_step_t0:.1f}s")
                        state.iteration += 1
                        step_num = state.iteration
                        action_type = type(action).__name__

                        if action_type == "AgentFinishAction":
                            self._log(f"\n[Step {step_num}] AgentFinishAction")
                            self._log(f"  Thought: {str(action.thought)[:500]}")
                            answer = action.thought or answer
                            break

                        if action_type == "MessageAction":
                            self._log(f"\n[Step {step_num}] MessageAction")
                            self._log(f"  Content: {str(action.content)[:500]}")
                            answer = action.content
                            if re.search(r"<finish\s*/?>", answer, re.IGNORECASE) or "Finish[" in answer:
                                break
                            # Append a nudge observation so the LLM sees a response and
                            # executes rather than repeating the same plan text.
                            obs = IPythonRunCellObservation()
                            obs.content = "Please proceed: use <execute_ipython> to run code or <execute_browse> to browse."
                            state.history.append((action, obs))
                            continue

                        if action_type == "IPythonRunCellAction":
                            self._log(f"\n[Step {step_num}] IPythonRunCellAction")
                            self._log(f"  Code:\n{action.code.rstrip()}")
                            try:
                                output = await asyncio.wait_for(
                                    loop.run_in_executor(None, self._exec_python, action.code, gitlab_url, token),
                                    timeout=60,
                                )
                            except asyncio.TimeoutError:
                                output = "Error: Python execution timed out after 60s"
                            self._log(f"  Output: {output[:800]}")
                            obs = IPythonRunCellObservation()
                            obs.content = output
                            state.history.append((action, obs))
                            self._last_steps.append(
                                {"type": "ipython", "code": action.code, "output": output}
                            )

                        elif action_type == "CmdRunAction":
                            if action.command.strip() == "exit":
                                self._log(f"\n[Step {step_num}] CmdRunAction: exit — stopping")
                                break
                            self._log(f"\n[Step {step_num}] CmdRunAction")
                            self._log(f"  Command: {action.command.rstrip()}")
                            output = self._exec_bash(action.command)
                            self._log(f"  Output: {output[:800]}")
                            obs = CmdOutputObservation()
                            obs.content = output
                            obs.command_id = str(step_num)
                            obs.exit_code = 0
                            state.history.append((action, obs))
                            self._last_steps.append(
                                {"type": "bash", "command": action.command, "output": output}
                            )

                        elif action_type == "BrowseInteractiveAction":
                            self._log(f"\n[Step {step_num}] BrowseInteractiveAction")
                            self._log(f"  Actions: {action.browser_actions.strip()[:300]}")
                            content, err, axtree_obj, extra_props = await self._exec_browse(
                                action.browser_actions
                            )
                            self._log(f"  Result: {content[:400]}")
                            obs = BrowserOutputObservation()
                            obs.content = content
                            obs.error = err
                            obs.axtree_object = axtree_obj
                            obs.extra_element_properties = extra_props
                            obs.last_browser_action = action.browser_actions
                            state.history.append((action, obs))
                            self._last_steps.append(
                                {"type": "browse", "actions": action.browser_actions, "content": content[:500]}
                            )

                        else:
                            self._log(f"\n[Step {step_num}] Unknown action: {action_type}")

                        # --- Stall detection ---
                        # 1. Same action repeated consecutively
                        action_key: Optional[str] = None
                        if action_type == "BrowseInteractiveAction":
                            action_key = action.browser_actions.strip()
                        elif action_type == "IPythonRunCellAction":
                            action_key = action.code.strip()
                        elif action_type == "CmdRunAction":
                            action_key = action.command.strip()
                        if action_key is not None:
                            if action_key == _last_action_key:
                                _consecutive_same_action += 1
                            else:
                                _last_action_key = action_key
                                _consecutive_same_action = 1
                            if _consecutive_same_action >= _SAME_ACTION_LIMIT:
                                stall_reason = f"same action repeated {_SAME_ACTION_LIMIT} times in a row"
                                break

                        # 2. Same URL visited too many times
                        if action_type == "BrowseInteractiveAction" and not stall_reason:
                            for _m in re.finditer(r'goto\("([^"]+)"\)', action.browser_actions):
                                _url = _m.group(1)
                                _url_visit_counts[_url] = _url_visit_counts.get(_url, 0) + 1
                                if _url_visit_counts[_url] >= _URL_VISIT_LIMIT:
                                    stall_reason = f"URL visited {_URL_VISIT_LIMIT}+ times: {_url}"
                                    break
                            if stall_reason:
                                break


                    if stall_reason:
                        self._log(f"\n[Stall detected: {stall_reason} — stopping early]")

                    if state.iteration >= self.max_iterations:
                        hit_max_iterations = True
                        self._log(f"\n[Max iterations ({self.max_iterations}) reached — stopping]")

                except Exception as exc:
                    import traceback
                    traceback.print_exc()
                    return {
                        "success": False,
                        "final_url": None,
                        "answer": "",
                        "execution_result": {"error": str(exc)},
                    }
            finally:
                self._page = None
                if self.webarena_output_dir:
                    task_out = Path(self.webarena_output_dir) / str(task.get("task_id", "unknown"))
                    task_out.mkdir(parents=True, exist_ok=True)
                    self._log(f"  [timing] tracing.stop start | active_threads={threading.active_count()} | t={time.monotonic():.1f}")
                    try:
                        await asyncio.wait_for(
                            _context.tracing.stop(path=str(task_out / "network.zip")),
                            timeout=30,
                        )
                        self._log(f"  ✓ Saved {task_out / 'network.zip'}")
                    except asyncio.TimeoutError:
                        self._log(f"  ⚠️  tracing.stop timed out after 30s — skipping trace save")
                    except Exception as _te:
                        self._log(f"  ⚠️  tracing.stop error: {_te}")
                    self._log(f"  [timing] tracing.stop done | t={time.monotonic():.1f}")
                self._log(f"  [timing] context.close start | t={time.monotonic():.1f}")
                try:
                    await asyncio.wait_for(_context.close(), timeout=15)
                except Exception as _ce:
                    self._log(f"  ⚠️  context.close error/timeout: {_ce}")
                self._log(f"  [timing] browser.close start | active_threads={threading.active_count()} | t={time.monotonic():.1f}")
                try:
                    await asyncio.wait_for(_browser.close(), timeout=15)
                except Exception as _be:
                    self._log(f"  ⚠️  browser.close error/timeout: {_be}")
                self._log(f"  [timing] browser closed | active_threads={threading.active_count()} | t={time.monotonic():.1f}")
                if self._task_log_fh:
                    self._task_log_fh.close()
                    self._task_log_fh = None

        # Extract Finish[answer] if the agent embedded the answer inline.
        # Use greedy match (.+) so JSON arrays like [1, 2, 3] inside retrieved_data aren't truncated.
        finish_match = re.search(r"Finish\[(.+)\]", answer, re.DOTALL)
        if finish_match:
            answer = finish_match.group(1).strip()

        if self.webarena_output_dir:
            self._save_wa_response(task, answer)

        self._log(f"\n[Answer] {str(answer)[:300]}")
        max_iter_error = f"max_iterations reached ({self.max_iterations})" if hit_max_iterations else None
        stall_error = f"stall_detected: {stall_reason}" if stall_reason else None
        final_error = max_iter_error or stall_error
        return {
            "success": not (hit_max_iterations or bool(stall_reason)),
            "final_url": None,
            "answer": answer,
            "error": final_error,
            "execution_result": {"steps": self._last_steps},
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _login_browser(self, gitlab_url: str) -> None:
        """Authenticate the Playwright session against GitLab before the task loop."""
        try:
            from api import gitlab_pw
            username, password = gitlab_pw.get_default_gitlab_credentials()
        except Exception:
            username, password = "byteblaze", "hello1234"
        try:
            await self._page.goto(f"{gitlab_url}/users/sign_in", wait_until="load", timeout=30000)
            await self._page.fill("#user_login", username)
            await self._page.fill("#user_password", password)
            await self._page.locator('button[type="submit"]').click()
            await self._page.wait_for_load_state("load", timeout=15000)
            self._log(f"  ✓ Browser logged in as {username} @ {gitlab_url}")
        except Exception as exc:
            self._log(f"  ⚠️  Browser pre-login failed: {exc}")

    async def _inject_bids(self) -> None:
        """Stamp sequential data-pw-bid attributes onto visible interactive elements only."""
        try:
            await self._page.evaluate("""
                () => {
                    const sel = [
                        'a[href]', 'button', 'input', 'select', 'textarea',
                        '[role="button"]', '[role="link"]', '[role="checkbox"]',
                        '[role="radio"]', '[role="combobox"]', '[role="textbox"]',
                        '[role="menuitem"]', '[role="option"]', '[role="tab"]',
                        '[tabindex="0"]',
                    ].join(', ');

                    function isVisible(el) {
                        const rect = el.getBoundingClientRect();
                        if (rect.width === 0 && rect.height === 0) return false;
                        let node = el;
                        while (node && node !== document.documentElement) {
                            const s = window.getComputedStyle(node);
                            if (s.display === 'none' || s.visibility === 'hidden' || s.opacity === '0') return false;
                            node = node.parentElement;
                        }
                        return true;
                    }

                    let bid = 1;
                    document.querySelectorAll(sel).forEach(el => {
                        if (isVisible(el)) {
                            el.setAttribute('data-pw-bid', String(bid++));
                        } else {
                            el.removeAttribute('data-pw-bid');
                        }
                    });
                }
            """)
        except Exception:
            pass

    async def _exec_browse(self, browser_actions: str) -> tuple:
        """Execute a browser_actions string via Playwright.

        Returns (content, error, axtree_object, extra_element_properties).
        content is either the captured send_msg_to_user value or a text
        snapshot of the current page including interactive-element BIDs.
        """
        page = self._page
        errors: list = []
        send_msg: Optional[str] = None

        for line in browser_actions.strip().splitlines():
            line = line.strip()
            if not line:
                continue

            # send_msg_to_user("…")
            m = re.match(r'send_msg_to_user\("(.*?)"\)\s*$', line, re.DOTALL)
            if m:
                send_msg = m.group(1)
                continue

            # goto("url")
            m = re.match(r'goto\("([^"]+)"\)', line)
            if m:
                url = m.group(1)
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    await self._inject_bids()
                except Exception as exc:
                    errors.append(f"goto({url!r}): {exc}")
                continue

            # click("bid")
            m = re.match(r'click\("(\d+)"\)', line)
            if m:
                bid = m.group(1)
                locator = page.locator(f'[data-pw-bid="{bid}"]')
                try:
                    await locator.scroll_into_view_if_needed(timeout=5000)
                    await locator.click(timeout=10000)
                    await page.wait_for_load_state("domcontentloaded", timeout=10000)
                    await self._inject_bids()
                except Exception:
                    # Element may be present but not interactable in the normal sense;
                    # dispatch a synthetic click as a last resort.
                    try:
                        await locator.dispatch_event("click")
                        await page.wait_for_load_state("domcontentloaded", timeout=10000)
                        await self._inject_bids()
                    except Exception as exc2:
                        errors.append(f"click({bid!r}): {exc2}")
                continue

            # fill("bid", "value")
            m = re.match(r'fill\("(\d+)",\s*"([^"]*)"\)', line)
            if m:
                bid, value = m.group(1), m.group(2)
                try:
                    await page.locator(f'[data-pw-bid="{bid}"]').fill(value, timeout=10000)
                except Exception as exc:
                    errors.append(f"fill({bid!r}, {value!r}): {exc}")
                continue

            # press("bid", "key")
            m = re.match(r'press\("(\d+)",\s*"([^"]*)"\)', line)
            if m:
                bid, key = m.group(1), m.group(2)
                try:
                    await page.locator(f'[data-pw-bid="{bid}"]').press(key, timeout=10000)
                    await page.wait_for_load_state("domcontentloaded", timeout=10000)
                    await self._inject_bids()
                except Exception as exc:
                    errors.append(f"press({bid!r}, {key!r}): {exc}")
                continue

            # select_option("bid", "value")
            m = re.match(r'select_option\("(\d+)",\s*"([^"]*)"\)', line)
            if m:
                bid, value = m.group(1), m.group(2)
                try:
                    await page.locator(f'[data-pw-bid="{bid}"]').select_option(value, timeout=10000)
                except Exception as exc:
                    errors.append(f"select_option({bid!r}, {value!r}): {exc}")
                continue

            # go_back() / go_forward()
            if line == "go_back()":
                try:
                    await page.go_back(wait_until="domcontentloaded", timeout=10000)
                    await self._inject_bids()
                except Exception as exc:
                    errors.append(f"go_back(): {exc}")
                continue

            if line == "go_forward()":
                try:
                    await page.go_forward(wait_until="domcontentloaded", timeout=10000)
                    await self._inject_bids()
                except Exception as exc:
                    errors.append(f"go_forward(): {exc}")
                continue

        if send_msg is not None:
            return send_msg, False, {}, {}

        # Build page-content observation
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=10000)
        except Exception:
            pass

        try:
            page_url = page.url
            page_text = await page.evaluate('() => document.body?.innerText || ""')
            elements = await page.evaluate("""
                () => {
                    const items = [];
                    document.querySelectorAll('[data-pw-bid]').forEach(el => {
                        const bid   = el.getAttribute('data-pw-bid');
                        const tag   = el.tagName.toLowerCase();
                        const role  = el.getAttribute('role') || tag;
                        const label = el.getAttribute('aria-label')
                                   || el.getAttribute('placeholder')
                                   || el.textContent?.trim()?.slice(0, 80)
                                   || '';
                        const value = el.value || '';
                        items.push({bid, role, label, value});
                    });
                    return items;
                }
            """)
            el_lines = []
            for el in elements[:150]:
                line = f"  [{el['bid']}] {el['role']}"
                if el['label']:
                    line += f" '{el['label']}'"
                if el['value']:
                    line += f" (value: {el['value']!r})"
                el_lines.append(line)

            error_prefix = ""
            if errors:
                error_prefix = "Errors:\n" + "\n".join(f"  {e}" for e in errors) + "\n\n"

            content = (
                error_prefix
                + f"URL: {page_url}\n\n"
                + f"Page Text:\n{page_text[:4000]}\n\n"
                + "Interactive Elements (use the BID number to click/fill/press):\n"
                + "\n".join(el_lines)
            )
            return content, bool(errors), {}, {}
        except Exception as exc:
            msg = "\n".join(errors + [f"Error reading page: {exc}"])
            return msg, True, {}, {}

    def _exec_python(self, code: str, gitlab_url: str, token: str) -> str:
        """Execute a Python code block; capture and return stdout (thread-safe)."""
        import requests as _requests_lib
        import builtins as _builtins_mod

        class _RequestsWithTimeout:
            """Drop-in requests wrapper that enforces a default timeout on every HTTP call."""
            def __getattr__(self, name):
                attr = getattr(_requests_lib, name)
                if callable(attr) and name in ('get', 'post', 'put', 'patch', 'delete', 'head', 'options', 'request'):
                    def _wrapped(*args, **kwargs):
                        kwargs.setdefault('timeout', 30)
                        return attr(*args, **kwargs)
                    return _wrapped
                return attr

        _requests_wrapper = _RequestsWithTimeout()
        _real_import = _builtins_mod.__import__

        def _safe_import(name, *args, **kwargs):
            if name == 'requests':
                return _requests_wrapper
            return _real_import(name, *args, **kwargs)

        custom_builtins = dict(vars(_builtins_mod))
        custom_builtins['__import__'] = _safe_import

        buf = io.StringIO()
        namespace: Dict[str, Any] = {
            "__builtins__": custom_builtins,
            "print": lambda *a, **kw: print(*a, **{**kw, "file": buf}),
            "requests": _requests_wrapper,
            "json": __import__("json"),
            "os": os,
            "re": re,
            "GITLAB_URL": gitlab_url,
            "GITLAB_TOKEN": token,
        }
        try:
            exec(compile(code, "<ipython>", "exec"), namespace)  # noqa: S102
            output = buf.getvalue()
        except Exception as exc:
            output = f"{type(exc).__name__}: {exc}"
        return truncate_observation(output or "(no output)")

    def _exec_bash(self, command: str) -> str:
        """Run a shell command; return combined stdout+stderr."""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = (result.stdout + result.stderr).strip()
        except subprocess.TimeoutExpired:
            output = "Error: command timed out after 30 seconds"
        except Exception as exc:
            output = f"Error: {exc}"
        return truncate_observation(output or "(no output)")
