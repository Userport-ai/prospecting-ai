import os
import uuid
import json
import logging
import requests
import google.generativeai as genai
from typing import Dict, Any
from .base import BaseTask
from services.bigquery_service import BigQueryService

logger = logging.getLogger(__name__)

class AccountEnhancementTask(BaseTask):
    def __init__(self):
        self.jina_api_token = os.getenv('JINA_API_TOKEN')
        self.google_api_key = os.getenv('GEMINI_API_TOKEN')
        self.bq_service = BigQueryService()

        if not self.google_api_key:
            raise ValueError("GEMINI_API_TOKEN environment variable is required")
        if not self.jina_api_token:
            raise ValueError("JINA_API_TOKEN environment variable is required")

        # Configure Gemini
        genai.configure(api_key=self.google_api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')

    @property
    def task_name(self) -> str:
        return "account_enhancement"

    async def create_task_payload(self, **kwargs) -> Dict[str, Any]:
        required_fields = ['account_id', 'company_name']
        missing_fields = [field for field in required_fields if field not in kwargs]

        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

        return {
            "account_id": kwargs["account_id"],
            "company_name": kwargs["company_name"],
            "job_id": str(uuid.uuid4())
        }

    async def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            company_name = payload.get('company_name')
            account_id = payload.get('account_id')
            job_id = payload.get('job_id')

            if not all([company_name, account_id, job_id]):
                return {"status": "failed", "error": "Missing required payload fields"}

            # Call the Jina API
            jina_url = f"https://s.jina.ai/{company_name}+company+profile"
            jina_headers = {
                "Authorization": f"Bearer {self.jina_api_token}",
            }

            jina_response = requests.get(jina_url, headers=jina_headers)
            jina_response.raise_for_status()
            company_profile = jina_response.text

            # Create extraction prompt for Gemini
            extraction_prompt = f"""
            Extract company information into a structured JSON format from the profile below.
            [Previous extraction prompt content...]
            """

            # Get structured data
            structure_response = self.model.generate_content(extraction_prompt)
            raw_text = structure_response.parts[0].text if structure_response.parts else ""

            # Clean and parse the structured data
            cleaned_text = raw_text.strip()
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text[7:]
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3]
            cleaned_text = cleaned_text.strip()

            structured_data = json.loads(cleaned_text)

            # Get analysis from Gemini
            analysis_prompt = f"""
            You're a Business Development rep working on profiling companies.
            [Previous analysis prompt content...]
            """

            analysis_response = self.model.generate_content(analysis_prompt)
            analysis_text = analysis_response.parts[0].text if analysis_response.parts else ""

            # Store the enrichment data in BigQuery
            await self.bq_service.insert_account_data(
                account_id=account_id,
                structured_data=structured_data,
                raw_profile=company_profile
            )

            # Store the raw enrichment data
            await self.bq_service.insert_enrichment_raw_data(
                job_id=job_id,
                entity_id=account_id,
                source='jina_ai',
                raw_data={
                    'jina_response': company_profile,
                    'gemini_structured': structured_data,
                    'gemini_analysis': analysis_text
                },
                processed_data=structured_data
            )

            # Return combined response
            return {
                "status": "completed",
                "account_id": account_id,
                "job_id": job_id,
                "company_name": company_name,
                "enrichment_data": {
                    "structured_data": structured_data,
                    "ai_analysis": analysis_text
                }
            }

        except requests.exceptions.RequestException as e:
            error_details = {'error_type': 'jina_api_error', 'message': str(e)}
            logger.error(f"Jina API error: {str(e)}")
            await self._store_error_state(job_id, account_id, error_details)
            return {
                "status": "failed",
                "error": f"Jina API error: {str(e)}",
                "job_id": job_id
            }
        except Exception as e:
            error_details = {'error_type': 'unexpected_error', 'message': str(e)}
            logger.error(f"Unexpected error: {str(e)}")
            await self._store_error_state(job_id, account_id, error_details)
            return {
                "status": "failed",
                "error": str(e),
                "job_id": job_id
            }

    async def _store_error_state(self, job_id: str, tenant_id: str, entity_id: str, error_details: Dict[str, Any]) -> None:
        """Store error state in BigQuery"""
        try:
            await self.bq_service.insert_enrichment_raw_data(
                job_id=job_id,
                entity_id=entity_id,
                source='jina_ai',
                raw_data={},
                processed_data={},
                status='failed',
                error_details=error_details
            )
        except Exception as e:
            logger.error(f"Error storing error state in BigQuery: {str(e)}")