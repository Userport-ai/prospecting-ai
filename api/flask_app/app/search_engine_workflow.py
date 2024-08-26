from googlesearch import search
import logging
import os
import random
import gzip
import tldextract
from typing import List, Dict
from app.database import Database
from app.linkedin_scraper import LinkedInScraper
from langchain_community.utilities import BingSearchAPIWrapper

logger = logging.getLogger()


class SearchEngineWorkflow:
    """Searches the web using search engine for content related to given person and their current company."""

    def __init__(self, database: Database, max_search_results_per_query: int = 20) -> None:
        self.database = database
        self.max_search_results_per_query = max_search_results_per_query
        self.blocklist_domains = set(
            ["crunchbase.com", "youtube.com", "twitter.com", "x.com", "facebook.com", "quora.com", "bloomberg.com"])
        self.all_user_agents = self.load_all_user_agents()
        self.bing_search = BingSearchAPIWrapper(bing_search_url=os.environ['BING_SEARCH_V7_ENDPOINT'],
                                                bing_subscription_key=os.environ['BING_SEARCH_V7_SUBSCRIPTION_KEY'], k=self.max_search_results_per_query)

    def get_search_results(self, search_queries: List[str], max_results_per_query: int) -> Dict[str, List[str]]:
        """Returns search result links for given search query using Bing Web search API.

        We skip certain blocklisted domains and some other URLs.
        """
        final_search_results = {}
        for query in search_queries:
            final_search_results[query] = []
            logger.info(
                f"Search query: {query}, max results: {max_results_per_query}")

            query_results = self.bing_search.results(
                query=query, num_results=max_results_per_query)
            for q_result in query_results:
                url = q_result["link"]

                if self.is_blocklist_domain(url=url):
                    logger.info(f"URL: {url} is in block list, so skip it.")
                    continue

                if LinkedInScraper.is_valid_profile_or_company_url(url=url):
                    # This is a person's profile or Company About page on LinkedIn, skip it.
                    logger.info(
                        f"URL: {url} is a LinkedIn profile or Company, skip parsing it.")
                    continue

                # If this URL has already been indexed, skip processing.
                if self.database.get_content_details_by_url(url=url):
                    logger.info(
                        f"Web URL: {url} already indexed in the database, skip processing again.")
                    continue

                final_search_results[query].append(url)
                logger.info(f"Added URL: {url} to the result list.")

        return final_search_results

    def get_google_search_results(self, search_queries: List[str], max_results_per_query: int) -> Dict[str, List[str]]:
        """Returns search result links for given search query using Google.

        DO NOT use in production unless tested. It may result in 429 errors due to it being an unofficial library.
        """
        results = {}
        for query in search_queries:
            results[query] = []
            logger.info(
                f"Search query: {query}, max results: {max_results_per_query}")
            for url in search(query, stop=max_results_per_query, user_agent=random.choice(self.all_user_agents)):

                if self.is_blocklist_domain(url=url):
                    logger.info(f"URL: {url} is in block list, so skip it.")
                    continue

                if LinkedInScraper.is_valid_profile_or_company_url(url=url):
                    # This is a person's profile or Company About page on LinkedIn, skip it.
                    logger.info(
                        f"URL: {url} is a LinkedIn profile or Company, skip parsing it.")
                    continue

                results[query].append(url)
                logger.info(f"Added URL: {url} to the result list.")

        return results

    def is_blocklist_domain(self, url: str) -> bool:
        """Returns true if given URL is part of blocklist domains that should not be scraped and false otherwise."""
        ext = tldextract.extract(url)
        return ext.registered_domain in self.blocklist_domains

    def load_all_user_agents(self) -> List[str]:
        """Loads all user agents."""
        all_agents = []
        with gzip.open("app/user_agents.txt.gz", 'rt') as f:
            for line in f.readlines():
                all_agents.append(line.strip())
        return all_agents


if __name__ == "__main__":
    # query = "aniket bajpai limechat ceo recent linkedin posts"
    # query = "Zachary Perret Plaid CEO recent LinkedIn posts"
    # query = "Anuj Kapur CEO Cloudbees recent articles or blogs"

    # profile_url = "https://www.linkedin.com/in/zperret"
    # write_profile_to_db(db, profile_url)\

    # Zach perret Profile ID.
    person_profile_id = '66a70cc8ff3944ed08fe4f1c'
    company_profile_id = '66a7a6b5066fac22c378bd75'

    wf = SearchEngineWorkflow(database=Database())
    # wf.run(person_profile_id=person_profile_id,
    #        company_profile_id=company_profile_id)

    results = wf.bing_search.results(
        query="Plaid recent product launches", num_results=20)
    import pprint
    pprint.pprint(results)
