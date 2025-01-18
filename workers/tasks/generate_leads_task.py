import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Union

import google.generativeai as genai

from services.api_cache_service import APICacheService, cached_request
from services.bigquery_service import BigQueryService
from services.django_callback_service import CallbackService
from .enrichment_task import AccountEnrichmentTask

FIT_SCORE_THRESHOLD = 0.0

logger = logging.getLogger(__name__)

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

    EXTRACTION_PROMPT = """
    Extract and structure key information about each lead from the raw employee data.
    Follow these rules strictly:
    1. Return ONLY valid JSON
    2. Include all available contact and professional details
    3. If a field is not available, use null
    4. Keep experience and education details concise
    5. Do not include any other information or pleasantries or anything else outside the JSON
    
    Employee Data:
    {employee_data}
    
    Required JSON format:
    {{
        "structured_leads": [
            {{
                "lead_id": string,
                "full_name": string,
                "first_name": string,
                "last_name": string,
                "linkedin_url": string,
                "public_identifier": string,
                "headline": string,
                "occupation": string,
                "summary": string or null,
                "recommendations": [string],
                
                "current_role": {{
                    "title": string,
                    "company": string,
                    "department": string,
                    "seniority": string,
                    "years_in_role": number or null,
                    "description": string or null,
                    "location": string or null,
                    "start_date": string or null
                }},
                
                "career_history": {{
                    "total_years_experience": number,
                    "companies_count": number,
                    "industry_exposure": [string],
                    "previous_roles": [
                        {{
                            "title": string,
                            "company": string,
                            "duration_years": number,
                            "description": string or null,
                            "start_date": string or null,
                            "end_date": string or null
                        }}
                    ]
                }},
                
                "education": [
                    {{
                        "degree": string,
                        "field_of_study": string or null,
                        "institution": string,
                        "start_date": string or null,
                        "end_date": string or null,
                        "logo_url": string or null
                    }}
                ],
                
                "professional_info": {{
                    "skills": [string],
                    "languages": [{{
                        "name": string,
                        "proficiency": string or null
                    }}],
                    "certifications": [string],
                    "volunteer_work": [string]
                }},
                
                "online_presence": {{
                    "follower_count": number or null,
                    "connection_count": number or null,
                    "profile_pic_url": string or null
                }},
                
                "location": {{
                    "city": string or null,
                    "state": string or null,
                    "country": string or null,
                    "country_full_name": string or null
                }}
            }}
        ]
    }}
    """

