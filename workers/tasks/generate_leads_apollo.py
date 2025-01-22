import asyncio
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, Any, List, Optional, Union

import google.generativeai as genai

from services.ai_service import AIServiceFactory
from services.api_cache_service import APICacheService, cached_request
from services.bigquery_service import BigQueryService
from services.django_callback_service import CallbackService
from utils.retry_utils import RetryableError, RetryConfig, with_retry
from utils.url_utils import UrlUtils
from .enrichment_task import AccountEnrichmentTask

logger = logging.getLogger(__name__)

@dataclass
class ApolloConfig:
    """Centralized configuration management."""
    max_employees: int = 2000
    batch_size: int = 100
    ai_batch_size: int = 10
    fit_score_threshold: float = 0.0
    cache_ttl_hours: int = 24 * 30
    concurrent_requests: int = 3
    max_retries: int = 3
    retry_delay: float = 1.0
    max_retry_delay: float = 5.0

@dataclass
class ProcessingMetrics:
    """Track processing metrics for monitoring."""
    total_leads_processed: int = 0
    successful_leads: int = 0
    failed_leads: int = 0
    processing_time: float = 0.0
    api_errors: int = 0
    ai_errors: int = 0

@dataclass
class PromptTemplates:
    """Store prompt templates for AI analysis of leads."""
    LEAD_EVALUATION_PROMPT = """
    You're an experienced SDR tasked with evaluating leads. 
    Evaluate potential leads based on the given product and persona criteria. Rate each lead's fit.
    1. Evaluate each lead independently, without referring to the other leads.
    2. Use the given product and persona information to evaluate each lead.
    3. You can assume that the account is already qualified and have a good potential fit, you're only evaluating leads.
    4. Rationale and analysis should highlight and quote specific instances from the data that supports the score.
    
    Product Information:
    {product_info}
    
    Target Personas:
    {persona_info}
    
    Lead Data:
    {lead_data}
    
    Evaluate each lead and return a JSON response with this structure:
    {{
        "evaluated_leads": [
            {{
                "lead_id": string,
                "fit_score": number (0-1),
                "rationale": string,
                "matching_criteria": [string],
                "persona_match": string or null,
                "recommended_approach": string,
                "overall_analysis":[string]
            }}
        ]
    }}
    1. Return ONLY valid JSON
    2. If a field is not available, use null
    3. Do not include any other information or pleasantries or anything else outside the JSON
    """

