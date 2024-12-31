from .base import BaseTask
from typing import Dict, Any

class HelloWorldTask(BaseTask):
    @property
    def task_name(self) -> str:
        return "hello_world"

    async def create_task_payload(self,**kwargs) -> Dict[str, Any]:
        return {
            **kwargs
        }

    async def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        message = payload.get('message')
        if not message:
            return {"status": "failed", "error": "No message provided"}

        print(f"Processing hello world task: {message}")
        return {
            "status": "completed",
            "message": message
        }
