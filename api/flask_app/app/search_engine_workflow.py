from googlesearch import search
import logging
import os
import random
import gzip
import requests
import tldextract
from typing import List, Dict, Set, Optional
from enum import Enum
from app.database import Database
from app.linkedin_scraper import LinkedInScraper
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger()


class SearchRequest(BaseModel):
    """Input config to perform search for given set of queries."""

    class QueryConfig(BaseModel):
        """Configuration for a single query."""
        class PrefixFormat(str, Enum):
            COMPANY_ROLE_LEAD_POSSESSION = 1
            COMPANY_POSSESSION = 2

        prefix_format: PrefixFormat = Field(
            ..., description="Format company name, person name and role title to be used for the query's prefix string in the final query.")
        suffix_query: str = Field(
            ..., description="Query provided by used that will be appended to the prefix formatted string above.")
        num_results: int = Field(
            ..., description="Number of search results to lookup for given query. Cannot exceed 100.")

        @field_validator('num_results', mode='before')
        @classmethod
        def validate_num_results(cls, v):
            if v < 1 or v > 100:
                raise ValueError(
                    f"Num results have to between 1-100 in search query config, got: {v}")
            return v

    person_name: str = Field(...,
                             description="Full name of person being looked up.")
    company_name: str = Field(...,
                              description="Name of the company person is associated with.")
    person_role_title: str = Field(...,
                                   description="Role title of the person in the company.")
    existing_urls: List[str] = Field(
        ..., description="URLs that have already been fetched previously using web search.")
    query_configs: List[QueryConfig] = Field(
        ..., description="List of query configurations for given request.")

    @field_validator('query_configs', mode='before')
    @classmethod
    def validate_query_configs(cls, v):
        """Convert date object to datetime object."""
        if len(v) == 0:
            raise ValueError(
                "Query config list cannot be empty in search request.")
        return v


class GoogleCustomSearchResponse(BaseModel):
    """Wraper around Google Custom Search API response. Contains a subset of all the response fields.

    Reference: https://developers.google.com/custom-search/v1/reference/rest/v1/Search
    """
    class QueriesObject(BaseModel):
        class RequestObject(BaseModel):
            count: int = Field(
                ..., description="Number of search results returned for given request.")
        request: List[RequestObject] = Field(...,
                                             description="Current request results.")
        nextPage: Optional[List[RequestObject]] = Field(
            default=None, description="Next page to query for search results.")

    class SearchResult(BaseModel):
        """Search result object."""
        link: str = Field(
            default=None, description="URL of the search result.")
        title: Optional[str] = Field(
            default=None, description="Title of the search result page.")

    queries: QueriesObject = Field()
    items: List[SearchResult] = Field(...,
                                      description="List of search result Items.")


class SearchEngineWorkflow:
    """Searches the web using search engine for content related to given person and their current company."""

    GOOGLE_CUSTOM_SEARCH_ENDPOINT = "https://www.googleapis.com/customsearch/v1"

    def __init__(self, database: Database, max_search_results_per_query: int = 20) -> None:
        self.database = database
        self.max_search_results_per_query = max_search_results_per_query
        self.blocklist_domains = set(
            ["crunchbase.com", "youtube.com", "twitter.com", "x.com", "facebook.com", "quora.com", "bloomberg.com", "zoominfo.com", "clay.com"])

    def get_search_results(self, search_request: SearchRequest) -> Dict[str, List[str]]:
        """Returns search results as a dictionary mapping each search query to a list of URLs for the given request."""
        person_name: str = search_request.person_name
        company_name: str = search_request.company_name
        person_role_title: str = search_request.person_role_title

        already_fetched_urls: Set[str] = set(search_request.existing_urls)
        search_results_map: Dict[str, List[str]] = {}
        for config in search_request.query_configs:
            # Construct search query.
            search_query: str = ""
            if config.prefix_format == SearchRequest.QueryConfig.PrefixFormat.COMPANY_ROLE_LEAD_POSSESSION:
                search_query += f"{company_name} {person_role_title} {person_name}'s "
            elif config.prefix_format == SearchRequest.QueryConfig.PrefixFormat.COMPANY_POSSESSION:
                search_query += f"{company_name}'s "

            search_query += config.suffix_query
            num_results: int = config.num_results
            # This is configured so that Google only returns URLs with company name mentioned.
            # TODO: Test if this is skipping false negatives.
            exact_terms = company_name

            # Fetch search results from API call.
            result_urls: List[str] = self.api_search(
                search_query=search_query, num_results=num_results, exact_terms=exact_terms, skip_urls=already_fetched_urls)
            already_fetched_urls = already_fetched_urls.union(set(result_urls))

            search_results_map[search_query] = result_urls

        return search_results_map

    def api_search(self, search_query: str, num_results: int, exact_terms: str, skip_urls: Set[str]) -> List[str]:
        """
        Returns a list of Web Search Result URLs for given search query.
        It does this by repeatedly calling Custom Search API until given number of results are fetched.
        URLS that already exist in the skip_urls set will be skipped and not returned.

        API reference: https://developers.google.com/custom-search/v1/reference/rest/v1/cse/list.
        """
        logger.info(f"Fetching search results for query: {search_query}")
        # This is the max page size per documentation.

        page_size: int = 10
        num_pages = int(num_results/page_size) + \
            (0 if num_results % page_size == 0 else 1)
        result_urls: List[str] = []
        for page_num in range(num_pages):
            start = page_num*page_size + 1
            params = {
                "key": os.environ["GOOGLE_CUSTOM_SEARCH_API_KEY"],
                "cx": os.environ["GOOGLE_PROGRAMMABLE_SEARCH_ENGINE_ID"],
                "q": search_query,
                # Results that date back to up to a year.
                "dateRestrict": "y1",
                "lr": "lang_en",
                # Offset for paginated query. Starts at 1.
                "start": start,
                # Min value: 1, Max value: 10.
                "num": page_size,
                "filter": "1",
                "exactTerms": exact_terms,
                "safe": "active",
            }
            response_dict = requests.get(
                SearchEngineWorkflow.GOOGLE_CUSTOM_SEARCH_ENDPOINT, params=params).json()
            search_response = GoogleCustomSearchResponse(**response_dict)

            if not search_response.queries.nextPage:
                # No more search results avaiable, exit.
                break
            for search_result in search_response.items:
                url = search_result.link
                if LinkedInScraper.is_valid_profile_or_company_url(url=url):
                    # This is a person's profile or Company About page on LinkedIn, skip it.
                    continue
                if self.is_blocklist_domain(url=url):
                    # Although blocklisted domains are already updated in the Programmable Search Engine console,
                    # we also manually skip them in the filtered results to be safe.
                    continue
                if url in skip_urls:
                    # User has asked to skip this URL.
                    continue

                # We assume the result URLs for the same query across pages is deduplicated by Google.
                result_urls.append(url)

        logger.info(
            f"Search for query: {search_query} complete. Wanted: {num_results} results, Got: {len(result_urls)}")
        return result_urls

    def get_unofficial_google_search_results(self, search_queries: List[str], max_results_per_query: int) -> Dict[str, List[str]]:
        """Returns search result links for given search query using Google.

        DO NOT use in production unless tested. It may result in 429 errors due to it being an unofficial library.
        """
        # Loads all user agents.
        all_user_agents = []
        with gzip.open("app/user_agents.txt.gz", 'rt') as f:
            for line in f.readlines():
                all_user_agents.append(line.strip())

        results = {}
        for query in search_queries:
            results[query] = []
            logger.info(
                f"Search query: {query}, max results: {max_results_per_query}")
            for url in search(query, stop=max_results_per_query, user_agent=random.choice(all_user_agents)):

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


