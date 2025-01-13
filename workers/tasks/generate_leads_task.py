import os
import uuid
import json
import logging
import asyncio
from dataclasses import dataclass
from datetime import datetime
import google.generativeai as genai
from typing import Dict, Any, List, Optional, Tuple, Union

from services.django_callback_service import CallbackService
from services.api_cache_service import APICacheService, cached_request
from .base import BaseTask
from services.bigquery_service import BigQueryService
from .enrichment_task import AccountEnrichmentTask

logger = logging.getLogger(__name__)

@dataclass
class PromptTemplates:
    """Store prompt templates for AI analysis of leads."""
    LEAD_EVALUATION_PROMPT = """
    Evaluate potential leads based on the given product and persona criteria. Rate each lead's fit.
    
    Product Information:
    {product_info}
    
    Target Personas:
    {persona_info}
    
    Lead Data:
    {lead_data}
    
    Evaluate each lead and return a JSON response with this structure:
    {
        "evaluated_leads": [
            {
                "lead_id": string,
                "fit_score": number (0-1),
                "rationale": string,
                "matching_criteria": [string],
                "persona_match": string or null,
                "recommended_approach": string
            }
        ]
    }
    """

    EXTRACTION_PROMPT = """
    Extract and structure key information about each lead from the raw employee data.
    Follow these rules strictly:
    1. Return ONLY valid JSON
    2. Include all available contact and professional details
    3. If a field is not available, use null
    4. Keep experience and education details concise
    
    Employee Data:
    {employee_data}
    
    Required JSON format:
    {
        "structured_leads": [
            {
                "lead_id": string,
                "full_name": string,
                "first_name": string,
                "last_name": string,
                "title": string,
                "linkedin_url": string,
                "email": string or null,
                "about_description": string or null,
                "current_role": {
                    "title": string,
                    "department": string,
                    "seniority": string,
                    "years_in_role": number or null,
                    "description": string or null
                },
                "location": string or null,
                "skills": [string],
                "education": [
                    {
                        "degree": string,
                        "institution": string,
                        "year": number or null
                    }
                ]
            }
        ]
    }
    """

