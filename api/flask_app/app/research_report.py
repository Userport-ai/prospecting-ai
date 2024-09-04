import logging
from typing import Optional, List, Dict, Set
from datetime import datetime
from dateutil.relativedelta import relativedelta
from itertools import chain
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

    def __init__(self, database: Database) -> None:
        self.database = database
        self.search_engine_workflow = SearchEngineWorkflow()
        self.outreach_template_matcher = OutreachTemplateMatcher(
            database=database)
        self.personalization = Personalization(database=database)

    def create(self, user_id: str, person_linkedin_url: str) -> LeadResearchReport:
        """Creates Research report in the database for given lead's LinkedIn URL and given user and returns the report."""
        lead_research_report = LeadResearchReport()

        # Compute person profile ID.
        person_profile: Optional[PersonProfile] = self.database.get_person_profile_by_url(
            person_linkedin_url=person_linkedin_url)
        if not person_profile:
            logger.info(
                f"Person LinkedIn profile: {person_linkedin_url} NOT found in database.")
            linkedin_scraper = LinkedInScraper()
            person_profile = linkedin_scraper.fetch_person_profile(
                profile_url=person_linkedin_url)
            lead_research_report.person_profile_id = self.database.insert_person_profile(
                person_profile=person_profile)
        else:
            logger.info(
                f"Person LinkedIn profile: {person_linkedin_url} profile found in database.")
            lead_research_report.person_profile_id = person_profile.id

        # Compute company profile ID.
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
            lead_research_report.company_profile_id = self.database.insert_company_profile(
                company_profile=company_profile)
        else:
            logger.info(
                f"Company {company_linkedin_url} profile found in database.")
            lead_research_report.company_profile_id = company_profile.id

        # Add to database.
        lead_research_report.person_linkedin_url = person_linkedin_url
        lead_research_report.company_name = company_name
        lead_research_report.person_name = person_profile.full_name
        lead_research_report.person_role_title = role_title
        lead_research_report.status = LeadResearchReport.Status.BASIC_PROFILE_FETCHED
        lead_research_report.company_headcount = company_profile.company_size_on_linkedin
        lead_research_report.company_industry_categories = company_profile.categories
        lead_research_report.user_id = user_id

        # Insert to database.
        id: str = self.database.insert_lead_research_report(
            lead_research_report=lead_research_report)
        lead_research_report.id = id
        return lead_research_report

    def fetch_search_results(self, lead_research_report_id: str):
        """Fetch and store search results for given lead."""
        research_report: LeadResearchReport = self.database.get_lead_research_report(
            lead_research_report_id=lead_research_report_id)

        company_name = research_report.company_name
        person_name: str = research_report.person_name
        role_title: str = research_report.person_role_title
        existing_search_results_map: Optional[Dict[str,
                                                   List[str]]] = research_report.search_results_map
        existing_urls: List[str] = list(
            chain.from_iterable(existing_search_results_map.values())) if existing_search_results_map else []

        # Queries to consider = ["recent LinkedIn posts", "recent product launches", "recent thoughts on the industry",
        #    "recent articles or blogs", "recent interviews or podcasts",
        #    "recent events or conferences attended",  "recent funding announcements",
        #    "recent leadership changes", "recent announcements made"]
        search_request = SearchRequest(
            person_name=person_name,
            company_name=company_name,
            person_role_title=role_title,
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
                    num_results=10,
                ),
                SearchRequest.QueryConfig(
                    prefix_format=SearchRequest.QueryConfig.PrefixFormat.COMPANY_ROLE_LEAD_POSSESSION,
                    suffix_query="blogs",
                    num_results=10,
                ),
                SearchRequest.QueryConfig(
                    prefix_format=SearchRequest.QueryConfig.PrefixFormat.COMPANY_ROLE_LEAD_POSSESSION,
                    suffix_query="interviews or podcasts",
                    num_results=10,
                ),
                # SearchRequest.QueryConfig(
                #     prefix_format=SearchRequest.QueryConfig.PrefixFormat.COMPANY_ROLE_LEAD_POSSESSION,
                #     suffix_query="personal recognitions",
                #     num_results=10,
                # ),
                SearchRequest.QueryConfig(
                    prefix_format=SearchRequest.QueryConfig.PrefixFormat.COMPANY_POSSESSION,
                    suffix_query="recent achievements",
                    num_results=10,
                ),
                SearchRequest.QueryConfig(
                    prefix_format=SearchRequest.QueryConfig.PrefixFormat.COMPANY_ROLE_LEAD_POSSESSION,
                    suffix_query="thoughts on the industry",
                    num_results=10,
                ),
                # SearchRequest.QueryConfig(
                #     prefix_format=SearchRequest.QueryConfig.PrefixFormat.COMPANY_ROLE_LEAD_POSSESSION,
                #     suffix_query="recent talks or events or conferences attended",
                #     num_results=10,
                # ),
                SearchRequest.QueryConfig(
                    prefix_format=SearchRequest.QueryConfig.PrefixFormat.COMPANY_POSSESSION,
                    suffix_query="funding announcements",
                    num_results=10,
                ),
                SearchRequest.QueryConfig(
                    prefix_format=SearchRequest.QueryConfig.PrefixFormat.COMPANY_POSSESSION,
                    suffix_query="recent news",
                    num_results=10,
                ),
                SearchRequest.QueryConfig(
                    prefix_format=SearchRequest.QueryConfig.PrefixFormat.COMPANY_POSSESSION,
                    suffix_query="recent partnerships",
                    num_results=10,
                ),
                SearchRequest.QueryConfig(
                    prefix_format=SearchRequest.QueryConfig.PrefixFormat.COMPANY_POSSESSION,
                    suffix_query="recent leadership hires",
                    num_results=10,
                ),
            ],
        )

        # Get search results and update them in the database.
        search_results_map: Dict[str, List[str]] = self.search_engine_workflow.get_search_results(
            search_request=search_request)

        # Merge new results with existing results.
        updated_search_results_map = existing_search_results_map.copy(
        ) if existing_search_results_map else {}
        for result_query in search_results_map:
            if result_query in updated_search_results_map:
                # Append new URLs
                updated_search_results_map[result_query].extend(
                    search_results_map[result_query])
            else:
                # Create new entry in updated_search_result.
                updated_search_results_map[result_query] = search_results_map[result_query].copy(
                )

        setFields = {
            "search_results_map": updated_search_results_map,
            "status": LeadResearchReport.Status.URLS_FROM_SEARCH_ENGINE_FETCHED,
        }
        self.database.update_lead_research_report(
            lead_research_report_id=lead_research_report_id, setFields=setFields)

    def process_content_in_search_urls(self, lead_research_report_id: str, search_results_batch: List[List[str]], task_num: int) -> List[str]:
        """Process URLs stored in given search results batch in a research report and return URLs that failed to process."""
        research_report: LeadResearchReport = self.database.get_lead_research_report(
            lead_research_report_id=lead_research_report_id)

        content_parsing_failed_results: List[List[str]] = []
        for search_result in search_results_batch:
            search_query, url = search_result
            try:
                logger.info(
                    f"Start processing search URL: {url} in task num: {task_num}")
                self.process_content(
                    url=url, search_query=search_query, research_report=research_report)
                logger.info(
                    f"Completed processing for search URL: {url} in task num: {task_num}")
            except Exception as e:
                logger.warning(
                    f"Failed to process content from search URL: {url} with error: {e}")
                content_parsing_failed_results.append(search_result)

        logger.info(
            f"Trying {len(content_parsing_failed_results)} failed URLs now for task num: {task_num}.")
        # Retry URLs that failed to process one more time.
        # Sometimes failures can be intermittent, so better to retry whenver possible.
        final_failed_urls: List[str] = []
        for failed_url_result in content_parsing_failed_results:
            failed_query, failed_url = failed_url_result
            try:
                logger.info(
                    f"Start processing failed search URL: {failed_url} in task num: {task_num}")
                self.process_content(
                    url=failed_url, search_query=failed_query, research_report=research_report)
                logger.info(
                    f"Completed processing for failed search URL: {failed_url} in task num: {task_num}")
            except Exception as e:
                logger.warning(
                    f"During retry: failed to process content from search URL: {failed_url} with error: {e}")
                final_failed_urls.append(failed_url)

        return final_failed_urls

    def process_content(self, url: str, search_query: str, research_report: LeadResearchReport):
        """Fetch content from given URL, process it and store it in the database."""
        # If this URL has already been indexed for this company, skip processing.
        if self.database.get_content_details_by_url(url=url, company_profile_id=research_report.company_profile_id):
            logger.info(
                f"Web URL: {url} already indexed in the database for report: {research_report.id}, skip processing again.")
            return

        # Fetch page and then process content.
        page_scraper = WebPageScraper(url=url)

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
            search_engine_query=search_query,
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

        # Only filter documents from recent months.
        report_publish_cutoff_date = time_now - relativedelta(months=12)

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

    def choose_outreach_email_template(self, lead_research_report_id: str):
        """Choose Email template for the lead based on their persona."""
        chosen_outreach_email_template: LeadResearchReport.ChosenOutreachEmailTemplate = self.outreach_template_matcher.match(
            lead_research_report_id=lead_research_report_id)

        # Update lead research report.
        setFields = {
            "status": LeadResearchReport.Status.EMAIL_TEMPLATE_SELECTION_COMPLETE,
            # We are allowing templates to be None.
            "chosen_outreach_email_template": chosen_outreach_email_template.model_dump() if chosen_outreach_email_template else None,
        }
        self.database.update_lead_research_report(
            lead_research_report_id=lead_research_report_id, setFields=setFields)
        logger.info(
            f"Completed Choosing Outreach Email Template for lead report: {lead_research_report_id}")

    def generate_personalized_emails(self, lead_research_report_id: str):
        """Generate personalized emails for lead based on their profile and email templates."""
        personalized_emails: List[LeadResearchReport.PersonalizedEmail] = self.personalization.generate_personalized_emails(
            lead_research_report_id=lead_research_report_id)
        personalized_emails_tokens_used: OpenAITokenUsage = self.personalization.get_tokens_used()

        # Update lead research report.
        personalized_emails_dict_list: List[Dict] = self.database.get_db_ready_personalized_emails(
            personalized_emails=personalized_emails)
        setFields = {
            "status": LeadResearchReport.Status.COMPLETE,
            "personalized_emails": personalized_emails_dict_list,
            "personalized_emails_tokens_used": personalized_emails_tokens_used.model_dump(),
        }
        self.database.update_lead_research_report(
            lead_research_report_id=lead_research_report_id, setFields=setFields)
        logger.info(
            f"Completed Generating personalized emails for lead report: {lead_research_report_id}")

    def update_template_and_regen_emails(self, lead_research_report_id: str, selected_template_id: str):
        """Updates existing lead research report with selected template and regenerates personalized emails using that template."""
        outreach_email_template: OutreachEmailTemplate = self.database.get_outreach_email_template(
            outreach_email_template_id=selected_template_id)
        lead_research_report: LeadResearchReport = self.database.get_lead_research_report(
            lead_research_report_id=lead_research_report_id)

        chosen_outreach_email_template: LeadResearchReport.ChosenOutreachEmailTemplate = OutreachTemplateMatcher.from_outreach_template(
            outreach_email_template=outreach_email_template)
        regenned_personalized_emails: List[LeadResearchReport.PersonalizedEmail] = self.personalization.regenerate_personalized_emails(
            lead_research_report=lead_research_report, chosen_outreach_email_template=chosen_outreach_email_template)

        # Add email tokens used to existing email tokens object in the report.
        total_tokens_used_so_far: OpenAITokenUsage = lead_research_report.personalized_emails_tokens_used.add_tokens(
            self.personalization.get_tokens_used())

        # Update lead research report.
        personalized_emails_dict_list: List[Dict] = self.database.get_db_ready_personalized_emails(
            personalized_emails=regenned_personalized_emails)
        setFields = {
            "status": LeadResearchReport.Status.COMPLETE,
            "chosen_outreach_email_template": chosen_outreach_email_template.model_dump(),
            "personalized_emails": personalized_emails_dict_list,
            "personalized_emails_tokens_used": total_tokens_used_so_far.model_dump(),
        }
        self.database.update_lead_research_report(
            lead_research_report_id=lead_research_report_id, setFields=setFields)

        logger.info(
            f"Completed template update and regenning of personalized emails for lead report: {lead_research_report_id}")


if __name__ == "__main__":
    # Zach perret Profile ID.
    person_url = "https://www.linkedin.com/in/zperret"
    # person_profile_id = '66a70cc8ff3944ed08fe4f1c'
    # company_profile_id = '66a7a6b5066fac22c378bd75'

    rp = Researcher(database=Database())
    # logger.info(
    #     f"Got {len(search_results)} search results for all the queries.")
    rp.aggregate(lead_research_report_id="66ab9633a3bb9048bc1a0be5")
