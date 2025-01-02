import json
import logging
import os
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

import google.generativeai as genai
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from services.bigquery_service import BigQueryService
from .base import BaseTask

logger = logging.getLogger(__name__)


class AccountEnhancementTask(BaseTask):
    def __init__(self):
        self.jina_api_token = os.getenv('JINA_API_TOKEN')
        self.google_api_key = os.getenv('GEMINI_API_TOKEN')
        self.bq_service = BigQueryService()

        # Initialize retry configuration
        self.max_retries = int(os.getenv('JINA_MAX_RETRIES', '3'))
        self.request_timeout = int(os.getenv('JINA_REQUEST_TIMEOUT', '30'))

        # Configure HTTP session with retries
        self.session = self._create_http_session()

        if not self.google_api_key:
            raise ValueError("GEMINI_API_TOKEN environment variable is required")
        if not self.jina_api_token:
            raise ValueError("JINA_API_TOKEN environment variable is required")

        # Configure Gemini
        genai.configure(api_key=self.google_api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')

    def _create_http_session(self) -> requests.Session:
        """Create and configure requests session with retry logic"""
        session = requests.Session()

        # Configure retry strategy
        retries = Retry(total=self.max_retries, backoff_factor=0.5,  # Will wait 0.5, 1, 2, 4... seconds between retries
            status_forcelist=[408, 429, 500, 502, 503, 504], allowed_methods=["GET"])

        # Mount the retry adapter
        adapter = HTTPAdapter(max_retries=retries)
        session.mount('http://', adapter)
        session.mount('https://', adapter)

        return session

    @property
    def task_name(self) -> str:
        return "account_enhancement"

    async def create_task_payload(self, **kwargs) -> Dict[str, Any]:
        required_fields = ['account_id', 'company_name']
        missing_fields = [field for field in required_fields if field not in kwargs]

        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

        return {"account_id": kwargs["account_id"], "company_name": kwargs["company_name"], "job_id": str(uuid.uuid4())}

    async def _fetch_company_profile(self, company_name: str) -> Optional[str]:
        """Fetch company profile from Jina with retry logic"""
        try:
            jina_url = f"https://s.jina.ai/{company_name}+company+profile"
            headers = {"Authorization": f"Bearer {self.jina_api_token}", "User-Agent": "AccountEnrichmentService/1.0"}

            start_time = datetime.utcnow()
            response = self.session.get(jina_url, headers=headers, timeout=self.request_timeout)
            response.raise_for_status()

            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"Jina API request completed in {duration:.2f} seconds")

            return response.text

        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching profile for {company_name} after {self.request_timeout}s")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching profile for {company_name}: {str(e)}")
            raise

    async def _extract_structured_data(self, company_profile: str) -> Dict[str, Any]:
        """Extract structured data from company profile using Gemini"""
        try:
            # Create extraction prompt for Gemini
            extraction_prompt = f"""
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
                "industry": {"primary": string or null,
                    "sectors": [string],
                    "categories": [string]
                },
                "location": {"headquarters": {"city": string or null,
                        "state": string or null,
                        "country": string or null,
                        "region": string or null
                    },
                    "office_locations": [
                        {"city": string,
                            "country": string,
                            "type": string
                        }
                    ]
                },
                "business_metrics": {"employee_count": {"total": number or null,
                        "range": string or null,
                        "as_of_date": string or null
                    },
                    "year_founded": number or null,
                    "company_type": string or null
                },
                "technology_stack": {"programming_languages": [string],
                    "frameworks": [string],
                    "databases": [string],
                    "cloud_services": [string],
                    "other_tools": [string]
                },
                "business_details": {"products": [string],
                    "services": [string],
                    "target_markets": [string],
                    "business_model": string or null,
                    "revenue_streams": [string]
                },
                "market_position": {"competitors": [string],
                    "partners": [string],
                    "customers": [string],
                    "target_industries": [string]
                },
                "financials": {"type": "public" or "private",
                    "public_data": {"stock_details": {"exchange": string or null,
                            "ticker": string or null,
                            "market_cap": {"value": number or null,
                                "currency": string or null,
                                "as_of_date": string or null
                            }
                        },
                        "financial_metrics": {"revenue": {"value": number or null,
                                "currency": string or null,
                                "period": string or null
                            },
                            "net_income": {"value": number or null,
                                "currency": string or null,
                                "period": string or null
                            }
                        }
                    },
                    "private_data": {"total_funding": {"amount": number or null,
                            "currency": string or null,
                            "as_of_date": string or null
                        },
                        "funding_rounds": [
                            {"series": string or null,
                                "amount": number or null,
                                "currency": string or null,
                                "date": string or null,
                                "lead_investors": [string],
                                "other_investors": [string],
                                "valuation": {"amount": number or null,
                                    "currency": string or null,
                                    "type": string or null
                                }
                            }
                        ]
                    }
                },
                "recent_developments": [
                    {"type": string,
                        "date": string or null,
                        "title": string,
                        "description": string
                    }
                ],
                "key_metrics": {"growth": {"employee_growth_rate": number or null,
                        "revenue_growth_rate": number or null,
                        "period": string or null
                    },
                    "market_presence": {"global_presence": boolean,
                        "regions_served": [string],
                        "languages_supported": [string]
                    }
                },
                "compliance_and_certifications": [
                    {"name": string,
                        "issuer": string or null,
                        "valid_until": string or null
                    }
                ],
                "digital_presence": {"website": string or null,
                    "social_media": {"linkedin": string or null,
                        "twitter": string or null,
                        "facebook": string or null
                    },
                    "app_store_presence": {"ios": boolean,
                        "android": boolean,
                        "ratings": {"ios_rating": number or null,
                            "android_rating": number or null
                        }
                    }
                }
            }}"""

            logger.debug("Sending extraction prompt to Gemini")

            # Get structured data
            structure_response = self.model.generate_content(extraction_prompt)

            if not structure_response or not structure_response.parts:
                logger.error("Empty response from Gemini")
                raise ValueError("Empty response from Gemini AI")

            raw_text = structure_response.parts[0].text

            # Clean and parse the structured data
            cleaned_text = raw_text.strip()
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text[7:]
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3]
            cleaned_text = cleaned_text.strip()

            try:
                return json.loads(cleaned_text)
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing error. Error: {str(e)}")
                logger.debug(f"Problematic text: {cleaned_text[:500]}...")  # Log first 500 chars
                raise ValueError(f"Failed to parse Gemini response as JSON: {str(e)}")

        except Exception as e:
            logger.error(f"Error extracting structured data: {str(e)}")
            raise

    async def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            company_name = payload.get('company_name')
            account_id = payload.get('account_id')
            job_id = payload.get('job_id')

            if not all([company_name, account_id, job_id]):
                return {"status": "failed", "error": "Missing required payload fields", "job_id": job_id}

            # Fetch company profile with retry logic
            logger.info(f"Fetching company profile for: {company_name}")
            company_profile = await self._fetch_company_profile(company_name)

            if not company_profile:
                raise ValueError("Empty company profile received")

            # Extract structured data
            structured_data = await self._extract_structured_data(company_profile)

            # Get analysis from Gemini
            analysis_prompt = f"""
            Analyze this company profile and provide a concise business summary.
            Focus on key metrics, market position, and recent developments.
            Keep it factual and data-driven.

            Company Profile:
            {company_profile}
            """

            analysis_response = self.model.generate_content(analysis_prompt)
            analysis_text = analysis_response.parts[0].text if analysis_response.parts else ""

            # Store the enrichment data in BigQuery
            await self.bq_service.insert_account_data(account_id=account_id, structured_data=structured_data,
                raw_profile=company_profile)

            # Store the raw enrichment data
            await self.bq_service.insert_enrichment_raw_data(job_id=job_id, entity_id=account_id, source='jina_ai',
                raw_data={'jina_response': company_profile, 'gemini_structured': structured_data,
                    'gemini_analysis': analysis_text}, processed_data=structured_data)

            return {"status": "completed", "account_id": account_id, "job_id": job_id, "company_name": company_name,
                "enrichment_data": {"structured_data": structured_data, "ai_analysis": analysis_text}}

        except requests.exceptions.Timeout as e:
            error_details = {'error_type': 'jina_timeout',
                'message': f"Request timed out after {self.request_timeout} seconds"}
            logger.error(f"Jina API timeout: {str(e)}")
            await self._store_error_state(job_id, account_id, error_details)
            return {"status": "failed", "error": f"Jina API timeout after {self.request_timeout}s", "job_id": job_id}
        except requests.exceptions.RequestException as e:
            error_details = {'error_type': 'jina_api_error', 'message': str(e)}
            logger.error(f"Jina API error: {str(e)}")
            await self._store_error_state(job_id, account_id, error_details)
            return {"status": "failed", "error": f"Jina API error: {str(e)}", "job_id": job_id}
        except Exception as e:
            error_details = {'error_type': 'unexpected_error', 'message': str(e)}
            logger.error(f"Unexpected error: {str(e)}")
            await self._store_error_state(job_id, account_id, error_details)
            return {"status": "failed", "error": str(e), "job_id": job_id}

    async def _store_error_state(self, job_id: str, entity_id: str, error_details: Dict[str, Any]) -> None:
        """Store error state in BigQuery"""
        try:
            await self.bq_service.insert_enrichment_raw_data(job_id=job_id, entity_id=entity_id, source='jina_ai',
                raw_data={}, processed_data={}, status='failed', error_details=error_details)
        except Exception as e:
            logger.error(f"Error storing error state in BigQuery: {str(e)}")
