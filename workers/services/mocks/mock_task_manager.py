from typing import Dict, Any
import asyncio
import uuid

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
        # Simulate some processing time
        await asyncio.sleep(2)

        task = self.tasks[task_id]
        task["status"] = "completed"
        print(f"Executed task {task_id}: {task}")
