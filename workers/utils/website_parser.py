import os
import asyncio
import httpx
from typing import List, Dict, Any
from services.ai.ai_service import AIServiceFactory
from google.api_core.exceptions import ResourceExhausted
from utils.retry_utils import RetryableError, RetryConfig, with_retry
from utils.loguru_setup import logger

# Configure logging


GEMINI_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=2.0,
    max_delay=30.0,
    retryable_exceptions=[
        RetryableError,
        ResourceExhausted,
        ValueError,
        RuntimeError,
        TimeoutError,
        ConnectionError
    ]
)

JINA_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=20.0,
    retryable_exceptions=[
        RetryableError,
        asyncio.TimeoutError,
        ConnectionError,
        httpx.ConnectTimeout,
        httpx.ConnectError,
    ]
)


class WebsiteParser:
    """Parser for a Company website."""

    def __init__(self, website: str):
        logger.info(f"Initializing Website parser for website: {website}")
        self.website = website
        # Use Jina Reader API to fetch customers from website.
        self.BASE_URL = "https://r.jina.ai/"
        self.jina_api_token = os.getenv('JINA_API_TOKEN')

        try:
            self.model = AIServiceFactory().create_service("gemini")
            logger.info("Successfully configured Gemini API")
        except Exception as e:
            logger.error(f"Failed to configure Gemini API: {str(e)}")
            raise

    async def fetch_company_customers(self) -> List[str]:
        """
        Fetches list of customers names listed on given Company Website.

        Note:
            This function does not return an exhaustive list of all customers.
            It provides a starting point for identifying potential customers.
        """
        try:
            website = self.website
            jina_endpoint = f"{self.BASE_URL}{website}"
            headers = {"Authorization": f"Bearer {self.jina_api_token}", "X-With-Images-Summary": "True"}
            response_text = await self._call_jina_api(endpoint=jina_endpoint, headers=headers)

            parsed_customers = await self._parse_customers(page_markdown=response_text)

            logger.debug(f"Successfully fetched company customers for website: {self.website}")
            return parsed_customers

        except httpx.HTTPStatusError as e:
            logger.error(f"Unexpected error in making call to Jina Reader while fetching Company customers in website: {website}: {str(e)}", exc_info=True)
            return []
        except Exception as e:
            logger.error(f"Unexpected error while fetching Company customers: {str(e)}", exc_info=True)
            return []

    async def _parse_customers(self, page_markdown: str) -> List[str]:
        """Extract customers from given Page markdown."""
        logger.info(f"Start parsing customers from Page Markdown for website: {self.website}")

        try:
            prompt = f"""Analyze the following Markdown formatted Web Page of a Company:

    {page_markdown}

    Extract the names of the Customers listed on the web page. Also give reason why they were extracted as a Customer.
    Sometimes Customer names are found within case study and logo links on the page.
    Intelligently convert the links to company names using real world knowledge.
    Do not add Company names that are setting cookies on the web page as Customers.
    Do not add Social media pages of the Company like LinkedIn, Facebook, Instagram or Twitter as Customers.

    Here are some examples:
    1. https://cdn.prod.website-files.com/601fab1cb6249b3cc9f592f0/66e0114153eb21ba3e5872d1_Transperfect.svg is Transperfect.
    2. https://www.postman.com/hubspot is Hubspot.
    3. https://www.postman.com/case-studies/intuit/ is Intuit.
    4. https://www.postman.com/ciscodevnet/workspace/cisco-devnet-s-public-workspace/overview is Cisco DevNet.
    5. https://cdn.prod.website-files.com/601fab1cb6249b3cc9f592f0/66e011428d6e6aaf3371b9c3_United%20Nations.svg is United Nations.
    6. https://cdn.prod.website-files.com/601fab1cb6249b3cc9f592f0/66e011403646b900e8faa4a3_Partnership%20Leaders.svg is Parntership Leaders.


    Return as JSON:
    {{
        "customers": [
            {{
                "name": string,
                "reason": string,
            }}
        ]
    }}"""
            response = await self._call_ai_api(prompt=prompt)
            if "customers" not in response:
                return []
            return [cust["name"] for cust in response["customers"]]
        except Exception as e:
            logger.error(f"Error parsing customers: {str(e)}", exc_info=True)
            return []

    async def fetch_technologies(self) -> List[str]:
        """
        Fetches list of technologies found on given Company Website.

        Note:
            This function does not return an exhaustive list of all technologies.
            It provides a starting point for identifying potential technologies.
        """
        try:
            website = self.website
            jina_endpoint = f"{self.BASE_URL}{website}"
            headers = {"Authorization": f"Bearer {self.jina_api_token}", "X-Return-Format": "html"}
            response_text = await self._call_jina_api(endpoint=jina_endpoint, headers=headers)

            parsed_technologies = await self._parse_technologies(page_html=response_text)

            logger.debug(f"Successfully fetched Technologies for website: {self.website}")
            return parsed_technologies

        except httpx.HTTPStatusError as e:
            logger.error(f"Unexpected error in making call to Jina Reader while fetching Company Technologies in website: {website}: {str(e)}", exc_info=True)
            return []
        except Exception as e:
            logger.error(f"Unexpected error while fetching Company Technologies: {str(e)}", exc_info=True)
            return []

    async def _parse_technologies(self, page_html: str) -> List[str]:
        """Extract technologies from given page HTML."""

        try:
            prompt = f"""Analyze the following HTML Web Page of a Company:

    {page_html}

    Using real world knowledge, extract the names of the Technologies used by the Company listed on the web page. Also give reason why they were extracted as a Technology.
    Do not add Customer names found within case studies, testimonials and logo links on the page as Technologies.
    Do not add Social media pages of the Company like LinkedIn, Facebook, Instagram or Twitter as Technologies.

    Here are some examples:
    1. https://zuddlforevents.webflow.io/platform/event-registration-and-ticketing-software is Webflow.
    2. https://assets.apollo.io/micro/website-tracker/tracker.iife.js?nocache=kfmipp is Apollo.io.
    3. https://scout-cdn.salesloft.com/sl.js is Salesloft.
    4. window.dataLayer.push({{event:"hubspot-form-success","hs-form-guid":a.data.id}} is Hubspot
    5. "New Relic uses this cookie to store a session identifier so that New Relic can monitor session counts for an application" is New Relic.
    6. https://tracking.g2crowd.com/attribution_tracking/conversions is G2.

    Return as JSON:
    {{
        "technologies": [
            {{
                "name": string,
                "reason": string,
            }}
        ]
    }}
    """
            response = await self._call_ai_api(prompt=prompt)
            if "technologies" not in response:
                return []
            return [tech["name"] for tech in response["technologies"]]
        except Exception as e:
            logger.error(f"Error parsing Technologies: {str(e)}", exc_info=True)
            return []

    @with_retry(retry_config=JINA_RETRY_CONFIG, operation_name="_website_parser_call_jina_reader_api")
    async def _call_jina_api(self, endpoint: str, headers: Dict) -> str:
        """Calls Jina API (with retries) and returns response text."""
        async with httpx.AsyncClient() as client:
            response = await client.get(url=endpoint, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.text

    @with_retry(retry_config=GEMINI_RETRY_CONFIG, operation_name="_website_parser_call_ai_api")
    async def _call_ai_api(self, prompt: str) -> Dict[str, Any] | str:
        """Calls AI API with retries and returns response."""
        response = await self.model.generate_content(prompt, is_json=True)
        return response
