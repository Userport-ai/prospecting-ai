import asyncio
import uuid
from typing import Dict, Any


class MockTaskManager:
    """Mock implementation of TaskManager for local development"""

    def __init__(self):
        self.tasks = {}

    async def create_task(self, task_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        task_id = str(uuid.uuid4())
        self.tasks[task_id] = {
            "task_name": task_name,
            "payload": payload,
            "status": "scheduled"
        }

        # Import utility for creating tasks with context preservation
        from utils.async_utils import create_task_with_context
        
        # Simulate async task execution with context preservation
        create_task_with_context(self._execute_task(task_id))

        return {
            "status": "scheduled",
            "task_name": task_name,
            "task_id": task_id
        }

    async def _execute_task(self, task_id: str):
        # Import and use sleep_with_context to preserve context during sleep
        from utils.async_utils import sleep_with_context
        
        # Simulate some processing time with context preservation
        await sleep_with_context(2)

        task = self.tasks[task_id]
        task["status"] = "completed"
        print(f"Executed task {task_id}: {task}")
