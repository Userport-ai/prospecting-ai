import os
from typing import List, Optional

import httpx
from pydantic import BaseModel, Field

from models.accounts import BrightDataAccount, AccountInfo, RecentDevelopments
from services.ai_service import AIServiceFactory
from services.api_cache_service import APICacheService
from services.bigquery_service import BigQueryService
from services.brightdata_service import BrightDataService
from services.builtwith_service import BuiltWithService
from services.jina_service import JinaService
from utils.connection_pool import ConnectionPool
from utils.retry_utils import RetryableError, RetryConfig, with_retry
from utils.url_utils import UrlUtils
from utils.loguru_setup import logger

# Configure logging



class FailedToFindLinkedInURLsError(Exception):
    pass


class FailedToSelectAccountError(Exception):
    pass


ACCOUNT_FETCHER_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=20.0,
    retryable_exceptions=[
        RetryableError,
        ConnectionError,
        FailedToFindLinkedInURLsError,
        FailedToSelectAccountError
    ]
)


class MatchedWebsiteResult(BaseModel):
    reason: str = Field(...)
    matched_website: Optional[str] = Field(default=None)


class AccountInfoFetcher:
    """Class that fetches Account information for given website."""

    def __init__(self, website: str):
        self.website = website

        try:
            self.jina_service = JinaService()
            logger.info("Successfully configured Jina Service")

            self.model = AIServiceFactory().create_service("gemini")
            logger.info("Successfully configured AI service")

            self.brightdata_service = BrightDataService()
            logger.info("Successfully configured Brightdata Service")

            # Initialize BigQuery and cache services
            self.bq_service = BigQueryService()
            self.project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
            self.dataset = os.getenv('BIGQUERY_DATASET', 'userport_enrichment')

            self.pool = ConnectionPool(
                limits=httpx.Limits(
                    max_keepalive_connections=15,
                    max_connections=20,            # Maximum concurrent connections
                    keepalive_expiry=150.0         # Connection TTL in seconds
                ),
                timeout=300.0
            )

            self.cache_service = APICacheService(
                client=self.bq_service.client,
                project_id=self.project_id,
                dataset=self.dataset,
                connection_pool=self.pool
            )

            self.builtwith_service = BuiltWithService(cache_service=self.cache_service)

        except Exception as e:
            logger.error(f"Failed to configure one of AccountInfoFetcher's Services: {str(e)}", exc_info=True)
            raise

    @with_retry(retry_config=ACCOUNT_FETCHER_RETRY_CONFIG, operation_name="_fetch_account_info")
    async def get(self) -> AccountInfo:
        """Get Account information for given website."""
        try:
            logger.debug(f"Starting fetch of Account information for website: {self.website}")
            domain = UrlUtils.get_domain(url=self.website)

            linkedin_url_fetched_from_builtwith = False
            # First attempt: Try to get LinkedIn URL from BuiltWith
            logger.debug(f"Attempting to get LinkedIn URL from BuiltWith for domain: {domain}")
            builtwith_result = await self.builtwith_service.get_technology_profile(
                domain=domain
            )

            account_linkedin_urls: Optional[List[str]] = None
            if builtwith_result:
                bw_linkedin_urls: Optional[List[str]] = builtwith_result.get_account_linkedin_urls()
                if bw_linkedin_urls:
                    logger.debug(f"Got LinkedIn URLs from BuiltWith: {bw_linkedin_urls}")
                    account_linkedin_urls = bw_linkedin_urls
                    linkedin_url_fetched_from_builtwith = True

            # Fallback: If no LinkedIn URL found from BuiltWith, use Jina search
            if not account_linkedin_urls:
                logger.debug(f"No LinkedIn URLs found in domain: {domain} in BuiltWith result, falling back to Jina Search")
                query = f"{domain} LinkedIn Page"
                web_search_results_md: str = await self.jina_service.search_query(
                    query=query,
                    headers={"X-Retain-Images": "none", "X-No-Cache": "true"}
                )
                account_linkedin_urls = await self._parse_account_linkedin_urls(
                    web_search_results_md=web_search_results_md)

            logger.debug(f"Fetched Potential Account LinkedIn URLs: {account_linkedin_urls} for website: {self.website}")

            snapshot_id: str = await self.brightdata_service.trigger_account_data_collection(account_linkedin_urls=account_linkedin_urls)
            logger.debug(f"Triggered Bright Data collection with Snapshot ID: {snapshot_id} for website: {self.website}")

            brightdata_accounts: List[BrightDataAccount] = await self.brightdata_service.collect_account_data(snapshot_id=snapshot_id)
            logger.debug(f"Collected Bright Data Accounts for Snapshot ID: {snapshot_id} for website: {self.website}")

            if len(brightdata_accounts) == 0:
                raise ValueError(f"Got empty list of BrightData Accounts for snapshot ID: {snapshot_id} and URLs: {account_linkedin_urls} for website: {self.website}")

            bd_account: BrightDataAccount = None
            if linkedin_url_fetched_from_builtwith:
                logger.debug(f"Selecting first BrightData Account since URL fetched from BuiltWith for website: {self.website}")
                # Select the first result. We assume BuiltWith is reliable and so we don't the LLM to select the correct LinkedIn URL.
                bd_account = brightdata_accounts[0]
            else:
                logger.debug(f"Selecting the correct BrightData Account using LLM for website: {self.website}")
                # Select the correct account using LLM among the ones fetched from Jina.
                bd_account = await self._select_correct_account(brightdata_accounts=brightdata_accounts)

            logger.debug(f"Successfully fetched Account Information for website: {self.website}")
            return AccountInfo(
                name=bd_account.name,
                website=self.website,  # Using provided website instead of result from LinkedIn page which could be a bit.ly link.
                linkedin_url=bd_account.url,
                employee_count=bd_account.employees_in_linkedin,
                company_size=bd_account.company_size,
                about=bd_account.about,
                description=bd_account.description,
                slogan=bd_account.slogan,
                industries=bd_account.industries,
                categories=bd_account.specialties,
                headquarters=bd_account.headquarters,
                organization_type=bd_account.organization_type,
                founded_year=bd_account.founded,
                logo=bd_account.logo,
                crunchbase_url=bd_account.crunchbase_url,
                locations=bd_account.formatted_locations,
                location_country_codes=bd_account.country_codes_array,
                recent_developments=RecentDevelopments(linkedin_posts=bd_account.updates)
            )

        except Exception as e:
            logger.error(f"Failed to get Account information for website: {self.website} with error: {str(e)}", exc_info=True)
            raise

    async def _parse_account_linkedin_urls(self, web_search_results_md: str) -> List[str]:
        """Parse Account LinkedIn URLs returned by Jina Web Search results."""
        try:
            prompt = f"""Analyze the following Markdown of Web Search Results.
    Extract the main Company LinkedIn URL from each result and return them as a list.
    Do not extract LinkedIn URLs of similar companies mentioned within a result.

    Here are some example of Company LinkedIn URLs:
    1. https://www.linkedin.com/company/gleanwork
    2. https://www.linkedin.com/company/coderhq
    3. https://www.linkedin.com/company/lumosidentity
    4. https://il.linkedin.com/company/bright-data

    Return as JSON:
    {{
        "linkedin_urls": [string]
    }}

    Markdown Text:
    {web_search_results_md}
    """
            response = await self.model.generate_content(prompt=prompt, is_json=True)
            if "linkedin_urls" not in response:
                raise ValueError(f"Failed to fetch Company LinkedIn URLs in web search results markdown: {web_search_results_md}")
            # LLMs can make mistakes, filter only valid Account URLs.
            return list(filter(lambda url: "linkedin.com/company/" in url, response["linkedin_urls"]))
        except Exception as e:
            raise Exception(f"Failed to parse Account LinkedIn URLs website: {self.website} with error: {str(e)}")

    async def _select_correct_account(self, brightdata_accounts: List[BrightDataAccount]) -> BrightDataAccount:
        """
        Select the correct account representing the given website from the given list of acounts.

        Simple matching using just website domain doesn't work for many examples.
        For example: [1] peppercontent.io => https://bit.ly/3LRJiBE on LinkedIn, [2] http://nubela.co/  => https://www.proxycurl.com on LinkedIn.
        """
        try:
            # Filter accounts that have website.
            accounts_with_websites = list(filter(lambda account: account.website, brightdata_accounts))
            if len(accounts_with_websites) == 0:
                raise ValueError(f"Failed to find any Bright data account with websites from given list: {brightdata_accounts}")

            # Read the web page input.
            page_markdown: str = await self.jina_service.read_url(url=self.website, headers={})
            logger.debug(f"Successfully fetched Website Markdown for website: {self.website}")

            company_descriptions: List[str] = []
            for account in accounts_with_websites:
                description_prompt = f"""
    ```
    Company Website: {account.website}
    Company Description: {account.about}
    ```
    """
                company_descriptions.append(description_prompt)

            company_descriptions_prompt = "\n\n".join(company_descriptions)
            prompt = f"""
    Web Page Markdown:
    ```
    {page_markdown}
    ```

    {company_descriptions_prompt}

    Which one of the Companies above has the Web page Markdown on its website?
    If none, please return null. Do not make up an answer.

    Return as JSON:
    {MatchedWebsiteResult.model_fields}
    """
            response = await self.model.generate_content(prompt=prompt, is_json=True)
            result = MatchedWebsiteResult(**response)
            matched_website: Optional[str] = result.matched_website
            reason: str = result.matched_website
            if not matched_website:
                raise ValueError(f"Failed to match any website with reason: {reason} among accounts: {brightdata_accounts}")

            # Find the Selected account.
            selected_accounts: List[BrightDataAccount] = list(filter(lambda account: account.website.strip("/").strip() == matched_website.strip("/").strip(),  accounts_with_websites))
            if len(selected_accounts) == 0:
                raise ValueError(f"Expected at least 1 Selected Account with matched website: {matched_website}, got {len(selected_accounts)} Accounts among all accounts: {brightdata_accounts}")
            # Pick the first one. Sometimes there can be more than 1 result with the same website like https://brdta.com/3go77R5 for Bright Data.
            return selected_accounts[0]
        except Exception as e:
            raise FailedToSelectAccountError(f"Failed to select Correct Account among: {brightdata_accounts} with error: {str(e)}")


"""
For testing
async def main():
    # website = "https://nubela.co/proxycurl"
    # website = "https://brightdata.com"
    website = "https://www.observeinc.com"
    fetcher = AccountInfoFetcher(website=website)

    account_info = await fetcher.get()

    import pprint
    pprint.pprint(account_info)

if __name__ == "__main__":
    import asyncio
    
    # Logging configuration is now in utils/loguru_setup.py

    from dotenv import load_dotenv
    load_dotenv()

    asyncio.run(main())
"""
