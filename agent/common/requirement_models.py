"""
Requirement analysis models and utility functions.
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class RequirementDetail(BaseModel):
    """Missing requirement discovered during spec analysis."""
    name: str
    description: Optional[str] = None
    resolution: Literal["model_decision", "default", "user_input"] = "user_input"
    model_decision_instructions: Optional[str] = None
    default_instructions: Optional[str] = None
    prompt: Optional[str] = None


class RequirementAnalysisResult(BaseModel):
    """Outcome of the requirement analysis."""
    requirements: List[RequirementDetail] = Field(default_factory=list)
    notes: Optional[str] = None


def _ensure_str(value: Optional[object]) -> Optional[str]:
    """Return the input as a stripped string if possible."""
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return None


def _normalize_resolution(value: Optional[object]) -> Literal["model_decision", "default", "user_input"]:
    """Normalize resolution labels coming from the requirement checker."""
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"model", "model_decision", "model-choice", "model_choice"}:
            return "model_decision"
        if lowered in {"default", "platform_default"}:
            return "default"
    return "user_input"
