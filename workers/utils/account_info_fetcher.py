import os
from typing import List, Optional

import httpx
from pydantic import BaseModel, Field

from models.accounts import BrightDataAccount, AccountInfo, RecentDevelopments
from services.ai.ai_service import AIServiceFactory
from services.ai.api_cache_service import APICacheService
from services.bigquery_service import BigQueryService
from services.brightdata_service import BrightDataService
from services.builtwith_service import BuiltWithService
from services.jina_service import JinaService, JinaSearchResults
from utils.connection_pool import ConnectionPool
from utils.retry_utils import RetryableError, RetryConfig, with_retry
from utils.url_utils import UrlUtils
from utils.loguru_setup import logger
from urllib.parse import urlparse

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

    @with_retry(retry_config=ACCOUNT_FETCHER_RETRY_CONFIG, operation_name="_fetch_account_info_v2")
    async def get_v2(self) -> AccountInfo:
        """Get Account information for given website."""
        try:
            logger.debug(f"Starting fetch of Account information v2 for website: {self.website}")
            domain = UrlUtils.get_domain(url=self.website)

            website_overview: str = await self._fetch_website_overview()
            logger.debug(f"Fetched website overview for website: {self.website}")

            # Try web search first.
            logger.info(f"Account Info: Trying web search first")
            try:
                brightdata_account = await self._web_search(domain=domain, website_overview=website_overview)
                return self._to_account_info(brightdata_account)
            except Exception as e:
                logger.error(f"Account Info: Failed web search with error: {str(e)}")

            # Try Built With next.
            logger.info(f"Account Info: Trying BuiltWith next")
            try:
                brightdata_account = await self._lookup_builtwith(domain=domain, website_overview=website_overview)
                return self._to_account_info(brightdata_account)
            except Exception as e:
                logger.error(f"Account Info: Failed Builtwith lookup with error: {str(e)}")

        except Exception as e:
            logger.error(f"Account info: Failed to get with error: {str(e)}", exc_info=True)
            raise

    async def _fetch_website_overview(self) -> str:
        """Fetches overview of the website. Used to figure out the correct LinkedIn URL associated with the website."""
        prompt = f"Provide overview of the company with website {self.website}."
        response = await self.model.generate_content(prompt=prompt, is_json=False, operation_tag="website_overview")
        return response

    async def _web_search(self, domain: str, website_overview: str) -> BrightDataAccount:
        """Perform web search and return the correct LinkedIn page."""
        query = f"{domain} LinkedIn Page"
        response_json: str = await self.jina_service.search_query(query=query, headers={"X-Respond-With": "no-content", "Accept": "application/json"})
        search_results: Optional[List[JinaSearchResults.Result]] = JinaSearchResults.model_validate_json(response_json).data
        if not search_results:
            raise ValueError(f"No Jina search results found for query: {query}")

        web_search_urls: List[str] = [result.url for result in search_results]
        logger.debug(f"Got {len(search_results)} Web Search URLs for query: {query} are: {web_search_urls}")

        # Select the correct Brightdata LinkedIn account.
        selected_account: BrightDataAccount = await self._fetch_and_select_linkedin_url(potential_urls=web_search_urls, website_overview=website_overview)
        logger.debug(f"Web Search: Found LinkedIn page with URL: {selected_account.url}")

        return selected_account

    async def _lookup_builtwith(self, domain: str, website_overview: str) -> BrightDataAccount:
        """Lookup Builtwith to find LinkedIn URL and return the correct LinkedIn page."""
        builtwith_result = await self.builtwith_service.get_technology_profile(domain=domain)
        if not builtwith_result:
            raise ValueError(f"Builtwith: Failed to get result for domain: {domain}")

        bw_linkedin_urls: Optional[List[str]] = builtwith_result.get_account_linkedin_urls()
        if not bw_linkedin_urls:
            raise ValueError(f"Builtwith: No LinkedIn URLs found for domain: {domain}")

        logger.debug(f"Builtwith: Found {len(bw_linkedin_urls)} LinkedIn URLs: {bw_linkedin_urls}")

        selected_account: BrightDataAccount = await self._fetch_and_select_linkedin_url(potential_urls=bw_linkedin_urls, website_overview=website_overview)
        logger.debug(f"Builtwith: Found LinkedIn page with URL: {selected_account.url}")

        return selected_account

    async def _fetch_and_select_linkedin_url(self, potential_urls: List[str], website_overview: str):
        """Helper that calls Brightdata and LLM to select the correct LinkedIn URL for the given input URLs."""
        valid_linkedin_urls: List[str] = list(filter(lambda url: self._is_valid_linkedin_url(url), potential_urls))
        if len(valid_linkedin_urls) == 0:
            raise ValueError(f"No Valid LinkedIn URLs not found among URLs: {potential_urls}")

        # Get LinkedIn pages.
        brightdata_accounts = await self._fetch_from_brightdata(valid_linkedin_urls)
        if len(brightdata_accounts) == 0:
            raise ValueError(f"No Brightdata accounts found for LinkedIn URLs: {valid_linkedin_urls}")

        # Select the correct Brightdata LinkedIn account.
        return await self._get_correct_linkedin_page(website_overview=website_overview, brightdata_accounts=brightdata_accounts)

    def _is_valid_linkedin_url(self, url: str):
        """Returns true if valid linkedin URL of company/school and false if not.

        Valid URLs:
        1. https://www.linkedin.com/company/gleanwork
        2. http://www.linkedin.com/company/coderhq
        3. https://www.linkedin.com/school/emory-university/

        Invalid URLs:
        1. http://in.linkedin.com/company/impactdotcom?trk=ppro_cpr
        2. https://www.linkedin.com/company/google/jobs
        3. https://pf.linkedin.com/company/google?trk=public_profile_profile-section-card_subtitle-click
        """
        try:
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"}:
                return False
            if "linkedin.com" not in parsed.netloc:
                return False
            path_parts = parsed.path.strip("/").split("/")

            if len(path_parts) != 2:
                return False

            first, second = path_parts
            if first not in {"company", "school"}:
                return False
            if not second:  # slug should not be empty
                return False
            if parsed.query:  # query string should ideally not be present
                return False

            return True

        except Exception as e:
            logger.error(f"Encountered error when checking if valid LinkedIn URL: {url} with error: {str(e)}")
            return False

    async def _fetch_from_brightdata(self, linkedin_urls: List[str]) -> List[BrightDataAccount]:
        """Fetch LinkedIn pages for the given LinkedIn URLs."""
        snapshot_id: str = await self.brightdata_service.trigger_account_data_collection(account_linkedin_urls=linkedin_urls)
        logger.debug(f"Triggered Bright Data collection with Snapshot ID: {snapshot_id}")

        brightdata_accounts: List[BrightDataAccount] = await self.brightdata_service.collect_account_data(snapshot_id=snapshot_id)
        logger.debug(f"Collected: {len(brightdata_accounts)} Bright Data Accounts for Snapshot ID: {snapshot_id}")

        # Filter out dead page accounts.
        brightdata_accounts = list(filter(lambda account: account.warning_code == None, brightdata_accounts))
        logger.debug(f"After skipping dead page accounts, got: {len(brightdata_accounts)} Brightdata Accounts for Snapshot ID: {snapshot_id}")

        return brightdata_accounts

    @with_retry(retry_config=ACCOUNT_FETCHER_RETRY_CONFIG, operation_name="_get_correct_linkedin_page")
    async def _get_correct_linkedin_page(self, website_overview: str, brightdata_accounts: List[BrightDataAccount]) -> BrightDataAccount:
        """Return the correct LinkedIn page from given list of bright data linkedin pages using website overview for matching."""
        account_pages = []
        for i, account in enumerate(brightdata_accounts):
            account_repr = f"Company ID: {i}\n{account.model_dump_json(include=account.get_serialization_fields(), indent=2)}"
            account_pages.append(account_repr)
        account_pages_repr = "\n\n".join(account_pages)
        prompt = f"""
You are a very intelligent person who is tasked finding the correct LikedIn page for a given Company.
You are provided with the following inputs:
1. Overview of the Company.
2. A list of LinkedIn Pages of companies.

Using these inputs, find the LinkedIn page that most accurately matches the Company's Overview.
Return the ID of the matched page and the rationale as a JSON response with the following structure:
{{
    "rationale": string,
    "matching_company_id": number,
}}


\"\"\"
## Company Overview
{website_overview}

## Company LinkedIn Pages
{account_pages_repr}
\"\"\"
"""
        try:
            response = await self.model.generate_content(prompt=prompt, is_json=True, force_refresh=True)
            if "matching_company_id" not in response:
                raise ValueError(f"matching_company_id not found")

            company_id = int(response["matching_company_id"])
            if company_id < 0 or company_id >= len(brightdata_accounts):
                raise ValueError(f"Invalid matching_company_id value: {company_id}")

            return brightdata_accounts[company_id]

        except Exception as e:
            raise FailedToSelectAccountError(f"Failed to Select LinkedIn page with error: {str(e)}")

    def _to_account_info(self, bd_account: BrightDataAccount):
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

            # Filter out dead page accounts.
            brightdata_accounts = list(filter(lambda account: account.warning_code == None, brightdata_accounts))

            if len(brightdata_accounts) == 0:
                raise ValueError(f"Got empty list of BrightData Accounts for snapshot ID: {snapshot_id} and URLs: {account_linkedin_urls} for website: {self.website}")

            bd_account: BrightDataAccount = None
            if linkedin_url_fetched_from_builtwith:
                logger.debug(f"Selecting first BrightData Account since URL was fetched from BuiltWith for website: {self.website}")
                # Select the first result. We assume BuiltWith is reliable and so we don't the LLM to select the correct LinkedIn URL.
                bd_account = brightdata_accounts[0]
            else:
                if len(brightdata_accounts) == 1:
                    logger.debug(f"Selecting first BrightData account since there is only 1 returned from Jina for website: {self.website}")
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
                raise ValueError(f"Failed to match any website with reason: {reason} among accounts Brightdata accounts")

            # Find the Selected account.
            selected_accounts: List[BrightDataAccount] = list(filter(lambda account: account.website.strip("/").strip() == matched_website.strip("/").strip(),  accounts_with_websites))
            if len(selected_accounts) == 0:
                raise ValueError(f"Expected at least 1 Selected Account with matched website: {matched_website}, got {len(selected_accounts)} Accounts among all Brightdata accounts")
            # Pick the first one. Sometimes there can be more than 1 result with the same website like https://brdta.com/3go77R5 for Bright Data.
            return selected_accounts[0]
        except Exception as e:
            raise FailedToSelectAccountError(f"Failed to select Correct Brightdata Account with error: {str(e)}")


async def main():
    # website = "https://nubela.co/proxycurl"
    # website = "https://brightdata.com"
    # website = "https://www.observeinc.com"
    website = "https://www.incred.com/"
    fetcher = AccountInfoFetcher(website=website)

    account_info = await fetcher.get_v2()

if __name__ == "__main__":
    import asyncio

    # Logging configuration is now in utils/loguru_setup.py

    from dotenv import load_dotenv
    load_dotenv()

    asyncio.run(main())
