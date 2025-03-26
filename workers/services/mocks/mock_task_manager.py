import asyncio
import uuid
from typing import Dict, Any


from services.task_registry import TaskRegistry
from utils.loguru_setup import logger


task_registry_instance = TaskRegistry()
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

        # Simulate async task execution
        asyncio.create_task(self._execute_task(task_id))

        return {
            "status": "scheduled",
            "task_name": task_name,
            "task_id": task_id
        }

    async def _execute_task(self, task_id: str):
        logger.info(f"Executing task {task_id} with payload: {self.tasks[task_id]['payload']}")
        task = self.tasks[task_id]

        task_instance = task_registry_instance.get_task(task.get("task_name"))
        if not task_instance or not task.get("task_name"):
            raise ValueError(f"No task found with name: {task.get('task_name')}")
        await task_instance.execute(task.get("payload"))
        task["status"] = "completed"

        print(f"Executed task {task_id}: {task}")