class GenerateLeadsTask(AccountEnrichmentTask):
    """Task for identifying potential leads for an account using ProxyCurl and AI analysis."""

    ENRICHMENT_TYPE = 'generate_leads'
    BATCH_SIZE = 2 # Batch size for Gemini processing
    PAGE_SIZE = 5 # Number of results fetched from ProxyCurl API. Note: Increasing this will bump up our cost significantly

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
                source="proxycurl",
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
                source="proxycurl",
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
                source="proxycurl",
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
            qualified_leads = [l for l in evaluated_leads if l['fit_score'] >= FIT_SCORE_THRESHOLD]

            # Send success callback
            await callback_service.send_callback(
                job_id=job_id,
                account_id=account_id,
                enrichment_type=self.ENRICHMENT_TYPE,
                source="proxycurl",
                status='completed',
                completion_percentage=100,
                processed_data={
                    'score_distribution': score_distribution,
                    'structured_leads': structured_leads,
                    'all_leads': evaluated_leads,
                    'qualified_leads': qualified_leads,
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
                source="proxycurl",
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
            if persona_type not in ['end_user', 'end_users']:  # Skip end_user profiles
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

    async def _fetch_employees_with_retry(
            self,
            linkedin_url: str,
            product_data: Dict[str, Any],
            max_retries: int = 3
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Fetch employees using ProxyCurl's Employee Search endpoint with retry mechanism.

        Args:
            linkedin_url: Company's LinkedIn URL
            product_data: Dictionary containing product and persona information
            max_retries: Maximum number of retry attempts

        Returns:
            Tuple containing list of transformed employee data and status code

        Raises:
            ValueError: If LinkedIn URL is missing or invalid
            Exception: If fetching fails after all retries
        """
        if not linkedin_url:
            raise ValueError("LinkedIn URL is required")

        # Set up search parameters
        search_params = {
            'url': linkedin_url,
            'page_size': self.PAGE_SIZE,
            'role_search': self.generate_role_search_pattern(
                product_data.get('persona_role_titles', {})
            ),
            'enrich_profiles': 'enrich'
        }

        # Attempt to fetch with retries
        for attempt in range(max_retries):
            try:
                logger.info(
                    f"Fetching employees attempt {attempt + 1}/{max_retries} "
                    f"for company: {linkedin_url}"
                )

                # Make API request
                response, status_code = await cached_request(
                    cache_service=self.cache_service,
                    url="https://nubela.co/proxycurl/api/linkedin/company/employees",
                    params=search_params,
                    headers={'Authorization': f'Bearer {self.proxycurl_api_key}'},
                    ttl_hours=24*30 # 1 month
                )

                if status_code == 200:
                    return await self._process_successful_response(response)

                elif status_code == 429:  # Rate limit
                    wait_time = min(2 ** attempt, 60)  # Cap at 60 seconds
                    logger.warning(
                        f"Rate limit exceeded. Waiting {wait_time} seconds before retry"
                    )
                    await asyncio.sleep(wait_time)
                    continue

                elif status_code == 404:
                    raise ValueError(f"Company not found: {linkedin_url}")

                else:
                    logger.error(f"ProxyCurl API error: Status {status_code}")
                    break

            except Exception as e:
                logger.error(
                    f"Error fetching employees (attempt {attempt + 1}): {str(e)}",
                    exc_info=True
                )
                if attempt == max_retries - 1:
                    raise

        raise Exception(f"Failed to fetch employees after {max_retries} attempts")

    async def _process_successful_response(
            self,
            response: Dict[str, Any]
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Process successful API response and transform employee data."""

        transformed_employees = []
        employees_data = response.get('employees', [])
        total_employees = len(employees_data)

        logger.info(f"Processing {total_employees} employees")

        for employee in employees_data:
            try:
                transformed = await self._transform_employee_data(
                    employee,
                    response.get('next_page')
                )
                if transformed:
                    transformed_employees.append(transformed)

            except Exception as e:
                logger.error(f"Error transforming employee data: {str(e)}", exc_info=True)
                continue

        logger.info(
            f"Successfully transformed {len(transformed_employees)}/{total_employees} "
            "employee profiles"
        )
        return transformed_employees, 200


    async def _transform_employee_data(
            self,
            employee: Dict[str, Any],
            next_page_url: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Transform individual employee data with safe handling of missing fields.
        Returns None if critical data is missing, partial data if some fields are missing.
        """
        try:
            # Get profile data with fallback to empty dict
            profile = employee.get('profile', {})

            # Check only absolutely critical fields
            # We only require profile_url as it's our unique identifier
            if not employee.get('profile_url'):
                logger.warning("Skipping employee with missing profile URL")
                return None

            # Get current experience
            experiences = profile.get('experiences', [])
            current_experience = {}

            try:
                current_experience = next(
                    (exp for exp in experiences
                     if exp.get('company') == 'Zuddl' and not exp.get('ends_at')),
                    {}
                )
            except Exception as e:
                logger.warning(f"Error finding current experience: {str(e)}")

            # Build location string
            location_parts = []
            if profile.get('city'):
                location_parts.append(profile.get('city'))
            if profile.get('state'):
                location_parts.append(profile.get('state'))
            if profile.get('country_full_name'):
                location_parts.append(profile.get('country_full_name'))

            location = ', '.join(location_parts) if location_parts else None

            # Build base profile with required and optional fields
            transformed = {
                # Core fields - use safe defaults
                'profile_url': employee.get('profile_url'),
                'last_updated': employee.get('last_updated'),
                'data_source': 'proxycurl',
                'fetch_timestamp': datetime.utcnow().isoformat(),

                # Basic profile - all optional
                'full_name': profile.get('full_name'),
                'first_name': profile.get('first_name'),
                'last_name': profile.get('last_name'),
                'headline': profile.get('headline'),
                'occupation': profile.get('occupation'),

                # Location - all optional
                'location': location,
                'country': profile.get('country'),
                'country_full_name': profile.get('country_full_name'),
                'city': profile.get('city'),
                'state': profile.get('state'),

                # Network stats - optional with safe defaults
                'follower_count': profile.get('follower_count', 0),
                'connection_count': profile.get('connections', 0)
            }

            # Add current role if available
            if current_experience:
                transformed['current_role'] = {
                    'company': current_experience.get('company'),
                    'title': current_experience.get('title'),
                    'description': current_experience.get('description'),
                    'location': current_experience.get('location'),
                    'start_date': current_experience.get('starts_at'),
                    'company_linkedin_url': current_experience.get('company_linkedin_profile_url'),
                    'company_facebook_url': current_experience.get('company_facebook_profile_url'),
                    'logo_url': current_experience.get('logo_url')
                }

            # Add education if available
            education = profile.get('education', [])
            if education:
                transformed['education'] = []
                for edu in education:
                    if edu:  # Check if education entry is not None
                        edu_entry = {
                            'school': edu.get('school'),
                            'degree': edu.get('degree_name'),
                            'field': edu.get('field_of_study')
                        }

                        # Optional education fields
                        if edu.get('starts_at'):
                            edu_entry['start_date'] = edu.get('starts_at')
                        if edu.get('ends_at'):
                            edu_entry['end_date'] = edu.get('ends_at')
                        if edu.get('description'):
                            edu_entry['description'] = edu.get('description')
                        if edu.get('activities_and_societies'):
                            edu_entry['activities'] = edu.get('activities_and_societies')
                        if edu.get('grade'):
                            edu_entry['grade'] = edu.get('grade')
                        if edu.get('school_linkedin_profile_url'):
                            edu_entry['school_linkedin_url'] = edu.get('school_linkedin_profile_url')

                        transformed['education'].append(edu_entry)

            # Add experience history if available
            experiences = profile.get('experiences', [])
            if experiences:
                transformed['experience_history'] = []
                for exp in experiences:
                    if exp:  # Check if experience entry is not None
                        exp_entry = {
                            'company': exp.get('company'),
                            'title': exp.get('title')
                        }

                        # Optional experience fields
                        if exp.get('description'):
                            exp_entry['description'] = exp.get('description')
                        if exp.get('location'):
                            exp_entry['location'] = exp.get('location')
                        if exp.get('starts_at'):
                            exp_entry['start_date'] = exp.get('starts_at')
                        if exp.get('ends_at'):
                            exp_entry['end_date'] = exp.get('ends_at')
                        if exp.get('company_linkedin_profile_url'):
                            exp_entry['company_linkedin_url'] = exp.get('company_linkedin_profile_url')

                        transformed['experience_history'].append(exp_entry)

            # Add skills and languages if available
            if profile.get('skills'):
                transformed['skills'] = profile.get('skills', [])

            if profile.get('languages'):
                transformed['languages'] = profile.get('languages', [])

            if profile.get('languages_and_proficiencies'):
                transformed['languages_and_proficiencies'] = [
                    {
                        'name': lang.get('name'),
                        'proficiency': lang.get('proficiency')
                    }
                    for lang in profile.get('languages_and_proficiencies', [])
                    if lang and lang.get('name')  # Only include if name exists
                ]

            # Add optional profile content if available
            if profile.get('summary'):
                transformed['summary'] = profile.get('summary')

            if profile.get('articles'):
                transformed['articles'] = profile.get('articles', [])

            if profile.get('activities'):
                transformed['activities'] = profile.get('activities', [])

            if profile.get('volunteer_work'):
                transformed['volunteer_work'] = profile.get('volunteer_work', [])

            # Add accomplishments if any exist
            accomplishments = {}
            for acc_type in [
                'courses', 'honors_awards', 'organisations', 'patents',
                'projects', 'publications', 'test_scores'
            ]:
                key = f'accomplishment_{acc_type}'
                if profile.get(key):
                    accomplishments[acc_type] = profile.get(key, [])

            if accomplishments:
                transformed['accomplishments'] = accomplishments

            # Add other optional sections if they exist
            if profile.get('certifications'):
                transformed['certifications'] = profile.get('certifications', [])

            if profile.get('recommendations'):
                transformed['recommendations'] = profile.get('recommendations', [])

            if profile.get('groups'):
                transformed['groups'] = [
                    {
                        'name': group.get('name'),
                        'url': group.get('url'),
                        'profile_pic_url': group.get('profile_pic_url')
                    }
                    for group in profile.get('groups', [])
                    if group and group.get('name')  # Only include if name exists
                ]

            # Add profile media if available
            if profile.get('profile_pic_url'):
                transformed['profile_pic_url'] = profile.get('profile_pic_url')

            if profile.get('background_cover_image_url'):
                transformed['background_cover_image_url'] = profile.get('background_cover_image_url')

            if profile.get('public_identifier'):
                transformed['public_identifier'] = profile.get('public_identifier')

            # Add pagination info if available
            if next_page_url:
                transformed['next_page_url'] = next_page_url

            return transformed

        except Exception as e:
            logger.error(f"Error transforming employee data: {str(e)}", exc_info=True)

            # Return basic profile if possible
            try:
                return {
                    'profile_url': employee.get('profile_url'),
                    'full_name': profile.get('full_name'),
                    'fetch_timestamp': datetime.utcnow().isoformat(),
                    'data_source': 'proxycurl',
                    'error': str(e)
                }
            except:
                logger.error("Could not create basic profile", exc_info=True)
                return None

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
            if not structured_leads:
                logger.warning("No structured leads provided for evaluation")
                return []

            # Process leads in batches to avoid token limits
            evaluated_leads = []
            batch_size = self.BATCH_SIZE

            for i in range(0, len(structured_leads), batch_size):
                batch = structured_leads[i:i + batch_size]

                evaluation_prompt = self.prompts.LEAD_EVALUATION_PROMPT.format(
                    product_info=json.dumps(product_data, indent=2),
                    persona_info=json.dumps(product_data.get('persona_role_titles', {}), indent=2),
                    lead_data=json.dumps(batch, indent=2)
                )

                response = self.model.generate_content(evaluation_prompt)
                if not response or not response.parts:
                    logger.error(f"Empty response from Gemini AI for batch {i//batch_size + 1}")
                    continue

                try:
                    batch_results = self._parse_gemini_response(response.parts[0].text)
                    if batch_results and 'evaluated_leads' in batch_results:
                        evaluated_leads.extend(batch_results['evaluated_leads'])
                    else:
                        logger.error(f"Invalid response structure for batch {i//batch_size + 1}")

                except ValueError as e:
                    logger.error(f"Error parsing batch {i//batch_size + 1}: {str(e)}")
                    continue

            # Validate and normalize scores
            for lead in evaluated_leads:
                lead['fit_score'] = max(0.0, min(1.0, float(lead.get('fit_score', 0))))

            return evaluated_leads

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
                    if lead.get('fit_score', 0) >= FIT_SCORE_THRESHOLD
                ]
            }
        )

    def _parse_gemini_response(self, response_text: str) -> Dict[str, Any]:
        """Parse and validate Gemini AI response."""
        logger.debug(f"Parsing Gemini response: {response_text}")
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