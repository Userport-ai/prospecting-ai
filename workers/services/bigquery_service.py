import json
import logging
import os
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional

from google.cloud import bigquery
from google.oauth2 import service_account

from utils.bigquery_json_encoder import safe_json_dumps

logger = logging.getLogger(__name__)

class BigQueryService:
    """Service class for handling BigQuery operations for account enrichment data."""

    def __init__(self):
        """Initialize BigQuery client and configuration."""
        service_account_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        self.project = os.getenv('GOOGLE_CLOUD_PROJECT')

        if service_account_path and os.path.exists(service_account_path) and self.project:
            # Initialize credentials from service account file
            credentials = service_account.Credentials.from_service_account_file(
                service_account_path,
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )

            # Initialize BigQuery client with explicit credentials
            self.client = bigquery.Client(
                credentials=credentials,
                project=self.project,
                location='US'
            )
        else:
            self.client = bigquery.Client(project=self.project,
                                          location='US')

        self.dataset = os.getenv('BIGQUERY_DATASET', 'userport_enrichment')

    def _get_table_ref(self, table_name: str) -> str:
        """Get fully qualified table reference."""
        return f"{self.project}.{self.dataset}.{table_name}"

    # Account Data Operations
    async def insert_account_data(
            self,
            account_id: str,
            structured_data: Dict[str, Any],
            raw_profile: str,
            is_partial: bool = False,
            error_info: Optional[Dict[str, Any]] = None
    ) -> str:
        """Store enriched account data with defaults for new columns."""
        try:
            record_id = str(uuid.uuid4())
            current_time = datetime.utcnow()

            # Prepare the base row
            new_row = self._prepare_account_row(record_id, account_id, structured_data, raw_profile)

            # Add additional fields with proper error handling for JSON
            try:
                error_json = safe_json_dumps(error_info) if error_info else None
            except (TypeError, ValueError):
                logger.warning(f"Could not serialize error_info to JSON: {error_info}")
                error_json = safe_json_dumps({"error": "Error info serialization failed"})

            new_row.update({
                'is_partial_data': bool(is_partial),
                'last_error': error_json,
                'data_quality_score': self._calculate_data_quality_score(structured_data, is_partial),
                'last_successful_update': current_time.isoformat() if not is_partial else None,
                'last_attempt': current_time.isoformat()
            })

            # Handle existing data
            existing_data = await self._get_existing_account_data(account_id)
            if existing_data:
                final_row = self._merge_account_data(existing_data, new_row)
                await self._update_account_data(account_id, final_row)
            else:
                table = self.client.get_table(self._get_table_ref('account_data'))
                errors = self.client.insert_rows_json(table, [new_row])
                if errors:
                    error_messages = '; '.join(str(error) for error in errors)
                    raise Exception(f"BigQuery insert errors: {error_messages}")

            return record_id

        except Exception as e:
            logger.error(f"Error storing account data in BigQuery: {str(e)}")
            raise

    async def _get_existing_account_data(self, account_id: str) -> Dict[str, Any]:
        """Retrieve existing account data if it exists."""
        try:
            query = """
            SELECT *
            FROM `{}.{}.account_data`
            WHERE account_id = @account_id
            ORDER BY fetched_at DESC
            LIMIT 1
            """.format(self.project, self.dataset)

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("account_id", "STRING", account_id)
                ]
            )

            query_job = self.client.query(query, job_config=job_config)
            results = list(query_job.result())

            if not results:
                logger.debug(f"No existing data found for account_id: {account_id}")
                return {}

            # Convert BigQuery Row to dict and handle array/JSON fields
            row_dict = dict(results[0])

            # Handle repeated string fields
            if 'industry' in row_dict:
                row_dict['industry'] = list(row_dict['industry']) if row_dict['industry'] else []
            if 'technologies' in row_dict:
                row_dict['technologies'] = list(row_dict['technologies']) if row_dict['technologies'] else []

            # Handle JSON fields
            json_fields = ['funding_details', 'raw_data', 'last_error']
            for field in json_fields:
                if field in row_dict and row_dict[field]:
                    try:
                        if isinstance(row_dict[field], str):
                            row_dict[field] = json.loads(row_dict[field])
                    except json.JSONDecodeError:
                        logger.warning(f"Could not parse {field} as JSON for account_id: {account_id}")
                        row_dict[field] = None

            return row_dict

        except Exception as e:
            logger.error(f"Error retrieving account data from BigQuery: {str(e)}")
            return {}

    async def _update_account_data(self, account_id: str, row_data: Dict[str, Any]) -> None:
        """Update existing account data in BigQuery."""
        try:
            update_query = """
            UPDATE `{}.{}.account_data`
            SET 
                company_name = @company_name,
                employee_count = @employee_count,
                industry = @industry,
                location = @location,
                website = @website,
                linkedin_url = @linkedin_url,
                technologies = @technologies,
                funding_details = PARSE_JSON(@funding_details),
                raw_data = PARSE_JSON(@raw_data),
                fetched_at = @fetched_at,
                is_partial_data = @is_partial_data,
                last_error = PARSE_JSON(@last_error),
                data_quality_score = @data_quality_score,
                last_successful_update = @last_successful_update,
                last_attempt = @last_attempt
            WHERE account_id = @account_id
            """.format(self.project, self.dataset)

            # Handle repeated string fields (arrays)
            industries = row_data.get('industry', [])
            if isinstance(industries, str):
                try:
                    industries = json.loads(industries)
                except json.JSONDecodeError:
                    industries = [industries]
            elif not isinstance(industries, list):
                industries = [str(industries)] if industries else []
            industries = [str(i) for i in industries if i is not None]

            technologies = row_data.get('technologies', [])
            if isinstance(technologies, str):
                try:
                    technologies = json.loads(technologies)
                except json.JSONDecodeError:
                    technologies = [technologies]
            elif not isinstance(technologies, list):
                technologies = [str(technologies)] if technologies else []
            technologies = [str(t) for t in technologies if t is not None]

            # Handle JSON fields - ensure they're valid JSON strings
            json_fields = ['funding_details', 'raw_data', 'last_error']
            for field in json_fields:
                value = row_data.get(field)
                if value is not None:
                    row_data[field] = safe_json_dumps(value)
                else:
                    row_data[field] = 'null'

            # Create query parameters
            query_parameters = [
                bigquery.ScalarQueryParameter("account_id", "STRING", row_data['account_id']),
                bigquery.ArrayQueryParameter("industry", "STRING", industries),
                bigquery.ArrayQueryParameter("technologies", "STRING", technologies)
            ]

            # Optional scalar parameters
            optional_params = [
                ("company_name", "STRING", row_data.get('company_name')),
                ("employee_count", "INTEGER", row_data.get('employee_count')),
                ("location", "STRING", row_data.get('location')),
                ("website", "STRING", row_data.get('website')),
                ("linkedin_url", "STRING", row_data.get('linkedin_url')),
                ("funding_details", "STRING", row_data.get('funding_details')),
                ("raw_data", "STRING", row_data.get('raw_data')),
                ("fetched_at", "TIMESTAMP", row_data.get('fetched_at')),
                ("is_partial_data", "BOOL", row_data.get('is_partial_data')),
                ("last_error", "STRING", row_data.get('last_error')),
                ("data_quality_score", "FLOAT64", row_data.get('data_quality_score')),
                ("last_successful_update", "TIMESTAMP", row_data.get('last_successful_update')),
                ("last_attempt", "TIMESTAMP", row_data.get('last_attempt'))
            ]

            # Add optional parameters only if they have a value
            for name, type_, value in optional_params:
                if value is not None:
                    query_parameters.append(bigquery.ScalarQueryParameter(name, type_, value))

            job_config = bigquery.QueryJobConfig(query_parameters=query_parameters)
            query_job = self.client.query(update_query, job_config=job_config)
            query_job.result()

        except Exception as e:
            logger.error(f"Error updating account data in BigQuery: {str(e)}")
            raise

    def _prepare_account_row(self, record_id: str, account_id: str,
                             structured_data: Dict[str, Any], raw_profile: str) -> Dict[str, Any]:
        """Prepare a row for insertion into account_data table."""
        try:
            company_data = structured_data.get('company_name', {})
            location_data = structured_data.get('location', {}).get('headquarters', {})
            business_metrics = structured_data.get('business_metrics', {})
            industry_data = structured_data.get('industry', {})
            tech_data = structured_data.get('technology_stack', {})
            financial_data = structured_data.get('financials', {})

            # Handle technologies as repeated string field
            technologies = []
            for tech_type in ['programming_languages', 'frameworks', 'cloud_services']:
                tech_list = tech_data.get(tech_type, [])
                if isinstance(tech_list, str):
                    try:
                        tech_list = json.loads(tech_list)
                    except json.JSONDecodeError:
                        tech_list = [tech_list]
                elif not isinstance(tech_list, list):
                    tech_list = [tech_list] if tech_list else []
                technologies.extend([str(tech) for tech in tech_list if tech])

            # Handle industry sectors as repeated string field
            sectors = industry_data.get('sectors', [])
            if isinstance(sectors, str):
                try:
                    sectors = json.loads(sectors)
                except json.JSONDecodeError:
                    sectors = [sectors]
            elif not isinstance(sectors, list):
                sectors = [sectors] if sectors else []
            sectors = [str(sector) for sector in sectors if sector]

            # Clean location string
            location = f"{location_data.get('city', '')}, {location_data.get('country', '')}".strip(', ')
            if not location:
                location = None

            # Handle employee count properly
            employee_count = business_metrics.get('employee_count', {}).get('total')
            if employee_count is not None:
                try:
                    employee_count = int(employee_count)
                except (ValueError, TypeError):
                    employee_count = None

            # Prepare funding details as valid JSON
            funding_details = financial_data.get('private_data', {})
            if funding_details:
                funding_details = safe_json_dumps(funding_details)
            else:
                funding_details = 'null'

            # Prepare raw data as valid JSON
            raw_data = safe_json_dumps(structured_data) if structured_data else 'null'

            return {
                'record_id': record_id,
                'account_id': account_id,
                'company_name': company_data.get('legal_name'),
                'employee_count': employee_count,
                'industry': sectors,
                'location': location,
                'website': structured_data.get('digital_presence', {}).get('website'),
                'linkedin_url': structured_data.get('digital_presence', {}).get('social_media', {}).get('linkedin'),
                'technologies': technologies,
                'funding_details': funding_details,
                'raw_data': raw_data,
                'fetched_at': datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error preparing account row: {str(e)}")
            raise

    def _merge_account_data(self, existing: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
        """Merge existing and new account data, preferring newer non-null values."""
        merged = existing.copy()

        # Handle scalar fields
        scalar_fields = [
            'company_name', 'employee_count', 'location', 'website',
            'linkedin_url', 'data_quality_score', 'is_partial_data'
        ]
        for field in scalar_fields:
            if new.get(field) is not None:
                merged[field] = new[field]

        # Handle repeated string fields (industry, technologies)
        merged['industry'] = self._merge_arrays(
            existing.get('industry', []),
            new.get('industry', [])
        )
        merged['technologies'] = self._merge_arrays(
            existing.get('technologies', []),
            new.get('technologies', [])
        )

        # Handle JSON fields
        json_fields = ['funding_details', 'raw_data', 'last_error']
        for field in json_fields:
            if field in new and new[field] is not None:
                try:
                    # Convert existing field to Python object if it's a JSON string
                    existing_data = {}
                    if existing.get(field):
                        if isinstance(existing[field], str):
                            try:
                                existing_data = json.loads(existing[field])
                            except json.JSONDecodeError:
                                logger.warning(f"Could not parse existing {field} as JSON")
                                existing_data = {}
                        else:
                            existing_data = existing[field]

                    # Convert new field to Python object if it's a JSON string
                    new_data = {}
                    if isinstance(new[field], str):
                        try:
                            new_data = json.loads(new[field])
                        except json.JSONDecodeError:
                            logger.warning(f"Could not parse new {field} as JSON")
                            new_data = {"value": new[field]}
                    else:
                        new_data = new[field]

                    # Merge the data if both are dictionaries
                    if isinstance(existing_data, dict) and isinstance(new_data, dict):
                        merged_data = {**existing_data, **new_data}
                    else:
                        merged_data = new_data

                    # Convert back to JSON string
                    merged[field] = safe_json_dumps(merged_data) if merged_data is not None else 'null'

                except Exception as e:
                    logger.error(f"Error merging {field}: {str(e)}")
                    merged[field] = safe_json_dumps(new[field])

        # Handle timestamp fields
        timestamp_fields = ['fetched_at', 'last_successful_update', 'last_attempt']
        for field in timestamp_fields:
            if new.get(field) is not None:
                merged[field] = new[field]

        return merged

    def _merge_arrays(self, existing: list, new: list) -> list:
        """Merge arrays keeping unique values and removing None/empty values."""
        combined = existing + new if existing and new else new or existing or []
        return list(set(filter(None, combined)))

    def _should_merge_data(self, existing: Dict[str, Any], new: Dict[str, Any]) -> bool:
        """Determine if new data should be merged based on quality and completeness."""
        existing_score = existing.get('data_quality_score', 0)
        new_score = new.get('data_quality_score', 0)

        if new_score > existing_score:
            return True

        if new_score == existing_score:
            return any(new[key] is not None and existing.get(key) is None for key in new)

        return False

    async def insert_enrichment_raw_data(
            self,
            job_id: str,
            source: str,
            entity_id: str,
            entity_type: str = 'account',
            raw_data: Optional[Dict[str, Any]] = None,
            processed_data: Optional[Dict[str, Any]] = None,
            status: str = 'completed',
            error_details: Optional[Dict[str, Any]] = None,
            attempt_number: Optional[int] = None,
            max_retries: Optional[int] = None,
    ) -> None:
        """Insert enrichment raw data into BigQuery."""
        try:
            # Prepare error information with proper JSON handling
            error_info = None
            if error_details:
                try:
                    error_info = {
                        'error_type': str(error_details.get('error_type', 'unknown')),
                        'message': str(error_details.get('message', '')),
                        'step': str(error_details.get('step', '')),
                        'partial_success': error_details.get('partial_success', {}),
                        'timestamp': datetime.utcnow().isoformat()
                    }
                except Exception as e:
                    logger.warning(f"Error preparing error details: {str(e)}")
                    error_info = {
                        'error_type': 'unknown',
                        'message': str(error_details),
                        'timestamp': datetime.utcnow().isoformat()
                    }

            # Prepare row data with proper JSON handling
            row = {
                'job_id': str(job_id),
                'tenant_id': 'default',
                'status': str(status),
                'entity_type': 'account',
                'entity_id': str(entity_id),
                'source': str(source),
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat(),
                'attempt_number': int(attempt_number if attempt_number is not None else 1),
                'max_retries': int(max_retries if max_retries is not None else 3),
                'is_partial': bool(error_details and raw_data),
                'completion_percentage': self._calculate_completion_percentage(raw_data, error_details),
                'retryable': bool(error_details.get('retryable', True)) if error_details else True
            }

            # Handle raw_data JSON
            if raw_data is not None:
                row['raw_data'] = safe_json_dumps(raw_data)

            # Handle processed_data JSON
            if processed_data is not None:
                row['processed_data'] = safe_json_dumps(processed_data)

            # Handle error_details JSON
            if error_info is not None:
                row['error_details'] = safe_json_dumps(error_info)

            # Insert data with proper error handling
            table = self.client.get_table(self._get_table_ref('enrichment_raw_data'))
            errors = self.client.insert_rows_json(table, [row])

            if errors:
                error_messages = '; '.join(str(error) for error in errors)
                raise Exception(f"BigQuery insert errors: {error_messages}")

        except Exception as e:
            logger.error(f"Error storing enrichment data in BigQuery: {str(e)}")
            raise

    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get detailed job status including error information and retry attempts."""
        query = """
        SELECT 
            job_id,
            entity_id,
            status,
            attempt_number,
            max_retries,
            error_details,
            created_at,
            updated_at
        FROM `{}.{}.enrichment_raw_data`
        WHERE job_id = @job_id
        ORDER BY attempt_number DESC
        LIMIT 1
        """.format(self.project, self.dataset)

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("job_id", "STRING", job_id)
            ]
        )

        results = list(self.client.query(query, job_config=job_config).result())
        if not results:
            raise KeyError(f"Job {job_id} not found")

        return dict(results[0])

    async def list_failed_jobs(
            self,
            start_date: datetime,
            end_date: datetime,
            retryable_only: bool = False,
            limit: int = 100
    ) -> List[Dict[str, Any]]:
        """List failed jobs within a date range."""
        query = """
        WITH RankedJobs AS (
            SELECT
                *,
                ROW_NUMBER() OVER (PARTITION BY job_id ORDER BY attempt_number DESC) as rn
            FROM `{}.{}.enrichment_raw_data`
            WHERE status = 'failed'
            AND created_at BETWEEN @start_date AND @end_date
            {}
        )
        SELECT
            job_id,
            entity_id,
            status,
            attempt_number,
            max_retries,
            is_partial,
            completion_percentage,
            retryable,
            error_details,
            created_at,
            updated_at
        FROM RankedJobs
        WHERE rn = 1
        ORDER BY created_at DESC
        LIMIT @limit
        """.format(
            self.project,
            self.dataset,
            "AND retryable = True" if retryable_only else ""
        )

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("start_date", "TIMESTAMP", start_date),
                bigquery.ScalarQueryParameter("end_date", "TIMESTAMP", end_date),
                bigquery.ScalarQueryParameter("limit", "INT64", limit)
            ]
        )

        results = self.client.query(query, job_config=job_config).result()
        return [dict(row) for row in results]

    # Scoring and Calculation Methods
    def _calculate_completion_percentage(self, raw_data: Optional[Dict[str, Any]],
                                         error_details: Optional[Dict[str, Any]]) -> int:
        """Calculate the percentage of completion based on successful steps."""
        if not raw_data:
            return 0

        total_steps = 3  # Jina API, Structured Data Extraction, Gemini Analysis
        completed_steps = 0

        if raw_data.get('jina_response'):
            completed_steps += 1
        if raw_data.get('gemini_structured'):
            completed_steps += 1
        if raw_data.get('gemini_analysis'):
            completed_steps += 1

        return int((completed_steps / total_steps) * 100)

    def _calculate_data_quality_score(self, structured_data: Dict[str, Any], is_partial: bool) -> float:
        """Calculate a score (0-1) representing data completeness and quality."""
        try:
            # Define field weights and validation rules
            field_weights = {
                'company_name': {
                    'weight': 1.0,
                    'required_subfields': ['legal_name']
                },
                'location': {
                    'weight': 1.0,
                    'required_subfields': ['headquarters.city', 'headquarters.country']
                },
                'industry': {
                    'weight': 1.0,
                    'required_subfields': ['sectors']
                },
                'business_metrics': {
                    'weight': 1.0,
                    'required_subfields': ['employee_count.total']
                },
                'technology_stack': {
                    'weight': 0.5,
                    'required_subfields': ['programming_languages', 'frameworks', 'cloud_services']
                },
                'business_details': {
                    'weight': 0.5,
                    'required_subfields': ['description', 'founding_year']
                },
                'market_position': {
                    'weight': 0.5,
                    'required_subfields': ['competitors', 'market_share']
                },
                'financials': {
                    'weight': 0.5,
                    'required_subfields': ['revenue', 'private_data']
                }
            }

            total_score = 0.0
            total_weight = sum(field['weight'] for field in field_weights.values())

            for field, config in field_weights.items():
                field_data = structured_data.get(field, {})
                if not field_data:
                    continue

                # Check required subfields
                subfield_score = 0
                for subfield in config['required_subfields']:
                    # Handle nested fields (e.g., 'headquarters.city')
                    value = field_data
                    for key in subfield.split('.'):
                        value = value.get(key, {})

                    if value and not (isinstance(value, dict) and not value):
                        subfield_score += 1

                # Calculate normalized score for this field
                field_score = (subfield_score / len(config['required_subfields'])) * config['weight']
                total_score += field_score

            # Calculate final normalized score
            final_score = total_score / total_weight

            # Apply penalties
            if is_partial:
                final_score *= 0.8

            # Ensure score is between 0 and 1
            final_score = max(0.0, min(1.0, final_score))

            return round(final_score, 2)

        except Exception as e:
            logger.error(f"Error calculating data quality score: {str(e)}")
            return 0.0