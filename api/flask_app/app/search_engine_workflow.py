from googlesearch import search
from web_page_scraper import WebPageScraper, PageContentInfo
from database import Database
from typing import List
from linkedin_scraper import LinkedInScraper
from models import (
    PersonProfile,
    ContentDetails,
    WebPage,
    LinkedInPost
)


class SearchEngineWorkflow:
    """Searches the web using search engine for content related to given person and their current company.

    The resultant content is then fetched, categorized and finally stored in the database.
    """
    GOOGLE_SEARCH_ENGINE = "google"

    def __init__(self, database: Database, max_search_results_per_query: int = 20) -> None:
        self.database = database
        self.max_search_results_per_query = max_search_results_per_query
        self.skip_sites = ["crunchbase.com"]

    def run(self, person_profile_id: str, company_profile_id: str):
        """Runs search queries, analyzes content for given person profile ID.

        The analyzed content is then saved to the database.
        """
        person_profile: PersonProfile = None
        try:
            person_profile = self.database.get_person_profile(
                person_profile_id=person_profile_id)
        except Exception as e:
            raise ValueError(
                f"Failed to fetch Person Profile in search workflow with id: {person_profile_id} with error: {e}")

        company_name, role_title = person_profile.get_company_and_role_title()
        person_name: str = person_profile.full_name
        all_search_queries: List[str] = self.get_all_search_queries(
            company_name=company_name, person_name=person_name, role_title=role_title)

        for search_query in all_search_queries:
            print(f"\nSearch query: {search_query}")
            print("-----------------------")
            for url in search(search_query, stop=self.max_search_results_per_query):
                print(f"\tGot URL {url} in search result.")

                if url in self.skip_sites:
                    print(f"\tURL: {url} is in skip list, so skip it.")
                    continue

                if LinkedInScraper.is_valid_profile_or_company_url(url=url):
                    # This is a person's profile or Company About page on LinkedIn, skip it.
                    print(
                        f"\tURL: {url} is a LinkedIn profile or Company, skip parsing it.")
                    continue

                # If this URL has already been indexed, skip processing.
                if self.database.get_content_details_by_url(url=url):
                    print(
                        f"\tWeb URL: {url} already indexed in the database, skip parsing again.")
                    continue

                try:
                    self.process_url(url=url, company_name=company_name, person_name=person_name,
                                     role_title=role_title, search_query=search_query, person_profile_id=person_profile_id, company_profile_id=company_profile_id)
                except Exception as e:
                    # Log error and continue.
                    print(
                        f"\tFailed to process search result URL: {url} for person: {person_profile_id} and query: {search_query} with error: {e}")

                # TODO: Remove this break once content parsing works.
                print("Done parsing for now!")
                break

    def process_url(self, url: str, company_name: str, person_name: str, role_title: str, search_query: str, person_profile_id: str, company_profile_id: str):
        """Process given URL from the web and stores the result in the database."""
        # Get page content.
        page_scraper = WebPageScraper(url=url)
        page_content_info: PageContentInfo = page_scraper.fetch_page_content_info(
            company_name=company_name, person_name=person_name)

        # Store content and any associated web page and linkedin post info to database.
        linkedin_post: LinkedInPost = None
        web_page = WebPage(
            url=page_content_info.url,
            header=page_content_info.page_structure.header,
            body=page_content_info.page_structure.body,
            footer=page_content_info.page_structure.footer
        )

        if page_content_info.linkedin_post_details:
            post_details = page_content_info.linkedin_post_details
            linkedin_post = LinkedInPost(
                url=post_details.url,
                author_name=post_details.author_name,
                author_type=post_details.author_type,
                author_profile_url=post_details.author_profile_url,
                author_headline=post_details.author_headline,
                author_follower_count=post_details.author_follower_count,
                publish_date=post_details.publish_date,
                text=post_details.text,
                text_links=post_details.text_links,
                card_links=post_details.card_links,
                num_reactions=post_details.num_reactions,
                num_comments=post_details.num_comments,
                repost=post_details.repost
            )

        content_details = ContentDetails(
            url=page_content_info.url,
            search_engine_query=search_query,
            person_name=person_name,
            company_name=company_name,
            person_role_title=role_title,
            person_profile_id=person_profile_id,
            company_profile_id=company_profile_id,
            type=page_content_info.type,
            type_reason=page_content_info.type_reason,
            author=page_content_info.author,
            publish_date=page_content_info.publish_date,
            detailed_summary=page_content_info.detailed_summary,
            concise_summary=page_content_info.concise_summary,
            category=page_content_info.category,
            category_reason=page_content_info.category_reason,
            key_persons=page_content_info.key_persons,
            key_organizations=page_content_info.key_organizations,
            requesting_user_contact=page_content_info.requesting_user_contact,
            focus_on_company=page_content_info.focus_on_company,
            focus_on_person=page_content_info.focus_on_person,
            num_linkedin_reactions=page_content_info.num_linkedin_reactions,
            num_linkedin_comments=page_content_info.num_linkedin_comments,
            openai_tokens_used=page_content_info.openai_usage.convert_to_model()
        )

        # Write to database transactionally.
        with self.database.transaction_session() as session:
            web_page_id = self.database.insert_web_page(
                web_page=web_page, session=session)
            if linkedin_post:
                post_id = self.database.insert_linkedin_post(
                    linkedin_post=linkedin_post, session=session)

            # Add web page and linkedin post storage reference to content details.
            content_details.web_page_ref_id = web_page_id
            if linkedin_post:
                content_details.linkedin_post_ref_id = post_id

            self.database.insert_content_details(
                content_details=content_details, session=session)

    def get_all_search_queries(self, company_name: str, person_name: str, role_title: str) -> List[str]:
        """Returns list of all search queries for given person employed in given company."""
        search_prefix = f"{company_name} {person_name} {role_title} "
        queries = ["recent LinkedIn posts", "recent thoughts on the industry",
                   "recent articles or blogs", "recent interviews or podcasts",
                   "recent conferences or events attended", "recent announcements made"]

        final_queries = []
        for q in queries:
            final_queries.append(search_prefix + q)
        return final_queries


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
    wf.run(person_profile_id=person_profile_id,
           company_profile_id=company_profile_id)
