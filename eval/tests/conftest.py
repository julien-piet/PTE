# tests/conftest.py
#
# Shared pytest configuration for the PTE test suite.
#
# Plugging in a custom agent
# ──────────────────────────
# Any agent implementation can be tested by subclassing BaseAgentRunner and
# passing the dotted import path via --agent-runner:
#
#   python3 -m pytest tests/ --agent-runner mymodule.MyAgentRunner -v
#
# The default is the built-in AgentRunner (PTE ToolCallAgent + MCP tools).
# See BaseAgentRunner in run_program_html_benchmark.py for the interface.

import asyncio
import importlib
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# CLI options
# ---------------------------------------------------------------------------

def pytest_addoption(parser):
    parser.addoption(
        "--task-limit",
        type=int,
        default=None,
        metavar="N",
        help="Only run the first N tasks in parameterised agent tests.",
    )
    parser.addoption(
        "--site",
        type=str,
        default=None,
        metavar="SITE",
        help=(
            "Filter tasks to a specific site before applying --task-limit. "
            "One of: gitlab, reddit, shopping, shopping_admin."
        ),
    )
    parser.addoption(
        "--agent-runner",
        type=str,
        default=None,
        metavar="MODULE.CLASS",
        help=(
            "Dotted import path of a BaseAgentRunner subclass to use instead "
            "of the default AgentRunner. Example: mymodule.MyAgentRunner"
        ),
    )
    parser.addoption(
        "--server",
        type=str,
        default="gitlab",
        metavar="SERVER",
        help=(
            "Server the agent authenticates against. "
            "One of: gitlab, reddit, shopping, shopping_admin. Default: gitlab."
        ),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_runner_class(dotted_path: str):
    """
    Import and return a runner class from a dotted path like 'mymodule.MyClass'.
    Raises ValueError, ImportError, or AttributeError with helpful messages.
    """
    parts = dotted_path.rsplit(".", 1)
    if len(parts) != 2:
        raise ValueError(
            f"--agent-runner must be a dotted MODULE.CLASS path, got: {dotted_path!r}"
        )
    module_path, class_name = parts
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls


# ---------------------------------------------------------------------------
# Session-scoped fixtures — shared across all three agent test files
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def session_event_loop():
    """
    Session-scoped asyncio event loop shared across all tests.

    Using a single loop for the whole test session lets the agent runner
    initialise its connections once and reuse them across every test,
    rather than creating and tearing down new connections per test.
    Named ``session_event_loop`` (not ``event_loop``) to avoid conflicting
    with pytest-asyncio's own loop fixture if that plugin is installed.
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.run_until_complete(asyncio.sleep(0))
    loop.close()


@pytest.fixture(scope="session")
def agent_runner(request, session_event_loop):
    """
    Initialise the agent runner exactly once for the entire test session.

    By default uses AgentRunner (PTE ToolCallAgent + MCP tools). Pass
    --agent-runner MODULE.CLASS to swap in any BaseAgentRunner subclass.

    Configuration:
    - headless=True      — no visible browser during evaluation.
    - enable_reset=True  — GitLab state is reset before each GitLab task.
    """
    runner_path = request.config.getoption("--agent-runner", default=None)

    if runner_path:
        runner_cls = _load_runner_class(runner_path)
    else:
        from eval.run_program_html_benchmark import AgentRunner
        runner_cls = AgentRunner

    runner = runner_cls(headless=True, enable_reset=True)
    runner.server = request.config.getoption("--server", default="gitlab")
    session_event_loop.run_until_complete(runner._init_agent())
    return runner
