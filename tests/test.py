"""Module containing the Test dataclass."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class Test(ABC):

    query: str
    parameters: Optional[Dict[str, str]]

    @abstractmethod
    def setup_env(self) -> bool:
        """Prepare the environment for this test."""

    @abstractmethod
    def check_env(self) -> bool:
        """Verify the environment is correct for this test."""