class LeadIdentificationTask(AccountEnrichmentTask):
    """Task for identifying potential leads for an account using ProxyCurl and AI analysis."""

    ENRICHMENT_TYPE = 'lead_identification'
    BATCH_SIZE = 2 # Batch size for Gemini processing
    PAGE_SIZE = 2 # Number of results fetched from ProxyCurl API. Note: Increasing this will bump up our cost significantly

    def __init__(self):
        """Initialize the task with required services and configurations."""
        self.bq_service = BigQueryService()
        self._initialize_credentials()
        self._configure_ai_service()
        self.prompts = PromptTemplates()

    def _initialize_credentials(self) -> None:
        """Initialize and validate required API credentials."""
        self.proxycurl_api_key = os.getenv('PROXYCURL_API_KEY')
        self.google_api_key = os.getenv('GEMINI_API_TOKEN')
        self.project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
        self.dataset = os.getenv('BIGQUERY_DATASET', 'userport_enrichment')

        if not self.proxycurl_api_key:
            raise ValueError("PROXYCURL_API_KEY environment variable is required")
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
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')

    @property
    def enrichment_type(self) -> str:
        return self.ENRICHMENT_TYPE

    @property
    def task_name(self) -> str:
        """Get the task identifier."""
        return "lead_identification"

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
        job_id = payload.get('job_id')
        account_id = payload.get('account_id')
        account_data = payload.get('account_data', {})
        product_data = payload.get('product_data', {})
        tenant_id = payload.get('tenant_id')
        callback_service = CallbackService()
        current_stage = 'initialization'

        logger.info(f"Starting lead identification for job_id: {job_id}, account_id: {account_id}")

        try:
            if not account_data.get('linkedin_url'):
                raise ValueError("Account LinkedIn URL is required for lead identification")

            # Send initial processing callback
            await callback_service.send_callback(
                job_id=job_id,
                account_id=account_id,
                enrichment_type=self.ENRICHMENT_TYPE,
                status='processing',
                completion_percentage=10,
                processed_data={'stage': current_stage}
            )

            current_stage = 'fetching_employees'
            # Fetch employees from ProxyCurl with retries
            raw_employee_data, status_code = await self._fetch_employees_with_retry(
                account_data['linkedin_url'],
                product_data
            )

            await callback_service.send_callback(
                job_id=job_id,
                account_id=account_id,
                enrichment_type=self.ENRICHMENT_TYPE,
                status='processing',
                completion_percentage=40,
                processed_data={
                    'stage': current_stage,
                    'employees_found': len(raw_employee_data)
                }
            )

            current_stage = 'structuring_leads'
            # Extract structured lead information
            structured_leads = await self._extract_structured_leads(raw_employee_data)

            await callback_service.send_callback(
                job_id=job_id,
                account_id=account_id,
                enrichment_type=self.ENRICHMENT_TYPE,
                status='processing',
                completion_percentage=70,
                processed_data={
                    'stage': current_stage,
                    'structured_leads': len(structured_leads)
                }
            )

            current_stage = 'evaluating_leads'
            # Evaluate leads against product criteria
            evaluated_leads = await self._evaluate_leads(structured_leads, product_data)

            # Store results in BigQuery
            current_stage = 'storing_results'
            await self._store_results(
                job_id=job_id,
                account_id=account_id,
                tenant_id=tenant_id,
                structured_leads=structured_leads,
                evaluated_leads=evaluated_leads
            )

            # Calculate score distribution for insights
            score_distribution = self._calculate_score_distribution(evaluated_leads)
            qualified_leads = [l for l in evaluated_leads if l['fit_score'] >= 0.7]

            # Send success callback
            await callback_service.send_callback(
                job_id=job_id,
                account_id=account_id,
                enrichment_type=self.ENRICHMENT_TYPE,
                status='completed',
                completion_percentage=100,
                processed_data={
                    'total_leads': len(evaluated_leads),
                    'qualified_leads': len(qualified_leads),
                    'score_distribution': score_distribution
                }
            )

            return {
                "status": "completed",
                "job_id": job_id,
                "account_id": account_id,
                "total_leads_found": len(evaluated_leads),
                "qualified_leads": len(qualified_leads),
                "score_distribution": score_distribution
            }

        except Exception as e:
            logger.error(f"Lead identification failed for job {job_id}: {str(e)}", exc_info=True)
            error_details = {
                'error_type': type(e).__name__,
                'message': str(e),
                'stage': current_stage,
                'retryable': True
            }

            # Store error state
            await self._store_error_state(job_id, account_id, error_details)

            # Send failure callback
            await callback_service.send_callback(
                job_id=job_id,
                account_id=account_id,
                enrichment_type=self.ENRICHMENT_TYPE,
                status='failed',
                error_details=error_details,
                processed_data={'stage': current_stage}
            )

            return {
                "status": "failed",
                "job_id": job_id,
                "account_id": account_id,
                "error": str(e),
                "stage": current_stage
            }


    def generate_role_search_pattern(self, persona_roles: Dict[str, Union[List[str], str]]) -> str:
        """
        Generate a regex pattern for role search based on persona role titles.

        Args:
            persona_roles: Dictionary of persona types and their role titles
                Example: {"buyer": ["Senior Product Manager"], "influencer": ["Tech Lead"]}

        Returns:
            str: A regex pattern matching various forms of the role titles
        """
        # Extract role titles excluding end_user
        all_roles = []
        for persona_type, titles in persona_roles.items():
            if persona_type != 'end_user':  # Skip end_user profiles
                if isinstance(titles, list):
                    all_roles.extend(titles)
                elif isinstance(titles, str):
                    all_roles.append(titles)

        # Clean and prepare roles for regex with built-in variations
        regex_patterns = []
        for role in all_roles:
            # Convert role to lowercase for case-insensitive matching
            role = role.lower()

            # Replace common variations using regex
            # 1. Make spaces optional between words
            # 2. Make hyphens optional and interchangeable with spaces
            role_pattern = role.replace(' ', r'[\s-]?')

            # Handle common prefix/suffix variations
            role_pattern = (
                role_pattern
                .replace('senior', r'(senior|sr\.?)')
                .replace('vice president', r'(vice[\s-]?president|vp)')
                .replace('president', r'(president|pres\.?)')
                .replace('manager', r'(manager|mgr\.?)')
                .replace('director', r'(director|dir\.?)')
                .replace('chief', r'(chief|c)')
                .replace('officer', r'(officer|o)')
                .replace('executive', r'(executive|exec\.?)')
                .replace('engineer', r'(engineer|eng\.?)')
                .replace('development', r'(development|dev\.?)')
            )

            # Add optional common prefixes for titles
            if not any(prefix in role.lower() for prefix in ['chief', 'vp', 'vice', 'head', 'director']):
                role_pattern = f"((head|director|vp|vice[\s-]?president)[\s-]?of[\s-]?)?{role_pattern}"

            regex_patterns.append(role_pattern)

        # Join all patterns with OR operator
        return f"({'|'.join(regex_patterns)})"

    async def _fetch_employees_with_retry(self, linkedin_url: str, product_data, max_retries: int = 3) -> Tuple[List[Dict[str, Any]], int]:
        """
        Fetch employees using ProxyCurl's Employee Search endpoint with retry mechanism.
        This endpoint is more cost-effective than the full employee search.
        """
        # Generate role search pattern from product data
        role_pattern = self.generate_role_search_pattern(product_data.get('persona_role_titles', {}))

        search_params = {
            'url': linkedin_url,
            'page_size': self.PAGE_SIZE,  # Reduced page size for cost optimization
            'role_search': role_pattern,  # Regex pattern based on product personas
            'enrich_profiles': 'enrich',
        }

        for attempt in range(max_retries):
            try:
                employees_data, status_code = await cached_request(
                    cache_service=self.cache_service,
                    url="https://nubela.co/proxycurl/api/linkedin/company/employees",
                    params=search_params,
                    headers={'Authorization': f'Bearer {self.proxycurl_api_key}'},
                    ttl_hours=24
                )

                if status_code == 200:
                    # Transform the response to match the original format
                    transformed_employees = []

                    for person in employees_data.get('people', []):
                        transformed_employee = {
                            'profile_url': person.get('linkedin_url'),
                            'full_name': person.get('full_name'),
                            'first_name': person.get('first_name'),
                            'last_name': person.get('last_name'),
                            'occupation': person.get('occupation'),
                            'location': person.get('location'),
                            'company': {
                                'name': person.get('company_name'),
                                'location': person.get('company_location')
                            },
                            'education': person.get('education', []),
                            'languages': person.get('languages', []),
                            'skills': person.get('skills', [])
                        }
                        transformed_employees.append(transformed_employee)

                    return transformed_employees, status_code

                elif status_code == 429:  # Rate limit
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    continue
                else:
                    logger.error(f"ProxyCurl API error: {status_code}")
                    break

            except Exception as e:
                logger.error(f"Error fetching employees (attempt {attempt + 1}): {str(e)}")
                if attempt == max_retries - 1:
                    raise

        raise Exception(f"Failed to fetch employees after {max_retries} attempts")

    async def _extract_structured_leads(self, employee_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract structured lead information using Gemini AI."""
        try:
            if not employee_data:
                logger.warning("No employee data provided for structuring")
                return []

            structured_leads = []

            # Process in batches
            for i in range(0, len(employee_data), self.BATCH_SIZE):
                batch = employee_data[i:i + self.BATCH_SIZE]

                extraction_prompt = self.prompts.EXTRACTION_PROMPT.format(
                    employee_data=json.dumps(batch, indent=2)
                )

                response = self.model.generate_content(extraction_prompt)
                if not response or not response.parts:
                    logger.error(f"Empty response from Gemini AI for batch {i//self.BATCH_SIZE + 1}")
                    continue

                batch_data = self._parse_gemini_response(response.parts[0].text)
                structured_leads.extend(batch_data.get('structured_leads', []))

            # Validate and clean structured leads
            valid_leads = []
            for lead in structured_leads:
                if self._validate_structured_lead(lead):
                    valid_leads.append(lead)

            return valid_leads

        except Exception as e:
            logger.error(f"Error extracting structured leads: {str(e)}", exc_info=True)
            raise

    def _validate_structured_lead(self, lead: Dict[str, Any]) -> bool:
        """Validate structured lead data."""
        required_fields = ['lead_id', 'linkedin_url']
        if not all(field in lead for field in required_fields):
            return False

        # Ensure LinkedIn URL is valid
        if not lead['linkedin_url'].startswith('https://www.linkedin.com/in/'):
            return False

        return True

    def _calculate_score_distribution(self, evaluated_leads: List[Dict[str, Any]]) -> Dict[str, int]:
        """Calculate distribution of lead scores."""
        distribution = {
            'excellent': 0,  # 0.8 - 1.0
            'good': 0,      # 0.6 - 0.8
            'moderate': 0,  # 0.4 - 0.6
            'low': 0        # 0.0 - 0.4
        }

        for lead in evaluated_leads:
            score = lead.get('fit_score', 0)
            if score >= 0.8:
                distribution['excellent'] += 1
            elif score >= 0.6:
                distribution['good'] += 1
            elif score >= 0.4:
                distribution['moderate'] += 1
            else:
                distribution['low'] += 1

        return distribution

    async def _evaluate_leads(self, structured_leads: List[Dict[str, Any]], product_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Evaluate leads using Gemini AI based on product criteria."""
        try:
            evaluation_prompt = self.prompts.LEAD_EVALUATION_PROMPT.format(
                product_info=json.dumps(product_data, indent=2),
                persona_info=json.dumps(product_data.get('persona_role_titles', {}), indent=2),
                lead_data=json.dumps(structured_leads, indent=2)
            )

            response = self.model.generate_content(evaluation_prompt)
            if not response or not response.parts:
                raise ValueError("Empty response from Gemini AI")

            evaluation_data = self._parse_gemini_response(response.parts[0].text)
            return evaluation_data.get('evaluated_leads', [])

        except Exception as e:
            logger.error(f"Error evaluating leads: {str(e)}", exc_info=True)
            raise

    async def _store_results(
            self,
            job_id: str,
            account_id: str,
            tenant_id: Optional[str],
            structured_leads: List[Dict[str, Any]],
            evaluated_leads: List[Dict[str, Any]]
    ) -> None:
        """Store processed results in BigQuery."""
        await self.bq_service.insert_enrichment_raw_data(
            job_id=job_id,
            entity_id=account_id,
            source='proxycurl',
            raw_data={
                'structured_leads': structured_leads,
                'evaluated_leads': evaluated_leads
            },
            processed_data={
                'qualified_leads': [
                    lead for lead in evaluated_leads
                    if lead.get('fit_score', 0) >= 0.7
                ]
            }
        )

    def _parse_gemini_response(self, response_text: str) -> Dict[str, Any]:
        """Parse and validate Gemini AI response."""
        try:
            cleaned_text = response_text.strip()

            # Remove code block markers if present
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text[7:]
            elif cleaned_text.startswith("```"):
                cleaned_text = cleaned_text[3:]

            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3]

            cleaned_text = cleaned_text.strip()

            try:
                parsed_data = json.loads(cleaned_text)

                # Validate basic structure
                if not isinstance(parsed_data, dict):
                    raise ValueError("Parsed response is not a dictionary")

                return parsed_data

            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing error. Text: '{cleaned_text[:500]}...'")
                logger.error(f"JSON error details: {str(e)}")
                raise ValueError(f"Failed to parse Gemini response as JSON: {str(e)}")

        except Exception as e:
            logger.error(f"Error parsing Gemini response: {str(e)}", exc_info=True)
            raise

    async def _store_error_state(self, job_id: str, entity_id: str, error_details: Dict[str, Any]) -> None:
        """Store error information in BigQuery."""
        try:
            if not job_id or not entity_id:
                logger.error("Missing required fields for error state storage")
                return

            # Ensure error details are properly formatted
            formatted_error = {
                'error_type': error_details.get('error_type', 'unknown_error'),
                'message': error_details.get('message', 'Unknown error occurred'),
                'stage': error_details.get('stage', 'unknown'),
                'timestamp': datetime.utcnow().isoformat(),
                'retryable': error_details.get('retryable', True),
                'additional_info': error_details.get('additional_info', {})
            }

            logger.debug(f"Storing error state for job {job_id}, entity {entity_id}")

            await self.bq_service.insert_enrichment_raw_data(
                job_id=job_id,
                entity_id=entity_id,
                source='proxycurl',
                raw_data={},
                processed_data={},
                status='failed',
                error_details=formatted_error
            )

            logger.info(f"Successfully stored error state for job {job_id}, entity {entity_id}")

        except Exception as e:
            logger.error(
                f"Failed to store error state in BigQuery for job {job_id}, entity {entity_id}: {str(e)}",
                exc_info=True
            )