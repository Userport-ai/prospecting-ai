import os
import logging
from datetime import datetime
from bson.objectid import ObjectId
from typing import List, Optional
from app.database import Database
from app.models import LeadResearchReport, ContentCategoryEnum, OpenAITokenUsage
from app.utils import Utils
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langchain_core.messages import SystemMessage
from langchain_core.prompts import HumanMessagePromptTemplate
from langchain_community.callbacks import get_openai_callback

logger = logging.getLogger()


class PersonalizedEmail(BaseModel):
    subject_line: Optional[str] = Field(
        default=None, description="Subject Line of the email.")
    email_opener: Optional[str] = Field(
        default=None, description="1-3 line personalized email opener to the recipient.")


class Personalization:
    """Helps generate personalized messages for a given lead."""

    OPERATION_TAG_NAME = "email_personalization"

    def __init__(self, database: Database) -> None:
        self.database = database

        # Open AI configurations.
        self.OPENAI_API_KEY = os.environ["OPENAI_USERPORT_API_KEY"]
        self.OPENAI_GPT_4O_MODEL = os.environ["OPENAI_GPT_4O_MODEL"]
        self.openai_tokens_used: Optional[OpenAITokenUsage] = None
        self.OPENAI_REQUEST_TIMEOUT_SECONDS = 20
        self.EMAIL_OPENER_SYSTEM_MESSAGE = SystemMessage(content=(
            "You are an exuberant sales person who is responsible for writing personalized cold emails that stand out to the prospect.\n"
            "Your goal is to write the opening lines of an email which addresses the prospect in second-person and is hyper personalized.\n"
            "You will be provided with information about the prospect as well as a summary of a recent news item related to them or their company.\n"
            "Reference specific details from the news summary (numbers, company names, quotes etc.) and details about the prospect and their company to create the hyper personalized opening lines.\n"
            "The opening lines should be up to a maximum of 2 sentences in length and not be very formal in tone.\n"
            "\n"
            "Here are some examples of very good hyper-personalized opening lines that you can use as inspiration:\n"
            "Kudos to Greenhouse for being named the Best Applicant Tracking System for mid-market enterprise this year! A 94% user satisfaction rating while serving companies such as HubSpot and Buzzfeed is no easy feat!\n"
            "Really impressed by how you showed gratitude to the product team for leveraging customer feedback to enhance dscout’s mobile usability testing capabilities. Teamwork makes the dream work!\n"
            "Thanks for your LinkedIn post where you spoke about the new AI-assisted note management in RecruitCRM!\n"
            "Congratulations to you and the Zluri team for being recognized as a Leader in the 2024 Gartner Magic Quadrant!\n"
            "Saw your LinkedIn post congratulating your team during BDR appreciation week and I thought it was a great leadership quality!\n"
            "Congratulations on Responsive's groundbreaking launch of the AI-powered SRM platform at the B2B Summit! Transforming response times from 5 minutes to just 38 seconds is a remarkable achievement!\n"
            "The remarkable 227% ROI increase at Okta and significant time-saving feats beams spotlight on how integral structured hiring is! Congrats on the great execution and for saving countless business hours for your customers like E2open, Wrike and Navan!\n"
            "Congratulations on Chargebee's launch of Retention AI! An AI solution generates personalized and contextual offers to streamline the retention process sounds very innovative!\n"
            "Congrats on Soroco winning the AI Innovation Award at the 14th Shared Services Event! Your insights on pioneering AI technologies, specifically in the keynote, show the incredible depth of innovation at Soroco.\n"
            "It was awesome to see your enthusiastic wrap-up on the APMP India's Samagam 2024 event, showcasing Responsive AI's pivotal role in reshaping the proposal landscape, thanks for sharing!\n"
            "Congrats on Eftsure's powerful partnership with Westpac to enhance anti-fraud awareness! The scale of engagement with over 600 businesses is truly impressive, and I can only imagine the positive impact it's having.\n"
            "Awesome to see BrightEdge's detailed research on Google's AI Overviews! Great to learn that AI overviews have shifted to using more authoritative sources and are focusing more on comparative shopping content!\n"
            "Loved seeing your promotion of the 2024 State of Subscriptions report on LinkedIn and its importance for maintaining and growing revenue!\n"
            "Congratulations on the integration between Recruit CRM and Jobma! Streamlining your recruiting workflows that enables recruiters to screen, interview, and evaluate candidates within a single system, improving collaboration and candidate experience is pretty cool!\n"
            "Wow, Responsive Technology Partners' recent acquisitions of DTEL and ICS mark an impressive leap in strengthening IT and infrastructure services!\n"
            "Thrilled to see Engagedly LinkedIn post about AI's pivotal role in transforming HR management! Very cool to see 45% of HR professionals are currently using AI, while 39% plan to adopt it in the future!\n"
            "Read FirstHive's blog post about the shifting martech landscape and the massive growth trajectory of the global CDP market. It's cool to see the shift to first-party data for omni-channel experiences given the transition away from third party cookies!\n"
            "Read the post by your CTO, Pankaj Singh, about how AI is transforming HR at Engagedly by offering advanced solutions for performance and talent management, I learned a lot!\n"
            "Hats off to the remarkable strides Kovai.co has made in 2023, scaling Document360 with generative AI and hitting major revenue growth against challenging economic conditions. I'm sure you guys will hit your $100M ARR target by 2030!\n"
            "Amazing advancements at Cresta with your new AI capabilities like 'Behavior Discovery' and 'Generative AI Intents' which will help customers use AI to analyze conversations!\n"
        ))
        self.EMAIL_SUBJECT_LINE_SYSTEM_MESSAGE = SystemMessage(content=(
            "You are an exuberant sales person who is responsible for writing personalized cold emails that stand out to the prospect.\n"
            "You will be provided with prospect details and an email body that contains the content addressed to the prospect.\n"
            "Your goal is to write an email subject line that addresses the prospect in second-person and captures their attention.\n"
            "The email subject line should be highly relevant (not spammy) and should reference prospect details and the content in the email body.\n"
            "The email subject line should not be more than 5-6 words in length. It can include emojis but should not contain trailing dots (known as an Ellipsis). Questions are allowed.\n"
            "\n"
            "Here are some example email subject lines templates that you can use as inspiration:\n"
            "Anish, AI powered outreach at Chargebee?\n"
            "Sergio, personalization driven outreach?\n"
            "Accelerate growth with personalized outreach, Nicole?\n"
            "simplifying payments with AI, Zach\n"
            "Strategic Response Platform + AI marketing will be a game changer!\n"
            "Carly, saw you're focussed on AI dev tools\n"
            "Samantha, does less meetings sound interesting?\n"
            "Akhilesh, how about AI to query data?\n"
            "John, AI for research?\n"
            "Growth to Fortune 500,000 with analytics!\n"
            "Kyle, SearchGPT but for enterprise?\n"
            "Rishav, prospect discovery similar to App Discovery?\n"
            "Alice, what's your take on team productivity?\n"
            "Cameron, loved your insights from RecFest USA!\n"
            "Reduce dowtime due to outages, Mary!\n"
            "Saleem, scale hiring after Uber's Series D?\n"
        ))

    def generate_personalized_emails(self, email_template: Optional[LeadResearchReport.ChosenOutreachEmailTemplate], lead_research_report: LeadResearchReport) -> List[LeadResearchReport.PersonalizedEmail]:
        """Generates personalized emails for given outreach email template message (can be None, that's allowed) for given lead and returns the list."""
        all_highlights: List[LeadResearchReport.ReportDetail.Highlight] = lead_research_report.get_all_highlights()
        if len(all_highlights) == 0:
            raise ValueError(
                f"No highlights found for lead report ID: {lead_research_report.id}, cannot generate personalized emails.")

        # Fetch best highlights and chosen email template.
        referenced_highlights: List[LeadResearchReport.ReportDetail.Highlight] = self.get_best_highlights(
            all_highlights=all_highlights)
        logger.info(
            f"Got {len(referenced_highlights)} reference highlights IDs for email personalization for research report ID: {lead_research_report.id}.")

        if email_template == None:
            logger.info(
                f"No Email Template found for Lead report ID: {lead_research_report.id}")

        generated_personalized_emails: List[LeadResearchReport.PersonalizedEmail] = [
        ]
        with get_openai_callback() as cb:
            creation_date: datetime = Utils.create_utc_time_now()
            for highlight in referenced_highlights:
                new_email = self._create_personalized_email_helper(
                    highlight=highlight, email_template=email_template, lead_research_report=lead_research_report, creation_date=creation_date)
                generated_personalized_emails.append(new_email)

            self.openai_tokens_used = OpenAITokenUsage(highlight_ids=[highlight.id for highlight in referenced_highlights], operation_tag=Personalization.OPERATION_TAG_NAME,
                                                       prompt_tokens=cb.prompt_tokens, completion_tokens=cb.completion_tokens, total_tokens=cb.total_tokens, total_cost_in_usd=cb.total_cost)
            logger.info(
                f"Total tokens used in email personalization for report ID: {lead_research_report.id} is : {self.openai_tokens_used}")

        logger.info(
            f"Created {len(generated_personalized_emails)} personalized emails for lead report ID: {lead_research_report.id}")

        return generated_personalized_emails

    def create_personalized_email(self, highlight: LeadResearchReport.ReportDetail.Highlight, email_template: Optional[LeadResearchReport.ChosenOutreachEmailTemplate], lead_research_report: LeadResearchReport) -> LeadResearchReport.PersonalizedEmail:
        """Creates a personalized email for given highlight and email template for given report."""
        creation_date = Utils.create_utc_time_now()
        created_email: LeadResearchReport.PersonalizedEmail = None
        with get_openai_callback() as cb:
            created_email = self._create_personalized_email_helper(
                highlight=highlight, email_template=email_template, lead_research_report=lead_research_report, creation_date=creation_date)
            self.openai_tokens_used = OpenAITokenUsage(highlight_ids=[highlight.id], operation_tag=Personalization.OPERATION_TAG_NAME,
                                                       prompt_tokens=cb.prompt_tokens, completion_tokens=cb.completion_tokens, total_tokens=cb.total_tokens, total_cost_in_usd=cb.total_cost)
        return created_email

    def _create_personalized_email_helper(self, highlight: LeadResearchReport.ReportDetail.Highlight, email_template: Optional[LeadResearchReport.ChosenOutreachEmailTemplate], lead_research_report: LeadResearchReport, creation_date: datetime) -> LeadResearchReport.PersonalizedEmail:
        """Helper method to create a personalized email for given highlight and email template for given report."""
        email_template_message: Optional[str] = email_template.message if email_template else None
        # TODO: Right now, we are generating email subject line even for follow up emails which is not technically correct but it helps us
        # not make any changes to the email generation prompt. If users actually ask for this to be removed in the UI, we will definitely implement it.
        email_opener: Optional[str] = self.generate_email_opener_v2(
            highlight=highlight, lead_research_report=lead_research_report)
        email_subject_line: Optional[str] = self.generate_email_subject_line_v2(
            lead_research_report=lead_research_report, email_opener=email_opener, email_template_message=email_template_message)

        # Uncomment to use the older way to generate email subject lines and openers.
        # email_subject_line: str = self.generate_email_subject_line(highlight=highlight, lead_research_report=lead_research_report, email_template_message=email_template_message)
        # email_opener: str = self.generate_email_opener(highlight=highlight, lead_research_report=lead_research_report,
        #                                                email_template_message=email_template_message, email_subject_line=email_subject_line)

        return LeadResearchReport.PersonalizedEmail(
            id=ObjectId(),
            creation_date=creation_date,
            creation_date_readable_str=Utils.to_human_readable_date_str(
                creation_date),
            last_updated_date=creation_date,
            last_updated_date_readable_str=Utils.to_human_readable_date_str(
                creation_date),
            highlight_id=highlight.id,
            highlight_url=highlight.url,
            template=email_template,
            email_subject_line=email_subject_line,
            email_opener=email_opener,
        )

    def generate_email_subject_line(self, highlight: LeadResearchReport.ReportDetail.Highlight, lead_research_report: LeadResearchReport, email_template_message: Optional[str]) -> Optional[str]:
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

        llm = ChatOpenAI(temperature=1.3, model_name=self.OPENAI_GPT_4O_MODEL,
                         api_key=self.OPENAI_API_KEY, timeout=self.OPENAI_REQUEST_TIMEOUT_SECONDS).with_structured_output(EmailSubjectLine)

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

    def generate_email_opener(self, highlight: LeadResearchReport.ReportDetail.Highlight, lead_research_report: LeadResearchReport, email_template_message: Optional[str], email_subject_line: str) -> Optional[str]:
        """Generates Personalized email opener for lead using given highlight and email subject line.

        If email template is provided it is used in determining the email opener. If not, only information from lead research report, highlight and email subject line are used.
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
            "1. Hi [Prospect First Name],\n\nCongrats on the new job and for the launch of [Product Name], it's amazing that teams can now get value from [Product's feature].\n"
            "2. Hi [Prospect First Name],\n\nRead the recent [Report Name]  and noticed to my surprise that [interesting insight from the report] has changed in 2023 compared to 2022!\n"
            "3. Hi [Prospect First Name],\n\nNoticed that you recently spoke at [Event Name] about [Content about Talk], it was a great listen and I learned a lot!\n"
            "4. Hi [Prospect First Name],\n\nCongrats on the recent [Promotion] and for [Company Achievement]!\n"
            "5. Hi [Prospect First Name],\n\nNoticed your repost about [Product Launch and how it solves a problem]. Excited to see how [the product transforms the industry]\n"
            "6. Hi [Prospect First Name],\n\nLoved reading your thoughts on [Content]! It was inspiring to see how [Product or Company accomplishes something]!\n"
            "7. Hi [Prospect First Name],\n\nKudos on being recognized about [Recognition Description]! [Explain why the Recognition means something]\n"
            "8. Hi [Prospect First Name],\n\nThrilled to see you'll be sharing insights about [Product or some other Content]. Looking forward to learning [some detail about the Product or Content]!\n"
            "9. Hi [Prospect First Name],\n\nYour [Content or Post] were truly insightful! Given your expertise, I wanted to touch base on how you are addressing [Pain Point].\n"
            "10. Hi [Prospect First Name],\n\nCongratulations on how you are tacking [Pain Point] and achieving [accomplishment]! Your dedication to addressing [Problem] is truly inspiring, especially amidst [Challenges they are facing].\n"
            "11. Hi [Prospect First Name],\n\nI was truly inspired by your thoughts on [recent Content or Post]! Your proactive approach of [doing a task] reflects an exceptional commitment to [a set positive attributes].\n"
            "12. Hi [Prospect First Name],\n\nKudos on taking a step towards [Solving a Problem] with the launch of [Product]! It's inspiring to see how [Company Name] can [Accomplish something] using [Product or Feature].\n"
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

        llm = ChatOpenAI(temperature=1.3, model_name=self.OPENAI_GPT_4O_MODEL,
                         api_key=self.OPENAI_API_KEY, timeout=self.OPENAI_REQUEST_TIMEOUT_SECONDS).with_structured_output(EmailOpener)

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

    def generate_email_opener_v2(self, highlight: LeadResearchReport.ReportDetail.Highlight, lead_research_report: LeadResearchReport) -> Optional[str]:
        """Generate opening lines of an email using prospect details (from the report) and given highlight about the prospect."""
        human_message_prompt_template = (
            "**Prospect Details:**\n"
            "Name: {person_name}\n"
            "Company: {company_name}\n"
            "Role Title: {person_role_title}\n"
            "\n"
            "**Recent News Summary:**\n"
            "{concise_summary}\n"
            "News Summary Publish Date: {publish_date_readable_str}\n"
            f"Today's date: {Utils.to_human_readable_date_str(Utils.create_utc_time_now())}\n"
        )
        human_message_prompt = HumanMessagePromptTemplate.from_template(
            human_message_prompt_template)
        prompt = ChatPromptTemplate.from_messages(
            [
                self.EMAIL_OPENER_SYSTEM_MESSAGE,
                human_message_prompt,
            ]
        )

        class EmailOpener(BaseModel):
            email_opener: Optional[str] = Field(
                default=None, description="Hyper personalized opening lines of email addressed to the prospect.")

        llm = ChatOpenAI(temperature=1.3, model_name=self.OPENAI_GPT_4O_MODEL,
                         api_key=self.OPENAI_API_KEY, timeout=self.OPENAI_REQUEST_TIMEOUT_SECONDS).with_structured_output(EmailOpener)

        chain = prompt | llm
        result: EmailOpener = chain.invoke({
            "person_name": lead_research_report.person_name,
            "company_name": lead_research_report.company_name,
            "person_role_title": lead_research_report.person_role_title,
            "concise_summary": highlight.concise_summary,
            "publish_date_readable_str": highlight.publish_date_readable_str,
        })

        if not result.email_opener:
            logger.error(
                f"Email opener not generated for report ID: {lead_research_report.id}")
            return None

        # Prepend first name to the opener.
        first_name = lead_research_report.person_name.split(" ")[0]
        email_opener = f"Hi {first_name},\n\n{result.email_opener}"
        return email_opener

    def generate_email_subject_line_v2(self, lead_research_report: LeadResearchReport, email_opener: Optional[str], email_template_message: Optional[str]) -> Optional[str]:
        """Generates Personalized email subject line for lead using the given email that consists of personalized email opener and the template explaining the problem statement and value proposition.

        If email template is provided it is used in determining the email subject line. If not, only information from personalized opener and prospect details is used.
        """
        if not email_opener and not email_template_message:
            logger.error(
                f"Cannot generate email subject, Email opener and Email template are both are None in report ID: {lead_research_report.id}")
            return None

        # Construct email body with just opener if email template is None.
        # In the future, when template doesn't exist, generate linkedin message instead.
        email_body = ""
        if not email_opener:
            email_body = email_template_message
        else:
            email_body = email_opener
            if email_template_message:
                email_body = f"{email_body}\n{email_template_message}"

        human_message_prompt_template = (
            "**Prospect Details:**\n"
            "Name: {person_name}\n"
            "Company: {company_name}\n"
            "Role Title: {person_role_title}\n"
            "\n"
            "**Email Body:**\n"
            "{email_body}\n"
        )
        human_message_prompt = HumanMessagePromptTemplate.from_template(
            human_message_prompt_template)
        prompt = ChatPromptTemplate.from_messages(
            [
                self.EMAIL_SUBJECT_LINE_SYSTEM_MESSAGE,
                human_message_prompt,
            ]
        )

        class EmailSubjectLine(BaseModel):
            subject_line: Optional[str] = Field(
                default=None, description="Subject Line of the email.")

        llm = ChatOpenAI(temperature=1.3, model_name=self.OPENAI_GPT_4O_MODEL,
                         api_key=self.OPENAI_API_KEY, timeout=self.OPENAI_REQUEST_TIMEOUT_SECONDS).with_structured_output(EmailSubjectLine)

        chain = prompt | llm
        result: EmailSubjectLine = chain.invoke({
            "person_name": lead_research_report.person_name,
            "company_name": lead_research_report.company_name,
            "person_role_title": lead_research_report.person_role_title,
            "email_body": email_body,
        })
        return result.subject_line

    def get_best_highlights(self, all_highlights: List[LeadResearchReport.ReportDetail.Highlight], k: int = 3) -> List[LeadResearchReport.ReportDetail.Highlight]:
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
            ContentCategoryEnum.COMPANY_PARTNERSHIP,
            ContentCategoryEnum.PERSONAL_THOUGHTS,
            ContentCategoryEnum.PERSONAL_TALK_AT_EVENT,
            ContentCategoryEnum.PERSONAL_ADVICE,
            ContentCategoryEnum.PERSONAL_ANECDOTE,
            ContentCategoryEnum.PERSONAL_RECOGITION,
            ContentCategoryEnum.PERSONAL_PROMOTION,
            ContentCategoryEnum.PERSONAL_JOB_CHANGE,
            ContentCategoryEnum.FINANCIAL_RESULTS,
            ContentCategoryEnum.COMPANY_NEW_MARKET_EXPANSION,
            ContentCategoryEnum.IPO_ANNOUNCEMENT,
            ContentCategoryEnum.COMPANY_ACQUISITION,
            ContentCategoryEnum.COMPANY_ACQUIRED,
            ContentCategoryEnum.LEADERSHIP_HIRE,
            ContentCategoryEnum.COMPANY_COMPETITION,
            ContentCategoryEnum.COMPANY_CUSTOMERS,
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

    def get_tokens_used(self) -> Optional[OpenAITokenUsage]:
        """Returns tokens used so far in personalization. Can return None value if no calls to LLMs were made yet."""
        return self.openai_tokens_used


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    load_dotenv(".env.dev")

    database = Database()
    pz = Personalization(database=database)

    pz.generate_email_opener_v2(None, None)

    lead_research_report_id = "66ab9633a3bb9048bc1a0be5"
    # email_list = pz.generate_personalized_emails(
    #     lead_research_report_id=lead_research_report_id)
    # email_list_json = [email.model_dump_json() for email in email_list]

    # lead_research_report = database.get_lead_research_report(
    #     lead_research_report_id=lead_research_report_id)
    # pz.generate_email_subject_line(
    #     highlight=lead_research_report.details[0].highlights[0], lead_research_report=lead_research_report, email_template_message=None)
