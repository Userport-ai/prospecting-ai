from abc import ABC, abstractmethod
from typing import Dict, Any
import logging
from datetime import datetime, UTC

logger = logging.getLogger(__name__)

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

    async def run_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute task with comprehensive logging and error handling.

        Args:
            payload: Task execution parameters

        Returns:
            Task execution results

        Raises:
            Exception: If task execution fails
        """
        job_id = payload.get('job_id', 'unknown')
        account_id = payload.get('account_id', 'unknown')
        attempt_number = payload.get('attempt_number', 1)
        start_time = datetime.now(UTC)

        # Log task start
        logger.info(
            f"Starting task execution: {self.task_name}",
            extra={
                'event': 'task_start',
                'job_id': job_id,
                'account_id': account_id,
                'task_name': self.task_name,
                'attempt_number': attempt_number,
                'max_retries': payload.get('max_retries'),
                'timestamp': start_time.isoformat()
            }
        )

        try:
            # Execute the task
            result = await self.execute(payload)
            end_time = datetime.now(UTC)
            duration = (end_time - start_time).total_seconds()

            # Log successful completion
            logger.info(
                f"Task completed successfully: {self.task_name}",
                extra={
                    'event': 'task_complete',
                    'job_id': job_id,
                    'account_id': account_id,
                    'task_name': self.task_name,
                    'attempt_number': attempt_number,
                    'duration_seconds': duration,
                    'status': result.get('status'),
                    'completion_percentage': result.get('completion_percentage', 100),
                    'timestamp': end_time.isoformat()
                }
            )

            return result

        except Exception as e:
            end_time = datetime.now(UTC)
            duration = (end_time - start_time).total_seconds()

            # Log error details
            logger.error(
                f"Task execution failed: {self.task_name}",
                extra={
                    'event': 'task_error',
                    'job_id': job_id,
                    'account_id': account_id,
                    'task_name': self.task_name,
                    'attempt_number': attempt_number,
                    'duration_seconds': duration,
                    'error_type': type(e).__name__,
                    'error_message': str(e),
                    'timestamp': end_time.isoformat()
                },
                exc_info=True
            )

            # Enhance error message with task context
            error_context = f"Task {self.task_name} failed (job_id: {job_id}, attempt: {attempt_number})"
            raise type(e)(f"{error_context} - {str(e)}") from e
