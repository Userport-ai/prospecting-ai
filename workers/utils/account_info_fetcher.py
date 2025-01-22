import os
import logging
import httpx
import tldextract
from typing import List
from services.ai_service import AIServiceFactory
from services.jina_service import JinaService
from services.brightdata_service import BrightDataService
from models import BrightDataAccount, AccountInfo

# Configure logging
logger = logging.getLogger(__name__)


class AccountInfoFetcher:
    """Class that fetches Account information for given website."""

    def __init__(self, website: str):
        self.website = website
        self.domain = self._get_domain(website)

        try:
            self.jina_service = JinaService()
            logger.info("Successfully configured Jina Service")

            self.model = AIServiceFactory.create_service("gemini")
            logger.info("Successfully configured AI service")

            self.brightdata_service = BrightDataService()
            logger.info("Successfully configured Brightdata Service")
        except Exception as e:
            logger.error(f"Failed to configure one of AccountInfoFetcher's Services: {str(e)}", exc_info=True)
            raise

    async def get(self) -> AccountInfo:
        """Get Account information for given website."""
        try:
            logger.debug(f"Starting fetch of Account information for website: {self.website}")
            query = f"{self.domain} LinkedIn Page"
            web_search_results_md: str = await self.jina_service.search_query(query=query, headers={"X-Retain-Images": "none"})
            logger.debug(f"Fetched Jina Web search results for query {query} for website: {self.website}")

            account_linkedin_urls: List[str] = await self._parse_account_linkedin_urls(web_search_results_md=web_search_results_md)
            logger.debug(f"Fetched Potential Account LinkedIn URLs: {account_linkedin_urls} for website: {self.website}")

            snapshot_id: str = await self.brightdata_service.trigger_account_data_collection(account_linkedin_urls=account_linkedin_urls)
            logger.debug(f"Triggered Bright Data collection with Snapshot ID: {snapshot_id} for website: {self.website}")

            brightdata_accounts: List[BrightDataAccount] = await self.brightdata_service.collect_account_data(snapshot_id=snapshot_id)
            logger.debug(f"Collected Bright Data Accounts for Snapshot ID: {snapshot_id} for website: {self.website}")

            bd_account = self._select_correct_account(brightdata_accounts=brightdata_accounts)
            logger.debug(f"Successfully fetched Account Information for website: {self.website}")
            return AccountInfo(
                name=bd_account.name,
                website=bd_account.website,
                linkedin_url=bd_account.url,
                employee_count=bd_account.employees_in_linkedin,
                company_size=bd_account.company_size,
                about=bd_account.about,
                description=bd_account.description,
                slogan=bd_account.slogan,
                industries=bd_account.industries,
                specialities=bd_account.specialties,
                headquarters=bd_account.headquarters,
                organization_type=bd_account.organization_type,
                founded_year=bd_account.founded,
                logo=bd_account.logo,
                crunchbase_url=bd_account.crunchbase_url,
                locations=bd_account.formatted_locations,
                location_country_codes=bd_account.country_codes_array
            )

        except Exception as e:
            logger.error(f"Failed to get Account information for website: {self.website} with error: {str(e)}", exc_info=True)
            raise

    async def _parse_account_linkedin_urls(self, web_search_results_md: str) -> List[str]:
        """Parse Account LinkedIn URLs returned by Jina Web Search results."""
        try:
            prompt = f"""Analyze the following Markdown of Web Search Results.
    Extract the Company LinkedIn URL from each result and return them as a list.

    Here are some example of Company LinkedIn URLs:
    1. https://www.linkedin.com/company/gleanwork
    2. https://www.linkedin.com/company/coderhq
    3. https://www.linkedin.com/company/lumosidentity

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
            return list(filter(lambda url: url.startswith("https://www.linkedin.com/company/"), response["linkedin_urls"]))
        except Exception as e:
            logger.error(f"Failed to parse Account LinkedIn URLs website: {self.website} with error: {str(e)}", exc_info=True)
            raise

    def _select_correct_account(self, brightdata_accounts: List[BrightDataAccount]) -> BrightDataAccount:
        """Select the correct account representing the given website from the given list of acounts."""
        for account in brightdata_accounts:
            if account.website and self._get_domain(account.website) == self.domain:
                # Domain of the bright data account and given website match.
                return account

        raise ValueError(f"Failed to find matching Bright data account from given list: {brightdata_accounts}")

    def _get_domain(self, url: str):
        """Helper to return domain for given website.

        For example: https://www.zuddle.com will return zuddle.com.
        """
        result = tldextract.extract(url)
        return f"{result.domain}.{result.suffix}"


async def main():
    website = "https://www.peppercontent.io"
    fetcher = AccountInfoFetcher(website=website)

    account_info = await fetcher.get()

    import pprint
    pprint.pprint(account_info)

if __name__ == "__main__":
    import asyncio
    import logging

    logging.basicConfig(level=logging.DEBUG)

    from dotenv import load_dotenv
    load_dotenv()

    asyncio.run(main())