if __name__ == "__main__":
    # query = "aniket bajpai limechat ceo recent linkedin posts"
    # query = "Zachary Perret Plaid CEO recent LinkedIn posts"
    # query = "Anuj Kapur CEO Cloudbees recent articles or blogs"

    # profile_url = "https://www.linkedin.com/in/zperret"
    # write_profile_to_db(db, profile_url)\
    import json
    from dotenv import load_dotenv
    load_dotenv()
    load_dotenv(".env.dev")

    # Zach perret Profile ID.
    person_profile_id = '66a70cc8ff3944ed08fe4f1c'
    company_profile_id = '66a7a6b5066fac22c378bd75'

    wf = SearchEngineWorkflow(database=Database())
    # wf.run(person_profile_id=person_profile_id,
    #        company_profile_id=company_profile_id)

    # "Plaid's product launches"
    # "Plaid CEO & Cofounder Zachary Perret's LinkedIn Posts"
    # "Plaid CEO & Cofounder Zachary Perret's interviews or podcasts"
    # "Plaid CEO & Cofounder Zachary Perret's blogs"
    # "Plaid CEO & Cofounder Zachary Perret's recent events or conferences attended"
    # "Plaid CEO & Cofounder Zachary Perret's personal recognitions"
    # "Plaid's recent recognitions"
    # "Plaid's recent achievements"
    # "Plaid CEO & Cofounder Zachary Perret's thoughts on the industry"
    # "Plaid's business challenges"
    # "Plaid's challenges as a company"
    existing_urls = []
    with open("example_linkedin_info/google_custom_search_results/existing_urls.json", "r") as f:
        existing_urls = json.loads(f.read())

    search_request = SearchRequest(
        person_name="Zachary Perret",
        company_name="Plaid",
        person_role_title="CEO & Cofounder",
        existing_urls=existing_urls,
        query_configs=[
            SearchRequest.QueryConfig(
                prefix_format=SearchRequest.QueryConfig.PrefixFormat.COMPANY_POSSESSION,
                suffix_query="product launches",
                num_results=10,
            ),
            SearchRequest.QueryConfig(
                prefix_format=SearchRequest.QueryConfig.PrefixFormat.COMPANY_ROLE_LEAD_POSSESSION,
                suffix_query="LinkedIn Posts",
                num_results=20,
            ),
            SearchRequest.QueryConfig(
                prefix_format=SearchRequest.QueryConfig.PrefixFormat.COMPANY_POSSESSION,
                suffix_query="recent achievements",
                num_results=10,
            ),
            SearchRequest.QueryConfig(
                prefix_format=SearchRequest.QueryConfig.PrefixFormat.COMPANY_POSSESSION,
                suffix_query="recent recognitions",
                num_results=10,
            ),
            SearchRequest.QueryConfig(
                prefix_format=SearchRequest.QueryConfig.PrefixFormat.COMPANY_ROLE_LEAD_POSSESSION,
                suffix_query="thoughts on the industry",
                num_results=20,
            ),
        ],
    )
    results = wf.get_search_results(search_request=search_request)
    with open("example_linkedin_info/google_custom_search_results/se_test_0.json", "w") as f:
        f.write(json.dumps(results, indent=4))
