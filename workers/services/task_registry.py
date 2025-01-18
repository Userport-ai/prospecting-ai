from typing import Dict, Type

from tasks.base import BaseTask


class TaskRegistry:
    """
    Service for registering and managing task implementations.
    Implements the Singleton pattern to ensure only one registry exists.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TaskRegistry, cls).__new__(cls)
            cls._instance._tasks = {}
        return cls._instance

    def register(self, task_class: Type[BaseTask]) -> None:
        """
        Register a new task implementation

        Args:
            task_class: The task class to register

        Raises:
            ValueError: If a task with the same name is already registered
        """
        task = task_class()
        if task.task_name in self._tasks:
            raise ValueError(f"Task {task.task_name} is already registered")
        self._tasks[task.task_name] = task

    def get_task(self, task_name: str) -> BaseTask:
        """
        Get a task implementation by name

        Args:
            task_name: Name of the task to retrieve

        Returns:
            The task implementation

        Raises:
            KeyError: If the task is not found
        """
        if task_name not in self._tasks:
            raise KeyError(f"Task {task_name} not found")
        return self._tasks[task_name]

    def list_tasks(self) -> Dict[str, BaseTask]:
        """
        Get all registered tasks

        Returns:
            Dictionary of task_name: task_implementation
        """
        return self._tasks.copy()

    def unregister(self, task_name: str) -> None:
        """
        Unregister a task implementation

        Args:
            task_name: Name of the task to unregister

        Raises:
            KeyError: If the task is not found
        """
        if task_name not in self._tasks:
            raise KeyError(f"Task {task_name} not found")
        del self._tasks[task_name]