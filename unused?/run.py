"""
Command-line entry point for the plan-then-execute agent.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agent import PlanThenExecuteAgent
from backend import get_chat_model


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the WebArena automation agent."
    )
    parser.add_argument(
        "--backend",
        required=True,
        choices=["openai", "anthropic", "gemini"],
        help="LLM backend to use for the conversation.",
    )
    parser.add_argument(
        "--task",
        required=True,
        help="High-level user task the agent should accomplish.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="If set, only generate the plan and program without executing it.",
    )
    parser.add_argument(
        "--log-output",
        default="stdout",
        help="Where to write the prompt/response log: 'stdout' or a file path.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    llm = get_chat_model(args.backend)
    agent = PlanThenExecuteAgent(llm=llm)

    result = agent.run(args.task, dry_run=args.dry_run)
    _emit_logs(result.logs, args.log_output)

    payload = result.model_dump()
    payload.update({"backend": args.backend})
    print(json.dumps(payload, indent=2, default=str, ensure_ascii=False))

    if args.dry_run:
        if result.plan:
            print(result.plan)
        if result.execution_result:
            print(result.execution_result.code)
        return 0

    return 0 if result.success else 1


def _emit_logs(logs, destination: str) -> None:
    """Write the collected prompt/response logs to the requested destination."""
    serialized = json.dumps([log.model_dump() for log in logs], indent=2, ensure_ascii=False)
    if destination.lower() == "stdout":
        print("=== Agent Logs ===")
        print(serialized)
        print("=== End Agent Logs ===")
        return

    path = Path(destination).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialized + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
