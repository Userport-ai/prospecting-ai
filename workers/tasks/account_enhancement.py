import asyncio
import datetime
import json
import os
import uuid
from dataclasses import dataclass
from typing import Dict, Any, List, Optional

import httpx
import requests

from models.accounts import AccountInfo, Financials
from models.builtwith import EnrichmentResult
from services.ai.ai_service import AIServiceFactory, AIService
from services.ai.ai_service_base import ThinkingBudget
from services.ai.api_cache_service import APICacheService
from services.bigquery_service import BigQueryService
from services.builtwith_service import BuiltWithService
from services.django_callback_service import CallbackService
from services.ai_market_intel_service import AICompanyIntelService
from utils.account_info_fetcher import AccountInfoFetcher
from utils.connection_pool import ConnectionPool
from utils.loguru_setup import logger, set_trace_context
from utils.retry_utils import RetryableError, RetryConfig, with_retry
from utils.url_utils import UrlUtils
from utils.website_parser import WebsiteParser
from .enrichment_task import AccountEnrichmentTask


# Removed direct google.genai import as factory handles it


@dataclass
class PromptTemplates:
    """Store prompt templates for AI interactions."""
    # Keep prompts as they are used by the methods calling the AI service
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
        self.openai_service = None
        self.gemini_service = None
        self._initialize_credentials()  # Keep credential checks for env vars needed by factory/services
        self.bq_service = BigQueryService()
        # Initialize the AI Service Factory
        self.ai_factory = AIServiceFactory()
        self.prompts = PromptTemplates()
        project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
        dataset = os.getenv('BIGQUERY_DATASET', 'userport_enrichment')
        self.pool = ConnectionPool(
            limits=httpx.Limits(
                max_keepalive_connections=15,
                max_connections=20,
                keepalive_expiry=150.0
            ),
            timeout=300.0
        )
        self.cache_service = APICacheService(self.bq_service.client, project_id=project_id, dataset=dataset, connection_pool=self.pool)

    def _initialize_credentials(self) -> None:
        """Initialize and validate required API credentials from environment variables."""
        self.jina_api_token = os.getenv('JINA_API_TOKEN')
        # Check for tokens needed by the services within the factory
        gemini_token = os.getenv('GEMINI_API_TOKEN')
        openai_token = os.getenv('OPENAI_API_KEY')

        if not gemini_token:
            logger.warning("GEMINI_API_TOKEN environment variable not set. Gemini functionality might fail.")
        if not openai_token:
            logger.warning("OPENAI_API_KEY environment variable not set. OpenAI functionality might fail.")
        if not self.jina_api_token:
            raise ValueError("JINA_API_TOKEN environment variable is required")
        # Add checks for GOOGLE_CLOUD_PROJECT and BIGQUERY_DATASET if not handled by factory init
        if not os.getenv('GOOGLE_CLOUD_PROJECT'):
            raise ValueError("GOOGLE_CLOUD_PROJECT environment variable is required for AI Service Factory caching.")

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
                    raise ValueError("Each account must have 'account_id' and 'website'")  # Corrected typo

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

    async def execute(self, payload: Dict[str, Any]) -> (Optional[Dict[str, Any]], Dict[str, Any]):
        """Execute the account enhancement task."""
        job_id = payload.get('job_id')
        accounts = payload.get('accounts') or []
        is_bulk = payload.get('is_bulk', False)
        callback_service = await CallbackService.get_instance()

        logger.info(f"Starting execution for job_id: {job_id}, is_bulk: {is_bulk}, total accounts: {len(accounts)}")

        if not accounts:
            logger.error(f"Job {job_id}: No accounts provided in payload")
            # Return structure: (callback_payload, final_status_payload)
            return None, {
                "status": "failed",
                "error": "No accounts provided",
                "job_id": job_id,
                "results": []
            }

        results = []
        final_callback_payload = None  # Store the last successful callback payload
        has_failures = False
        processed_count = 0
        total_accounts = len(accounts)

        self.gemini_service = self.ai_factory.create_service(provider="gemini", model_name="gemini-2.5-pro-preview-03-25",
                                                             default_temperature=0.1, thinking_budget=ThinkingBudget.HIGH)
        # self.openai_service = self.ai_factory.create_service(provider="openai", model_name="gpt-4o",
        #                                                      default_temperature=0.1)

        for account in accounts:
            processed_count += 1
            account_id = account.get('account_id')
            website = account.get('website')
            current_account_callback_payload = None  # Payload for this specific account

            # Update account_id for logging context
            set_trace_context(account_id=account_id)

            logger.info(f"Processing account {processed_count}/{total_accounts}: ID {account_id}, website: {website}")

            try:
                if not all([account_id, website]):
                    logger.error(f"Job {job_id}, Account {account_id}: Missing required fields")
                    error_details = {'error_type': 'validation_error', 'message': "Missing required fields"}
                    await self._handle_failure(job_id, account_id, error_details, results, callback_service,
                                               processed_count, total_accounts)
                    has_failures = True
                    continue

                # --- Start Processing ---
                logger.info(f"Job {job_id}, Account {account_id}: Starting processing")
                await callback_service.send_callback(
                    job_id=job_id, account_id=account_id, status='processing', enrichment_type='company_info',
                    completion_percentage=int((processed_count - 0.9) / total_accounts * 100)  # Start progress early
                )

                # --- Fetch Basic Account Info ---
                logger.debug(f"Job {job_id}, Account {account_id}: Fetching Basic Account information")
                account_info_fetcher = AccountInfoFetcher(website=website)
                account_info: AccountInfo = await account_info_fetcher.get_v2()
                await callback_service.send_callback(
                    job_id=job_id, account_id=account_id, status='processing', enrichment_type='company_info',
                    is_partial=True, completion_percentage=int((processed_count - 0.8) / total_accounts * 100),
                    processed_data={'linkedin_url': account_info.linkedin_url} if account_info.linkedin_url else {}
                )

                # --- Fetch Jina AI Profile ---
                logger.debug(
                    f"Job {job_id}, Account {account_id}: Fetching company profile from Jina AI for: {account_info.name}")
                company_profile = await self._fetch_company_profile(account_info.name)
                await callback_service.send_callback(
                    job_id=job_id, account_id=account_id, status='processing', enrichment_type='company_info',
                    completion_percentage=int((processed_count - 0.7) / total_accounts * 100)
                )

                # --- Extract Structured Data (Gemini) ---
                logger.debug(f"Job {job_id}, Account {account_id}: Extracting structured data using Gemini")
                # Pass the service instance created outside the loop
                structured_data = await self._extract_structured_data(company_profile, self.gemini_service)
                await callback_service.send_callback(
                    job_id=job_id, account_id=account_id, status='processing', enrichment_type='company_info',
                    completion_percentage=int((processed_count - 0.5) / total_accounts * 100)
                )

                # --- Populate Account Info from Structured Data ---
                account_info.financials = Financials(**structured_data.get('financials')) if structured_data.get('financials') else None
                account_info.technologies = self._extract_technologies(structured_data.get('technology_stack') or {})
                account_info.customers = (structured_data.get('market_position') or {}).get('customers') or []
                account_info.competitors = (structured_data.get('market_position') or {}).get('competitors') or []
                if account_info.linkedin_url:  # Ensure LinkedIn URL from fetcher is added
                    if 'digital_presence' not in structured_data:
                        structured_data['digital_presence'] = {}
                    if 'social_media' not in structured_data['digital_presence']:
                        structured_data['digital_presence'][
                            'social_media'] = {}
                    structured_data['digital_presence']['social_media']['linkedin'] = account_info.linkedin_url
                    if not self._is_valid_linkedin_url(account_info.linkedin_url):
                        logger.warning(f"LinkedIn URL - {account_info.linkedin_url} is invalid!")

                # --- Generate Analysis (Gemini) ---
                logger.debug(f"Job {job_id}, Account {account_id}: Generating analysis using Gemini")
                # Pass the service instance created outside the loop
                analysis_text = await self._generate_analysis(company_profile, self.gemini_service)
                await callback_service.send_callback(
                    job_id=job_id, account_id=account_id, status='processing', enrichment_type='company_info',
                    completion_percentage=int((processed_count - 0.4) / total_accounts * 100)
                )

                # --- Fetch Website Customers ---
                wb_parser = WebsiteParser(website=website)
                wb_customers: List[str] = await wb_parser.fetch_company_customers()
                logger.debug(f"Customers from Website for account ID {account_id} are {wb_customers}")
                account_info.customers = list(set(account_info.customers) | set(wb_customers))

                # --- Fetch Technology Stack (BuiltWith/Website) ---
                technologies, tech_profile = await self._fetch_technology_stack(website=website, account_id=account_id, existing_technologies=account_info.technologies)
                account_info.technologies = technologies
                account_info.tech_profile = tech_profile
                await callback_service.send_callback(
                    job_id=job_id, account_id=account_id, status='processing', enrichment_type='company_info',
                    completion_percentage=int((processed_count - 0.2) / total_accounts * 100)
                )

                # --- Fetch Market Intelligence (OpenAI Search) ---
                logger.debug(f"Job {job_id}, Account {account_id}: Fetching market intelligence using OpenAI")
                # Pass the service instance created outside the loop
                intelligence_data = await self._fetch_market_intelligence(website, self.gemini_service)
                account_info.competitors = self._merge_lists(intelligence_data.get("competitors", []),
                                                             account_info.competitors)
                account_info.customers = self._merge_lists(intelligence_data.get("customers", []),
                                                           account_info.customers)
                recent_events = intelligence_data.get("recent_events", [])
                logger.debug(
                    f"Job {job_id}, Account {account_id}: Updated competitors ({len(account_info.competitors)}), customers ({len(account_info.customers)})")

                # --- Prepare Final Processed Data ---
                processed_data = {
                    'company_name': account_info.name,
                    'employee_count': account_info.employee_count,
                    'industry': account_info.industries,
                    'location': account_info.formatted_hq(),
                    'website': website,
                    'linkedin_url': account_info.linkedin_url,
                    'technologies': account_info.technologies,
                    'funding_details': account_info.financials.private_data.model_dump(
                        mode='json') if account_info.financials and account_info.financials.private_data else {},
                    'company_type': account_info.organization_type,
                    'founded_year': account_info.founded_year,
                    'customers': account_info.customers,
                    'competitors': account_info.competitors,
                    'tech_profile': account_info.tech_profile.model_dump() if hasattr(account_info.tech_profile, 'model_dump') else (account_info.tech_profile.processed_data if account_info.tech_profile else {}),
                    # Use processed data from EnrichmentResult
                    'recent_events': recent_events,  # Add recent events
                    'analysis_summary': analysis_text  # Add analysis summary
                }

                # --- Store Raw Data (Consolidated) ---
                raw_bq_data = {
                    'jina_response': company_profile,
                    'gemini_structured': structured_data,
                    'gemini_analysis': analysis_text,
                    # Store the raw intelligence data which might contain citations etc.
                    'openai_intelligence': intelligence_data.get("raw_intelligence", {})
                }
                logger.debug(f"Job {job_id}, Account {account_id}: Storing final enrichment data")
                await self.bq_service.insert_enrichment_raw_data(
                    job_id=job_id,
                    entity_id=account_id,
                    source='jina_ai_gemini_openai',  # Combined source
                    raw_data=raw_bq_data,
                    processed_data=processed_data,
                    status='completed'  # Mark as completed here
                )

                # --- Send Final Success Callback for this Account ---
                logger.info(f"Job {job_id}, Account {account_id}: Processing completed successfully")
                current_account_callback_payload = {
                    'job_id': job_id,
                    'account_id': account_id,
                    'status': 'completed',
                    'enrichment_type': 'company_info',
                    'raw_data': raw_bq_data,  # Send combined raw data
                    'processed_data': processed_data,
                    'completion_percentage': int((processed_count / total_accounts) * 100)
                }
                await callback_service.send_callback(**current_account_callback_payload)

                results.append({
                    "status": "completed",
                    "account_id": account_id,
                    "company_name": account_info.name
                })
                final_callback_payload = current_account_callback_payload  # Store last success

            except Exception as e:
                has_failures = True
                logger.error(f"Job {job_id}, Account {account_id}: Processing failed - {type(e).__name__}: {str(e)}",
                             exc_info=True)
                error_details = {
                    'error_type': type(e).__name__,
                    'message': str(e),
                    # Check if the exception is marked as retryable by the service's retry config
                    'retryable': isinstance(e, RetryableError)  # Or check against known retryable exceptions if needed
                }
                # Use helper to handle failure logging, BQ storing, and callback
                await self._handle_failure(job_id, account_id, error_details, results, callback_service,
                                           processed_count, total_accounts)

        # --- Final Job Status Determination ---
        successful_accounts = sum(1 for r in results if r["status"] == "completed")
        failed_accounts = total_accounts - successful_accounts

        if total_accounts == 0:
            final_status = "failed"  # Handle empty account list case
        elif has_failures:
            # If there are any failures but some accounts succeeded, use partially_completed
            if successful_accounts > 0:
                final_status = "partially_completed"
            else:
                # All accounts failed, mark as failed
                final_status = "failed"
        else:
            # No failures, mark as completed (same as original code)
            final_status = "completed"

        logger.info(f"Job {job_id} finished. Status: {final_status}, "
                    f"Total: {total_accounts}, Success: {successful_accounts}, Failed: {failed_accounts}")

        # Prepare final status payload
        final_status_payload = {
            "status": final_status,
            "job_id": job_id,
            "is_bulk": is_bulk,
            "total_accounts": total_accounts,
            "successful_accounts": successful_accounts,
            "failed_accounts": failed_accounts,
            "results": results
        }

        return final_callback_payload, final_status_payload

    async def _handle_failure(self, job_id: str, account_id: str, error_details: Dict, results: List,
                              callback_service: CallbackService, processed_count: int, total_accounts: int):
        """Helper function to handle account processing failures."""
        try:
            # Store error state in BigQuery
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
                # Mark completion % at failure point
            )
        except Exception as callback_error:
            logger.error(
                f"Job {job_id}, Account {account_id}: Failed to send error callback/store state - {str(callback_error)}",
                exc_info=True)

        results.append({
            "status": "failed",
            "account_id": account_id,
            "error": error_details.get('message', 'Unknown error')
        })

    async def _fetch_technology_stack(self, website: str, account_id: str,
                                      existing_technologies: List[str]) -> tuple[List[str], Optional[EnrichmentResult]]:
        """
        Fetches technology stack from BuiltWith API and website parser if needed.
        Returns tuple of (technologies list, raw tech profile EnrichmentResult or None).
        """
        logger.debug(f"Fetching technology stack for account ID {account_id}")
        tech_profile_result: Optional[EnrichmentResult] = None
        technologies: List[str] = list(set(existing_technologies))  # Start with technologies from structured data

        try:
            # Try BuiltWith first
            domain = UrlUtils.get_domain(url=website)
            if domain:
                builtwith_service = BuiltWithService(cache_service=self.cache_service)
                tech_profile_result = await builtwith_service.get_technology_profile(domain=domain)

                # Get BuiltWith technologies if available
                bw_technologies: List[str] = []
                if (tech_profile_result
                        and tech_profile_result.processed_data  # Check if processed_data is not None
                        and (tech_profile_result.processed_data.get("profile") or {}).get("technologies")):
                    bw_technologies = [
                        str(tech["name"])
                        for tech in tech_profile_result.processed_data["profile"]["technologies"]
                        if tech.get("name")
                    ]
                    logger.debug(f"Technologies from Built With for account ID {account_id} are {bw_technologies}")
                    # Merge BuiltWith technologies
                    technologies = list(set(technologies) | set(bw_technologies))
            else:
                logger.warning(f"Could not extract domain from website: {website} for BuiltWith lookup.")

        except Exception as e:
            logger.warning(f"BuiltWith lookup failed for {website}: {str(e)}", exc_info=True)
            tech_profile_result = None  # Ensure result is None on failure

        # Fallback to website parser if BuiltWith failed or found nothing substantial
        # (Define 'substantial' - e.g., less than 3 techs found by BuiltWith?)
        should_parse_website = not technologies or len(technologies) < 3

        if should_parse_website:
            logger.debug("Attempting website parse for technologies (BuiltWith insufficient or failed)")
            try:
                wb_parser = WebsiteParser(website=website)
                website_technologies = await wb_parser.fetch_technologies()
                website_technologies = [str(tech) for tech in website_technologies if tech]
                logger.debug(f"Technologies from Website for account ID {account_id} are {website_technologies}")
                # Merge website technologies
                technologies = list(set(technologies) | set(website_technologies))
            except Exception as e:
                logger.warning(f"Website technology parsing failed for {website}: {str(e)}", exc_info=True)

        return list(set(technologies)), tech_profile_result  # Return unique list and the BW result

    def _is_valid_linkedin_url(self, url: Optional[str]) -> bool:
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
            logger.error(f"Error validating LinkedIn URL '{url}': {str(e)}")
            return False

    @with_retry(retry_config=API_RETRY_CONFIG, operation_name="fetch_company_profile")
    async def _fetch_company_profile(self, company_name: str) -> str:
        """Fetch company profile from Jina AI."""
        if not company_name:
            raise ValueError("Company name cannot be empty for Jina AI search.")
        search_query = f"{company_name} company overview business profile"
        logger.debug(f"Searching Jina AI for company profile with query: {search_query}")

        jina_url = f"https://s.jina.ai/{requests.utils.quote(search_query)}"  # URL encode query
        response = requests.get(
            jina_url,
            headers={
                "Authorization": f"Bearer {self.jina_api_token}",
                "Accept": "text/plain"  # Prefer plain text
            },
            timeout=45  # Increased timeout
        )
        response.raise_for_status()

        profile_text = response.text.strip()
        if not profile_text:
            raise ValueError(f"Empty response from Jina AI for company: {company_name}")
        if len(profile_text) < 100:  # Check for very short, potentially useless responses
            logger.warning(f"Jina AI response for {company_name} seems short: {profile_text[:100]}...")

        return profile_text

    @with_retry(retry_config=AI_RETRY_CONFIG, operation_name="extract_structured_data")
    async def _extract_structured_data(self, company_profile: str, gemini_service: AIService) -> Dict[str, Any]:
        """Extract structured data from company profile using the Gemini AI service."""
        try:
            logger.debug("Creating extraction prompt for structured data...")
            extraction_prompt = self.prompts.EXTRACTION_PROMPT.format(
                company_profile=company_profile
            )

            logger.debug("Sending structured data extraction prompt to Gemini Service...")
            # Use the factory-created service instance
            # is_json=True tells the service to expect/parse JSON
            structured_data_response = await gemini_service.generate_content(
                extraction_prompt,
                is_json=True,
                operation_tag="structured_data_extraction"
            )

            # --- MODIFICATION START ---
            # Handle case where Gemini returns a list containing the dictionary
            structured_data: Optional[Dict[str, Any]] = None

            if isinstance(structured_data_response, list):
                if len(structured_data_response) > 0 and isinstance(structured_data_response[0], dict):
                    # If it's a non-empty list and the first item is a dict, extract it
                    structured_data = structured_data_response[0]
                    logger.debug("Received list from Gemini service, extracted first dictionary element.")
                else:
                    logger.warning(f"Gemini service returned a list, but it's empty or doesn't contain a dictionary: {structured_data_response}")
            elif isinstance(structured_data_response, dict):
                # If it's already a dictionary, use it directly
                structured_data = structured_data_response
            else:
                logger.error(f"Gemini service returned unexpected type for structured data extraction. Got: {type(structured_data_response)}")

            # Check if we successfully obtained a dictionary
            if structured_data is None:
                raise ValueError("Failed to extract a valid dictionary from AI service response.")
            # --- MODIFICATION END ---

            # Validate essential fields (optional but recommended)
            if not (structured_data.get('company_name') or {}).get('legal_name'):
                logger.warning("Structured data extraction missing company legal name")
            if not structured_data.get('location'):
                logger.warning("Structured data extraction missing location info")

            # Add post-processing or validation if necessary
            return structured_data

        except Exception as e:
            logger.error(f"Error extracting structured data via AI Service: {str(e)}", exc_info=True)
            # Re-raise to be caught by the main execute loop handler
            raise

    async def _fetch_market_intelligence(self, website: str, ai_service: AIService) -> Dict[str, Any]:
        """
        Fetch market intelligence including competitors and customers using OpenAI Search service.
        """
        try:
            # Assume OpenAISearchService wraps the factory-created openai_service
            intelligence_service = AICompanyIntelService(ai_service)

            logger.debug(f"Fetching market intelligence for website: {website}")

            # Call the wrapper service method (assuming it uses generate_structured_search_content internally)
            intelligence_data = await intelligence_service.fetch_company_intelligence(website)

            # Extract structured data using the wrapper service's methods
            competitors = intelligence_service.extract_competitor_names(intelligence_data)
            customers = intelligence_service.extract_customer_names(intelligence_data)
            recent_events = intelligence_service.extract_recent_events(intelligence_data)
            # citations = intelligence_service.extract_citations(intelligence_data) # Citations might be inside raw_intelligence

            logger.debug(f"Found {len(competitors)} competitors and {len(customers)} customers via OpenAI Search")

            return {
                "competitors": competitors,
                "customers": customers,
                "recent_events": recent_events,
                # Pass the raw response which might contain citations etc.
                "raw_intelligence": intelligence_data
            }
        except Exception as e:
            logger.error(f"Error fetching market intelligence via OpenAI Service: {str(e)}", exc_info=True)
            # Return empty data rather than failing the entire enrichment
            return {
                "competitors": [],
                "customers": [],
                "recent_events": [],
                "raw_intelligence": {"error": f"Failed to fetch market intelligence: {str(e)}"}
            }

    @with_retry(retry_config=AI_RETRY_CONFIG, operation_name="generate_analysis")
    async def _generate_analysis(self, company_profile: str, gemini_service: AIService) -> str:
        """Generate business analysis using the Gemini AI service."""
        try:
            logger.debug("Creating analysis prompt...")
            analysis_prompt = self.prompts.ANALYSIS_PROMPT.format(
                company_profile=company_profile
            )

            logger.debug("Sending analysis prompt to Gemini Service...")
            # Use the factory-created service instance
            # is_json=False tells the service to return raw text
            analysis_text = await gemini_service.generate_content(
                analysis_prompt,
                is_json=False,
                operation_tag="business_analysis",
            )

            if not isinstance(analysis_text, str) or not analysis_text.strip():
                logger.warning("Generated analysis is empty or not a string.")
                # Return a placeholder or raise an error? For now, return placeholder.
                return "Analysis could not be generated."

            return analysis_text.strip()

        except Exception as e:
            logger.error(f"Error generating analysis via AI Service: {str(e)}", exc_info=True)
            # Re-raise to be caught by the main execute loop handler
            raise

    def _format_location(self, location_data: Optional[Dict]) -> Optional[str]:
        """Format location from structured data"""
        if not location_data:
            return None
        hq = location_data.get('headquarters') or {}
        parts = [
            hq.get('city'),
            hq.get('state'),
            hq.get('country')
        ]
        # Filter out None or empty strings and join
        formatted = ', '.join(filter(bool, parts))
        return formatted or None

    def _extract_technologies(self, tech_data: Optional[Dict]) -> List[str]:
        """Extract and flatten technology information"""
        if not tech_data:
            return []
        tech_lists = [
            tech_data.get('programming_languages') or [],
            tech_data.get('frameworks') or [],
            tech_data.get('databases') or [],
            tech_data.get('cloud_services') or [],
            tech_data.get('other_tools') or []
        ]
        # Flatten list, remove duplicates, and filter out empty/None items
        return list(set(item for sublist in tech_lists for item in sublist if item))

    def _merge_lists(self, primary_list: List[str], secondary_list: List[str]) -> List[str]:
        """Merges two lists, prioritizing items from the primary list, ensuring uniqueness (case-insensitive)."""
        merged_set = set(p.lower() for p in primary_list if p)
        result_list = list(p for p in primary_list if p)  # Keep original casing from primary

        for item in secondary_list:
            if item and item.lower() not in merged_set:
                merged_set.add(item.lower())
                result_list.append(item)
        return result_list

    async def _store_error_state(self, job_id: str, entity_id: str, error_details: Dict[str, Any]) -> None:
        """Store error information in BigQuery."""
        try:
            if not job_id or not entity_id:
                logger.error("Missing required fields for error state storage (job_id or entity_id)")
                return

            # Ensure error details are properly formatted and JSON serializable
            formatted_error = {
                'error_type': error_details.get('error_type', 'unknown_error'),
                'message': str(error_details.get('message', 'Unknown error occurred')),  # Ensure string
                'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),  # Use UTC timestamp
                'retryable': error_details.get('retryable', False),  # Default to False unless specified
                # Ensure additional info is serializable or removed
                'additional_info': json.loads(json.dumps(error_details.get('additional_info', {}), default=str))
            }

            logger.debug(f"Storing error state for job {job_id}, entity {entity_id}")

            await self.bq_service.insert_enrichment_raw_data(
                job_id=job_id,
                entity_id=entity_id,
                source='system_error',  # Indicate the source is an error during processing
                raw_data={'error_details': formatted_error},  # Store error in raw_data
                processed_data={},
                status='failed',
                error_details=formatted_error  # Also store in the dedicated error field if schema supports it
            )

            logger.info(f"Successfully stored error state for job {job_id}, entity {entity_id}")

        except Exception as e:
            logger.error(
                f"Failed to store error state in BigQuery for job {job_id}, entity {entity_id}: {str(e)}",
                exc_info=True
            )
