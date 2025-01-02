import os
import uuid
from datetime import datetime
from typing import Dict, Any
from google.cloud import bigquery
import logging

logger = logging.getLogger(__name__)

class BigQueryService:
    def __init__(self):
        self.client = bigquery.Client()
        self.dataset = os.getenv('BIGQUERY_DATASET', 'userport_enrichment')
        self.project = os.getenv('GOOGLE_CLOUD_PROJECT')

    def _get_table_ref(self, table_name: str) -> str:
        return f"{self.project}.{self.dataset}.{table_name}"

    async def insert_account_data(self,
                                  account_id: str,
                                  structured_data: Dict[str, Any],
                                  raw_profile: str) -> str:
        """Store enriched account data in BigQuery"""
        try:
            record_id = str(uuid.uuid4())
            table_ref = self._get_table_ref('account_data')

            # Extract relevant fields from structured data
            company_data = structured_data.get('company_name', {})
            location_data = structured_data.get('location', {}).get('headquarters', {})
            business_metrics = structured_data.get('business_metrics', {})
            industry_data = structured_data.get('industry', {})
            tech_data = structured_data.get('technology_stack', {})
            financial_data = structured_data.get('financials', {})

            # Prepare row for insertion
            row = {
                'record_id': record_id,
                'account_id': account_id,
                'company_name': company_data.get('legal_name'),
                'employee_count': business_metrics.get('employee_count', {}).get('total'),
                'industry': industry_data.get('sectors', []),
                'location': f"{location_data.get('city', '')}, {location_data.get('country', '')}".strip(', '),
                'website': structured_data.get('digital_presence', {}).get('website'),
                'linkedin_url': structured_data.get('digital_presence', {}).get('social_media', {}).get('linkedin'),
                'technologies': tech_data.get('programming_languages', []) + tech_data.get('frameworks', []) + tech_data.get('cloud_services', []),
                'funding_details': financial_data.get('private_data', {}),  
                'raw_data': structured_data,  
                'fetched_at': datetime.utcnow().isoformat()
            }

            logger.debug(f"Inserting row into BigQuery: {row}")

            table = self.client.get_table(table_ref)
            errors = self.client.insert_rows_json(table, [row])

            if errors:
                logger.error(f"Errors inserting into account_data: {errors}")
                raise Exception(f"BigQuery insert errors: {errors}")

            return record_id

        except Exception as e:
            logger.error(f"Error storing account data in BigQuery: {str(e)}")
            raise


    async def insert_enrichment_raw_data(self,
                                         job_id: str,
                                         entity_id: str,
                                         source: str,
                                         raw_data: Dict[str, Any],
                                         processed_data: Dict[str, Any],
                                         status: str = 'completed',
                                         error_details: Dict[str, Any] = None) -> None:
        """Store raw enrichment data in BigQuery"""
        try:
            table_ref = self._get_table_ref('enrichment_raw_data')

            row = {
                'job_id': job_id,
                'tenant_id': 'default',
                'status': status,
                'entity_type': 'account',
                'entity_id': entity_id,
                'source': source,
                'raw_data': json.dumps(raw_data),
                'processed_data': json.dumps(processed_data),
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat(),
                'error_details': json.dumps(error_details) if error_details else None
            }

            logger.debug(f"Inserting row into BigQuery enrichment_raw_data: {row}")

            table = self.client.get_table(table_ref)
            errors = self.client.insert_rows_json(table, [row])

            if errors:
                logger.error(f"Errors inserting into enrichment_raw_data: {errors}")
                raise Exception(f"BigQuery insert errors: {errors}")

        except Exception as e:
            logger.error(f"Error storing enrichment data in BigQuery: {str(e)}")
            raise