class ApolloLeadsTask(AccountEnrichmentTask):
    """Task for identifying potential leads using Apollo API and AI analysis."""

    ENRICHMENT_TYPE = 'generate_leads'

    # Retry configurations
    APOLLO_RETRY_CONFIG = RetryConfig(
        max_attempts=3,
        base_delay=1.0,
        max_delay=5.0,
        retryable_exceptions=[
            RetryableError,
            asyncio.TimeoutError,
            ConnectionError
        ]
    )

    def __init__(self, config: Optional[ApolloConfig] = None):
        """Initialize the task with required services and configurations."""
        self.config = config or ApolloConfig()
        self.metrics = ProcessingMetrics()
        self.bq_service = BigQueryService()
        self._initialize_credentials()
        self._configure_ai_service()
        self.prompts = PromptTemplates()

    def _initialize_credentials(self) -> None:
        """Initialize and validate required API credentials."""
        self.apollo_api_key = os.getenv('APOLLO_API_KEY')
        self.google_api_key = os.getenv('GEMINI_API_TOKEN')
        self.project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
        self.dataset = os.getenv('BIGQUERY_DATASET', 'userport_enrichment')

        if not self.apollo_api_key:
            raise ValueError("APOLLO_API_KEY environment variable is required")
        if not self.google_api_key:
            raise ValueError("GEMINI_API_TOKEN environment variable is required")

        # Initialize cache service
        self.cache_service = APICacheService(
            client=self.bq_service.client,
            project_id=self.project_id,
            dataset=self.dataset
        )

    def _configure_ai_service(self) -> None:
        """Configure the Gemini AI service."""
        genai.configure(api_key=self.google_api_key)
        self.model = AIServiceFactory.create_service("openai")

    @property
    def enrichment_type(self) -> str:
        return self.ENRICHMENT_TYPE

    @property
    def task_name(self) -> str:
        """Get the task identifier."""
        return "lead_identification_apollo"

    async def create_task_payload(self, **kwargs) -> Dict[str, Any]:
        """Create a standardized task payload."""
        required_fields = ['account_id', 'account_data', 'product_data']
        missing_fields = [field for field in required_fields if field not in kwargs]

        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

        return {
            "account_id": kwargs["account_id"],
            "account_data": kwargs["account_data"],
            "product_data": kwargs["product_data"],
            "tenant_id": kwargs.get("tenant_id"),
            "job_id": str(uuid.uuid4())
        }

    async def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the lead identification task."""
        start_time = time.time()
        job_id = payload.get('job_id')
        account_id = payload.get('account_id')
        account_data = payload.get('account_data', {})
        product_data = payload.get('product_data', {})
        callback_service = CallbackService()
        current_stage = 'initialization'

        website = account_data.get('website')
        if not website:
            raise ValueError("Account website/domain is required for lead identification")
        account_data['domain'] = UrlUtils.extract_domain(website)

        logger.info(f"Starting lead identification for job_id: {job_id}, account_id: {account_id}")

        try:
            # Send initial processing callback
            await callback_service.send_callback(
                job_id=job_id,
                account_id=account_id,
                enrichment_type=self.ENRICHMENT_TYPE,
                source="apollo",
                status='processing',
                completion_percentage=10,
                processed_data={'stage': current_stage}
            )

            # Fetch employees with concurrent processing
            current_stage = 'fetching_employees'
            raw_employee_data = await self._fetch_employees_concurrent(account_data['domain'])
            self.metrics.total_leads_processed = len(raw_employee_data)

            await callback_service.send_callback(
                job_id=job_id,
                account_id=account_id,
                enrichment_type=self.ENRICHMENT_TYPE,
                source="apollo",
                status='processing',
                completion_percentage=40,
                processed_data={
                    'stage': current_stage,
                    'employees_found': len(raw_employee_data),
                    'metrics': asdict(self.metrics)
                }
            )

            # Transform employees in batches
            current_stage = 'structuring_leads'
            structured_leads = await self._process_leads_in_batches(
                raw_employee_data,
                self.config.batch_size,
                self._transform_apollo_employee
            )
            self.metrics.successful_leads = len(structured_leads)

            await callback_service.send_callback(
                job_id=job_id,
                account_id=account_id,
                enrichment_type=self.ENRICHMENT_TYPE,
                source="apollo",
                status='processing',
                completion_percentage=70,
                processed_data={
                    'stage': current_stage,
                    'structured_leads': len(structured_leads),
                    'metrics': asdict(self.metrics)
                }
            )

            # Evaluate leads
            current_stage = 'evaluating_leads'
            evaluated_leads = await self._evaluate_leads(structured_leads, product_data)

            # Store results with enhanced metadata
            current_stage = 'storing_results'
            self.metrics.processing_time = time.time() - start_time

            await self._store_results(
                job_id=job_id,
                account_id=account_id,
                structured_leads=structured_leads,
                evaluated_leads=evaluated_leads
            )

            score_distribution = self._calculate_score_distribution(evaluated_leads)
            qualified_leads = [l for l in evaluated_leads if l['fit_score'] >= self.config.fit_score_threshold]

            # Send final callback with complete metrics
            await callback_service.paginated_service.send_callback(
                job_id=job_id,
                account_id=account_id,
                enrichment_type=self.ENRICHMENT_TYPE,
                source="apollo",
                status='completed',
                completion_percentage=100,
                processed_data={
                    'score_distribution': score_distribution,
                    'structured_leads': structured_leads,
                    'all_leads': evaluated_leads,
                    'qualified_leads': qualified_leads,
                    'metrics': asdict(self.metrics)
                }
            )

            return {
                "status": "completed",
                "job_id": job_id,
                "account_id": account_id,
                "total_leads_found": len(evaluated_leads),
                "qualified_leads": len(qualified_leads),
                "score_distribution": score_distribution,
                "metrics": asdict(self.metrics)
            }

        except Exception as e:
            logger.error(f"Lead identification failed for job {job_id}: {str(e)}", exc_info=True)
            error_details = {
                'error_type': type(e).__name__,
                'message': str(e),
                'stage': current_stage,
                'metrics': asdict(self.metrics)
            }

            await self._store_error_state(job_id, account_id, error_details)
            await callback_service.send_callback(
                job_id=job_id,
                account_id=account_id,
                enrichment_type=self.ENRICHMENT_TYPE,
                source="apollo",
                status='failed',
                error_details=error_details,
                processed_data={'stage': current_stage}
            )

            return {
                "status": "failed",
                "job_id": job_id,
                "account_id": account_id,
                "error": str(e),
                "stage": current_stage,
                "metrics": asdict(self.metrics)
            }


    @with_retry(retry_config=APOLLO_RETRY_CONFIG, operation_name="fetch_employees_concurrent")
    async def _fetch_employees_concurrent(self, domain: str) -> List[Dict[str, Any]]:
        """Fetch employees with concurrent processing."""
        if not domain:
            raise ValueError("Domain is required")

        all_employees = []
        semaphore = asyncio.Semaphore(self.config.concurrent_requests)

        async def fetch_page(page_num: int) -> Optional[Dict[str, Any]]:
            async with semaphore:
                try:
                    search_params = {
                        'api_key': self.apollo_api_key,
                        'q_organization_domains': domain,
                        'page': page_num,
                        'per_page': self.config.batch_size
                    }

                    response, status_code = await cached_request(
                        cache_service=self.cache_service,
                        url="https://api.apollo.io/v1/mixed_people/search",
                        method='POST',
                        params=search_params,
                        headers={'Content-Type': 'application/json'},
                        ttl_hours=self.config.cache_ttl_hours
                    )

                    if status_code == 200:
                        return {
                            'people': response.get('people', []),
                            'pagination': response.get('pagination', {})
                        }
                    elif status_code == 429:
                        raise RetryableError("Rate limit exceeded")
                    return None

                except Exception as e:
                    logger.error(f"Error fetching page {page_num}: {str(e)}")
                    self.metrics.api_errors += 1
                    return None

        # Fetch first page to get total count and pagination info
        first_page_result = await fetch_page(1)
        if not first_page_result:
            logger.error("Failed to fetch first page")
            return []

        all_employees.extend(first_page_result['people'])

        # Get total count and calculate number of pages needed
        pagination = first_page_result['pagination']
        total_count = min(
            pagination.get('total_entries', 0),
            self.config.max_employees
        )

        if total_count <= self.config.batch_size:
            logger.info(f"Only {total_count} employees found, no additional pages needed")
            return all_employees

        # Calculate actual number of pages needed based on total count
        remaining_count = total_count - len(first_page_result['people'])
        pages_needed = (remaining_count + self.config.batch_size - 1) // self.config.batch_size

        logger.info(f"Fetching {remaining_count} remaining employees across {pages_needed} pages")

        # Fetch remaining pages concurrently
        tasks = []
        total_pages = pagination.get('total_pages', 1)
        for p in range(2, min(pages_needed + 2, total_pages + 1)):
            tasks.append(fetch_page(p))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, dict) and 'people' in result:
                    all_employees.extend(result['people'])
                elif isinstance(result, Exception):
                    logger.error(f"Error in concurrent fetch: {str(result)}")
                    self.metrics.api_errors += 1

        return all_employees

    async def _process_leads_in_batches(
            self,
            leads: List[Dict[str, Any]],
            batch_size: int,
            process_func: callable
    ) -> List[Dict[str, Any]]:
        """Process leads in concurrent batches."""
        results: List[Dict[str, Any]] = []
        for i in range(0, len(leads), batch_size):
            batch = leads[i:i + batch_size]
            tasks = [process_func(lead) for lead in batch]
            batch_results: List[Union[Dict[str, Any], Exception]] = await asyncio.gather(*tasks, return_exceptions=True)

            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Batch processing error: {str(result)}")
                    self.metrics.failed_leads += 1
                elif isinstance(result, dict):
                    results.append(result)

        return results

    async def _store_results(
            self,
            job_id: str,
            account_id: str,
            structured_leads: List[Dict[str, Any]],
            evaluated_leads: List[Dict[str, Any]]
    ) -> None:
        """Enhanced result storage with metadata and metrics."""
        try:
            # Add processing metadata
            metadata = {
                'processing_timestamp': datetime.utcnow().isoformat(),
                'total_leads_processed': len(structured_leads),
                'successful_evaluations': len(evaluated_leads),
                'processing_metrics': asdict(self.metrics),
                'config_used': asdict(self.config)
            }

            # Calculate quality metrics
            quality_metrics = {
                'complete_profile_rate': self._calculate_profile_completion_rate(structured_leads),
                'email_coverage_rate': self._calculate_email_coverage_rate(structured_leads),
                'seniority_distribution': self._calculate_seniority_distribution(structured_leads)
            }

            metadata['quality_metrics'] = quality_metrics

            await self.bq_service.insert_enrichment_raw_data(
                job_id=job_id,
                entity_id=account_id,
                source='apollo',
                raw_data={
                    'structured_leads': structured_leads,
                    'evaluated_leads': evaluated_leads,
                    'metadata': metadata
                },
                processed_data={
                    'qualified_leads': [
                        lead for lead in evaluated_leads
                        if lead.get('fit_score', 0) >= self.config.fit_score_threshold
                    ],
                    'quality_metrics': quality_metrics
                }
            )
        except Exception as e:
            logger.error(f"Error storing results: {str(e)}")
            self.metrics.api_errors += 1
            raise

    def _calculate_profile_completion_rate(self, leads: List[Dict[str, Any]]) -> float:
        """Calculate the rate of complete profiles."""
        required_fields = ['full_name', 'email', 'current_role.title', 'location.country']
        complete_profiles = 0

        for lead in leads:
            is_complete = True
            for field in required_fields:
                if '.' in field:
                    parent, child = field.split('.')
                    value = lead.get(parent, {}).get(child)
                else:
                    value = lead.get(field)

                if not value:
                    is_complete = False
                    break

            if is_complete:
                complete_profiles += 1

        return round(complete_profiles / len(leads), 4) if leads else 0.0

    def _calculate_email_coverage_rate(self, leads: List[Dict[str, Any]]) -> float:
        """Calculate the rate of leads with valid email addresses."""
        leads_with_email = sum(1 for lead in leads if lead.get('email'))
        return round(leads_with_email / len(leads), 4) if leads else 0.0

    def _calculate_seniority_distribution(self, leads: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate the distribution of seniority levels."""
        seniority_counts = {}
        total_leads = len(leads)

        for lead in leads:
            seniority = lead.get('current_role', {}).get('seniority', 'unknown')
            seniority_counts[seniority] = seniority_counts.get(seniority, 0) + 1

        return {
            level: round(count / total_leads, 4)
            for level, count in seniority_counts.items()
        } if total_leads else {}

    async def _transform_apollo_employee(self, employee: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Transform a single Apollo employee record with enhanced field extraction and null safety."""
        try:
            # Safely extract employment history details
            employment_history = []
            for job in employee.get('employment_history', []):
                if isinstance(job, dict):  # Ensure job is a dictionary
                    employment_entry = {
                        "company": job.get('organization_name'),
                        "title": job.get('title'),
                        "start_date": job.get('start_date'),
                        "end_date": job.get('end_date'),
                        "is_current": job.get('current', False)
                    }
                    employment_history.append(employment_entry)

            # Safely extract social profiles with None fallback
            social_profiles = {
                "linkedin_url": employee.get('linkedin_url'),
                "twitter_url": employee.get('twitter_url'),
                "facebook_url": employee.get('facebook_url'),
                "github_url": employee.get('github_url')
            }

            # Safely get organization details
            organization = employee.get('organization', {})
            if not isinstance(organization, dict):
                organization = {}

            company_details = {
                "name": organization.get('name'),
                "website": organization.get('website_url'),
                "linkedin_url": organization.get('linkedin_url'),
                "founded_year": organization.get('founded_year'),
                "logo_url": organization.get('logo_url')
            }

            # Safely process phone numbers
            phone_numbers = []
            for phone in employee.get('phone_numbers', []):
                if isinstance(phone, dict):
                    phone_numbers.append({
                        "number": phone.get('raw_number'),
                        "type": phone.get('type'),
                        "status": phone.get('status')
                    })

            # Enhanced lead structure with safe access
            lead = {
                "lead_id": str(employee.get('id', '')),
                "full_name": employee.get('name'),
                "first_name": employee.get('first_name'),
                "last_name": employee.get('last_name'),
                "headline": employee.get('headline'),
                "linkedin_url": employee.get('linkedin_url'),

                # Contact information
                "contact_info": {
                    "email": employee.get('email'),
                    "email_status": employee.get('email_status'),
                    "phone_numbers": phone_numbers,
                    "time_zone": employee.get('time_zone')
                },

                # Current role and company
                "current_role": {
                    "title": employee.get('title'),
                    "department": employee.get('department'),
                    "seniority": employee.get('seniority'),
                    "functions": employee.get('functions', []),
                    "subdepartments": employee.get('subdepartments', [])
                },

                # Location information - all optional
                "location": {
                    "city": employee.get('city'),
                    "state": employee.get('state'),
                    "country": employee.get('country'),
                    "raw_address": employee.get('present_raw_address')
                },

                # Company information
                "company": company_details,

                # Additional metadata
                "social_profiles": social_profiles,
                "employment_history": employment_history,

                # Enrichment metadata
                "data_quality": {
                    "existence_level": employee.get('existence_level'),
                    "email_domain_catchall": employee.get('email_domain_catchall', False),
                    "profile_photo_url": employee.get('photo_url'),
                    "last_updated": employee.get('updated_at')
                },

                # Intent and engagement data
                "engagement_data": {
                    "intent_strength": employee.get('intent_strength'),
                    "show_intent": employee.get('show_intent', False),
                    "last_activity_date": employee.get('last_activity_date')
                }
            }

            if not lead['lead_id']:
                logger.warning("Missing lead ID, skipping record")
                self.metrics.failed_leads += 1
                return None

            return lead

        except Exception as e:
            logger.error(f"Error transforming employee data: {str(e)}")
            self.metrics.failed_leads += 1
            return None

    async def _evaluate_leads(self, structured_leads: List[Dict[str, Any]],
                              product_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Evaluate leads in batches with enhanced error handling."""
        if not structured_leads:
            logger.warning("No structured leads provided for evaluation")
            return []

        evaluated_leads = []
        start_time = time.time()

        for i in range(0, len(structured_leads), self.config.ai_batch_size):
            try:
                batch = structured_leads[i:i + self.config.ai_batch_size]

                evaluation_prompt = self.prompts.LEAD_EVALUATION_PROMPT.format(
                    product_info=json.dumps(product_data, indent=2),
                    persona_info=json.dumps(product_data.get('persona_role_titles', {}), indent=2),
                    lead_data=json.dumps(batch, indent=2)
                )

                response = await self.model.generate_content(
                    prompt=evaluation_prompt,
                    is_json=True,
                    operation_tag="lead_evaluation"
                )

                if not response:
                    logger.error(f"Empty response from AI for batch {i//self.config.ai_batch_size + 1}")
                    self.metrics.ai_errors += 1
                    continue

                # Validate and normalize each lead score
                if 'evaluated_leads' in response:
                    normalized_leads = []
                    for lead in response['evaluated_leads']:
                        try:
                            lead['fit_score'] = max(0.0, min(1.0, float(lead.get('fit_score', 0))))
                            normalized_leads.append(lead)
                        except (ValueError, TypeError) as e:
                            logger.error(f"Score normalization error: {str(e)}")
                            self.metrics.failed_leads += 1

                    evaluated_leads.extend(normalized_leads)
                    self.metrics.successful_leads += len(normalized_leads)
                else:
                    logger.error(f"Invalid response structure for batch {i//self.config.ai_batch_size + 1}")
                    self.metrics.ai_errors += 1

            except Exception as e:
                logger.error(f"Error processing batch {i//self.config.ai_batch_size + 1}: {str(e)}")
                self.metrics.ai_errors += 1
                continue

        self.metrics.processing_time = time.time() - start_time
        return evaluated_leads

    async def _store_error_state(self, job_id: str, entity_id: str, error_details: Dict[str, Any]) -> None:
        """Store error information with enhanced metadata in BigQuery."""
        try:
            if not job_id or not entity_id:
                logger.error("Missing required fields for error state storage")
                return

            # Add timestamp and processing metrics
            current_time = datetime.utcnow().isoformat()

            # Ensure error details are properly formatted
            formatted_error = {
                'error_type': error_details.get('error_type', 'unknown_error'),
                'message': error_details.get('message', 'Unknown error occurred'),
                'stage': error_details.get('stage', 'unknown'),
                'timestamp': current_time,
                'retryable': error_details.get('retryable', True),
                'metrics': asdict(self.metrics),
                'processing_metadata': {
                    'config': asdict(self.config),
                    'partial_completion': self.metrics.total_leads_processed > 0,
                    'success_rate': (
                        self.metrics.successful_leads / self.metrics.total_leads_processed
                        if self.metrics.total_leads_processed > 0 else 0
                    ),
                    'api_failure_rate': (
                            self.metrics.api_errors / max(1, self.metrics.total_leads_processed)
                    ),
                    'processing_duration': self.metrics.processing_time
                }
            }

            # Add stack trace if available
            if error_details.get('traceback'):
                formatted_error['traceback'] = error_details['traceback']

            logger.debug(f"Storing error state for job {job_id}, entity {entity_id}")

            await self.bq_service.insert_enrichment_raw_data(
                job_id=job_id,
                entity_id=entity_id,
                source='apollo',
                raw_data={},  # Empty since this is an error state
                processed_data={},  # Empty since this is an error state
                status='failed',
                error_details=formatted_error,
                attempt_number=error_details.get('attempt_number', 1),
                max_retries=error_details.get('max_retries', self.config.max_retries)
            )

            logger.info(f"Successfully stored error state for job {job_id}, entity {entity_id}")

        except Exception as e:
            logger.error(
                f"Failed to store error state for job {job_id}, entity {entity_id}: {str(e)}",
                exc_info=True
            )
            # Don't re-raise since this is already error handling code

    def _calculate_score_distribution(self, evaluated_leads: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate comprehensive score distribution with metrics."""
        if not evaluated_leads:
            return {
                'distribution': {
                    'excellent': 0,
                    'good': 0,
                    'moderate': 0,
                    'low': 0
                },
                'metrics': {
                    'average_score': 0.0,
                    'median_score': 0.0,
                    'qualified_rate': 0.0
                },
                'score_ranges': {
                    '0.8-1.0': 0,
                    '0.6-0.8': 0,
                    '0.4-0.6': 0,
                    '0.0-0.4': 0
                }
            }

        # Basic distribution counting
        distribution = {
            'excellent': 0,  # 0.8 - 1.0
            'good': 0,      # 0.6 - 0.8
            'moderate': 0,  # 0.4 - 0.6
            'low': 0        # 0.0 - 0.4
        }

        # Detailed score ranges for histogram
        score_ranges = {
            '0.8-1.0': 0,
            '0.6-0.8': 0,
            '0.4-0.6': 0,
            '0.0-0.4': 0
        }

        # Calculate score statistics
        scores = []
        for lead in evaluated_leads:
            score = lead.get('fit_score', 0)
            scores.append(score)

            # Update distribution categories
            if score >= 0.8:
                distribution['excellent'] += 1
                score_ranges['0.8-1.0'] += 1
            elif score >= 0.6:
                distribution['good'] += 1
                score_ranges['0.6-0.8'] += 1
            elif score >= 0.4:
                distribution['moderate'] += 1
                score_ranges['0.4-0.6'] += 1
            else:
                distribution['low'] += 1
                score_ranges['0.0-0.4'] += 1

        # Calculate statistical metrics
        total_leads = len(evaluated_leads)
        qualified_leads = sum(1 for lead in evaluated_leads
                              if lead.get('fit_score', 0) >= self.config.fit_score_threshold)

        scores.sort()
        median_index = total_leads // 2
        median_score = scores[median_index] if scores else 0
        average_score = sum(scores) / total_leads if scores else 0
        qualified_rate = qualified_leads / total_leads if total_leads > 0 else 0

        return {
            'distribution': distribution,
            'metrics': {
                'average_score': round(average_score, 4),
                'median_score': round(median_score, 4),
                'qualified_rate': round(qualified_rate, 4),
                'total_leads': total_leads,
                'qualified_leads': qualified_leads
            },
            'score_ranges': score_ranges,
            'statistics': {
                'min_score': round(min(scores), 4) if scores else 0,
                'max_score': round(max(scores), 4) if scores else 0,
                'score_variance': round(self._calculate_variance(scores), 4),
                'score_distribution_skew': self._calculate_distribution_skew(scores)
            }
        }

    def _calculate_variance(self, scores: List[float]) -> float:
        """Calculate variance of scores."""
        if not scores:
            return 0.0
        mean = sum(scores) / len(scores)
        squared_diff_sum = sum((x - mean) ** 2 for x in scores)
        return squared_diff_sum / len(scores)

    def _calculate_distribution_skew(self, scores: List[float]) -> str:
        """Calculate if distribution is skewed towards high or low scores."""
        if not scores:
            return "no_data"

        mean = sum(scores) / len(scores)
        median = sorted(scores)[len(scores) // 2]

        if abs(mean - median) < 0.1:  # Threshold for considering it normal
            return "normal"
        elif mean > median:
            return "right_skewed"  # More high scores
        else:
            return "left_skewed"  # More low scores

    def _attempt_json_fix(self, text: str) -> str:
        """Attempt to fix common JSON formatting issues."""
        # Fix 1: Replace single quotes with double quotes
        # Before: {'name': 'John'}
        # After:  {"name": "John"}
        text = text.replace("'", '"')

        # Fix 2: Handle missing commas between objects and fix missing quotes around keys
        # Before: { title: "Manager" } { role: "lead" }
        # After:  { "title": "Manager" }, { "role": "lead" }
        import re
        text = re.sub(r'(\s*})(\s*,?\s*{?\s*[\w_]+\s*:)', r'\1,\2', text)
        text = re.sub(r'([\w_]+)(:)', r'"\1"\2', text)

        # Fix 3: Remove trailing commas in objects/arrays
        # Before: {"items": ["a", "b",]}
        # After:  {"items": ["a", "b"]}
        text = re.sub(r',(\s*[}\]])', r'\1', text)

        # Fix 4: Add quotes around unquoted string values
        # Before: {"status": pending, "id": 123}
        # After:  {"status": "pending", "id": 123}
        text = re.sub(r':\s*([\w_-]+)([,}])', r': "\1"\2', text)

        return text