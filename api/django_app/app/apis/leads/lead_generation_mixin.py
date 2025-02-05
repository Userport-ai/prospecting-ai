# app/mixins/lead_generation_mixin.py
from typing import Dict, Any
from app.services.worker_service import WorkerService


class LeadGenerationMixin:
    def _create_lead_generation_payload(self, account) -> Dict[str, Any]:
        """
        Creates standardized payload for lead generation
        """
        return {
            "account_id": str(account.id),
            "account_data": {
                "website": account.website
            },
            "product_data": {
                "name": account.product.name,
                "description": account.product.description,
                "icp_description": account.product.icp_description,
                "persona_role_titles": account.product.persona_role_titles,
                "additional_lead_signals": account.product.playbook_description
            },
            "tenant_id": str(account.tenant.id)
        }

    def _trigger_lead_generation(self, account) -> Dict[str, Any]:
        """
        Triggers lead generation for a single account
        """
        worker_service = WorkerService()
        payload = self._create_lead_generation_payload(account)
        return worker_service.trigger_lead_generation(payload)
