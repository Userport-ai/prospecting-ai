# file: tasks/base.py

from abc import ABC, abstractmethod
from typing import Dict, Any
import logging
from datetime import datetime, UTC

from services.django_callback_service import CallbackService
from services.task_result_manager import TaskResultManager

logger = logging.getLogger(__name__)

class BaseTask(ABC):
    """Base class for all tasks."""
    def __init__(self, callback_service):
        """
        - result_manager: An instance of TaskResultManager
        - callback_service: An instance of CallbackService
        """
        self.result_manager = TaskResultManager()
        self.callback_service = callback_service

    @classmethod
    async def create(cls):
        try:
            callback_service = await CallbackService.get_instance()
            return cls(callback_service)
        except Exception as e:
            logger.error(f"Failed to initialize CallbackService: {e}")
            raise

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
    async def execute(self, payload: Dict[str, Any]) -> (Dict[str, Any], Dict[str, Any]):
        """Execute the task's logic and return the final callback dict."""
        pass

    async def run_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute task with idempotency:
          1. Check if a completed result is stored
          2. If yes, re-send callback and return
          3. Otherwise, call `execute()`, store, and callback
        """
        lead_id = payload.get("lead_id")
        account_id = payload.get("account_id")
        attempt_number = payload.get("attempt_number")
        job_id = payload.get("job_id")
        start_time = datetime.now(UTC)

        # Log task start
        logger.info(
            f"Starting task execution: {self.task_name}",
            extra={
                'event': 'task_start',
                'account_id': account_id,
                'lead_id': lead_id,
                'task_name': self.task_name,
                'attempt_number': attempt_number,
                'max_retries': payload.get('max_retries'),
                'timestamp': start_time.isoformat(),
            }
        )

        try:
            # 1. Check existing stored result
            existing = await self.result_manager.get_result(account_id, lead_id)
            logger.info(f"Searched for {account_id} and {lead_id} in the table and found : {existing}")
            if existing and existing.get("status") == "completed":
                logger.info(f"Found existing completed result for account_id={account_id}, lead_id={lead_id}, resending callback.")
                callback_params = {k: v for k, v in existing.items() if k != 'job_id'}
                await self.callback_service.paginated_service.send_callback(job_id = job_id, **callback_params)
                return existing

            # 2. If no existing result, we do the normal flow
            result, summary = await self.execute(payload)

            # Store final result if successful
            await self.result_manager.store_result(result)

            # Send callback if successful
            if result and (result.get("status", "unknown") == "completed"):
                await self.callback_service.paginated_service.send_callback(**result)
            return summary

        except Exception as e:
            end_time = datetime.now(UTC)
            duration = (end_time - start_time).total_seconds()

            # Log error details
            logger.error(
                f"Task {self.task_name} failed: {str(e)}",
                extra={
                    "account_id": account_id,
                    "lead_id": lead_id
                },
                exc_info=True
            )
            raise
