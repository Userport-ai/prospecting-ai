import os
import uuid
import json
import logging
from typing import Dict, Any
from dataclasses import dataclass
import requests
import google.generativeai as genai

from .base import BaseTask
from services.bigquery_service import BigQueryService

logger = logging.getLogger(__name__)

@dataclass
class PromptTemplates:
    """Store prompt templates for AI interactions."""
    EXTRACTION_PROMPT = """
    Extract company information into a structured JSON format from the profile below.
    Follow these rules strictly:
    1. Return ONLY valid JSON, no extra text or markdown
    2. Do not include any explanations or notes
    3. If a field's information is not available, use null
    4. Use the exact field names and structure shown below
    5. Ensure all strings are properly quoted
    6. Arrays should never be null, use empty array [] if no data

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

class AccountEnhancementTask(BaseTask):
    """Task for enhancing account data with AI-powered company information."""

    def __init__(self):
        """Initialize the task with required services and configurations."""
        self._initialize_credentials()
        self.bq_service = BigQueryService()
        self._configure_ai_service()
        self.prompts = PromptTemplates()

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
        genai.configure(api_key=self.google_api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')

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
                if not all(k in account for k in ['account_id', 'company_name']):
                    raise ValueError("Each account must have 'account_id' and 'company_name'")

            return {
                "accounts": accounts,
                "job_id": str(uuid.uuid4()),
                "is_bulk": True
            }

        # Single account case
        required_fields = ['account_id', 'company_name']
        missing_fields = [field for field in required_fields if field not in kwargs]

        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

        return {
            "accounts": [{
                "account_id": kwargs["account_id"],
                "company_name": kwargs["company_name"]
            }],
            "job_id": str(uuid.uuid4()),
            "is_bulk": False
        }


    async def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the account enhancement task."""
        job_id = payload.get('job_id')
        accounts = payload.get('accounts', [])
        is_bulk = payload.get('is_bulk', False)

        if not accounts:
            return {
                "status": "failed",
                "error": "No accounts provided",
                "job_id": job_id
            }

        results = []
        has_failures = False

        for account in accounts:
            try:
                account_id = account.get('account_id')
                company_name = account.get('company_name')

                if not all([company_name, account_id]):
                    error_details = {'error_type': 'validation_error', 'message': "Missing required fields"}
                    await self._store_error_state(job_id, account_id, error_details)
                    results.append({
                        "status": "failed",
                        "account_id": account_id,
                        "error": "Missing required fields"
                    })
                    has_failures = True
                    continue

                # Fetch and process company data
                company_profile = await self._fetch_company_profile(company_name)
                structured_data = await self._extract_structured_data(company_profile)
                analysis_text = await self._generate_analysis(company_profile)

                # Store processed data
                await self.bq_service.insert_account_data(
                    account_id=account_id,
                    structured_data=structured_data,
                    raw_profile=company_profile
                )

                # Store raw enrichment data
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

                results.append({
                    "status": "completed",
                    "account_id": account_id,
                    "company_name": company_name,
                    "enrichment_data": {
                        "structured_data": structured_data,
                        "ai_analysis": analysis_text
                    }
                })

            except requests.exceptions.RequestException as e:
                error_details = {'error_type': 'jina_api_error', 'message': str(e)}
                await self._store_error_state(job_id, account.get('account_id'), error_details)
                results.append({
                    "status": "failed",
                    "account_id": account.get('account_id'),
                    "error": f"Jina API error: {str(e)}"
                })
                has_failures = True

            except Exception as e:
                error_details = {'error_type': 'unexpected_error', 'message': str(e)}
                await self._store_error_state(job_id, account.get('account_id'), error_details)
                results.append({
                    "status": "failed",
                    "account_id": account.get('account_id'),
                    "error": str(e)
                })
                has_failures = True

        return {
            "status": "completed" if not has_failures else "partially_completed",
            "job_id": job_id,
            "is_bulk": is_bulk,
            "total_accounts": len(accounts),
            "successful_accounts": len([r for r in results if r["status"] == "completed"]),
            "failed_accounts": len([r for r in results if r["status"] == "failed"]),
            "results": results
        }

    async def _fetch_company_profile(self, company_name: str) -> str:
        """Fetch company profile from Jina AI."""
        try:
            jina_url = f"https://s.jina.ai/{company_name}+company+profile"
            response = requests.get(
                jina_url,
                headers={"Authorization": f"Bearer {self.jina_api_token}"}
            )
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            logger.error(f"Jina API error: {str(e)}")
            raise

    async def _extract_structured_data(self, company_profile: str) -> Dict[str, Any]:
        """Extract structured data from company profile using Gemini AI."""
        try:
            logger.debug("Creating extraction prompt...")
            extraction_prompt = self.prompts.EXTRACTION_PROMPT.format(
                company_profile=company_profile
            )

            try:
                logger.debug("Sending prompt to Gemini...")
                response = self.model.generate_content(extraction_prompt)
            except Exception as e:
                logger.error(f"Gemini call failed: {e}")
                raise
            if not response or not response.parts:
                raise ValueError("Empty response from Gemini AI")
            return self._parse_gemini_response(response.parts[0].text)
        except Exception as e:
            logger.error(f"Error extracting structured data from response, error: {str(e)}")
            raise


    def _parse_gemini_response(self, response_text: str) -> Dict[str, Any]:
        """Parse and clean Gemini AI response."""
        cleaned_text = response_text.strip()
        if cleaned_text.startswith("```json"):
            cleaned_text = cleaned_text[7:]
        if cleaned_text.endswith("```"):
            cleaned_text = cleaned_text[:-3]
        cleaned_text = cleaned_text.strip()

        try:
            return json.loads(cleaned_text)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error. Text: '{cleaned_text}'. Error: {str(e)}")
            raise ValueError(f"Failed to parse Gemini response as JSON: {str(e)}")

    async def _generate_analysis(self, company_profile: str) -> str:
        """Generate business analysis using Gemini AI."""
        analysis_prompt = self.prompts.ANALYSIS_PROMPT.format(
            company_profile=company_profile
        )
        response = self.model.generate_content(analysis_prompt)
        return response.parts[0].text if response.parts else ""

    async def _store_error_state(self, job_id: str, entity_id: str, error_details: Dict[str, Any]) -> None:
        """Store error information in BigQuery."""
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
