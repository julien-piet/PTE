"""
Eval script: run string_match tasks from a verified JSON file through the agent
and score the agent's response against reference_answers.

Works with any verified task file:
    shopping_verified_string_match.json
    gitlab_verified_string_match.json

Scoring rules:
  exact_match   - reference string must appear in the response (case-insensitive substring)
  must_include  - every string in the list must appear in the response (case-insensitive)
  fuzzy_match   - if "N/A", task is unscoreable; otherwise treat like must_include

Usage:
    python scripts/eval_string_match.py \
        --tasks-file eval/tests/shopping_verified_string_match.json \
        --server shopping \
        [--base-url http://localhost:7770] \
        [--output results/shopping_string_match.json] \
        [--start 0] [--limit N]

    python scripts/eval_string_match.py \
        --tasks-file eval/tests/gitlab_verified_string_match.json \
        --server gitlab
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.agent import Agent
from agent.auth import StaticAuth
from config.servers import SERVER_URLS


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _contains(haystack: str, needle: str) -> bool:
    return needle.lower() in haystack.lower()


def score_response(response: str, reference_answers: Dict[str, Any]) -> Tuple[str, str]:
    """
    Score the agent response against reference_answers.

    Returns:
        (result, reason)  where result is "pass" | "fail" | "unscoreable"
    """
    if not response:
        return "fail", "empty response"

    # exact_match: single string
    if "exact_match" in reference_answers:
        ref = str(reference_answers["exact_match"])
        if _contains(response, ref):
            return "pass", f"found {ref!r} in response"
        return "fail", f"{ref!r} not found in response"

    # must_include: list where each element is either:
    #   - a string  → must appear in the response (AND)
    #   - a list    → at least one string in the sublist must appear (OR within AND)
    if "must_include" in reference_answers:
        refs = reference_answers["must_include"]
        if isinstance(refs, str):
            refs = [refs]
        missing = []
        for r in refs:
            if isinstance(r, list):
                # OR group: pass if any alternative is present
                if not any(_contains(response, str(alt)) for alt in r):
                    missing.append(r)
            else:
                if not _contains(response, str(r)):
                    missing.append(r)
        if not missing:
            return "pass", f"all {len(refs)} required strings found"
        return "fail", f"missing: {missing}"

    # fuzzy_match: "N/A" means unscoreable; otherwise treat like must_include
    if "fuzzy_match" in reference_answers:
        ref = reference_answers["fuzzy_match"]
        if ref == "N/A" or ref is None:
            return "unscoreable", "reference answer is N/A"
        if isinstance(ref, str):
            ref = [ref]
        missing = []
        for r in ref:
            if isinstance(r, list):
                if not any(_contains(response, str(alt)) for alt in r):
                    missing.append(r)
            else:
                if not _contains(response, str(r)):
                    missing.append(r)
        if not missing:
            return "pass", "all fuzzy strings found"
        return "fail", f"missing: {missing}"

    return "unscoreable", "no recognized reference_answers key"


# ---------------------------------------------------------------------------
# Task runner
# ---------------------------------------------------------------------------

class StringMatchEvalRunner:
    def __init__(
        self,
        tasks_file: str,
        output_file: str,
        server: str,
        base_url: str,
        start: int = 0,
        limit: Optional[int] = None,
        task_ids: Optional[List[int]] = None,
        env_file: str = "config/.env",
        api_dir: str = "api",
    ):
        self.tasks_file = Path(tasks_file)
        self.output_file = Path(output_file)
        self.server = server
        self.base_url = base_url
        self.start = max(0, start)
        self.limit = limit
        self.task_ids = task_ids  # if set, overrides start/limit
        self.env_file = env_file
        self.api_dir = api_dir
        self.agent: Optional[Agent] = None
        self.results: List[Dict[str, Any]] = []
        self._token_refreshed_at: float = 0.0  # epoch seconds

    def initialize(self):
        # Load environment variables from env_file
        env_path = Path(self.env_file)
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    os.environ.setdefault(key.strip(), val.strip())

        print(f"Initializing agent for server={self.server!r} base_url={self.base_url!r} ...")
        self.agent = Agent(api_dir=self.api_dir, env_file=self.env_file)
        self.agent.initialize({self.server: self.base_url})

        # Shopping requires a fresh Magento admin Bearer token — StaticAuth({}) is
        # just a placeholder in the auth registry; inject the real token here.
        if self.server == "shopping" and self.agent.execution_agent is not None:
            self._refresh_shopping_token()

        print("Agent initialized\n")

    def _refresh_shopping_token(self):
        """Fetch a fresh Magento admin token and inject it into the agent. Records the time."""
        if self.agent is None or self.agent.execution_agent is None:
            return
        from config.init_tokens.refresh_shopping_tokens import refresh_tokens
        print("Refreshing shopping admin token ...")
        token = refresh_tokens(base_url=self.base_url, credentials_file=self.env_file)
        self.agent.execution_agent.auth = StaticAuth(
            {"Authorization": f"Bearer {token}"}
        )
        self._token_refreshed_at = time.monotonic()

    def _maybe_refresh_shopping_token(self, token_ttl_seconds: int = 2700):
        """Re-fetch the token if it is older than token_ttl_seconds (default 45 min)."""
        if self.server != "shopping":
            return
        age = time.monotonic() - self._token_refreshed_at
        if age >= token_ttl_seconds:
            print(f"\n  ⟳ Token age {age/60:.1f} min — refreshing ...")
            self._refresh_shopping_token()

    def load_tasks(self) -> List[Dict[str, Any]]:
        if not self.tasks_file.exists():
            raise FileNotFoundError(f"Tasks file not found: {self.tasks_file}")

        with open(self.tasks_file) as f:
            all_tasks = json.load(f)

        # Keep only string_match tasks
        string_tasks = [t for t in all_tasks if "string_match" in t["eval"]["eval_types"]]

        if self.task_ids is not None:
            tasks = [t for t in string_tasks if t.get("task_id") in self.task_ids]
            print(f"Found {len(string_tasks)} string_match tasks in {self.tasks_file.name}")
            print(f"Running {len(tasks)} task(s) by ID: {sorted(self.task_ids)}\n")
        else:
            end = self.start + self.limit if self.limit else len(string_tasks)
            tasks = string_tasks[self.start:end]
            print(f"Found {len(string_tasks)} string_match tasks in {self.tasks_file.name}")
            print(f"Running tasks {self.start}–{self.start + len(tasks) - 1} ({len(tasks)} tasks)\n")
        return tasks

    async def run_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        task_id = task.get("task_id", "?")
        intent = task.get("intent", "")
        reference_answers = task["eval"].get("reference_answers", {})

        # Include start_url context if it adds useful path info
        start_url = task.get("start_url", "")
        repo_path = (
            start_url
            .replace("__GITLAB__", "")
            .replace("__SHOPPING__", "")
            .replace("__REDDIT__", "")
            .replace("__SHOPPING_ADMIN__", "")
            .strip("/")
        )
        prompt = f"Project path: {repo_path}\n\nTask: {intent}" if repo_path else intent

        needs_investigation = task.get("needs_investigation", False)
        inv_marker = " ⚠ NEEDS INVESTIGATION" if needs_investigation else ""
        print(f"  Task {task_id}{inv_marker}: {intent[:70]}...")

        try:
            result = await asyncio.wait_for(
                self.agent.run_task(prompt),
                timeout=300,  # 5 min per task
            )
            response = result.answer or ""
            agent_error = None
        except asyncio.TimeoutError:
            response = ""
            agent_error = "timeout"
        except Exception as e:
            response = ""
            agent_error = str(e)

        if agent_error:
            eval_result, eval_reason = "fail", f"agent error: {agent_error}"
        else:
            eval_result, eval_reason = score_response(response, reference_answers)

        icon = {"pass": "✅", "fail": "❌", "unscoreable": "⚪"}.get(eval_result, "?")
        print(f"  {icon} {eval_result.upper()} — {eval_reason}")

        return {
            "task_id": task_id,
            "intent": intent,
            "sites": task.get("sites", []),
            "needs_investigation": needs_investigation,
            "eval_result": eval_result,
            "eval_reason": eval_reason,
            "reference_answers": reference_answers,
            "response": response,
            "agent_error": agent_error,
        }

    async def run_all(self):
        tasks = self.load_tasks()
        print("=" * 70)
        try:
            for i, task in enumerate(tasks, 1):
                self._maybe_refresh_shopping_token()
                print(f"\n[{i}/{len(tasks)}]", end=" ")
                result = await self.run_task(task)
                self.results.append(result)
            print("\n" + "=" * 70)
        except (KeyboardInterrupt, asyncio.CancelledError):
            # CancelledError is what asyncio raises internally when Ctrl+C is
            # pressed in Python 3.11 — the outer try/except in main() never
            # sees it, so we save here before propagating.
            print("\n\nInterrupted — saving partial results...")
            self.save_and_report()
            sys.exit(1)

    def save_and_report(self):
        needs_inv = [r for r in self.results if r.get("needs_investigation")]
        scoreable_results = [r for r in self.results if not r.get("needs_investigation")]
        passed = [r for r in scoreable_results if r["eval_result"] == "pass"]
        failed = [r for r in scoreable_results if r["eval_result"] == "fail"]
        unscoreable = [r for r in scoreable_results if r["eval_result"] == "unscoreable"]
        scoreable = [r for r in scoreable_results if r["eval_result"] != "unscoreable"]

        score_pct = (len(passed) / len(scoreable) * 100) if scoreable else 0.0

        output = {
            "timestamp": datetime.now().isoformat(),
            "server": self.server,
            "base_url": self.base_url,
            "tasks_file": str(self.tasks_file),
            "summary": {
                "total_run": len(self.results),
                "needs_investigation": len(needs_inv),
                "scoreable": len(scoreable),
                "passed": len(passed),
                "failed": len(failed),
                "unscoreable": len(unscoreable),
                "score_pct": round(score_pct, 1),
            },
            "needs_investigation": [
                {"task_id": r["task_id"], "intent": r["intent"], "note": r.get("eval_reason", "")}
                for r in needs_inv
            ],
            "tasks": self.results,
        }

        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_file, "w") as f:
            json.dump(output, f, indent=2, default=str)

        print(f"\nResults saved to {self.output_file}")
        print("\n" + "=" * 70)
        print("EVAL SUMMARY")
        print("=" * 70)
        print(f"  Server:              {self.server} ({self.base_url})")
        print(f"  Tasks file:          {self.tasks_file.name}")
        print(f"  Tasks run:           {len(self.results)}")
        print(f"  ⚠ Needs invest.:   {len(needs_inv)}")
        print(f"  Scoreable:           {len(scoreable)}")
        print(f"  ✅ Passed:           {len(passed)}")
        print(f"  ❌ Failed:           {len(failed)}")
        print(f"  ⚪ Unscoreable:      {len(unscoreable)}")
        print(f"  Score:               {len(passed)}/{len(scoreable)} ({score_pct:.1f}%)")

        if needs_inv:
            print("\n--- NEEDS INVESTIGATION ---")
            for r in needs_inv:
                print(f"  Task {r['task_id']}: {r['intent'][:80]}")

        if failed:
            print("\n--- FAILED TASKS ---")
            for r in failed:
                print(f"  Task {r['task_id']}: {r['intent'][:60]}...")
                print(f"    Expected: {r['reference_answers']}")
                print(f"    Reason:   {r['eval_reason']}")
                if r["response"]:
                    print(f"    Response: {r['response'][:120]}...")

        print("=" * 70)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Eval agent on string_match tasks from a verified JSON file"
    )
    parser.add_argument(
        "--tasks-file",
        default="eval/tests/gitlab_verified_string_match.json",
        help="Path to the verified task JSON (shopping or gitlab).",
    )
    parser.add_argument(
        "--server",
        default="gitlab",
        choices=list(SERVER_URLS.keys()),
        help="Server the agent authenticates against (default: gitlab).",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Override the server base URL (default: value from config/servers.py).",
    )
    parser.add_argument(
        "--output", "-o",
        dest="output_file",
        default="results/string_match_eval.json",
        help="Path for the JSON results output.",
    )
    parser.add_argument("--start", type=int, default=0, help="Index of first task to run.")
    parser.add_argument("--limit", type=int, default=None, help="Max number of tasks to run.")
    parser.add_argument(
        "--task-id",
        default=None,
        help="Run only specific task IDs, comma-separated (e.g. --task-id 21,49,50). Overrides --start/--limit.",
    )
    parser.add_argument(
        "--env-file",
        default="config/.env",
        help="Path to the .env file with API keys and credentials.",
    )
    args = parser.parse_args()

    base_url = args.base_url or SERVER_URLS.get(args.server, "")
    task_ids = (
        {int(x.strip()) for x in args.task_id.split(",")}
        if args.task_id else None
    )

    runner = StringMatchEvalRunner(
        tasks_file=args.tasks_file,
        output_file=args.output_file,
        server=args.server,
        base_url=base_url,
        start=args.start,
        limit=args.limit,
        task_ids=task_ids,
        env_file=args.env_file,
    )

    try:
        runner.initialize()
        await runner.run_all()
        runner.save_and_report()
    except KeyboardInterrupt:
        print("\n\nInterrupted — saving partial results...")
        runner.save_and_report()
        sys.exit(1)
    except Exception as e:
        print(f"\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
