import os
import logging
import aiohttp
from typing import List
from services.ai_service import AIServiceFactory
from google.api_core.exceptions import ResourceExhausted
from utils.retry_utils import RetryableError, RetryConfig, with_retry

# Configure logging
logger = logging.getLogger(__name__)

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


class WebsiteParser:
    """Parser for a Company website."""

    def __init__(self, website: str):
        logger.info(f"Initializing Website parser for website: {website}")
        self.website = website
        # Use Jina Reader API to fetch customers from website.
        self.BASE_URL = "https://r.jina.ai/"
        self.jina_api_token = os.getenv('JINA_API_TOKEN')

        try:
            self.model = AIServiceFactory.create_service("gemini")
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
            if not website.startswith("https://"):
                raise ValueError(f"Invalid website format: {website}")

            jina_endpoint = f"{self.BASE_URL}{website}"
            headers = {"Authorization": f"Bearer {self.jina_api_token}", "X-With-Images-Summary": "True"}
            timeout = aiohttp.ClientTimeout(total=20)  # Add timeout to prevent hanging
            async with aiohttp.ClientSession() as session:
                async with session.get(url=jina_endpoint, headers=headers, timeout=timeout) as response:
                    response.raise_for_status()

                    page_markdown: str = await response.text()

                    parsed_customers = await self._parse_customers(page_markdown=page_markdown)

                    logger.info(f"Successfully fetched company customers for website: {self.website}")
                    return parsed_customers

        except aiohttp.ClientError as e:
            logger.error(f"Unexpected error in making call to Jina Reader while fetching Company customers in website: {website}: {str(e)}", exc_info=True)
            return []
        except Exception as e:
            logger.error(f"Unexpected error while fetching Company customers: {str(e)}", exc_info=True)
            return []

    @with_retry(retry_config=GEMINI_RETRY_CONFIG, operation_name="_extract_customers")
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
            response = await self.model.generate_content(prompt, is_json=True)
            if "customers" not in response:
                return []
            return [cust["name"] for cust in response["customers"]]
        except Exception as e:
            logger.error(f"Error parsing customers: {str(e)}", exc_info=True)
            return []
