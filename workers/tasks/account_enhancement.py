from .base import BaseTask
from typing import Dict, Any

class AccountEnhancementTask(BaseTask):
    @property
    def task_name(self) -> str:
        return "account_enhancement_using_jina_ai"

    async def create_task_payload(self, message: str = "Hello World", **kwargs) -> Dict[str, Any]:
        return {
            "message": message,
            **kwargs
        }

    async def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        print(f"Processing account enhancement task: {payload['message']}")
        return {"status": "completed", "message": payload['message']}
