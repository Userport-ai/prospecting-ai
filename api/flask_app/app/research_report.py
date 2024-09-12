import logging
from typing import Optional, List, Dict, Set
from datetime import datetime
from dateutil.relativedelta import relativedelta
from app.utils import Utils
from app.database import Database
from app.linkedin_scraper import LinkedInScraper
from app.search_engine_workflow import SearchEngineWorkflow, SearchRequest
from app.web_page_scraper import WebPageScraper, PageContentInfo
from app.outreach_template import OutreachTemplateMatcher
from app.personalization import Personalization
from app.models import (
    ContentDetails,
    ContentTypeEnum,
    ContentCategoryEnum,
    WebPage,
    LinkedInPost,
    OpenAITokenUsage,
    LeadResearchReport,
    PersonProfile,
    CompanyProfile,
    OutreachEmailTemplate,
    content_category_to_human_readable_str
)

logger = logging.getLogger()


class Researcher:
    """Helper to create a research report for given person in a company from all relevant data in the database."""

    PERSONALIZED_MESSAGES_OPERATION_TAG_NAME = "personalized_messages"

    def __init__(self, database: Database) -> None:
        self.database = database
        self.search_engine_workflow = SearchEngineWorkflow()
        self.outreach_template_matcher = OutreachTemplateMatcher(
            database=database)
        self.personalization = Personalization(database=database)

    def enrich_lead_info(self, lead_research_report_id: str) -> str:
        """Enriches lead report with information such as name, their company, role etc."""
        research_report: LeadResearchReport = self.database.get_lead_research_report(
            lead_research_report_id=lead_research_report_id)

        # Compute person profile ID.
        person_profile_id: str = None
        person_linkedin_url: str = research_report.person_linkedin_url
        person_profile: Optional[PersonProfile] = self.database.get_person_profile_by_url(
            person_linkedin_url=person_linkedin_url)
        if not person_profile:
            logger.info(
                f"Person LinkedIn profile: {person_linkedin_url} NOT found in database.")
            linkedin_scraper = LinkedInScraper()
            person_profile = linkedin_scraper.fetch_person_profile(
                profile_url=person_linkedin_url)
            person_profile_id = self.database.insert_person_profile(
                person_profile=person_profile)
        else:
            logger.info(
                f"Person LinkedIn profile: {person_linkedin_url} profile found in database.")
            # TODO: Force Fetch profile from API if it is stale (over a couple of months old).
            person_profile_id = person_profile.id

        # Compute company profile ID.
        company_profile_id: str = None
        company_name, role_title = person_profile.get_company_and_role_title()
        company_linkedin_url = person_profile.get_company_linkedin_url(
            company_name=company_name)
        company_profile: Optional[CompanyProfile] = self.database.get_company_profile_by_url(
            company_linkedin_url=company_linkedin_url)
        if not company_profile:
            logger.info(
                f"Company {company_linkedin_url} profile NOT found in database.")
            linkedin_scraper = LinkedInScraper()
            company_profile = linkedin_scraper.fetch_company_profile(
                profile_url=company_linkedin_url)
            company_profile_id = self.database.insert_company_profile(
                company_profile=company_profile)
        else:
            logger.info(
                f"Company {company_linkedin_url} profile found in database.")
            company_profile_id = company_profile.id

        setFields = {
            "person_profile_id": person_profile_id,
            "company_profile_id": company_profile_id,
            "company_name": company_name,
            "person_name": person_profile.full_name,
            "person_role_title": role_title,
            "company_headcount": company_profile.company_size_on_linkedin,
            "company_industry_categories": company_profile.categories,
            "status":  LeadResearchReport.Status.BASIC_PROFILE_FETCHED,
        }
        self.database.update_lead_research_report(
            lead_research_report_id=lead_research_report_id, setFields=setFields)

    def fetch_search_results(self, lead_research_report_id: str):
        """Fetch and store search results for given lead."""
        research_report: LeadResearchReport = self.database.get_lead_research_report(
            lead_research_report_id=lead_research_report_id)

        company_name = research_report.company_name
        person_name: str = research_report.person_name
        role_title: str = research_report.person_role_title
        existing_web_search_results: Optional[LeadResearchReport.WebSearchResults] = research_report.web_search_results
        existing_urls: List[str] = [
            r.url for r in existing_web_search_results.results] if existing_web_search_results else []

        search_request = SearchRequest(
            person_name=person_name,
            company_name=company_name,
            person_role_title=role_title,
            existing_urls=existing_urls,
            query_configs=self._get_query_configs(exhaustive_search=False),
        )
        # Get search results and update them in the database.
        web_search_results: LeadResearchReport.WebSearchResults = self.search_engine_workflow.get_search_results(
            search_request=search_request)

        # Merge new results with existing results if any.
        if existing_web_search_results and existing_web_search_results.results:
            web_search_results.results.extend(
                existing_web_search_results.results)
            web_search_results.num_results = len(web_search_results.results)

        setFields = {
            "web_search_results": web_search_results.model_dump(),
            "status": LeadResearchReport.Status.URLS_FROM_SEARCH_ENGINE_FETCHED,
        }
        self.database.update_lead_research_report(
            lead_research_report_id=lead_research_report_id, setFields=setFields)

    def _get_query_configs(self, exhaustive_search: bool) -> List[SearchRequest.QueryConfig]:
        """Return query configs used for searching the web depending type of searcg requested by the user."""
        # Queries to consider = ["recent LinkedIn posts", "recent product launches", "recent thoughts on the industry",
        #    "recent articles or blogs", "personal recognitions", "recent interviews or podcasts",
        #    "recent talks or events or conferences attended",  "recent funding announcements",
        #    "recent leadership changes", "recent announcements made"]
        # The most important configs that are required for every search.
        base_search_configs = [
            SearchRequest.QueryConfig(
                prefix_format=SearchRequest.QueryConfig.PrefixFormat.COMPANY_POSSESSION,
                suffix_query="product launches",
                num_results_per_method=10,
                methods=[
                    SearchRequest.QueryConfig.Method.GOOGLE_CUSTOM_SEARCH_API],
            ),
            SearchRequest.QueryConfig(
                prefix_format=SearchRequest.QueryConfig.PrefixFormat.COMPANY_POSSESSION,
                suffix_query="recent achievements",
                num_results_per_method=10,
                methods=[
                    SearchRequest.QueryConfig.Method.GOOGLE_CUSTOM_SEARCH_API],
            ),
            SearchRequest.QueryConfig(
                prefix_format=SearchRequest.QueryConfig.PrefixFormat.COMPANY_ROLE_LEAD_POSSESSION,
                suffix_query="recent LinkedIn Posts",
                num_results_per_method=10,
                methods=[
                    SearchRequest.QueryConfig.Method.UNOFFICIAL_GOOGLE_SEARCH_LIBRARY],
            ),
        ]
        if exhaustive_search:
            base_search_configs.extend([
                SearchRequest.QueryConfig(
                    prefix_format=SearchRequest.QueryConfig.PrefixFormat.COMPANY_POSSESSION,
                    suffix_query="recent blogs or articles",
                    num_results_per_method=10,
                    methods=[SearchRequest.QueryConfig.Method.GOOGLE_CUSTOM_SEARCH_API,
                             SearchRequest.QueryConfig.Method.UNOFFICIAL_GOOGLE_SEARCH_LIBRARY],
                ),
                SearchRequest.QueryConfig(
                    prefix_format=SearchRequest.QueryConfig.PrefixFormat.COMPANY_POSSESSION,
                    suffix_query="funding announcements",
                    num_results_per_method=5,
                    methods=[SearchRequest.QueryConfig.Method.GOOGLE_CUSTOM_SEARCH_API,
                             SearchRequest.QueryConfig.Method.UNOFFICIAL_GOOGLE_SEARCH_LIBRARY],
                ),
                SearchRequest.QueryConfig(
                    prefix_format=SearchRequest.QueryConfig.PrefixFormat.COMPANY_POSSESSION,
                    suffix_query="recent partnerships",
                    num_results_per_method=5,
                    methods=[SearchRequest.QueryConfig.Method.GOOGLE_CUSTOM_SEARCH_API,
                             SearchRequest.QueryConfig.Method.UNOFFICIAL_GOOGLE_SEARCH_LIBRARY],
                ),
                SearchRequest.QueryConfig(
                    prefix_format=SearchRequest.QueryConfig.PrefixFormat.COMPANY_POSSESSION,
                    suffix_query="recent leadership hires",
                    num_results_per_method=5,
                    methods=[SearchRequest.QueryConfig.Method.GOOGLE_CUSTOM_SEARCH_API,
                             SearchRequest.QueryConfig.Method.UNOFFICIAL_GOOGLE_SEARCH_LIBRARY],
                ),
                SearchRequest.QueryConfig(
                    prefix_format=SearchRequest.QueryConfig.PrefixFormat.COMPANY_ROLE_LEAD_POSSESSION,
                    suffix_query="interviews or podcasts",
                    num_results_per_method=10,
                    methods=[
                        SearchRequest.QueryConfig.Method.UNOFFICIAL_GOOGLE_SEARCH_LIBRARY],
                ),
                # SearchRequest.QueryConfig(
                #     prefix_format=SearchRequest.QueryConfig.PrefixFormat.COMPANY_ROLE_LEAD_POSSESSION,
                #     suffix_query="thoughts on the industry",
                #     num_results_per_method=10,
                #     methods=[
                #         SearchRequest.QueryConfig.Method.UNOFFICIAL_GOOGLE_SEARCH_LIBRARY],
                # ),
                # SearchRequest.QueryConfig(
                #     prefix_format=SearchRequest.QueryConfig.PrefixFormat.COMPANY_ROLE_LEAD_POSSESSION,
                #     suffix_query="personal recognitions",
                #     num_results=10,
                # ),
                # SearchRequest.QueryConfig(
                #     prefix_format=SearchRequest.QueryConfig.PrefixFormat.COMPANY_ROLE_LEAD_POSSESSION,
                #     suffix_query="recent talks or events or conferences attended",
                #     num_results=10,
                # ),
            ])
        return base_search_configs

    def process_content_in_search_urls(self, lead_research_report_id: str, search_results_batch: List[LeadResearchReport.WebSearchResults.Result], task_num: int) -> List[str]:
        """Process URLs stored in given search results batch in a research report and return URLs that failed to process."""
        research_report: LeadResearchReport = self.database.get_lead_research_report(
            lead_research_report_id=lead_research_report_id)

        content_parsing_failed_results: List[LeadResearchReport.WebSearchResults.Result] = [
        ]
        for search_result in search_results_batch:
            url: str = search_result.url
            try:
                logger.info(
                    f"Start processing search URL: {url} in task num: {task_num}")
                self.process_content(
                    search_result=search_result, research_report=research_report)
                logger.info(
                    f"Completed processing for search URL: {url} in task num: {task_num}")
            except Exception as e:
                logger.warning(
                    f"Failed to process content from search URL: {url} with error: {e}")
                content_parsing_failed_results.append(search_result)

        if len(content_parsing_failed_results) == 0:
            # Nothing to do.
            return []

        logger.info(
            f"Trying {len(content_parsing_failed_results)} failed URLs now for task num: {task_num}.")
        # Retry URLs that failed to process one more time.
        # Sometimes failures can be intermittent, so better to retry whenver possible.
        final_failed_urls: List[str] = []
        for failed_url_result in content_parsing_failed_results:
            failed_url: str = failed_url_result.url
            try:
                logger.info(
                    f"Start processing failed search URL: {failed_url} in task num: {task_num}")
                self.process_content(
                    search_result=search_result, research_report=research_report)
                logger.info(
                    f"Completed processing for failed search URL: {failed_url} in task num: {task_num}")
            except Exception as e:
                logger.warning(
                    f"During retry: failed to process content from search URL: {failed_url} with error: {e}")
                final_failed_urls.append(failed_url)

        return final_failed_urls

    def process_content(self, search_result: LeadResearchReport.WebSearchResults.Result, research_report: LeadResearchReport):
        """Fetch content from given URL, process it and store it in the database."""
        # If this URL has already been indexed for this company and has been processed successfully, skip processing again.
        if self.database.get_content_details_by_url(url=search_result.url, company_profile_id=research_report.company_profile_id, processing_status=ContentDetails.ProcessingStatus.COMPLETE):
            logger.info(
                f"Web URL: {search_result.url} already indexed in the database for report: {research_report.id}, skip processing again.")
            return

        # Fetch page and then process content.
        page_scraper = WebPageScraper(
            url=search_result.url, title=search_result.title, snippet=search_result.snippet)

        doc = page_scraper.fetch_page()

        page_content_info: PageContentInfo = page_scraper.fetch_page_content_info(
            doc=doc, company_name=research_report.company_name, person_name=research_report.person_name)

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
            )
            if post_details.repost:
                linkedin_post.repost = LinkedInPost(
                    url=post_details.repost.url,
                    author_name=post_details.repost.author_name,
                    author_type=post_details.repost.author_type,
                    author_profile_url=post_details.repost.author_profile_url,
                    author_headline=post_details.repost.author_headline,
                    author_follower_count=post_details.repost.author_follower_count,
                    publish_date=post_details.repost.publish_date,
                    text=post_details.repost.text,
                    text_links=post_details.repost.text_links,
                    card_links=post_details.repost.card_links,
                    num_reactions=post_details.repost.num_reactions,
                    num_comments=post_details.repost.num_comments,
                )

        content_details = ContentDetails(
            url=page_content_info.url,
            search_engine_query=search_result.query,
            person_name=research_report.person_name,
            company_name=research_report.company_name,
            person_role_title=research_report.person_role_title,
            person_profile_id=research_report.person_profile_id,
            company_profile_id=research_report.company_profile_id,
            processing_status=page_content_info.processing_status,
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

    def aggregate(self, lead_research_report_id: str):
        """Aggregate Details of research report for given Person and Company and updates them in the database."""
        research_report: LeadResearchReport = self.database.get_lead_research_report(
            lead_research_report_id=lead_research_report_id)

        time_now: datetime = Utils.create_utc_time_now()

        # Only filter documents from recent months. We use 15 since LinkedIn posts are configured to be at max 15 months old.
        report_publish_cutoff_date = time_now - relativedelta(months=15)

        stage_match_person_and_company = {
            "$match": {
                "person_profile_id": research_report.person_profile_id,
                "company_profile_id": research_report.company_profile_id,
            }
        }

        stage_match_publish_date = {
            "$match": {
                "publish_date": {"$gt": report_publish_cutoff_date}
            }
        }

        stage_match_category = {
            "$match": {
                "category": {"$nin": [None, ContentCategoryEnum.NONE_OF_THE_ABOVE.value]}
            }
        }

        stage_match_not_requesting_contact_info = {
            "$match": {
                "requesting_user_contact": {"$eq": False}
            }
        }

        # Skip results that show documentation of a website.
        stage_match_not_documentation = {
            "$match": {
                "type": {"$ne": ContentTypeEnum.DOCUMENTATION.value}
            }
        }

        # TODO: Add filter to focus on company. Existing docs for Perret have bad values for the doc
        # but we can try with new docs that we will index on.

        stage_project_fields = {
            "$project": {
                # These next 2 lines will remove _id MongoDB ID and replace with id in our storage.
                "_id": 0,
                "id": "$_id",
                "url": 1,
                "publish_date": 1,
                "concise_summary": 1,
                "category": 1,
            }
        }

        stage_group_by_category = {
            "$group": {
                "_id": "$category",
                "highlights": {"$push": "$$ROOT"}
            }
        }

        stage_final_projection = {
            "$project": {
                "_id": 0,
                "category": "$_id",
                "highlights": 1,
            }
        }

        pipeline = [
            stage_match_person_and_company,
            stage_match_publish_date,
            stage_match_category,
            stage_match_not_requesting_contact_info,
            stage_match_not_documentation,
            stage_project_fields,
            stage_group_by_category,
            stage_final_projection
        ]

        report_details: List[LeadResearchReport.ReportDetail] = []
        results = self.database.get_content_details_collection().aggregate(pipeline=pipeline)
        for detail in results:
            rep_detail = LeadResearchReport.ReportDetail(**detail)

            # Update publish date readable string manually.
            for highlight in rep_detail.highlights:
                # Convert to 02 August, 2024 format.
                highlight.publish_date_readable_str = highlight.publish_date.strftime(
                    "%d %B, %Y")
                # Update category human readable string manually.
                highlight.category_readable_str = content_category_to_human_readable_str(
                    category=highlight.category)

            # Update category human readable string manually.
            rep_detail.category_readable_str = content_category_to_human_readable_str(
                category=rep_detail.category)

            report_details.append(rep_detail)

        for detail in report_details:
            logger.info(f"Category: {detail.category}")
            logger.info(f"Num highlights: {len(detail.highlights)}")

        setFields = {
            "status": LeadResearchReport.Status.RECENT_NEWS_AGGREGATION_COMPLETE,
            "report_creation_date_readable_str": Utils.to_human_readable_date_str(time_now),
            "report_publish_cutoff_date": report_publish_cutoff_date,
            "report_publish_cutoff_date_readable_str": Utils.to_human_readable_date_str(report_publish_cutoff_date),
            "details": [detail.model_dump() for detail in report_details],
        }
        self.database.update_lead_research_report(
            lead_research_report_id=lead_research_report_id, setFields=setFields)

        logger.info(f"Done with aggregating report: {lead_research_report_id}")

    def choose_template_and_create_emails(self, lead_research_report_id: str):
        """Chooses Email template for the lead automatically based on their persona using LLM.

        This should only be called when the lead report is being created for the first time.
        Thereafter, all new templates are manually selected by the user and should not enter this flow.
        """
        lead_research_report: LeadResearchReport = self.database.get_lead_research_report(
            lead_research_report_id=lead_research_report_id)
        if lead_research_report.personalized_outreach_messages:
            raise ValueError(
                f"Choosing outreach email template: Expected personalized_outreach_messages to be None, got non None value for report ID: {lead_research_report_id}")
        # Total tokens used in choosing template and generating personalized emails.
        total_tokens_used: Optional[OpenAITokenUsage] = OpenAITokenUsage(
            operation_tag=Researcher.PERSONALIZED_MESSAGES_OPERATION_TAG_NAME, prompt_tokens=0, completion_tokens=0, total_tokens=0, total_cost_in_usd=0)

        # Select outreach template to use for given lead.
        selected_email_template: Optional[LeadResearchReport.ChosenOutreachEmailTemplate] = self.outreach_template_matcher.match(
            lead_research_report=lead_research_report)
        selected_email_template_tokens_used: Optional[OpenAITokenUsage] = self.outreach_template_matcher.get_tokens_used(
        )
        if selected_email_template_tokens_used:
            total_tokens_used.add_tokens(
                selected_email_template_tokens_used)

        # Create personalized emails from chosen template.
        personalized_emails: List[LeadResearchReport.PersonalizedEmail] = self.personalization.generate_personalized_emails(
            email_template=selected_email_template, lead_research_report=lead_research_report)
        personalized_emails_tokens_used: Optional[OpenAITokenUsage] = self.personalization.get_tokens_used(
        )
        if personalized_emails_tokens_used:
            total_tokens_used.add_tokens(personalized_emails_tokens_used)

        # Create personalized messages using list of generated personalized emails.
        personalized_outreach_messages = LeadResearchReport.PersonalizedOutreachMessages(
            personalized_emails=personalized_emails, total_tokens_used=total_tokens_used)

        # Update lead research report.
        setFields = {
            "status": LeadResearchReport.Status.COMPLETE,
            "personalized_outreach_messages": personalized_outreach_messages.model_dump(),
        }
        self.database.update_lead_research_report(
            lead_research_report_id=lead_research_report_id, setFields=setFields)
        logger.info(
            f"Completed Choosing template and creating personalized emails for lead report ID: {lead_research_report_id}")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    load_dotenv(".env.dev")
    # Zach perret Profile ID.
    person_url = "https://www.linkedin.com/in/zperret"
    # person_profile_id = '66a70cc8ff3944ed08fe4f1c'
    # company_profile_id = '66a7a6b5066fac22c378bd75'

    rp = Researcher(database=Database())
    # logger.info(
    #     f"Got {len(search_results)} search results for all the queries.")
    # rp.aggregate(lead_research_report_id="66ab9633a3bb9048bc1a0be5")
