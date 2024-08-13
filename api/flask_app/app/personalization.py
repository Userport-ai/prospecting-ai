import os
import logging
from datetime import datetime
from typing import List, Optional
from app.database import Database
from app.models import LeadResearchReport, ContentCategoryEnum, OpenAITokenUsage
from app.utils import Utils
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_community.callbacks import get_openai_callback

from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger()


class PersonalizedEmail(BaseModel):
    subject_line: Optional[str] = Field(
        default=None, description="Subject Line of the email.")
    email_opener: Optional[str] = Field(
        default=None, description="1-3 line personalized email opener to the recipient.")


class Personalization:
    """Helps generate personalized messages for a given lead."""

    # Open AI configurations.
    OPENAI_API_KEY = os.getenv("OPENAI_USERPORT_API_KEY")
    OPENAI_GPT_4O_MODEL = os.getenv("OPENAI_GPT_4O_MODEL")

    OPERATION_TAG_NAME = "email_personalization"

    def __init__(self, database: Database) -> None:
        self.database = database
        self.openai_tokens_used: Optional[OpenAITokenUsage] = None

    def generate_personalized_emails(self, lead_research_report_id: str, referenced_highlight_ids: Optional[List[str]] = None) -> List[LeadResearchReport.PersonalizedEmail]:
        """Generates personalized emails for given lead using the given highlights as reference and returns the list.

        If no highlights are provided, then k highlights are auto-selected by the method and the
        personalized emails are generated using them as references.
        """
        lead_research_report: LeadResearchReport = self.database.get_lead_research_report(
            lead_research_report_id=lead_research_report_id)
        if lead_research_report.status != LeadResearchReport.Status.EMAIL_TEMPLATE_SELECTION_COMPLETE:
            raise ValueError(
                f"Expected report status to be: {LeadResearchReport.Status.EMAIL_TEMPLATE_SELECTION_COMPLETE}, got: {lead_research_report.status}")

        all_highlights: List[LeadResearchReport.ReportDetail.Highlight] = lead_research_report.get_all_highlights()
        if len(all_highlights) == 0:
            raise ValueError(
                f"No highlights found for lead report ID: {lead_research_report.id}, cannot generate personalized emails.")
        referenced_highlights: List[LeadResearchReport.ReportDetail.Highlight] = [
        ]
        if referenced_highlight_ids is None:
            referenced_highlights = self.get_best_highlights(
                all_highlights=all_highlights)
        else:
            referenced_highlights = list(
                filter(lambda x: x.id in set(referenced_highlight_ids), all_highlights))

        logger.info(
            f"Got {len(referenced_highlights)} reference highlights for email personalization.")

        chosen_email_template: LeadResearchReport.ChosenOutreachEmailTemplate = lead_research_report.chosen_outreach_email_template
        email_template_message: Optional[str] = None
        if chosen_email_template.id:
            email_template_message = chosen_email_template.message
        else:
            logger.info(
                f"No Email template matched for Lead report: {lead_research_report_id} and user ID: {lead_research_report.user_id}")

        generated_personalized_emails: List[LeadResearchReport.PersonalizedEmail] = [
        ]
        with get_openai_callback() as cb:
            for highlight in referenced_highlights:
                email_subject_line: str = self.generate_email_subject_line(
                    highlight=highlight, lead_research_report=lead_research_report, email_template_message=email_template_message)
                email_opener: str = self.generate_email_opener(highlight=highlight, lead_research_report=lead_research_report,
                                                               email_template_message=email_template_message, email_subject_line=email_subject_line)
                logger.info(f"Email Subject Line: {email_subject_line}")
                logger.info(f"Email Opener: {email_opener}\n\n")
                generated_personalized_emails.append(LeadResearchReport.PersonalizedEmail(
                    # IDs, creation and update dates will be generated when inserting into the database.
                    referenced_highlight_ids=referenced_highlight_ids,
                    email_subject_line=email_subject_line,
                    email_opener=email_opener,
                ))

            self.openai_tokens_used = OpenAITokenUsage(highlight_ids=referenced_highlight_ids, operation_tag=Personalization.OPERATION_TAG_NAME,
                                                       prompt_tokens=cb.prompt_tokens, completion_tokens=cb.completion_tokens, total_tokens=cb.total_tokens, total_cost_in_usd=cb.total_cost)
            logger.info(
                f"Total tokens used in email personalization: {self.openai_tokens_used}")

        return generated_personalized_emails

    def generate_email_subject_line(self, highlight: LeadResearchReport.ReportDetail.Highlight, lead_research_report: LeadResearchReport, email_template_message: Optional[str]):
        """Generates Personalized email subject line for lead using given highlight and Lead research report.

        If email template is provided it is used in determining the email subject line. If not, only information from lead research report and highlight are used.
        """
        prompt_email_template_present_reference_details = (
            "You are also given the email template message that will be used to highlight the pain point your product solves and its potential value proposition to the prospect.\n"
            "Reference specific details from information about the prospect as well as the email template message to construct an email subject line that is addressed to the prospect.\n"
        )
        prompt_email_template_missing_reference_details = (
            "Reference specific details from information about the prospect to construct an email subject line that is addressed to the prospect.\n"
        )
        prompt_email_template_formatted = (
            "## Email Template Message\n"
            f"{email_template_message}"
        )

        prompt_template = (
            f"Today's date: {Utils.to_human_readable_date_str(Utils.create_utc_time_now())}\n\n"
            "You are an exuberant sales person who is responsible for writing personalized outbound emails that stand out to the prospect.\n"
            "You are provided with information about the prospect as well as summaries of recent news about them.\n"
            f"{prompt_email_template_present_reference_details if email_template_message else prompt_email_template_missing_reference_details}"
            "The email subject line should address the prospect in second-person and capture their attention. It could reference a recent story, statistic or a question about some comments they made.\n"
            "\n"
            "Here are some examples of subject lines templates that you can use as inspiration to capture the attention of a prospect:\n"
            "1. [Prospect First Name], [pose an interesting question]?\n"
            "2. Idea for [topic the prospect cares about]\n"
            "3. If you are struggling with [pain point], you are not alone\n"
            "4. [Prospect First Name], saw you're focused on [goal]\n"
            "5. [Prospect First Name], loved your post about [content]\n"
            "6. A solution for [Pain Point], [Prospect First Name]?\n"
            "7. [Prospect First Name], [Pain point] initiatives for [Company name]?\n"
            "8. [Prospect First Name], improving [Pain point] at [Company name]?\n"
            "9. [Pain Point]: There’s a better way!\n"
            "10. Excited about using [Product Name that solves the pain point] to ease your [Pain Point]?\n"
            "11. [Prospect First Name], tackling [Pain Point] after [specific announcement or event]?\n"
            "12. [Prospect First Name], curious about your take on [Content or Issue or Trend]?\n"
            "13. [Prospect First Name], your [Content or post] got me thinking...\n"
            "14. [Prospect First Name], inspired by your [Content] - must read for [audience]!\n"
            "15. Curious about your take on [Content or Product or Story] after your chat with [Interviewer or Podcast Host]?\n"
            "16. Curious about how [Product or Feature] has influenced [Company's decisions]?\n"
            "17. Curious about your take on tackling [Pain point]?\n"
            "\n"
            "## Prospect Details\n"
            "Name: {person_name}\n"
            "Company: {company_name}\n"
            "Role Title: {person_role_title}\n"
            "News Source: {url}\n"
            "News Publish Date: {publish_date_readable_str}\n"
            "News Summary:\n"
            "{concise_summary}\n"
            "\n"
            f"{prompt_email_template_formatted if email_template_message else ''}"
        )
        prompt = PromptTemplate.from_template(prompt_template)

        class EmailSubjectLine(BaseModel):
            subject_line: Optional[str] = Field(
                default=None, description="Subject Line of the email.")

        llm = ChatOpenAI(temperature=1.3, model_name=Personalization.OPENAI_GPT_4O_MODEL,
                         api_key=Personalization.OPENAI_API_KEY).with_structured_output(EmailSubjectLine)

        chain = prompt | llm
        result: EmailSubjectLine = chain.invoke({
            "person_name": lead_research_report.person_name,
            "company_name": lead_research_report.company_name,
            "person_role_title": lead_research_report.person_role_title,
            "url": highlight.url,
            "publish_date_readable_str": highlight.publish_date_readable_str,
            "concise_summary": highlight.concise_summary,
        })
        return result.subject_line

    def generate_email_opener(self, highlight: LeadResearchReport.ReportDetail.Highlight, lead_research_report: LeadResearchReport, email_template_message: Optional[str], email_subject_line: str):
        """Generates Personalized email opener for lead using given highlight and email subject line.

        If email template is provided it is used in determining the email subject line. If not, only information from lead research report, highlight and email subject line are used.
        """
        prompt_email_template_is_given = (
            "You are given the email template message that will be used to highlight the pain point your product solves and its potential value proposition to the prospect.\n"
        )
        prompt_email_template_present_reference_details = (
            "Reference specific details from information about the prospect, the email subject line and the email template message to construct an email opener that is addressed to the prospect.\n"
        )
        prompt_email_template_missing_reference_details = (
            "Reference specific details from information about the prospect and the email subject line to construct an email opener that is addressed to the prospect.\n"
        )
        prompt_email_template_formatted = (
            "**Email Template Message:**\n"
            f"{email_template_message}"
        )

        prompt_template = (
            f"Today's date: {Utils.to_human_readable_date_str(Utils.create_utc_time_now())}\n\n"
            "You are an exuberant sales person who is responsible for writing personalized outbound emails that stand out to the prospect.\n"
            "You are provided with information about the prospect as well as summaries of recent news about them.\n"
            f"{prompt_email_template_is_given if email_template_message else ''}"
            "You are also given the email subject line.\n"
            f"{prompt_email_template_present_reference_details if email_template_message else prompt_email_template_missing_reference_details}"
            "The email opener should address the prospect in second-person and be hyper personalized.\n"
            "It should be up to a maximum of 3 sentences in length.\n"
            "\n"
            "Here are some examples of email opener templates that you can use as inspiration to capture the attention of a prospect:\n"
            "1. Hi [Prospect First Name], Congrats on the new job and for the launch of [Product Name], it's amazing that teams can now get value from [Product's feature].\n"
            "2. Hi [Prospect First Name], read the recent [Report Name]  and noticed to my surprise that [interesting insight from the report] has changed in 2023 compared to 2022!\n"
            "3. Hi [Prospect First Name] Noticed that you recently spoke at [Event Name] about [Content about Talk], it was a great listen and I learned a lot!\n"
            "4. Hi [Prospect First Name], Congrats on the recent [Promotion] and for [Company Achievement]!\n"
            "5. Hi [Prospect First Name], noticed your repost about [Product Launch and how it solves a problem]. Excited to see how [the product transforms the industry]\n"
            "6. Hi [Prospect First Name], loved reading your thoughts on [Content]! It was inspiring to see how [Product or Company accomplishes something]!\n"
            "7. Hi [Prospect First Name], kudos on being recognized about [Recognition Description]! [Explain why the Recognition means something]\n"
            "8. Hi [Prospect First Name], thrilled to see you'll be sharing insights about [Product or some other Content]. Looking forward to learning [some detail about the Product or Content]!\n"
            "9. Hi [Prospect First Name], your [Content or Post] were truly insightful! Given your expertise, I wanted to touch base on how you are addressing [Pain Point].\n"
            "10. Hi [Prospect First Name], Congratulations on how you are tacking [Pain Point] and achieving [accomplishment]! Your dedication to addressing [Problem] is truly inspiring, especially amidst [Challenges they are facing].\n"
            "11. Hi [Prospect First Name], I was truly inspired by your thoughts on [recent Content or Post]! Your proactive approach of [doing a task] reflects an exceptional commitment to [a set positive attributes].\n"
            "12. Hi [Prospect First Name], kudos on taking a step towards [Solving a Problem] with the launch of [Product]! It's inspiring to see how [Company Name] can [Accomplish something] using [Product or Feature].\n"
            "\n"
            "**Prospect Details:**\n"
            "Name: {person_name}\n"
            "Company: {company_name}\n"
            "Role Title: {person_role_title}\n"
            "News Source: {url}\n"
            "News Publish Date: {publish_date_readable_str}\n"
            "News Summary:\n"
            "{concise_summary}\n"
            "\n"
            f"**Email Subject Line:** {email_subject_line}\n"
            "\n"
            f"{prompt_email_template_formatted if email_template_message else ''}"
        )
        prompt = PromptTemplate.from_template(prompt_template)

        class EmailOpener(BaseModel):
            email_opener: Optional[str] = Field(
                default=None, description="Personalized email opener addressed to the recipient.")

        llm = ChatOpenAI(temperature=1.3, model_name=Personalization.OPENAI_GPT_4O_MODEL,
                         api_key=Personalization.OPENAI_API_KEY).with_structured_output(EmailOpener)

        chain = prompt | llm
        result: EmailOpener = chain.invoke({
            "person_name": lead_research_report.person_name,
            "company_name": lead_research_report.company_name,
            "person_role_title": lead_research_report.person_role_title,
            "url": highlight.url,
            "publish_date_readable_str": highlight.publish_date_readable_str,
            "concise_summary": highlight.concise_summary,
        })
        return result.email_opener

    def get_best_highlights(self, all_highlights: List[LeadResearchReport.ReportDetail.Highlight], k: int = 5) -> List[LeadResearchReport.ReportDetail.Highlight]:
        """Selectes up to k highlights that will provide best outreach messages and returns them.

        Each highlight is from a different category.
        """
        # Sorted order of categories that we think can lead to best personalized emails.
        # Update this list whenever categories enums are updated.
        categories_sorting_order: List[ContentCategoryEnum] = [
            # Start with positive categories first.
            ContentCategoryEnum.INDUSTRY_TRENDS,
            ContentCategoryEnum.COMPANY_ACHIEVEMENT,
            ContentCategoryEnum.COMPANY_RECOGNITION,
            ContentCategoryEnum.PRODUCT_LAUNCH,
            ContentCategoryEnum.PRODUCT_UPDATE,
            ContentCategoryEnum.FINANCIAL_RESULTS,
            ContentCategoryEnum.COMPANY_NEW_MARKET_EXPANSION,
            ContentCategoryEnum.PERSONAL_THOUGHTS,
            ContentCategoryEnum.PERSONAL_TALK_AT_EVENT,
            ContentCategoryEnum.PERSONAL_ADVICE,
            ContentCategoryEnum.PERSONAL_ANECDOTE,
            ContentCategoryEnum.PERSONAL_RECOGITION,
            ContentCategoryEnum.PERSONAL_PROMOTION,
            ContentCategoryEnum.PERSONAL_JOB_CHANGE,
            ContentCategoryEnum.IPO_ANNOUNCEMENT,
            ContentCategoryEnum.COMPANY_PARTNERSHIP,
            ContentCategoryEnum.LEADERSHIP_HIRE,
            ContentCategoryEnum.COMPANY_REBRAND,
            ContentCategoryEnum.COMPANY_ANNIVERSARY,
            ContentCategoryEnum.FUNDING_ANNOUNCEMENT,
            ContentCategoryEnum.COMPANY_HIRING,
            ContentCategoryEnum.COMPANY_NEW_OFFICE,
            ContentCategoryEnum.COMPANY_STORY,
            ContentCategoryEnum.PERSONAL_EVENT_ATTENDED,
            ContentCategoryEnum.COMPANY_EVENT_HOSTED_ATTENDED,
            ContentCategoryEnum.COMPANY_WEBINAR,
            ContentCategoryEnum.COMPANY_INTERNAL_EVENT,
            ContentCategoryEnum.COMPANY_OFFSITE,
            ContentCategoryEnum.COMPANY_SOCIAL_RESPONSIBILITY,
            ContentCategoryEnum.EMPLOYEE_PROMOTION,
            # Negative categories.
            ContentCategoryEnum.COMPANY_CHALLENGE,
            ContentCategoryEnum.COMPANY_LEGAL_CHALLENGE,
            ContentCategoryEnum.COMPANY_LAYOFFS,
            ContentCategoryEnum.COMPANY_REGULATION,
            ContentCategoryEnum.COMPANY_LAWSUIT,
            ContentCategoryEnum.LEADERSHIP_CHANGE,
            ContentCategoryEnum.PRODUCT_SHUTDOWN,
            ContentCategoryEnum.EMPLOYEE_LEAVING,
        ]

        category_index_dict = {category: idx for idx,
                               category in enumerate(categories_sorting_order)}
        sorted_highlights = sorted(
            all_highlights, key=lambda highlight: category_index_dict.get(highlight.category, float('inf')))

        # Pick one highlight from each category from the sorted highlights.
        result_highlights: List[LeadResearchReport.ReportDetail.Highlight] = []
        curr_category: ContentCategoryEnum = None
        for highlight in sorted_highlights:
            if len(result_highlights) >= k:
                break
            if not curr_category or highlight.category != curr_category:
                curr_category = highlight.category
                result_highlights.append(highlight)
        return result_highlights

    def get_tokens_used(self) -> OpenAITokenUsage:
        """Returns tokens used so far in personalization. Throws exception if personalized workflow is not run yet."""
        if not self.openai_tokens_used:
            raise ValueError(
                f"Personalization Workflow not run yet, not tokens used!")
        return self.openai_tokens_used


if __name__ == "__main__":
    database = Database()
    pz = Personalization(database=database)

    lead_research_report_id = "66ab9633a3bb9048bc1a0be5"
    email_list = pz.generate_personalized_emails(
        lead_research_report_id=lead_research_report_id)
    # email_list_json = [email.model_dump_json() for email in email_list]

    # lead_research_report = database.get_lead_research_report(
    #     lead_research_report_id=lead_research_report_id)
    # pz.generate_email_subject_line(
    #     highlight=lead_research_report.details[0].highlights[0], lead_research_report=lead_research_report, email_template_message=None)
    # pz.generate_email_opener(
    #     highlight=lead_research_report.details[0].highlights[0], lead_research_report=lead_research_report, email_template_message=lead_research_report.chosen_outreach_email_template.message, email_subject_line="hello subject line")
