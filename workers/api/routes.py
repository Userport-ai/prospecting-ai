import os

from fastapi import APIRouter, HTTPException
from typing import Dict, Any

from services.mocks.mock_task_manager import MockTaskManager
from services.task_registry import TaskRegistry
from services.task_manager import TaskManager
from tasks.account_enhancement import AccountEnhancementTask

router = APIRouter()

task_registry = TaskRegistry()

if os.getenv('ENVIRONMENT') == 'local':
    task_manager = MockTaskManager()
else:
    task_manager = TaskManager()

task_registry.register(AccountEnhancementTask)

@router.post("/tasks/create/{task_name}")
async def create_task(task_name: str, payload: Dict[str, Any]):
    try:
        task = task_registry.get_task(task_name)
        task_payload = await task.create_task_payload(**payload)
        return await task_manager.create_task(task_name, task_payload)
    except KeyError:
        raise HTTPException(status_code=404, detail="Task not found")


@router.post("/tasks/{task_name}")
async def execute_task(task_name: str, payload: Dict[str, Any]):
    try:
        task = task_registry.get_task(task_name)
        return await task.execute(payload)
    except KeyError:
        raise HTTPException(status_code=404, detail="Task not found")