import os
import logging
from typing import List, Optional
from datetime import datetime
from dateutil.relativedelta import relativedelta
from app.models import LinkedInActivity, ContentDetails, ContentCategoryEnum, OpenAITokenUsage
from app.linkedin_scraper import LinkedInScraper
from app.utils import Utils
from bs4 import BeautifulSoup
from markdownify import markdownify
from langchain_core.messages import SystemMessage
from langchain_community.callbacks import get_openai_callback
from langchain_core.prompts import HumanMessagePromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from app.metrics import Metrics

logger = logging.getLogger()


class LinkedInActivityParser:
    """Parses activity for a lead that is stored in the lead report."""

    RECENT_ACTIVITY = "recent-activity"
    ACTIVITY_POSTS = "all/"
    ACTIVITY_COMMENTS = "comments/"
    ACTIVITY_REACTIONS = "reactions/"

    def __init__(self, person_name: str, company_name: str, company_description: str, person_role_title: str, person_profile_id: str, company_profile_id: str) -> None:
        self.person_name = person_name
        self.company_name = company_name
        self.company_description = company_description
        self.person_role_title = person_role_title
        self.person_profile_id = person_profile_id
        self.company_profile_id = company_profile_id
        self.metrics = Metrics()

        # Constants.
        self.OPENAI_API_KEY = os.environ["OPENAI_USERPORT_API_KEY"]
        self.OPENAI_GPT_4O_MODEL = os.environ["OPENAI_GPT_4O_MODEL"]
        self.OPENAI_GPT_4O_MINI_MODEL = os.environ["OPENAI_GPT_4O_MINI_MODEL"]
        self.OPENAI_REQUEST_TIMEOUT_SECONDS = 20
        self.RAW_ACTIVITY_SYSTEM_MESSAGE = SystemMessage(content=(
            "You are a very intelligent and truthful sales person that analyzes recent LinkedIn activities of your prospect to extract useful information about them.\n"
            "You are given your prospect's name, the company they work for, their current role and the company description.\n"
            "You will also be given a text in Markdown format that represents a LinkedIn activity (a post, comment or reaction) associated with your prospect.\n"
            "The text will be delimited by triple quotes.\n"
            "Your job is to answer the user's questions using the information found in the text.\n"
            "\n"
            "**Prospect Details:**\n"
            f"Name: {person_name}\n"
            f"Company: {company_name}\n"
            f"Company Description: {company_description}\n"
            f"Role Title: {person_role_title}\n"
            "\n"
            ""
        ))
        self.SUMMARY_ACTIVITY_SYSTEM_MESSAGE = SystemMessage(content=(
            "You are a very intelligent and truthful sales person that analyzes recent LinkedIn activities of your prospect to extract useful information about them.\n"
            "You are given your prospect's name, the company they work for, their current role and the company description.\n"
            "You will also be given a text that contains a detailed summary of a LinkedIn activity (a post, comment or reaction) that your prospect has engaged with.\n"
            "The text will be delimited by triple quotes.\n"
            "Your job is to answer the user's questions using the information found in the text.\n"
            "\n"
            "**Prospect Details:**\n"
            f"Name: {person_name}\n"
            f"Company: {company_name}\n"
            f"Company Description: {company_description}\n"
            f"Role Title: {person_role_title}\n"
            "\n"
            ""
        ))
        self.CATEGORY_ACTIVITY_SYSTEM_MESSAGE = SystemMessage(content=(
            "You are a very intelligent and truthful sales person that analyzes recent LinkedIn activities of your prospect to extract useful information about them.\n"
            "You are given your prospect's name, the company they work for, their current role and the company description.\n"
            "You will also be given a text that contains a detailed summary of a LinkedIn activity (a post, comment or reaction) that your prospect has engaged with.\n"
            "The text will be delimited by triple quotes.\n"
            "Your job is to classify the content in the text into one of the Categories (provided below) that best describes it.\n"
            "\n"
            "**Categories:**\n"
            f"The prospect shared their personal thoughts with everyone. [Enum value: {ContentCategoryEnum.PERSONAL_THOUGHTS.value}]\n"
            f"The prospect shared personal advice with everyone. [Enum value: {ContentCategoryEnum.PERSONAL_ADVICE.value}]\n"
            f"The prospect shared an anecdote or story. [Enum value: {ContentCategoryEnum.PERSONAL_ANECDOTE.value}]\n"
            f"The prospect got a promotion. [Enum value: {ContentCategoryEnum.PERSONAL_PROMOTION.value}]\n"
            f"The prospect celebrated a work anniversary at their company. [Enum value: {ContentCategoryEnum.PERSONAL_JOB_ANNIVERSARY.value}]\n"
            f"The prospect received personal recognition or an award. [Enum value: {ContentCategoryEnum.PERSONAL_RECOGITION.value}]\n"
            f"The prospect switched jobs recently. [Enum value: {ContentCategoryEnum.PERSONAL_JOB_CHANGE.value}]\n"
            f"The prospect attended an event or conference or workshop recently. [Enum value: {ContentCategoryEnum.PERSONAL_EVENT_ATTENDED.value}]\n"
            f"The prospect gave a talk at an event or conference or a workshop. [Enum value: {ContentCategoryEnum.PERSONAL_TALK_AT_EVENT.value}]\n"
            f"Announcement of the company's recent partnership with another company. [Enum value: {ContentCategoryEnum.COMPANY_PARTNERSHIP.value}]\n"
            f"About industry trends in the company's industry. [Enum value: {ContentCategoryEnum.INDUSTRY_TRENDS.value}]\n"
            f"A collaboration or alliance by the company with other companies in the industry. [Enum value: {ContentCategoryEnum.INDUSTRY_COLLABORATION.value}]\n"
            f"The company's product launch. [Enum value: {ContentCategoryEnum.PRODUCT_LAUNCH.value}]\n"
            f"An update to the company's existing product. [Enum value: {ContentCategoryEnum.PRODUCT_UPDATE.value}]\n"
            f"A new leadership hire at the company. [Enum value: {ContentCategoryEnum.LEADERSHIP_HIRE.value}]\n"
            f"The company received recognition or an award for an achievement. [Enum value: {ContentCategoryEnum.COMPANY_RECOGNITION.value}]\n"
            f"A significant achievement by the company. [Enum value: {ContentCategoryEnum.COMPANY_ACHIEVEMENT.value}]\n"
            f"The company recognized achievements of one of their partners. [Enum value: {ContentCategoryEnum.PARTNER_RECOGNITION.value}]\n"
            f"The company is hiring. [Enum value: {ContentCategoryEnum.COMPANY_HIRING.value}]\n"
            f"Leadership change or reorganization at the company. [Enum value: {ContentCategoryEnum.LEADERSHIP_CHANGE.value}]\n"
            f"An employee at the company got promoted. [Enum value: {ContentCategoryEnum.EMPLOYEE_PROMOTION.value}]\n"
            f"An employee at the company is leaving the company. [Enum value: {ContentCategoryEnum.EMPLOYEE_LEAVING.value}]\n"
            f"The company's quarterly or annual financial results were announced. [Enum value: {ContentCategoryEnum.FINANCIAL_RESULTS.value}]\n"
            f"General information about the company. [Enum value: {ContentCategoryEnum.ABOUT_COMPANY.value}]\n"
            f"A Story or anecdote about the company. [Enum value: {ContentCategoryEnum.COMPANY_STORY.value}]\n"
            f"A report released by the company. [Enum value: {ContentCategoryEnum.COMPANY_REPORT.value}]\n"
            f"Funding announcement made by the company. [Enum value: {ContentCategoryEnum.FUNDING_ANNOUNCEMENT.value}]\n"
            f"IPO announcement made by the company. [Enum value: {ContentCategoryEnum.IPO_ANNOUNCEMENT.value}]\n"
            f"The company announced the acquisition of another company. [Enum value: {ContentCategoryEnum.COMPANY_ACQUISITION.value}]\n"
            f"The company has announced it has been acquired by another company. [Enum value: {ContentCategoryEnum.COMPANY_ACQUIRED.value}]\n"
            f"The company's anniversary announcement. [Enum value: {ContentCategoryEnum.COMPANY_ANNIVERSARY.value}]\n"
            f"Content about the company's competition. [Enum value: {ContentCategoryEnum.COMPANY_COMPETITION.value}]\n"
            f"Content about the company's customers. [Enum value: {ContentCategoryEnum.COMPANY_CUSTOMERS.value}]\n"
            f"An event, conference or trade show hosted or attended by the company. [Enum value: {ContentCategoryEnum.COMPANY_EVENT_HOSTED_ATTENDED.value}]\n"
            f"An talk given by a company employee in a conference or workshop or event. [Enum value: {ContentCategoryEnum.COMPANY_TALK.value}]\n"
            f"A webinar hosted by the company. [Enum value: {ContentCategoryEnum.COMPANY_WEBINAR.value}]\n"
            f"A panel discussion hosted or organized by the company. [Enum value: {ContentCategoryEnum.COMPANY_PANEL_DISCUSSION.value}]\n"
            f"Layoffs announced by the company. [Enum value: {ContentCategoryEnum.COMPANY_LAYOFFS.value}]\n"
            f"A business challenge facing the company. [Enum value: {ContentCategoryEnum.COMPANY_CHALLENGE.value}]\n"
            f"A rebranding initiative by the company. [Enum value: {ContentCategoryEnum.COMPANY_REBRAND.value}]\n"
            f"The company announced expansion plans to a new market. [Enum value: {ContentCategoryEnum.COMPANY_NEW_MARKET_EXPANSION.value}]\n"
            f"The company announced a new office or branch opening. [Enum value: {ContentCategoryEnum.COMPANY_NEW_OFFICE.value}]\n"
            f"The company announced a social responsibility initiative. [Enum value: {ContentCategoryEnum.COMPANY_SOCIAL_RESPONSIBILITY.value}]\n"
            f"A Legal challenge affecting the company. [Enum value: {ContentCategoryEnum.COMPANY_LEGAL_CHALLENGE.value}]\n"
            f"A government regulation that impacts the company. [Enum value: {ContentCategoryEnum.COMPANY_REGULATION.value}]\n"
            f"A Lawsuit filed against the company. [Enum value: {ContentCategoryEnum.COMPANY_LAWSUIT.value}]\n"
            f"Internal Company event attended by the company employees. [Enum value: {ContentCategoryEnum.COMPANY_INTERNAL_EVENT.value}]\n"
            f"Team offsite attended by the company employees. [Enum value: {ContentCategoryEnum.COMPANY_OFFSITE.value}]\n"
            f"Shutdown of the company's product. [Enum value: {ContentCategoryEnum.PRODUCT_SHUTDOWN.value}]\n"
            f"None of the above categories. [Enum value: {ContentCategoryEnum.NONE_OF_THE_ABOVE.value}]\n"
            "\n"
            "**Prospect Details:**\n"
            f"Name: {person_name}\n"
            f"Company: {company_name}\n"
            f"Company Description: {company_description}\n"
            f"Role Title: {person_role_title}\n"
            "\n"
            ""
        ))

    def parse(self, activity: LinkedInActivity) -> ContentDetails:
        """Parse given LinkedIn activity and convert it into Content instance post processing."""
        # Populate content details as content is parsed.
        content_details = ContentDetails(
            url=activity.activity_url,
            person_name=self.person_name,
            company_name=self.company_name,
            company_description=self.company_description,
            person_role_title=self.person_role_title,
            person_profile_id=self.person_profile_id,
            company_profile_id=self.company_profile_id,
            linkedin_activity_ref_id=activity.id,
            requesting_user_contact=False
        )

        with get_openai_callback() as cb:
            if not self.is_content_related_and_publish_date(
                    content_md=activity.content_md, content_details=content_details):
                content_details.openai_tokens_used = OpenAITokenUsage(url=content_details.url, operation_tag="activity_processing", prompt_tokens=cb.prompt_tokens,
                                                                      completion_tokens=cb.completion_tokens, total_tokens=cb.total_tokens, total_cost_in_usd=cb.total_cost)
                logger.info(
                    f"\n\nTotal cost: {content_details.openai_tokens_used.total_cost_in_usd}")
                return content_details

            if not self.fetch_detailed_summary(
                    content_md=activity.content_md, content_details=content_details):
                content_details.openai_tokens_used = OpenAITokenUsage(url=content_details.url, operation_tag="activity_processing", prompt_tokens=cb.prompt_tokens,
                                                                      completion_tokens=cb.completion_tokens, total_tokens=cb.total_tokens, total_cost_in_usd=cb.total_cost)
                logger.info(
                    f"\n\nTotal cost: {content_details.openai_tokens_used.total_cost_in_usd}")
                return content_details

            self.compute_content_category(content_details=content_details)

            self.extract_mentioned_team_members(
                content_details=content_details)

            self.extract_products(content_details=content_details)

            logger.info(
                f"Successfully processed Content in LinkedIn Activity URL: {content_details.url} with Activity ID: {content_details.linkedin_activity_ref_id}")

            content_details.processing_status = ContentDetails.ProcessingStatus.COMPLETE
            content_details.openai_tokens_used = OpenAITokenUsage(url=content_details.url, operation_tag="activity_processing", prompt_tokens=cb.prompt_tokens,
                                                                  completion_tokens=cb.completion_tokens, total_tokens=cb.total_tokens, total_cost_in_usd=cb.total_cost)
            logger.info(
                f"\n\nTotal cost: {content_details.openai_tokens_used.total_cost_in_usd}")
            return content_details

    def is_content_related_and_publish_date(self, content_md: str, content_details: ContentDetails) -> bool:
        """Checks if content is related to given company and extracts publish date. Populates Content details with the result.

        Returns True if the workflow should continue to the next step and False otherwise."""

        questions = (
            "Answer the following questions:\n"
            f"1. Is the content in the text is related to the company {self.company_name}? Sometimes a part of the company name (not the entire company name) is mentioned in the content, that counts as being related to the company."
            "If the company name is only mentioned in the author or prospect's experience, that is not enough to be related to the company. If text is about a product offering by the company, that counts as being related to the company as well.\n"
            f"2. Extract the date when the text was published. The publish date is usually in one of the following formats: 4h, 5d, 1mo, 2yr, 3w etc.\n"
        )
        human_message_prompt_template = (
            '"""{content_md}"""'
            "\n\n"
            f"{questions}"
        )
        human_message_prompt = HumanMessagePromptTemplate.from_template(
            human_message_prompt_template)

        prompt = ChatPromptTemplate.from_messages(
            [
                self.RAW_ACTIVITY_SYSTEM_MESSAGE,
                human_message_prompt,
            ]
        )

        class RelatedToCompanyAndPublishDate(BaseModel):
            related: Optional[bool] = Field(
                default=None, description="Set to True if the content is related to the Company and False otherwise.")
            reason: Optional[str] = Field(
                default=None, description="Reason for why the content is related or not related to the Company.")
            publish_date: Optional[str] = Field(
                default=None, description="Publish date of the post.")

        llm = ChatOpenAI(temperature=0, model_name=self.OPENAI_GPT_4O_MODEL,
                         api_key=self.OPENAI_API_KEY, timeout=self.OPENAI_REQUEST_TIMEOUT_SECONDS).with_structured_output(RelatedToCompanyAndPublishDate)

        chain = prompt | llm
        result: RelatedToCompanyAndPublishDate = chain.invoke({
            "content_md": content_md,
        })

        publish_date_str: Optional[str] = result.publish_date
        if not publish_date_str:
            logger.warning(
                f"Publish date returned None in result: {result}, Exiting content processing in LinkedIn activity URL: {content_details.url} and ID: {content_details.linkedin_activity_ref_id}.")
            # Usually date is present in LinkedIn activity, so we definitely want to try one more time to extract the date
            # with a different prompt.
            publish_date_str = self.extract_date_only(
                content_md=content_md, content_details=content_details)
            if not publish_date_str:
                logger.warning(
                    f"Retry Publish date returned None, Exiting content processing in LinkedIn activity URL: {content_details.url} and ID: {content_details.linkedin_activity_ref_id}.")
                content_details.processing_status = ContentDetails.ProcessingStatus.FAILED_MISSING_PUBLISH_DATE

                # Send event.
                self.metrics.capture_system_event(event_name="activity_processing_skipped_missing_publish_date", properties={
                                                  "activity_url": content_details.url, "activity_id": content_details.linkedin_activity_ref_id})
                return False

        publish_date: Optional[datetime] = LinkedInScraper.fetch_publish_date(
            publish_date_str)
        if publish_date == None:
            logger.error(
                f"Got None when converting LinkedIn activity date: {publish_date_str} to datetime object in LinkedIn Activity URL: {content_details.url} and ID: {content_details.linkedin_activity_ref_id}.")
            content_details.processing_status = ContentDetails.ProcessingStatus.FAILED_MISSING_PUBLISH_DATE

            # Send event.
            self.metrics.capture_system_event(event_name="activity_processing_skipped_publish_date_conversion_failed", properties={
                "activity_url": content_details.url, "activity_id": content_details.linkedin_activity_ref_id})
            return False

        # If post is older than 1 year and 3 months from todays date, skip it may be too old for relevance.
        # We add 3 months extra because it might be someone's work anniversary which we can still celebrate 1 year and 3 months later.
        publish_cutoff_date = Utils.create_utc_time_now() - relativedelta(months=15)
        if publish_date < publish_cutoff_date:
            logger.warning(
                f"Got Stale publish date: {publish_date} which is older than 15 months, Exiting content processing in LinkedIn activity URL: {content_details.url} and ID: {content_details.linkedin_activity_ref_id}.")
            content_details.processing_status = ContentDetails.ProcessingStatus.FAILED_STALE_PUBLISH_DATE

            # Send event.
            self.metrics.capture_system_event(event_name="activity_processing_skipped_stale_publish_date", properties={
                "activity_url": content_details.url, "activity_id": content_details.linkedin_activity_ref_id, "publish_date": publish_date.strftime("%d-%m-%Y")})
            return False

        # Populate publish date.
        content_details.publish_date = publish_date

        if result.related == None:
            logger.error(
                f"Related to company returned None with reason: {result.reason} and publish date: {content_details.publish_date}, Exiting content processing in LinkedIn Activity URL: {content_details.url} and ID: {content_details.linkedin_activity_ref_id}.")
            content_details.processing_status = ContentDetails.ProcessingStatus.FAILED_UNRELATED_TO_COMPANY
            
            # Send event.
            self.metrics.capture_system_event(event_name="activity_processing_skipped_related_to_company_none_result", properties={
                "activity_url": content_details.url, "activity_id": content_details.linkedin_activity_ref_id})
            return False

        if result.related == False:
            logger.info(
                f"Not related to company: {self.company_name}, reason: {result.reason} and publish date: {content_details.publish_date}, Exiting content processing for content in LinkedIn Activity URL: {content_details.url} and ID: {content_details.linkedin_activity_ref_id}")
            content_details.processing_status = ContentDetails.ProcessingStatus.FAILED_UNRELATED_TO_COMPANY
            
            # Send event.
            self.metrics.capture_system_event(event_name="activity_processing_skipped_unrelated_to_company", properties={
                "activity_url": content_details.url, "activity_id": content_details.linkedin_activity_ref_id})
            return False

        # Populate content details.
        content_details.focus_on_company = result.related
        content_details.focus_on_company_reason = result.reason

        logger.info(
            f"Content is related to company with publish date: {content_details.publish_date} and reason: {content_details.focus_on_company_reason} in LinkedIn Activity URL: {content_details.url} and ID: {content_details.linkedin_activity_ref_id}")
        return True

    def fetch_detailed_summary(self, content_md: str, content_details: ContentDetails) -> bool:
        """Extracts detailed summary from the following activity and populates in the content details. Returns True if workflow should continue to next step and False otherwise."""

        question = (
            f"Provide a detailed summary explaining the text. Include details like all the names names, titles, numbers, metrics and the engagement action of the prospect {self.person_name} in the detailed summary wherever possible.\n"
        )
        human_message_prompt_template = (
            '"""{content_md}"""'
            "\n\n"
            f"{question}"
        )
        detailed_summary_prompt = HumanMessagePromptTemplate.from_template(
            human_message_prompt_template)

        prompt = ChatPromptTemplate.from_messages(
            [
                self.RAW_ACTIVITY_SYSTEM_MESSAGE,
                detailed_summary_prompt,
            ]
        )

        llm = ChatOpenAI(temperature=0, model_name=self.OPENAI_GPT_4O_MODEL,
                         api_key=self.OPENAI_API_KEY, timeout=self.OPENAI_REQUEST_TIMEOUT_SECONDS)

        chain = prompt | llm
        result = chain.invoke({
            "content_md": content_md,
        })

        # Populate content details.
        content_details.detailed_summary = result.content
        content_details.concise_summary = result.content

        if not content_details.detailed_summary:
            logger.error(
                f"Detailed Summary returned None, Exiting content processing for LinkedIn Activity URL: {content_details.url}, activity ID: {content_details.linkedin_activity_ref_id}")
            return False

        logger.info(
            f"Detailed Summary of content: {content_details.detailed_summary} for LinkedIn Activity URL: {content_details.url}, activity ID: {content_details.linkedin_activity_ref_id}")
        return True

    def compute_content_category(self, content_details: ContentDetails):
        """Computes content category from the detailed summary."""
        if not content_details.detailed_summary:
            logger.error(
                f"Content Category: Expected detailed summary to be not None in Content Details, found None. Exiting content processing for Content Details: {content_details}")
            return
        human_message_prompt_template = (
            '"""{detailed_summary}"""'
            "\n\n"
        )
        human_message_prompt = HumanMessagePromptTemplate.from_template(
            human_message_prompt_template)

        prompt = ChatPromptTemplate.from_messages(
            [
                self.CATEGORY_ACTIVITY_SYSTEM_MESSAGE,
                human_message_prompt,
            ]
        )

        class Category(BaseModel):
            category: Optional[ContentCategoryEnum] = Field(
                default=None, description="Category of the content in the text.")
            reason: Optional[str] = Field(
                default=None, description="Reason for the category selection.")

        llm = ChatOpenAI(temperature=0, model_name=self.OPENAI_GPT_4O_MODEL,
                         api_key=self.OPENAI_API_KEY, timeout=self.OPENAI_REQUEST_TIMEOUT_SECONDS).with_structured_output(Category)

        chain = prompt | llm
        result: Category = chain.invoke({
            "detailed_summary": content_details.detailed_summary,
        })

        # Populate content details.
        content_details.category = result.category
        content_details.category_reason = result.reason

        if content_details.category == None or content_details.category == ContentCategoryEnum.NONE_OF_THE_ABOVE:
            logger.error(
                f"Got Category: {content_details.category} which is None with reason: {content_details.category_reason} for LinkedIn Activity URL: {content_details.url} for activity ID: {content_details.linkedin_activity_ref_id}")
            return

        logger.info(
            f"Got Content Category: {content_details.category} with reason: {content_details.category_reason} for LinkedIn Activity URL: {content_details.url} for activity ID: {content_details.linkedin_activity_ref_id}")

    def extract_mentioned_team_members(self, content_details: ContentDetails):
        """Extracts team members who are mentioned in the detailed summary of LinkedIn Activity."""
        if not content_details.detailed_summary:
            logger.error(
                f"Team Members: Expected detailed summary to be not None in Content Details, found None. Exiting content processing for Content Details: {content_details}")
            return

        questions = (
            f"We are trying to infer team members of the prospect at {self.company_name} by inspecting their LinkedIn activity engagement.\n"
            f"Extract the names of all other members mentioned (excluding {self.person_name}) in the text from company {self.company_name}. If the author of the activity is from the same company, include them as well.\n"
        )
        human_message_prompt_template = (
            '"""{detailed_summary}"""'
            "\n\n"
            f"{questions}"
        )
        human_message_prompt = HumanMessagePromptTemplate.from_template(
            human_message_prompt_template)

        prompt = ChatPromptTemplate.from_messages(
            [
                self.SUMMARY_ACTIVITY_SYSTEM_MESSAGE,
                human_message_prompt,
            ]
        )

        class TeamMembers(BaseModel):
            team_members: Optional[List[str]] = Field(
                default=None, description="Team members of the prospect in the text.")

        llm = ChatOpenAI(temperature=0, model_name=self.OPENAI_GPT_4O_MODEL,
                         api_key=self.OPENAI_API_KEY, timeout=self.OPENAI_REQUEST_TIMEOUT_SECONDS).with_structured_output(TeamMembers)

        chain = prompt | llm
        result: TeamMembers = chain.invoke({
            "detailed_summary": content_details.detailed_summary,
        })

        # Populate team members.
        content_details.mentioned_team_members = result.team_members

        logger.info(
            f"Team Members mentioned: {content_details.mentioned_team_members} for LinkedIn Activity URL: {content_details.url} for activity ID: {content_details.linkedin_activity_ref_id}")

    def extract_products(self, content_details: ContentDetails):
        """Extracts products mentioned in the detailed summary for given LinkedIn Activity."""
        if not content_details.detailed_summary:
            logger.error(
                f"Products: Expected detailed summary to be not None in Content Details, found None. Exiting content processing for Content Details: {content_details}")
            return

        questions = (
            f"We are trying to infer which products the prospect works on at their role at {self.company_name} by inspecting their LinkedIn activity engagement.\n"
            f"Extract the names of any products offered by {self.company_name} mentioned in the text.\n"
        )
        human_message_prompt_template = (
            '"""{detailed_summary}"""'
            "\n\n"
            f"{questions}"
        )
        human_message_prompt = HumanMessagePromptTemplate.from_template(
            human_message_prompt_template)

        prompt = ChatPromptTemplate.from_messages(
            [
                self.SUMMARY_ACTIVITY_SYSTEM_MESSAGE,
                human_message_prompt,
            ]
        )

        class Products(BaseModel):
            products: Optional[List[str]] = Field(
                default=None, description="Products or brands mentioned in the text.")

        llm = ChatOpenAI(temperature=0, model_name=self.OPENAI_GPT_4O_MODEL,
                         api_key=self.OPENAI_API_KEY, timeout=self.OPENAI_REQUEST_TIMEOUT_SECONDS).with_structured_output(Products)

        chain = prompt | llm
        result: Products = chain.invoke({
            "detailed_summary": content_details.detailed_summary,
        })
        # Populate content details.
        content_details.product_associations = result.products

        logger.info(
            f"Got Product associations: {content_details.product_associations} in LinkedIn Activity URL: {content_details.url} and Activity ID: {content_details.linkedin_activity_ref_id}")

    def extract_date_only(self, content_md: str, content_details: ContentDetails) -> Optional[str]:
        """Extract date from given LinkedIn Activity Markdown and return it. Used as backup if date extraction failed when checking if activity is related to company or not.
        Note that the date returned will be of the format: 4h, 5d, 1mo, 2yr, 3w etc. The caller must covert it to datetime instance separately.
        """
        question = (
            "Extract the date when the text was published. The publish date is usually in one of the following formats: 4h, 5d, 1mo, 2yr, 3w etc."
        )
        human_message_prompt_template = (
            '"""{content_md}"""'
            "\n\n"
            f"{question}"
        )
        human_message_prompt = HumanMessagePromptTemplate.from_template(
            human_message_prompt_template)

        prompt = ChatPromptTemplate.from_messages(
            [
                self.RAW_ACTIVITY_SYSTEM_MESSAGE,
                human_message_prompt,
            ]
        )

        class PublishDate(BaseModel):
            publish_date: Optional[str] = Field(
                default=None, description="Publish date of the post.")

        llm = ChatOpenAI(temperature=0, model_name=self.OPENAI_GPT_4O_MODEL,
                         api_key=self.OPENAI_API_KEY, timeout=self.OPENAI_REQUEST_TIMEOUT_SECONDS).with_structured_output(PublishDate)

        chain = prompt | llm
        result: PublishDate = chain.invoke({
            "content_md": content_md,
        })

        logger.info(
            f"Backup publish date result: {result.publish_date} for LinkedIn Activity URL: {content_details.url} and activity ID: {content_details.linkedin_activity_ref_id}")
        return result.publish_date

    @staticmethod
    def get_activities(person_linkedin_url: str, page_html: str, activity_type: LinkedInActivity.Type) -> List[LinkedInActivity]:
        """Parses given lead's Activity HTML page and returns the list of activities found on the page. The returned objects are created only in memory in this method."""

        # Remove tags that contain the user's name (who was logged in and piped the content from the chrome extension). We do this so that during processing,
        # The LLM does not accidentally reference it as a key person while generating a summary.
        soup = BeautifulSoup(page_html, "html.parser")
        member_tags = soup.find_all("div", class_="member")
        for tag in member_tags:
            # Mutate soup instance by clearing these tags.
            tag.clear()

        # Convert to markdown format.
        page_md: str = markdownify(str(soup), heading_style="ATX")

        # Split markdown into individual content activities.
        content_list: List[str] = page_md.split("* ## Feed post number")

        activity_list: List[str] = []
        for i, content in enumerate(content_list):
            if i == 0:
                # Skip the first item since it preceeds the actual activity and doesn't have
                # any meaningul data.
                continue
            act = LinkedInActivity(
                person_linkedin_url=person_linkedin_url,
                activity_url=LinkedInActivityParser._get_activity_url(
                    person_linkedin_url=person_linkedin_url, activity_type=activity_type),
                type=activity_type,
                content_md=content
            )
            activity_list.append(act)
        return activity_list

    @staticmethod
    def _get_activity_url(person_linkedin_url: str, activity_type: LinkedInActivity.Type) -> str:
        """Returns URL of the given activity for given lead's LinkedIn URL and activity type. These are hardcoded based on
        the endpoints we observe on LinkedIn today (as of 2024) but they can change in the future if LinkedIn wants it to.
        """
        if (activity_type == LinkedInActivity.Type.POST):
            return f"{person_linkedin_url}/{LinkedInActivityParser.RECENT_ACTIVITY}/{LinkedInActivityParser.ACTIVITY_POSTS}"

        if (activity_type == LinkedInActivity.Type.COMMENT):
            return f"{person_linkedin_url}/{LinkedInActivityParser.RECENT_ACTIVITY}/{LinkedInActivityParser.ACTIVITY_COMMENTS}"

        if (activity_type == LinkedInActivity.Type.REACTION):
            return f"{person_linkedin_url}/{LinkedInActivityParser.RECENT_ACTIVITY}/{LinkedInActivityParser.ACTIVITY_REACTIONS}"

        raise ValueError(
            f"Invalid LinkedInActivity type: {activity_type}, cannot get URL.")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    load_dotenv(".env.dev")

    import logging
    logging.basicConfig(level=logging.INFO)

    person_linkedin_url = "https://www.linkedin.com/in/pankush-kapoor-4407634b"
    company_name = "Dabur India Limited"
    company_description = "We are Dabur, an Indian Transnational offering the best nature-based solutions to provide holistic Health & Well-Being to households in more than 120 markets spanning Asia, Europe and The US. A world leader in Ayurveda, we are a family of over 7,000 individuals continuously striving to conduct business in an environmentally sustainable manner."
    # person_name = "Pankush Kapoor"
    # person_role_title = "Group Brand Manager"
    # person_name = "Prashant Agarwal"
    # person_role_title = "Head of Marketing - Health Supplements & Baby Care"
    # person_name = "Vikram Dhawan"
    # person_role_title = "Senior Brand Manager"
    person_name = "Abhishek Jain"
    person_role_title = "Senior Brand Manager"
    activity_type = LinkedInActivity.Type.COMMENT

    filename = "_".join([p.lower() for p in person_name.split(
        " ")] + [activity_type.value.lower() + "s"])
    page_html = ""
    with open(f"example_linkedin_info/extension_activity/{filename}.txt", "r") as f:
        page_html = f.read()

    activities: List[LinkedInActivity] = LinkedInActivityParser.get_activities(
        person_linkedin_url=person_linkedin_url, page_html=page_html, activity_type=activity_type)

    parser = LinkedInActivityParser(person_name=person_name, company_name=company_name,
                                    company_description=company_description, person_role_title=person_role_title)

    import time
    start_time = time.time()
    for i, act in enumerate(activities):
        if i == 1:
            act.id = "1"
            parser.parse(activity=act)
            break
    logger.info(f"\n\nTotal time taken: {time.time() - start_time} seconds")
