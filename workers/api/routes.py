import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import JSONResponse

from services.mocks.mock_task_manager import MockTaskManager
from services.task_manager import TaskManager
from services.task_registry import TaskRegistry
from tasks.account_enhancement import AccountEnhancementTask
from tasks.generate_leads_task import GenerateLeadsTask
from tasks.lead_linkedin_research_task import LeadLinkedInResearchTask

router = APIRouter()

# Initialize task registry and register tasks
task_registry = TaskRegistry()
task_registry.register(AccountEnhancementTask)
task_registry.register(GenerateLeadsTask)
task_registry.register(LeadLinkedInResearchTask)


def get_task_manager() -> TaskManager:
    """Dependency injection for task manager."""
    if os.getenv('ENVIRONMENT') == 'local':
        return MockTaskManager()
    return TaskManager()


class TaskError(HTTPException):
    """Custom exception for task-related errors."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(status_code=status_code, detail=detail)


@router.post("/tasks/create/{task_name}")
async def create_task(
        task_name: str,
        payload: Dict[str, Any],
        task_manager: TaskManager = Depends(get_task_manager, use_cache=True)
) -> JSONResponse:
    """
    Create a new task with the given name and payload.

    Args:
        task_name: Name of the task to create
        payload: Task configuration and parameters
        task_manager: Injected task manager instance
    """
    try:
        task = task_registry.get_task(task_name)
        task_payload = await task.create_task_payload(**payload)
        result = await task_manager.create_task(task_name, task_payload)
        return JSONResponse(content=result)
    except KeyError:
        raise TaskError(status_code=404, detail="Task not found")


@router.post("/tasks/{task_name}")
async def execute_task(
        task_name: str,
        payload: Dict[str, Any],
        task_manager: TaskManager = Depends(get_task_manager, use_cache=True)
) -> JSONResponse:
    """
    Execute a task with the given name and payload.

    Args:
        task_name: Name of the task to execute
        payload: Task execution parameters
        task_manager: Injected task manager instance
    """
    try:
        task = task_registry.get_task(task_name)
        result = await task.execute(payload)
        return JSONResponse(content=result)
    except KeyError:
        raise TaskError(status_code=404, detail="Task not found")


@router.get("/tasks/{job_id}/status")
async def get_task_status(
        job_id: str,
        task_manager: TaskManager = Depends(get_task_manager, use_cache=True)
) -> Dict[str, Any]:
    """
    Get detailed status of a specific job.

    Args:
        job_id: ID of the job to query
        task_manager: Injected task manager instance
    """
    try:
        return await task_manager.get_job_status(job_id)
    except KeyError:
        raise TaskError(status_code=404, detail="Job not found")
    except Exception as e:
        raise TaskError(status_code=500, detail=str(e))


@router.get("/tasks/failed")
async def list_failed_tasks(
        start_date: Optional[datetime] = Query(None),
        end_date: Optional[datetime] = Query(None),
        retryable_only: bool = Query(False),
        limit: int = Query(100, gt=0, le=1000),
        task_manager: TaskManager = Depends(get_task_manager, use_cache=True)
) -> List[Dict[str, Any]]:
    """
    List failed tasks with filtering options.

    Args:
        start_date: Optional start date for filtering (defaults to 7 days ago)
        end_date: Optional end date for filtering (defaults to now)
        retryable_only: If True, only show retryable tasks
        limit: Maximum number of tasks to return
        task_manager: Injected task manager instance
    """
    try:
        return await task_manager.list_failed_jobs(
            start_date=start_date or (datetime.utcnow() - timedelta(days=7)),
            end_date=end_date or datetime.utcnow(),
            retryable_only=retryable_only,
            limit=limit
        )
    except Exception as e:
        raise TaskError(status_code=500, detail=str(e))


@router.post("/tasks/{job_id}/retry")
async def retry_task(
        job_id: str,
        task_manager: TaskManager = Depends(get_task_manager, use_cache=True)
) -> Dict[str, Any]:
    """
    Retry a failed task.

    Args:
        job_id: ID of the failed job to retry
        task_manager: Injected task manager instance

    Raises:
        TaskError: If the task cannot be retried
    """
    try:
        status = await task_manager.get_job_status(job_id)

        # Validate task can be retried
        if status['status'] != 'failed':
            raise TaskError(status_code=400, detail="Only failed tasks can be retried")

        if not status.get('retryable', False):
            raise TaskError(status_code=400, detail="This task is not retryable")

        if status['attempt_number'] >= status['max_retries']:
            raise TaskError(status_code=400, detail="Maximum retry attempts exceeded")

        # Create new task with incremented attempt number
        new_payload = {
            'account_id': status['entity_id'],
            'attempt_number': status['attempt_number'] + 1,
            'max_retries': status['max_retries'],
            'original_job_id': job_id
        }

        return await task_manager.create_task('account_enhancement', new_payload)

    except TaskError:
        raise
    except KeyError:
        raise TaskError(status_code=404, detail="Job not found")
    except Exception as e:
        raise TaskError(status_code=500, detail=str(e))
