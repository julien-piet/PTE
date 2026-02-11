"""
Agent state definitions for LangGraph workflow.
"""

from typing import Annotated, Any, Dict, List, Optional

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from agent.planner import ExecutionContext
from agent.common.api_parser import WebsiteAPI


class AgentState(TypedDict):
    """State passed between nodes in the graph."""
    messages: Annotated[list, add_messages]
    plan: Optional[List[Any]] 
    intercepted: bool
    execution_context: ExecutionContext  # Encapsulates all execution state
    execution_result: dict
    mapped_arguments: dict
    response: str
    global_message_history: List[Any]
    # New fields for routing and requirements
    routed_websites: Optional[List[WebsiteAPI]]
    api_context: Optional[str]
    requirements_context: Optional[str]
    model_decisions: Optional[List[str]]
    defaults_used: Optional[List[str]]
    user_inputs: Optional[Dict[str, str]]
    auth_requirements: Optional[Dict[str, Any]]
