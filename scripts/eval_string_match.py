"""
Eval script: Run only string_match tasks from gitlab_tasks.json through the agent
and score the agent's response against reference_answers.

Scoring rules:
  exact_match   - reference string must appear in the response (case-insensitive substring)
  must_include  - every string in the list must appear in the response (case-insensitive)
  fuzzy_match   - if "N/A", task is unscoreable; otherwise every string must appear (case-insensitive)

Usage:
    python scripts/eval_string_match.py [--tasks-file gitlab_tasks.json] [--output results.json] [--start 0] [--limit N]
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.agent_replan import ToolCallAgent
from agent.common.configurator import Configurator
from agent.common.tool_manager import initialize_tools
from agent.providers.provider import ModelProvider


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
            return "pass", f"found '{ref}' in response"
        return "fail", f"'{ref}' not found in response"

    # must_include: list of strings — all must appear
    if "must_include" in reference_answers:
        refs = reference_answers["must_include"]
        if isinstance(refs, str):
            refs = [refs]
        missing = [r for r in refs if not _contains(response, str(r))]
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
        missing = [r for r in ref if not _contains(response, str(r))]
        if not missing:
            return "pass", f"all fuzzy strings found"
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
        start: int = 0,
        limit: Optional[int] = None,
    ):
        self.tasks_file = Path(tasks_file)
        self.output_file = Path(output_file)
        self.start = max(0, start)
        self.limit = limit
        self.agent: Optional[ToolCallAgent] = None
        self.results: List[Dict[str, Any]] = []

    async def initialize(self):
        print("Initializing agent...")
        config = Configurator()
        config.load_all_env()
        config.check_llm_env_vars()
        config.get_mcp_servers()

        provider = ModelProvider(config)
        llm_signature = provider.get_llm_model_provider()
        print(f"Using model: {llm_signature}")

        tools, token_store = await initialize_tools(config)
        print(f"Loaded {len(tools)} tools")

        self.agent = ToolCallAgent(
            llm=llm_signature,
            miniscope=False,
            tools=tools,
            token_store=token_store,
        )
        print("Agent initialized\n")

    def load_tasks(self) -> List[Dict[str, Any]]:
        if not self.tasks_file.exists():
            raise FileNotFoundError(f"Tasks file not found: {self.tasks_file}")

        with open(self.tasks_file) as f:
            all_tasks = json.load(f)

        # Keep only string_match tasks
        string_tasks = [t for t in all_tasks if "string_match" in t["eval"]["eval_types"]]

        end = self.start + self.limit if self.limit else len(string_tasks)
        tasks = string_tasks[self.start:end]

        print(f"Found {len(string_tasks)} string_match tasks in {self.tasks_file.name}")
        print(f"Running tasks {self.start}–{self.start + len(tasks) - 1} ({len(tasks)} tasks)\n")
        return tasks

    async def run_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        task_id = task.get("task_id", "?")
        intent = task.get("intent", "")
        reference_answers = task["eval"].get("reference_answers", {})

        print(f"  Task {task_id}: {intent[:70]}...")

        state = {
            "messages": [{"role": "user", "content": intent}],
            "plan": None,
            "intercepted": False,
            "execution_result": {},
            "mapped_arguments": {},
            "response": "",
            "global_message_history": [{"role": "user", "content": intent}],
            "routed_websites": None,
            "api_context": None,
            "requirements_context": None,
            "model_decisions": None,
            "defaults_used": None,
            "user_inputs": None,
            "auth_requirements": None,
        }

        try:
            result_state = await asyncio.wait_for(
                self.agent.invoke(state),
                timeout=300,  # 5 min per task
            )
            response = result_state.get("response", "")
            agent_error = None
        except asyncio.TimeoutError:
            response = ""
            agent_error = "timeout"
        except Exception as e:
            response = ""
            agent_error = str(e)

        # Score
        if agent_error:
            eval_result, eval_reason = "fail", f"agent error: {agent_error}"
        else:
            eval_result, eval_reason = score_response(response, reference_answers)

        icon = {"pass": "✅", "fail": "❌", "unscoreable": "⚪"}.get(eval_result, "?")
        print(f"  {icon} {eval_result.upper()} — {eval_reason}")

        return {
            "task_id": task_id,
            "intent": intent,
            "eval_result": eval_result,
            "eval_reason": eval_reason,
            "reference_answers": reference_answers,
            "response": response,
            "agent_error": agent_error,
        }

    async def run_all(self):
        tasks = self.load_tasks()
        print("=" * 70)
        for i, task in enumerate(tasks, 1):
            print(f"\n[{i}/{len(tasks)}]", end=" ")
            result = await self.run_task(task)
            self.results.append(result)
        print("\n" + "=" * 70)

    def save_and_report(self):
        passed = [r for r in self.results if r["eval_result"] == "pass"]
        failed = [r for r in self.results if r["eval_result"] == "fail"]
        unscoreable = [r for r in self.results if r["eval_result"] == "unscoreable"]
        scoreable = [r for r in self.results if r["eval_result"] != "unscoreable"]

        score_pct = (len(passed) / len(scoreable) * 100) if scoreable else 0.0

        output = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_run": len(self.results),
                "scoreable": len(scoreable),
                "passed": len(passed),
                "failed": len(failed),
                "unscoreable": len(unscoreable),
                "score_pct": round(score_pct, 1),
            },
            "tasks": self.results,
        }

        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_file, "w") as f:
            json.dump(output, f, indent=2, default=str)

        print(f"\nResults saved to {self.output_file}")
        print("\n" + "=" * 70)
        print("EVAL SUMMARY")
        print("=" * 70)
        print(f"  Tasks run:      {len(self.results)}")
        print(f"  Scoreable:      {len(scoreable)}")
        print(f"  ✅ Passed:      {len(passed)}")
        print(f"  ❌ Failed:      {len(failed)}")
        print(f"  ⚪ Unscoreable: {len(unscoreable)}")
        print(f"  Score:          {len(passed)}/{len(scoreable)} ({score_pct:.1f}%)")

        if failed:
            print("\n--- FAILED TASKS ---")
            for r in failed:
                print(f"  Task {r['task_id']}: {r['intent'][:60]}...")
                print(f"    Expected: {r['reference_answers']}")
                print(f"    Reason:   {r['eval_reason']}")
                if r['response']:
                    print(f"    Response: {r['response'][:120]}...")

        print("=" * 70)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Eval agent on string_match GitLab tasks")
    parser.add_argument("--tasks-file", default="gitlab_tasks.json")
    parser.add_argument("--output", "-o", dest="output_file", default="testing_results/string_match_eval.json")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    runner = StringMatchEvalRunner(
        tasks_file=args.tasks_file,
        output_file=args.output_file,
        start=args.start,
        limit=args.limit,
    )

    try:
        await runner.initialize()
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
