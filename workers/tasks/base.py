from typing import Dict, Any
from abc import ABC, abstractmethod

class BaseTask(ABC):
    """Base class for all tasks"""

    @property
    @abstractmethod
    def task_name(self) -> str:
        """Task identifier"""
        pass

    @abstractmethod
    async def create_task_payload(self, **kwargs) -> Dict[str, Any]:
        """Create the payload for the task"""
        pass

    @abstractmethod
    async def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the task"""
        pass
