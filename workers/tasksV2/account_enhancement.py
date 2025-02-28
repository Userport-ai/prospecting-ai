import asyncio
import datetime
import json
import logging
import os
import uuid
from dataclasses import dataclass
from typing import Dict, Any, List

import requests
from prefect import task, flow

from models.builtwith import EnrichmentResult
from services.ai_service import AIServiceFactory
from services.api_cache_service import APICacheService
from services.bigquery_service import BigQueryService
from services.builtwith_service import BuiltWithService
from services.django_callback_service import CallbackService
from utils.website_parser import WebsiteParser
from utils.retry_utils import RetryableError, RetryConfig, with_retry
from tasks.enrichment_task import AccountEnrichmentTask
from utils.account_info_fetcher import AccountInfoFetcher
from utils.url_utils import UrlUtils
from models.accounts import AccountInfo, Financials

logger = logging.getLogger(__name__)


@dataclass
class PromptTemplates:
    """Store prompt templates for AI interactions."""
    LINKEDIN_EXTRACTION_PROMPT = """
    Extract the LinkedIn company URL from the search results below.
    Follow these rules strictly:
    1. Return ONLY valid JSON with a single field "linkedin_url"
    2. The URL must be a valid LinkedIn company page URL (starting with https://www.linkedin.com/company/)
    3. If no valid LinkedIn company URL is found, set the value to null
    4. Do not include any explanations or notes
    5. Ensure proper JSON formatting with quotes

    Search Results:
    {search_results}

    Expected format:
    {{
        "linkedin_url": "https://www.linkedin.com/company/example" or null
    }}
    """

    EXTRACTION_PROMPT = """
    Extract company information into a structured JSON format from the profile below.
    Also include any LinkedIn URL if provided in the digital_presence section.
    Follow these rules strictly:
    1. Return ONLY valid JSON, no extra text or markdown
    2. Do not include any explanations or notes
    3. If a field's information is not available, use null
    4. Use the exact field names and structure shown below
    5. Ensure all strings are properly quoted
    6. Arrays should never be null, use empty array [] if no data
    7. If a LinkedIn URL is found, ensure it's properly formatted and included in digital_presence.social_media

    Company Profile:
    {company_profile}

    Required JSON format:
    {{
        "company_name": {{
            "legal_name": string,
            "trading_name": string or null,
            "aliases": [string]
        }},
        "industry": {{
            "primary": string or null,
            "sectors": [string],
            "categories": [string]
        }},
        "location": {{
            "headquarters": {{
                "city": string or null,
                "state": string or null,
                "country": string or null,
                "region": string or null
            }},
            "office_locations": [
                {{
                    "city": string,
                    "country": string,
                    "type": string
                }}
            ]
        }},
        "business_metrics": {{
            "employee_count": {{
                "total": number or null,
                "range": string or null,
                "as_of_date": string or null
            }},
            "year_founded": number or null,
            "company_type": string or null
        }},
        "technology_stack": {{
            "programming_languages": [string],
            "frameworks": [string],
            "databases": [string],
            "cloud_services": [string],
            "other_tools": [string]
        }},
        "business_details": {{
            "products": [string],
            "services": [string],
            "target_markets": [string],
            "business_model": string or null,
            "revenue_streams": [string]
        }},
        "market_position": {{
            "competitors": [string],
            "partners": [string],
            "customers": [string],
            "target_industries": [string]
        }},
        "financials": {{
            "type": "public" or "private",
            "public_data": {{
                "stock_details": {{
                    "exchange": string or null,
                    "ticker": string or null,
                    "market_cap": {{
                        "value": number or null,
                        "currency": string or null,
                        "as_of_date": string or null
                    }}
                }},
                "financial_metrics": {{
                    "revenue": {{
                        "value": number or null,
                        "currency": string or null,
                        "period": string or null
                    }},
                    "net_income": {{
                        "value": number or null,
                        "currency": string or null,
                        "period": string or null
                    }}
                }}
            }},
            "private_data": {{
                "total_funding": {{
                    "amount": number or null,
                    "currency": string or null,
                    "as_of_date": string or null
                }},
                "funding_rounds": [
                    {{
                        "series": string or null,
                        "amount": number or null,
                        "currency": string or null,
                        "date": string or null,
                        "lead_investors": [string],
                        "other_investors": [string],
                        "valuation": {{
                            "amount": number or null,
                            "currency": string or null,
                            "type": string or null
                        }}
                    }}
                ]
            }}
        }},
        "recent_developments": [
            {{
                "type": string,
                "date": string or null,
                "title": string,
                "description": string
            }}
        ],
        "key_metrics": {{
            "growth": {{
                "employee_growth_rate": number or null,
                "revenue_growth_rate": number or null,
                "period": string or null
            }},
            "market_presence": {{
                "global_presence": boolean,
                "regions_served": [string],
                "languages_supported": [string]
            }}
        }},
        "compliance_and_certifications": [
            {{
                "name": string,
                "issuer": string or null,
                "valid_until": string or null
            }}
        ],
        "digital_presence": {{
            "website": string or null,
            "social_media": {{
                "linkedin": string or null,
                "twitter": string or null,
                "facebook": string or null
            }},
            "app_store_presence": {{
                "ios": boolean,
                "android": boolean,
                "ratings": {{
                    "ios_rating": number or null,
                    "android_rating": number or null
                }}
            }}
        }}
    }}"""

    ANALYSIS_PROMPT = """
Provide a direct business summary in this format:

**[Company Name]**

*Core Business:* Single sentence description of main business focus.

*Key Metrics:*
- Revenue and financial data if available
- Market position and competitive standing
- Employee count and growth metrics

*Product & Services:*
Key offerings and capabilities

*Recent Developments:*
Latest significant changes or announcements

*Market Position:*
Competitive landscape and market standing

Company Profile for analysis:
{company_profile}

Important: Start directly with the company name header. Do not include any introductory phrases like "Here's a summary" or "Let me provide".
"""


