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
import logging
import os
import re
import subprocess
import sys
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

    # ------------------------------------------------------------------
    # BaseAgentRunner interface
    # ------------------------------------------------------------------

    async def _init_agent(self) -> None:
        from react_agent.codeact_agent.codeact_agent import CodeActAgent

        print("🔧 Initializing react agent...")
        self._react_agent = CodeActAgent(llm=None)  # LLM sourced from config/config.yaml
        print("✓ React Agent initialized\n")

    async def run_agent_on_task(self, task):
        """Override to do cleanup AFTER the task instead of before."""
        resetter = self._resetter
        self._resetter = None  # suppress pre-task reset in super()
        try:
            result = await super().run_agent_on_task(task)
        finally:
            self._resetter = resetter  # restore
            if resetter is not None:
                reset_task = dict(task, require_reset=True) if self.force_reset else task
                try:
                    resetter.reset_for_task(reset_task)
                except Exception as exc:
                    print(f"   ⚠️  [post-reset] {exc}")
        return result

    async def _run_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Run the CodeActAgent ReAct loop on a single task."""
        intent = task.get("intent", "")
        raw_start = task.get("start_url", "")
        gitlab_url = getattr(self, "base_url", None) or self.gitlab_base_url
        start_url = raw_start.replace("__GITLAB__", gitlab_url).strip("/")
        token = self.glpat or os.environ.get("GLPAT") or os.environ.get("GITLAB_TOKEN") or _token_from_server_env()

        # Include the GitLab URL in the prompt so history_str picks it up for
        # _get_site_hints() / _get_api_schema_section() inside step().
        prompt_parts = [
            f"GitLab instance: {gitlab_url}",
            f"Task: {intent}",
            "Use <execute_ipython> to call the GitLab REST API with the requests library.",
            "Pre-defined variables available in every Python block:",
            "  GITLAB_URL  — base URL of the GitLab instance",
            "  GITLAB_TOKEN — authenticated personal access token",
            "  Example: requests.get(f'{GITLAB_URL}/api/v4/projects', headers={'PRIVATE-TOKEN': GITLAB_TOKEN})",
        ]
        if start_url and start_url != gitlab_url:
            prompt_parts.append(f"Start URL: {start_url}")
        prompt = "\n".join(prompt_parts)

        print(f"\n{'='*70}")
        print(f"[Task] {intent}")
        if start_url and start_url != gitlab_url:
            print(f"[Start URL] {start_url}")
        print(f"{'='*70}")

        # Expose URL for _get_site_urls() inside the agent.
        os.environ["GITLAB"] = gitlab_url

        self._react_agent.reset()
        self._last_steps = []
        state = _SimpleState(task_prompt=prompt, max_iterations=self.max_iterations)
        answer = ""

        try:
            loop = asyncio.get_event_loop()
            while state.iteration < self.max_iterations:
                action = await loop.run_in_executor(None, self._react_agent.step, state)
                state.iteration += 1
                step_num = state.iteration
                action_type = type(action).__name__

                if action_type == "AgentFinishAction":
                    print(f"\n[Step {step_num}] AgentFinishAction")
                    print(f"  Thought: {str(action.thought)[:500]}")
                    answer = action.thought or answer
                    break

                if action_type == "MessageAction":
                    print(f"\n[Step {step_num}] MessageAction")
                    print(f"  Content: {str(action.content)[:500]}")
                    answer = action.content
                    if re.search(r"<finish\s*/?>", answer, re.IGNORECASE) or "Finish[" in answer:
                        break
                    state.history.append((action, None))
                    continue

                if action_type == "IPythonRunCellAction":
                    print(f"\n[Step {step_num}] IPythonRunCellAction")
                    print(f"  Code:\n{action.code.rstrip()}")
                    output = self._exec_python(action.code, gitlab_url, token)
                    print(f"  Output: {output[:800]}")
                    obs = IPythonRunCellObservation()
                    obs.content = output
                    state.history.append((action, obs))
                    self._last_steps.append(
                        {"type": "ipython", "code": action.code, "output": output}
                    )

                elif action_type == "CmdRunAction":
                    if action.command.strip() == "exit":
                        print(f"\n[Step {step_num}] CmdRunAction: exit — stopping")
                        break
                    print(f"\n[Step {step_num}] CmdRunAction")
                    print(f"  Command: {action.command.rstrip()}")
                    output = self._exec_bash(action.command)
                    print(f"  Output: {output[:800]}")
                    obs = CmdOutputObservation()
                    obs.content = output
                    obs.command_id = str(step_num)
                    obs.exit_code = 0
                    state.history.append((action, obs))
                    self._last_steps.append(
                        {"type": "bash", "command": action.command, "output": output}
                    )

                elif action_type == "BrowseInteractiveAction":
                    print(f"\n[Step {step_num}] BrowseInteractiveAction (EVAL_MODE login mock)")
                    # EVAL_MODE hardcodes login steps for the first 3 iterations;
                    # mock them with an empty page so the loop reaches real LLM calls.
                    obs = BrowserOutputObservation()
                    obs.content = ""
                    obs.error = False
                    obs.axtree_object = {}
                    obs.extra_element_properties = {}
                    obs.last_browser_action = action.browser_actions
                    state.history.append((action, obs))

                else:
                    print(f"\n[Step {step_num}] Unknown action: {action_type}")

        except Exception as exc:
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "final_url": None,
                "answer": "",
                "execution_result": {"error": str(exc)},
            }

        # Extract Finish[answer] if the agent embedded the answer inline.
        finish_match = re.search(r"Finish\[(.+?)\]", answer, re.DOTALL)
        if finish_match:
            answer = finish_match.group(1).strip()

        print(f"\n[Answer] {str(answer)[:300]}")
        return {
            "success": True,
            "final_url": None,
            "answer": answer,
            "execution_result": {"steps": self._last_steps},
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _exec_python(self, code: str, gitlab_url: str, token: str) -> str:
        """Execute a Python code block; capture and return stdout."""
        namespace: Dict[str, Any] = {
            "__builtins__": __builtins__,
            "requests": __import__("requests"),
            "json": __import__("json"),
            "os": os,
            "re": re,
            "GITLAB_URL": gitlab_url,
            "GITLAB_TOKEN": token,
        }
        buf = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf
        try:
            exec(compile(code, "<ipython>", "exec"), namespace)  # noqa: S102
            output = buf.getvalue()
        except Exception as exc:
            output = f"{type(exc).__name__}: {exc}"
        finally:
            sys.stdout = old_stdout
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
