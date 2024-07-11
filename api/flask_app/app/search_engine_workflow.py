from googlesearch import search
from typing import List
from linkedin_scraper import LinkedInScraper, LinkedInPost
from database import Database
from utils import Utils
from models import (
    CurrentEmployment,
    WebSearchResult,
    SearchEngineMetadata,
    ContentType,
    ContentCategory,
    LinkedInPostReference
)


class SearchEngineWorkflow:
    """Searches the web using search engine for content related to given person and their current company.

    The resultant content is then fetched, categorized and finally stored in the database.
    """
    GOOGLE_SEARCH_ENGINE = "google"

    def __init__(self, database: Database, max_search_results_per_query: int = 10) -> None:
        self.database = database
        self.max_search_results_per_query = max_search_results_per_query

    def run(self, current_employment: CurrentEmployment) -> List[str]:
        """Performs web search for given person in their current employment.

        Content for the fetched links are then parsed.
        """
        search_query: str = SearchEngineWorkflow.get_recent_linkedin_posts_query(
            current_employment=current_employment)
        web_search_metadata = SearchEngineMetadata.create(
            name=SearchEngineWorkflow.GOOGLE_SEARCH_ENGINE, query=search_query)
        for url in search(search_query, stop=self.max_search_results_per_query):
            # Check if URL already exists in database, if so skip it.
            if self.database.get_web_search_result_by_url(url=url):
                print(
                    f"Web URL: {url} already stored in in database, skipping parsing again.")
                continue

            if LinkedInScraper.is_valid_post(post_url=url):
                linkedin_post: LinkedInPost
                try:
                    # Fetch Post details from scraper.
                    linkedin_post = LinkedInScraper.fetch_linkedin_post(
                        post_url=url)
                except Exception as e:
                    # Log error and continue to the next URL.
                    print(
                        f"Failed to scrape LinkedIn post: {url} with error: {e}")
                    continue

                # Convert to websearch result and write to to database.
                # TODO: Compute content category and summary and mark as None.
                time_now = Utils.create_utc_time_now()
                web_search_result = WebSearchResult(
                    current_employment=current_employment,
                    web_search_metadata=web_search_metadata,
                    url=url,
                    created_on=time_now,
                    content_publish_date=linkedin_post.date_published,
                    content_type=ContentType.LINKEDIN_POST,
                    content_category=None,
                    content_short_summary=None,
                    is_relevant_content=None,
                    not_relevant_content_reason=None
                )

                # Write LinkedIn post and web search result transactionally.
                try:
                    with self.database.transaction_session() as session:
                        post_id = self.database.insert_linkedin_post(
                            linkedin_post=linkedin_post, session=session)

                        # Add post storage reference to web search result.
                        web_search_result.content_extra_reference = LinkedInPostReference.create(
                            id=post_id)
                        self.database.insert_web_search_result(
                            web_search_result=web_search_result, session=session)
                except Exception as e:
                    # Log error and continue.
                    print(
                        f"Failed to write WebSearchResult to database for url: {url} with error: {e}")
                    continue

                # TODO: Remove this break once content parsing works.
                break

    @staticmethod
    def get_recent_linkedin_posts_query(current_employment: CurrentEmployment) -> str:
        """Returns search query for recent linkedin posts for person in given company."""
        return f"{current_employment.full_name} {current_employment.role_title} {current_employment.company_name} recent LinkedIn posts"


if __name__ == "__main__":
    # query = "aniket bajpai limechat ceo recent linkedin posts"
    # query = "Zachary Perret Plaid CEO recent LinkedIn posts"
    # query = "Anuj Kapur CEO Cloudbees recent articles or blogs"
    from bson.objectid import ObjectId
    db = database = Database()
    wf = SearchEngineWorkflow(database=db)
    current_emp = db.get_current_employment(
        person_profile_id=ObjectId("668eae5d8a5ac202c0215d7a"))
    wf.run(current_employment=current_emp)