class AccountEnhancementTask(AccountEnrichmentTask):
    """Task for enhancing account data with AI-powered company information."""
    ENRICHMENT_TYPE = 'company_info'

    API_RETRY_CONFIG = RetryConfig(
        max_attempts=3,
        base_delay=1.0,
        max_delay=5.0,
        retryable_exceptions=[
            RetryableError,
            asyncio.TimeoutError,
            requests.exceptions.RequestException,
            ConnectionError
        ]
    )

    AI_RETRY_CONFIG = RetryConfig(
        max_attempts=3,
        base_delay=2.0,
        max_delay=8.0,
        retryable_exceptions=[
            RetryableError,
            ValueError,
            RuntimeError
        ]
    )

    def __init__(self, callback_service):
        """Initialize the task with required services and configurations."""
        super().__init__(callback_service)
        self._initialize_credentials()
        self.bq_service = BigQueryService()
        self._configure_ai_service()
        self.prompts = PromptTemplates()
        project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
        dataset = os.getenv('BIGQUERY_DATASET', 'userport_enrichment')
        self.cache_service = APICacheService(client=self.bq_service.client, project_id=project_id, dataset=dataset)

    def _initialize_credentials(self) -> None:
        """Initialize and validate required API credentials."""
        self.jina_api_token = os.getenv('JINA_API_TOKEN')
        self.google_api_key = os.getenv('GEMINI_API_TOKEN')

        if not self.google_api_key:
            raise ValueError("GEMINI_API_TOKEN environment variable is required")
        if not self.jina_api_token:
            raise ValueError("JINA_API_TOKEN environment variable is required")

    def _configure_ai_service(self) -> None:
        """Configure the Gemini AI service."""
        self.model = AIServiceFactory().create_service(provider="gemini")

    @property
    def enrichment_type(self) -> str:
        return self.ENRICHMENT_TYPE

    @property
    def task_name(self) -> str:
        """Get the task identifier."""
        return "account_enhancement"

    async def create_task_payload(self, **kwargs) -> Dict[str, Any]:
        """Create a standardized task payload."""
        # Check if this is a bulk request
        if 'accounts' in kwargs:
            accounts = kwargs['accounts']
            if not accounts or not isinstance(accounts, list):
                raise ValueError("'accounts' must be a non-empty list")

            for account in accounts:
                if not all(k in account for k in ['account_id', 'website']):
                    raise ValueError("Each account must have 'account_id' and and 'website'")

            return {
                "accounts": accounts,
                "job_id": str(uuid.uuid4()),
                "is_bulk": True
            }

        # Single account case
        required_fields = ['account_id', 'website']
        missing_fields = [field for field in required_fields if field not in kwargs]

        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

            return {
                "accounts": [{
                    "account_id": kwargs["account_id"],
                    "website": kwargs["website"],
                }],
                "job_id": str(uuid.uuid4()),
                "is_bulk": False
            }

    @flow
    async def execute(self, payload: Dict[str, Any]) -> (Dict[str, Any], Dict[str, Any]):
        """Execute the account enhancement task."""
        job_id = payload.get('job_id')
        accounts = payload.get('accounts', [])
        is_bulk = payload.get('is_bulk', False)
        callback_service = await CallbackService.get_instance()

        logger.info(f"Starting execution for job_id: {job_id}, is_bulk: {is_bulk}, total accounts: {len(accounts)}")

        if not accounts:
            logger.error(f"Job {job_id}: No accounts provided in payload")
            return {
                "status": "failed",
                "error": "No accounts provided",
                "job_id": job_id
            }

        results = []
        has_failures = False
        processed_count = 0
        total_accounts = len(accounts)

        callback_payload = None  # result payload to be sent back to django
        for account in accounts:
            processed_count += 1
            account_id = account.get('account_id')
            website = account.get('website')

            logger.info(f"Processing account {processed_count}/{total_accounts}: ID {account_id}, website: {website}")

            try:
                if not all([account_id, website]):
                    logger.error(f"Job {job_id}, Account {account_id}: Missing required fields")
                    error_details = {'error_type': 'validation_error', 'message': "Missing required fields"}

                    # Store error state
                    await self._store_error_state(job_id, account_id, error_details)

                    # Send validation failure callback
                    await callback_service.send_callback(
                        job_id=job_id,
                        account_id=account_id,
                        status='failed',
                        enrichment_type='company_info',
                        error_details=error_details,
                        completion_percentage=int((processed_count / total_accounts) * 100)
                    )

                    results.append({
                        "status": "failed",
                        "account_id": account_id,
                        "error": "Missing required fields"
                    })
                    has_failures = True
                    continue

                # Initial processing callback
                logger.info(f"Job {job_id}, Account {account_id}: Starting processing")
                await callback_service.send_callback(
                    job_id=job_id,
                    account_id=account_id,
                    status='processing',
                    enrichment_type='company_info',
                    completion_percentage=int((processed_count - 0.5) / total_accounts * 100)
                )

                # Fetch Basic Account information first.
                logger.debug(f"Job {job_id}, Account {account_id}: Fetching Basic Account information")
                account_info_fetcher = AccountInfoFetcher(website=website)
                account_info: AccountInfo = await account_info_fetcher.get()

                # Send intermediate callback after Basic Account information has been fetched.
                await callback_service.send_callback(
                    job_id=job_id,
                    account_id=account_id,
                    status='processing',
                    enrichment_type='company_info',
                    is_partial=True,
                    completion_percentage=int((processed_count - 0.75) / total_accounts * 100),
                    processed_data={'linkedin_url': account_info.linkedin_url} if account_info.linkedin_url else {}
                )

                # Fetch company profile
                logger.debug(f"Job {job_id}, Account {account_id}: Fetching company profile from Jina AI")
                try:
                    company_profile = await self._fetch_company_profile(account_info.name)
                except requests.exceptions.RequestException as e:
                    logger.error(f"Jina API error for company profile: {str(e)}", exc_info=True)
                    raise
                except Exception as e:
                    logger.error(f"Unexpected error fetching company profile: {str(e)}", exc_info=True)
                    raise

                # Send intermediate callback after profile fetch
                await callback_service.send_callback(
                    job_id=job_id,
                    account_id=account_id,
                    status='processing',
                    enrichment_type='company_info',
                    completion_percentage=int((processed_count - 0.25) / total_accounts * 100)
                )

                # Extract structured data
                logger.debug(f"Job {job_id}, Account {account_id}: Extracting structured data using Gemini")
                structured_data = await self._extract_structured_data(company_profile)

                # Populate some fields from structured data to account info.
                account_info.financials = Financials(**structured_data.get('financials'))
                account_info.technologies = self._extract_technologies(structured_data.get('technology_stack', {}))
                account_info.customers = structured_data.get('market_position', {}).get('customers', [])
                account_info.competitors = structured_data.get('market_position', {}).get('competitors', [])

                # Ensure LinkedIn URL is properly set in structured data
                if account_info.linkedin_url:
                    if 'digital_presence' not in structured_data:
                        structured_data['digital_presence'] = {}
                    if 'social_media' not in structured_data['digital_presence']:
                        structured_data['digital_presence']['social_media'] = {}

                    # Only update if not already present or if existing URL is invalid
                    structured_data['digital_presence']['social_media']['linkedin'] = account_info.linkedin_url
                    if not self._is_valid_linkedin_url(account_info.linkedin_url):
                        logger.warning(f"LinkedIn URL - {account_info.linkedin_url} is invalid!")

                # Generate analysis
                logger.debug(f"Job {job_id}, Account {account_id}: Generating analysis")
                analysis_text = await self._generate_analysis(company_profile)

                # Fetch customers.
                wb_parser = WebsiteParser(website=website)
                wb_customers: List[str] = await wb_parser.fetch_company_customers()
                logger.debug(f"Customers from Website for account ID {account_id} are {wb_customers}")
                # Merge customers from website parser.
                account_info.customers = list(set(account_info.customers) | set(wb_customers))

                # Fetch technologies and update account info
                technologies, tech_profile = await self._fetch_technology_stack(website=website, account_id=account_id, existing_technologies=account_info.technologies)
                account_info.technologies = technologies
                account_info.tech_profile = tech_profile

                # Process and format enrichment data
                processed_data = {
                    'company_name': account_info.name,
                    'employee_count': account_info.employee_count,
                    'industry': account_info.industries,
                    'location': account_info.formatted_hq(),
                    'website': website,
                    'linkedin_url': account_info.linkedin_url,
                    'technologies': account_info.technologies,
                    'funding_details': account_info.financials.private_data.model_dump(),
                    'company_type': account_info.organization_type,
                    'founded_year': account_info.founded_year,
                    'customers': account_info.customers,
                    'competitors': account_info.competitors,
                    'tech_profile': account_info.tech_profile.model_dump(),
                }

                # Store enrichment raw data
                logger.debug(f"Job {job_id}, Account {account_id}: Storing enrichment raw data")
                await self.bq_service.insert_enrichment_raw_data(
                    job_id=job_id,
                    entity_id=account_id,
                    source='jina_ai',
                    raw_data={
                        'jina_response': company_profile,
                        'gemini_structured': structured_data,
                        'gemini_analysis': analysis_text
                    },
                    processed_data=processed_data
                )

                # Send success callback
                logger.info(f"Job {job_id}, Account {account_id}: Processing completed successfully")
                callback_payload = {
                    'job_id': job_id,
                    'account_id': account_id,
                    'status': 'completed',
                    'enrichment_type': 'company_info',
                    'raw_data': structured_data,
                    'processed_data': processed_data,
                    'completion_percentage': int((processed_count / total_accounts) * 100)
                }

                results.append({
                    "status": "completed",
                    "account_id": account_id,
                    "company_name": account_info.name
                })

            except Exception as e:
                has_failures = True
                logger.error(f"Job {job_id}, Account {account_id}: Processing failed - {str(e)}", exc_info=True)

                error_details = {
                    'error_type': type(e).__name__,
                    'message': str(e),
                    'retryable': True
                }

                try:
                    # Store error state
                    logger.debug(f"Job {job_id}, Account {account_id}: Storing error state")
                    await self._store_error_state(job_id, account_id, error_details)

                    # Send failure callback
                    await callback_service.send_callback(
                        job_id=job_id,
                        account_id=account_id,
                        status='failed',
                        enrichment_type='company_info',
                        error_details=error_details,
                        completion_percentage=int((processed_count / total_accounts) * 100)
                    )
                except Exception as callback_error:
                    logger.error(f"Job {job_id}, Account {account_id}: Failed to send error callback - {str(callback_error)}", exc_info=True)

                results.append({
                    "status": "failed",
                    "account_id": account_id,
                    "error": str(e)
                })

        # Final status determination
        successful_accounts = len([r for r in results if r["status"] == "completed"])
        failed_accounts = len([r for r in results if r["status"] == "failed"])

        final_status = "completed" if not has_failures else "partially_completed"
        logger.info(f"Job {job_id} finished. Status: {final_status}, "
                    f"Success: {successful_accounts}, Failed: {failed_accounts}")

        return callback_payload, {
            "status": final_status,
            "job_id": job_id,
            "is_bulk": is_bulk,
            "total_accounts": total_accounts,
            "successful_accounts": successful_accounts,
            "failed_accounts": failed_accounts,
            "results": results
        }

    @task
    async def _fetch_technology_stack(self, website: str, account_id: str,
                                      existing_technologies) -> tuple[List[str], EnrichmentResult]:
        """
        Fetches technology stack from BuiltWith API and website parser if needed.
        Returns tuple of (technologies list, raw tech profile).
        """
        logger.debug(f"Fetching technology stack for account ID {account_id}")

        # Try BuiltWith first
        domain = UrlUtils.get_domain(url=website)
        builtwith_service = BuiltWithService(cache_service=self.cache_service)
        tech_profile = await builtwith_service.get_technology_profile(domain=domain)

        # Get BuiltWith technologies
        bw_technologies: List[str] = []
        if (tech_profile
                and tech_profile.processed_data.get("profile", {}).get("technologies")):
            bw_technologies = [
                str(tech["name"])
                for tech in tech_profile.processed_data["profile"]["technologies"]
                if tech.get("name")
            ]
            logger.debug(f"Technologies from Built With for account ID {account_id} are {bw_technologies}")

        # Start with BuiltWith technologies
        technologies = list(set(bw_technologies))

        # Fallback to website parser if no BuiltWith technologies found
        if not bw_technologies:
            logger.debug("No BuiltWith technologies found, attempting website parse")
            wb_parser = WebsiteParser(website=website)
            website_technologies = await wb_parser.fetch_technologies()
            website_technologies = [str(tech) for tech in website_technologies if tech]
            logger.debug(f"Technologies from Website for account ID {account_id} are {website_technologies}")
            # Merge website technologies with any existing ones
            technologies = list(set(existing_technologies) | set(website_technologies))

        return technologies, tech_profile

    @with_retry(retry_config=API_RETRY_CONFIG, operation_name="fetch_linkedin_url")
    async def _fetch_linkedin_url(self, company_name: str) -> str:
        """Fetch LinkedIn URL for a company using Jina AI and Gemini."""
        try:
            # Search specifically for LinkedIn company page
            search_query = f"{company_name} company linkedin page"
            logger.debug(f"Searching Jina AI for LinkedIn URL with query: {search_query}")

            jina_url = f"https://s.jina.ai/{search_query}"
            response = requests.get(
                jina_url,
                headers={"Authorization": f"Bearer {self.jina_api_token}"},
                timeout=10  # Add timeout to prevent hanging
            )
            response.raise_for_status()
            search_results = response.text

            if not search_results.strip():
                logger.warning(f"Empty search results from Jina AI for company: {company_name}")
                return None

            # Extract LinkedIn URL using Gemini
            extraction_prompt = self.prompts.LINKEDIN_EXTRACTION_PROMPT.format(
                search_results=search_results
            )

            try:
                logger.debug("Sending LinkedIn URL extraction prompt to Gemini")
                response = self.model.generate_content(extraction_prompt)

                if not response or not response.parts:
                    logger.warning(f"Empty response from Gemini AI for LinkedIn URL extraction: {company_name}")
                    return None

                parsed_response = self._parse_gemini_response(response.parts[0].text)
                linkedin_url = parsed_response.get("linkedin_url")

                # Validate LinkedIn URL format
                if linkedin_url and self._is_valid_linkedin_url(linkedin_url):
                    logger.info(f"Valid LinkedIn URL found for {company_name}: {linkedin_url}")
                    return linkedin_url
                else:
                    logger.warning(f"Invalid or missing LinkedIn URL format for {company_name}: {linkedin_url}")
                    return None

            except Exception as e:
                logger.error(f"Error extracting LinkedIn URL with Gemini for {company_name}: {str(e)}", exc_info=True)
                return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Jina API error while fetching LinkedIn URL for {company_name}: {str(e)}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Unexpected error while fetching LinkedIn URL for {company_name}: {str(e)}", exc_info=True)
            return None

    def _is_valid_linkedin_url(self, url: str) -> bool:
        """Validate LinkedIn company URL format."""
        if not url:
            return False

        try:
            # Basic validation of LinkedIn company URL format
            return (
                url.startswith('https://www.linkedin.com/company/') and
                len(url) > len('https://www.linkedin.com/company/') and
                ' ' not in url and
                '\n' not in url
            )
        except Exception as e:
            logger.error(f"Error validating LinkedIn URL: {str(e)}")
            return False

    @task
    @with_retry(retry_config=API_RETRY_CONFIG, operation_name="fetch_company_profile")
    async def _fetch_company_profile(self, company_name: str) -> str:
        """Fetch company profile from Jina AI."""
        search_query = f"{company_name}+company+profile"
        logger.debug(f"Searching Jina AI for company profile with query: {search_query}")

        jina_url = f"https://s.jina.ai/{search_query}"
        response = requests.get(
            jina_url,
            headers={"Authorization": f"Bearer {self.jina_api_token}"},
            timeout=30
        )
        response.raise_for_status()

        if not response.text.strip():
            raise ValueError(f"Empty response from Jina AI for company: {company_name}")

        return response.text

    @task
    @with_retry(retry_config=AI_RETRY_CONFIG, operation_name="extract_structured_data")
    async def _extract_structured_data(self, company_profile: str) -> Dict[str, Any]:
        """Extract structured data from company profile using Gemini AI."""
        try:
            logger.debug("Creating extraction prompt for structured data...")
            extraction_prompt = self.prompts.EXTRACTION_PROMPT.format(
                company_profile=company_profile
            )

            try:
                logger.debug("Sending structured data extraction prompt to Gemini...")
                response = self.model.generate_content(extraction_prompt)

                if not response or not response.parts:
                    raise ValueError("Empty response from Gemini AI for structured data extraction")

                structured_data = self._parse_gemini_response(response.parts[0].text)

                # Validate essential fields
                if not structured_data.get('company_name', {}).get('legal_name'):
                    logger.warning("Structured data missing company legal name")

                return structured_data

            except Exception as e:
                logger.error(f"Gemini API error: {str(e)}", exc_info=True)
                raise

        except Exception as e:
            logger.error(f"Error extracting structured data: {str(e)}", exc_info=True)
            raise

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

    @task
    async def _generate_analysis(self, company_profile: str) -> str:
        """Generate business analysis using Gemini AI."""
        try:
            logger.debug("Creating analysis prompt...")
            analysis_prompt = self.prompts.ANALYSIS_PROMPT.format(
                company_profile=company_profile
            )

            try:
                logger.debug("Sending analysis prompt to Gemini...")
                response = self.model.generate_content(analysis_prompt)

                if not response or not response.parts:
                    raise ValueError("Empty response from Gemini AI for analysis generation")

                analysis_text = response.parts[0].text

                if not analysis_text.strip():
                    raise ValueError("Generated analysis is empty")

                return analysis_text

            except Exception as e:
                logger.error(f"Error generating analysis with Gemini: {str(e)}", exc_info=True)
                raise

        except Exception as e:
            logger.error(f"Error generating analysis: {str(e)}", exc_info=True)
            raise

    def _format_location(self, location_data: Dict) -> str:
        """Format location from structured data"""
        hq = location_data.get('headquarters', {})
        parts = [
            hq.get('city'),
            hq.get('state'),
            hq.get('country')
        ]
        return ', '.join(filter(None, parts)) or None

    def _extract_technologies(self, tech_data: Dict) -> List[str]:
        """Extract and flatten technology information"""
        tech_lists = [
            tech_data.get('programming_languages', []),
            tech_data.get('frameworks', []),
            tech_data.get('databases', []),
            tech_data.get('cloud_services', []),
            tech_data.get('other_tools', [])
        ]
        return list(set(item for sublist in tech_lists for item in sublist if item))

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
                'timestamp': datetime.datetime.utcnow().isoformat(),
                'retryable': error_details.get('retryable', True),
                'additional_info': error_details.get('additional_info', {})
            }

            logger.debug(f"Storing error state for job {job_id}, entity {entity_id}")

            await self.bq_service.insert_enrichment_raw_data(
                job_id=job_id,
                entity_id=entity_id,
                source='jina_ai',
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
