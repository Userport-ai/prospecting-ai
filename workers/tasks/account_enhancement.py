import os
import json
import logging
import requests
import google.generativeai as genai
from typing import Dict, Any
from .base import BaseTask

logger = logging.getLogger(__name__)

class AccountEnhancementTask(BaseTask):
    def __init__(self):
        self.jina_api_token = os.getenv('JINA_API_TOKEN')
        self.google_api_key = os.getenv('GEMINI_API_TOKEN')

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
        if 'company_name' not in kwargs:
            raise ValueError("company_name is required")

        return {
            "company_name": kwargs["company_name"],
            "account_id": kwargs.get("account_id")
        }

    async def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            company_name = payload.get('company_name')
            if not company_name:
                return {"status": "failed", "error": "No company name provided"}

            # Call the Jina API
            jina_url = f"https://s.jina.ai/{company_name}+company+profile"
            jina_headers = {
                "Authorization": f"Bearer {self.jina_api_token}",
            }
            jina_response = requests.get(jina_url, headers=jina_headers)
            jina_response.raise_for_status()
            company_profile = jina_response.text

            # Create a more specific prompt for Gemini
            extraction_prompt = f"""
            Extract company information into a structured JSON format from the profile below.
            For any field where information is not found, use null.
            Only return the JSON object, no other text.
            Be precise with numbers, dates, and currency values.
            For metrics, include the date/period when the value was reported if available.
            If a company is private/startup, focus on startup metrics like funding, investors, etc.
            If a company is public, focus on stock metrics and financials.

            Company Profile:
            {company_profile}

            Required JSON format:
            {{
                "company_name": {{
                    "legal_name": string,
                    "trading_name": string or null,
                    "aliases": [string] or null
                }},
                "founding": {{
                    "year": number,
                    "location": string,
                    "founders": [string]
                }},
                "headquarters": {{
                    "address": string or null,
                    "city": string,
                    "state": string or null,
                    "country": string,
                    "postal_code": string or null
                }},
                "company_type": {{
                    "status": string (e.g. "Public", "Private", "Subsidiary"),
                    "entity_type": string or null
                }},
                "stock_info": [
                    {{
                        "exchange": string,
                        "ticker": string,
                        "currency": string,
                        "isin": string or null,
                        "listing_date": string or null
                    }}
                ],
                "industry": {{
                    "sector": string,
                    "sub_sector": string or null,
                    "categories": [string]
                }},
                "business_metrics": {{
                    "employees": {{
                        "count": number or null,
                        "as_of_date": string or null
                    }},
                    "locations": {{
                        "countries": [string],
                        "office_count": number or null
                    }}
                }},
                "financials": {{
                    "type": string ("public" or "private"),
                    "public_metrics": {{
                        "currency": string or null,
                        "market_cap": {{
                            "value": number or null,
                            "as_of_date": string or null
                        }},
                        "latest_quarter": {{
                            "revenue": number or null,
                            "operating_income": number or null,
                            "net_income": number or null,
                            "period": string or null
                        }},
                        "key_ratios": {{
                            "eps_ttm": number or null,
                            "pe_ratio": number or null,
                            "dividend_yield": number or null
                        }}
                    }},
                    "private_metrics": {{
                        "total_funding": {{
                            "amount": number or null,
                            "currency": string or null,
                            "as_of_date": string or null
                        }},
                        "funding_rounds": [
                            {{
                                "round_name": string,
                                "amount": number or null,
                                "currency": string,
                                "date": string,
                                "lead_investors": [string],
                                "other_investors": [string]
                            }}
                        ],
                        "valuation": {{
                            "amount": number or null,
                            "currency": string or null,
                            "date": string or null,
                            "type": string or null
                        }}
                    }}
                }},
                "leadership": [
                    {{
                        "name": string,
                        "title": string,
                        "since": string or null
                    }}
                ],
                "investors": {{
                    "major_shareholders": [
                        {{
                            "name": string,
                            "stake_percentage": number or null,
                            "as_of_date": string or null
                        }}
                    ],
                    "key_investors": [string]
                }},
                "business_model": {{
                    "type": string or null,
                    "revenue_streams": [string],
                    "key_products": [string],
                    "target_markets": [string]
                }},
                "major_subsidiaries": [
                    {{
                        "name": string,
                        "ownership_stake": number or null,
                        "country": string or null,
                        "description": string or null
                    }}
                ],
                "major_competitors": [string],
                "website": string or null,
                "recent_developments": [
                    {{
                        "event": string,
                        "date": string or null,
                        "description": string
                    }}
                ]
            }}
            """

            # Get structured data with debug logging
            logger.info("Sending extraction prompt to Gemini")
            structure_response = self.model.generate_content(extraction_prompt)

            try:
                raw_text = structure_response.parts[0].text if structure_response.parts else ""
                logger.debug(f"Extracted text: {raw_text}")

                # Clean the text before parsing JSON
                cleaned_text = raw_text.strip()
                if cleaned_text.startswith("```json"):
                    cleaned_text = cleaned_text[7:]
                if cleaned_text.endswith("```"):
                    cleaned_text = cleaned_text[:-3]
                cleaned_text = cleaned_text.strip()

                structured_data = json.loads(cleaned_text)

            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing error: {str(e)}")
                structured_data = {
                    "error": "Could not parse structured data",
                    "raw_response": raw_text
                }

            # Get analysis from Gemini
            analysis_prompt = f"""
            You're a Business Development rep working on profiling companies. Based on the given company profile, provide a concise analysis covering:

            1. MARKET POSITION & COMPETITIVE ADVANTAGES
            - Core competitive strengths
            - Market positioning
            - Brand value/recognition
            - Technological or intellectual property advantages

            2. BUSINESS MODEL & FINANCIAL HEALTH
            For public companies focus on:
            - Revenue and profitability trends
            - Market performance
            - Key financial ratios
            - Capital structure

            For private companies/startups focus on:
            - Business model and revenue streams
            - Funding history and investor backing
            - Growth metrics and burn rate (if available)
            - Path to profitability

            3. RISKS & CHALLENGES
            - Market and competitive risks
            - Regulatory/compliance challenges
            - Operational risks
            - Financial/funding risks
            - Technology risks

            4. GROWTH OPPORTUNITIES
            - Market expansion potential
            - Product/service development
            - M&A opportunities
            - Industry trends benefiting the company

            5. RECENT DEVELOPMENTS
            - Major strategic initiatives
            - Management changes
            - Funding rounds/acquisitions
            - Product launches
            - Partnerships

            Profile Text:
            {company_profile}

            Keep the analysis data-driven, specific, and focused on key insights.
            For startups/private companies, emphasize funding, growth, and path to profitability.
            For public companies, emphasize financial performance and market position.
            Don't add any general comments, pleasantries or greetings. Keep it professional.
            """

            analysis_response = self.model.generate_content(analysis_prompt)
            analysis_text = analysis_response.parts[0].text if analysis_response.parts else ""

            # Return combined response
            return {
                "status": "completed",
                "account_id": payload.get("account_id"),
                "company_name": company_name,
                "enrichment_data": {
                    "structured_data": structured_data,
                    "raw_profile": company_profile,
                    "ai_analysis": analysis_text
                }
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"Jina API error: {str(e)}")
            return {
                "status": "failed",
                "error": f"Jina API error: {str(e)}",
                "company_name": company_name
            }
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return {
                "status": "failed",
                "error": str(e),
                "company_name": company_name
            }