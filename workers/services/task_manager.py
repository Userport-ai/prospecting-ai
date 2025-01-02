import json
import os
from typing import Dict, Any

from google.cloud import tasks_v2


class TaskManager:
    def __init__(self):
        self.client = tasks_v2.CloudTasksClient()
        self.project = os.getenv('GOOGLE_CLOUD_PROJECT')
        self.queue = os.getenv('CLOUD_TASKS_QUEUE')
        self.location = os.getenv('CLOUD_TASKS_LOCATION', 'us-west1')
        self.base_url = os.getenv('WORKER_BASE_URL')
        self.service_account_email = os.getenv('CLOUD_TASKS_SERVICE_ACCOUNT_EMAIL')

    def _get_queue_path(self) -> str:
        return self.client.queue_path(self.project, self.location, self.queue)

    async def create_task(self, task_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        parent = self._get_queue_path()

        task = {'http_request': {'http_method': tasks_v2.HttpMethod.POST, 'url': f"{self.base_url}/api/v1/tasks/{task_name}",
                                 'headers': {'Content-Type': 'application/json'}, 'body': json.dumps(payload).encode(),
                                 'oidc_token': tasks_v2.OidcToken(service_account_email=self.service_account_email,
                                                                  audience=self.base_url), }}

        response = self.client.create_task(request={"parent": parent, "task": task})

        return {"status": "scheduled", "task_name": task_name, "task_id": response.name}
