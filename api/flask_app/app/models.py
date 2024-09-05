import logging
from typing import Optional, Annotated, List, Tuple, Dict
from deprecated import deprecated
from pydantic.functional_validators import BeforeValidator
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from app.utils import Utils
from enum import Enum
import re

logger = logging.getLogger()

# Represents an ObjectId field in the database.
# It will be represented as a `str` on the model so that it can be serialized to JSON.
# The Before validator will convert ObjectId from DB into string so model validation does not
# throw an error.
PyObjectId = Annotated[str, BeforeValidator(str)]


class User(BaseModel):
    """Represents a real user who has signed up for the application."""

    class State(str, Enum):
        # Enum defining current State of a user in the application.
        # This will help tailor application for each user.
        NEW_USER = "new_user"
        VIEWED_WELCOME_PAGE = "viewed_welcome_page"
        CREATED_FIRST_TEMPLATE = "created_first_template"
        ADDED_FIRST_LEAD = "added_first_lead"
        VIEWED_PERSONALIZED_EMAILS = "viewed_personalized_emails"

    id: Optional[str] = Field(
        alias="_id", default=None, description="Auth system generated unique identifier for authenticated user.")
    creation_date: Optional[datetime] = Field(
        default=None, description="Date in UTC timezone when this user document was inserted in the database.")
    last_updated_date: Optional[datetime] = Field(
        default=None, description="Date in UTC timezone when this user document was last updated in the database.")
    state: Optional[State] = Field(
        default=None, description="State of user using which we can tailor the frontend of the application. Example: User Onboarding.")


class OpenAITokenUsage(BaseModel):
    """Token usage when calling workflows using Open AI models."""
    url: Optional[str] = Field(default=None,
                               description="URL for which tokens are being tracked. Set when parsing web page and None otherwise.")
    highlight_ids: Optional[List[str]] = Field(
        default=None, description="Content Highlights that resulted in token usage. Set when personalizing email and None otherwise.")
    operation_tag: str = Field(
        ..., description="Tag describing the operation for which cost is computed.")
    prompt_tokens: int = Field(..., description="Prompt tokens used")
    completion_tokens: int = Field(..., description="Completion tokens used")
    total_tokens: int = Field(..., description="Total tokens used")
    total_cost_in_usd: float = Field(...,
                                     description="Total cost of tokens used.")

    def add_tokens(self, another: "OpenAITokenUsage") -> "OpenAITokenUsage":
        """Add and return tokens from another instance of OpenAITokenUsage class."""
        return OpenAITokenUsage(
            url=self.url,
            highlight_ids=self.highlight_ids,
            operation_tag=self.operation_tag,
            prompt_tokens=self.prompt_tokens + another.prompt_tokens,
            completion_tokens=self.completion_tokens + another.completion_tokens,
            total_tokens=self.total_tokens + another.total_tokens,
            total_cost_in_usd=self.total_cost_in_usd + another.total_cost_in_usd,
        )


class WebPage(BaseModel):
    """Model representing web page broken into header, body and footer elements."""
    id: Optional[PyObjectId] = Field(
        alias="_id", default=None, description="MongoDB generated unique identifier for web page.")
    creation_date: Optional[datetime] = Field(
        default=None, description="Date when this page was created in the database in UTC timezone.")

    url: str = Field(..., description="URL of the web page.")
    header: Optional[str] = Field(
        default=None, description="Header of the page in Markdown formatted text. None if no header exists.")
    body: Optional[str] = Field(
        default=None, description="Body of the page in Markdown formatted text.")
    footer: Optional[str] = Field(
        default=None, description="Footer of the page in Markdown formatted text. None if it does not exist.")


class ContentTypeEnum(str, Enum):
    """Enum values associated with ContentTypeSource class."""
    ARTICLE = "article"
    BLOG_POST = "blog_post"
    WHITE_PAPER = "white_paper"
    WEBINAR = "webinar"
    CASE_STUDY = "case_study"
    ANNOUCEMENT = "announcement"
    INTERVIEW = "interview"
    PODCAST = "podcast"
    DOCUMENTATION = "documentation"
    PANEL_DISCUSSION = "panel_discussion"
    LINKEDIN_POST = "linkedin_post"
    NONE_OF_THE_ABOVE = "none_of_the_above"


# Update Personalization class in personalization module whenever enums are updated below.
class ContentCategoryEnum(str, Enum):
    """Enum values associated with ContentCategory class."""
    PERSONAL_THOUGHTS = "personal_thoughts"
    PERSONAL_ADVICE = "personal_advice"
    PERSONAL_ANECDOTE = "personal_anecdote"
    PERSONAL_PROMOTION = "personal_promotion"
    PERSONAL_RECOGITION = "personal_recognition"
    PERSONAL_JOB_CHANGE = "personal_job_change"
    PERSONAL_EVENT_ATTENDED = "personal_event_attended"
    PERSONAL_TALK_AT_EVENT = "personal_talk_at_event"
    PRODUCT_LAUNCH = "product_launch"
    PRODUCT_UPDATE = "product_update"
    PRODUCT_SHUTDOWN = "product_shutdown"
    LEADERSHIP_HIRE = "leadership_hire"
    LEADERSHIP_CHANGE = "leadership_change"
    EMPLOYEE_PROMOTION = "employee_promotion"
    EMPLOYEE_LEAVING = "employee_leaving"
    COMPANY_HIRING = "company_hiring"
    FINANCIAL_RESULTS = "financial_results"
    COMPANY_STORY = "company_story"
    INDUSTRY_TRENDS = "industry_trends"
    COMPANY_PARTNERSHIP = "company_partnership"
    COMPANY_ACHIEVEMENT = "company_achievement"
    FUNDING_ANNOUNCEMENT = "funding_announcement"
    IPO_ANNOUNCEMENT = "ipo_announcement"
    COMPANY_RECOGNITION = "company_recognition"
    COMPANY_ANNIVERSARY = "company_anniversary"
    COMPANY_EVENT_HOSTED_ATTENDED = "company_event_hosted_attended"
    COMPANY_WEBINAR = "company_webinar"
    COMPANY_LAYOFFS = "company_layoffs"
    COMPANY_CHALLENGE = "company_challenge"
    COMPANY_REBRAND = "company_rebrand"
    COMPANY_NEW_MARKET_EXPANSION = "company_new_market_expansion"
    COMPANY_NEW_OFFICE = "company_new_office"
    COMPANY_SOCIAL_RESPONSIBILITY = "company_social_responsibility"
    COMPANY_LEGAL_CHALLENGE = "company_legal_challenge"
    COMPANY_REGULATION = "company_regulation"
    COMPANY_LAWSUIT = "company_lawsuit"
    COMPANY_INTERNAL_EVENT = "company_internal_event"
    COMPANY_OFFSITE = "company_offsite"
    NONE_OF_THE_ABOVE = "none_of_the_above"


def content_category_to_human_readable_str(category: ContentCategoryEnum) -> str:
    """Returns human readable string for given content category enum. Update this method whenever Enum class changes."""
    if category == ContentCategoryEnum.PERSONAL_THOUGHTS:
        return "Personal Thoughts"
    elif category == ContentCategoryEnum.PERSONAL_ADVICE:
        return "Personal Advice"
    elif category == ContentCategoryEnum.PERSONAL_ANECDOTE:
        return "Personal Anecdotes"
    elif category == ContentCategoryEnum.PERSONAL_PROMOTION:
        return "Personal Promotion"
    elif category == ContentCategoryEnum.PERSONAL_RECOGITION:
        return "Personal Recognition"
    elif category == ContentCategoryEnum.PERSONAL_JOB_CHANGE:
        return "Personal Job Change"
    elif category == ContentCategoryEnum.PERSONAL_EVENT_ATTENDED:
        return "Personal Events Attended"
    elif category == ContentCategoryEnum.PERSONAL_TALK_AT_EVENT:
        return "Personal Talks"
    elif category == ContentCategoryEnum.PRODUCT_LAUNCH:
        return "Product Launches"
    elif category == ContentCategoryEnum.PRODUCT_UPDATE:
        return "Product Updates"
    elif category == ContentCategoryEnum.PRODUCT_SHUTDOWN:
        return "Product Shutdowns"
    elif category == ContentCategoryEnum.LEADERSHIP_HIRE:
        return "Leadership Hires"
    elif category == ContentCategoryEnum.LEADERSHIP_CHANGE:
        return "Leadership Changes"
    elif category == ContentCategoryEnum.EMPLOYEE_PROMOTION:
        return "Employee Promotions"
    elif category == ContentCategoryEnum.EMPLOYEE_LEAVING:
        return "Employee Leaving"
    elif category == ContentCategoryEnum.COMPANY_HIRING:
        return "Company Hiring"
    elif category == ContentCategoryEnum.FINANCIAL_RESULTS:
        return "Company Financial Results"
    elif category == ContentCategoryEnum.COMPANY_STORY:
        return "Company Stories"
    elif category == ContentCategoryEnum.INDUSTRY_TRENDS:
        return "Industry Trends"
    elif category == ContentCategoryEnum.COMPANY_PARTNERSHIP:
        return "Company Patnerships"
    elif category == ContentCategoryEnum.COMPANY_ACHIEVEMENT:
        return "Company Achievements"
    elif category == ContentCategoryEnum.FUNDING_ANNOUNCEMENT:
        return "Funding Announcements"
    elif category == ContentCategoryEnum.IPO_ANNOUNCEMENT:
        return "IPO Announcement"
    elif category == ContentCategoryEnum.COMPANY_RECOGNITION:
        return "Company Recognition"
    elif category == ContentCategoryEnum.COMPANY_ANNIVERSARY:
        return "Company Anniversary"
    elif category == ContentCategoryEnum.COMPANY_EVENT_HOSTED_ATTENDED:
        return "Company Events or Conferences"
    elif category == ContentCategoryEnum.COMPANY_WEBINAR:
        return "Company Webinars"
    elif category == ContentCategoryEnum.COMPANY_LAYOFFS:
        return "Company Layoffs"
    elif category == ContentCategoryEnum.COMPANY_CHALLENGE:
        return "Company Challenges"
    elif category == ContentCategoryEnum.COMPANY_REBRAND:
        return "Company Rebrand"
    elif category == ContentCategoryEnum.COMPANY_NEW_MARKET_EXPANSION:
        return "Company New Market Expansion News"
    elif category == ContentCategoryEnum.COMPANY_NEW_OFFICE:
        return "Company New Office Openings"
    elif category == ContentCategoryEnum.COMPANY_SOCIAL_RESPONSIBILITY:
        return "Company Social Initiatives"
    elif category == ContentCategoryEnum.COMPANY_LEGAL_CHALLENGE:
        return "Company Legal Challenges"
    elif category == ContentCategoryEnum.COMPANY_REGULATION:
        return "Company Regulation Challenges"
    elif category == ContentCategoryEnum.COMPANY_LAWSUIT:
        return "Company Lawsuits"
    elif category == ContentCategoryEnum.COMPANY_INTERNAL_EVENT:
        return "Company Internal Events"
    elif category == ContentCategoryEnum.COMPANY_OFFSITE:
        return "Company Offsites"
    elif category == ContentCategoryEnum.NONE_OF_THE_ABOVE:
        return "None of the Above"


class ContentDetails(BaseModel):
    """
    Contains details related to a lead or company (or both) found using various workflows.

    Example workflows:
    1. Using search engine to find page and then scrape it manually or using an API (e.g. LinkedIn posts).
    2. Scraping company website directly.
    3. Calling specific APIs like Crunchbase, NYSE for information about the company.

    In the future, we can add more workflows if needed.
    """
    class ProcessingStatus(str, Enum):
        FAILED_MISSING_PUBLISH_DATE = "failed_missing_publish_date"
        FAILED_UNRELATED_TO_COMPANY = "failed_unrelated_to_company"
        COMPLETE = "complete"

    id: Optional[PyObjectId] = Field(
        alias="_id", default=None, description="MongoDB generated unique identifier for web search result.")
    creation_date: Optional[datetime] = Field(
        default=None, description="Date in UTC timezone when this document was inserted in the database.")
    url: Optional[str] = Field(
        default=None, description="URL of the content if any.")

    # Metadata associated with the content.
    search_engine_query: Optional[str] = Field(
        ..., description="Search engine query that resulted in this URL.")
    person_name: Optional[str] = Field(
        default=None, description="Full name of person. Populated only when the workflow was explicitly searching for person information and None when searching for only company information.")
    company_name: Optional[str] = Field(
        default=None, description="Company name used when searching content. Should mostly be populated, there may be some exceptions that are not known as of now.")
    person_role_title: Optional[str] = Field(
        default=None, description="Role title of person at company. Populated only when person_name is populated and None otherwise.")
    person_profile_id: Optional[str] = Field(
        default=None, description="PersonProfile reference of this person. Populated only when person_name is populated and None otherwise.")
    web_page_ref_id: Optional[str] = Field(
        default=None, description="Reference ID to the parent web page that is stored in the database.")
    linkedin_post_ref_id: Optional[str] = Field(
        default=None, description="Reference ID to the parent LinkedIn post that is stored in the database.")
    company_profile_id: Optional[str] = Field(
        default=None, description="Reference ID to the Company Profile that is stored in the database.")

    # Content related fields below.
    processing_status: Optional[ProcessingStatus] = Field(
        default=None, description="Processing status of the content.")
    type: Optional[ContentTypeEnum] = Field(
        default=None, description="Type of content (Interview, podcast, blog, article, LinkedIn post etc.).")
    type_reason: Optional[str] = Field(
        default=None, description="Reason for chosen enum value of type.")
    author: Optional[str] = Field(
        default=None, description="Full name of author of content if any.")
    publish_date: Optional[datetime] = Field(
        default=None, description="Date when this content was published in UTC timezone.")
    detailed_summary: Optional[str] = Field(default=None,
                                            description="A detailed summary of the content.")
    concise_summary: Optional[str] = Field(default=None,
                                           description="A concise summary of the content.")
    category: Optional[ContentCategoryEnum] = Field(
        default=None, description="Category of the content found")
    category_reason: Optional[str] = Field(
        default=None, description="Reason for chosen enum value of category.")
    key_persons: Optional[List[str]] = Field(
        default=None, description="Names of key persons extracted from the content.")
    key_organizations: Optional[List[str]] = Field(
        default=None, description="Names of key organizations extracted from the content.")
    requesting_user_contact: Optional[bool] = Field(
        default=False, description="Whether the page is requesting user contact information in exchange for access to white paper, case study, webinar etc. Always False for LinkedIn posts.")
    focus_on_company: Optional[bool] = Field(
        default=False, description="Whether the content is related to the Company.")
    num_linkedin_reactions: Optional[int] = Field(
        default=None, description="Number of LinkedIn reactions for a post. Set only for LinkedIn post content and None otherwise.")
    num_linkedin_comments: Optional[int] = Field(
        default=None, description="Number of LinkedIn comments for a post. Set only for LinkedIn post content and None otherwise.")

    openai_tokens_used: Optional[OpenAITokenUsage] = Field(
        default=None, description="Total Open AI tokens used in fetching this content info.")

    # To prevent encoding error, see https://stackoverflow.com/questions/65209934/pydantic-enum-field-does-not-get-converted-to-string.

    class Config:
        use_enum_values = True


class LeadResearchReport(BaseModel):
    """Research report associated with a lead."""

    class Status(str, Enum):
        # Fetched basic details about the person and company.
        NEW = "new"
        BASIC_PROFILE_FETCHED = "basic_profile_fetched"
        URLS_FROM_SEARCH_ENGINE_FETCHED = "urls_from_search_engine_fetched"
        CONTENT_PROCESSING_COMPLETE = "content_processing_complete"
        RECENT_NEWS_AGGREGATION_COMPLETE = "recent_news_aggregation_complete"
        EMAIL_TEMPLATE_SELECTION_COMPLETE = "email_template_selection_complete"
        COMPLETE = "complete"
        FAILED_WITH_ERRORS = "failed_with_errors"

    class ReportDetail(BaseModel):
        """Details associated with the report."""
        class Highlight(BaseModel):
            """Highhlight associated with report."""
            id: Optional[PyObjectId] = Field(default=None,
                                             description="ID of the Content detail referenced in creating this highlight.")
            category: Optional[ContentCategoryEnum] = Field(default=None,
                                                            description="Category of the content. Field is repeated at outer level too.")
            category_readable_str: Optional[str] = Field(
                default=None, description="Human readable Category string.")
            concise_summary: Optional[str] = Field(default=None,
                                                   description="Concise summary of the content.")
            publish_date: Optional[datetime] = Field(default=None,
                                                     description="Publish date of the content.")
            publish_date_readable_str: Optional[str] = Field(default=None,
                                                             description="Human readable publish date string.")
            url: Optional[str] = Field(
                default=None, description="URL of the content.")

        category: Optional[ContentCategoryEnum] = Field(default=None,
                                                        description="Category of the highlights.")
        category_readable_str: Optional[str] = Field(
            default=None, description="Human readable Category string.")
        highlights: Optional[List[Highlight]] = Field(
            default=None, description="List of Highlights associated with given category.")

    class ChosenOutreachEmailTemplate(BaseModel):
        """Outreach Template chosen for this Lead. If ID is None, then none of the existing templates were chosen at that time."""
        id: Optional[PyObjectId] = Field(
            default=None, description="ID of the selected OutreachEmailTemplate. Set to None if none of the templates created by the user were selected.")
        creation_date: Optional[datetime] = Field(
            default=None, description="Date in UTC Timezone when the template choosing was done. It is set even when no template is chosen.")
        name: Optional[str] = Field(
            default=None, description="Name of the temmplate selected.")
        message: Optional[str] = Field(
            default=None, description="Message template used for outreach to role titles above.")
        reason: Optional[str] = Field(
            default=None, description="Reason why this template or None was selected.")

    class PersonalizedEmail(BaseModel):
        """Personalized Email addressed to a given lead in the lead research report. Uses chosen template if it exists else generates email without template."""
        id: Optional[PyObjectId] = Field(
            alias="_id", default=None, description="MongoDB generated unique identifier for Personalized Email.")
        creation_date: Optional[datetime] = Field(
            default=None, description="Date in UTC timezone when this document was inserted in the database.")
        creation_date_readable_str: Optional[str] = Field(
            default=None, description="Human Readable Date string when this document was inserted in the database.")
        # If the user wants to edit generated emails.
        last_updated_date: Optional[datetime] = Field(
            default=None, description="Date in UTC timezone when this document was last updated in the database.")
        last_updated_date_readable_str: Optional[str] = Field(
            default=None, description="Human Readable Date string when this document was last updated in the database.")
        highlight_id: Optional[str] = Field(
            default=None, description="The IDs of the Highlight that was referenced to generate this personalized email.")
        highlight_url: Optional[str] = Field(
            default=None, description="The source URL which was used to create the highlight.")
        email_subject_line: Optional[str] = Field(
            default=None, description="Generated subject Line of the email.")
        email_opener: Optional[str] = Field(
            default=None, description="1-2 line opener of the email referencing the highlights mentioned above.")

    id: Optional[PyObjectId] = Field(
        alias="_id", default=None, description="MongoDB generated unique identifier for Lead Research Report.")
    creation_date: Optional[datetime] = Field(
        default=None, description="Date in UTC timezone when this document was inserted in the database.")
    last_updated_date: Optional[datetime] = Field(
        default=None, description="Date in UTC timezone when this document was last updated in the database.")
    person_linkedin_url: Optional[str] = Field(
        default=None, description="LinkedIn URL of the person's profile.")
    person_profile_id: Optional[str] = Field(
        default=None, description="PersonProfile reference of this lead.")
    company_profile_id: Optional[str] = Field(
        default=None, description="Reference ID to the Company Profile that is stored in the database.")
    person_name: Optional[str] = Field(
        default=None, description="Full name of person being researched.")
    company_name: Optional[str] = Field(
        default=None, description="Company name of the person being researched.")
    person_role_title: Optional[str] = Field(
        default=None, description="Role title of person at company.")
    status: Optional[Status] = Field(
        default=None, description="Status of the report creation at given point in time.")
    status_before_failure: Optional[Status] = Field(
        default=None, description="Last status before report creation failed. It is set only if current status is failed_with_errors.")
    company_headcount: Optional[int] = Field(
        default=None, description="Company Headcount during document creation.")
    company_industry_categories: Optional[List[str]] = Field(
        default=None, description="Company Industry categories")
    user_id: Optional[str] = Field(
        default=None, description="User ID of the person who created this report.")

    # Store search results.
    search_results_map: Optional[Dict[str, List[str]]] = Field(
        default=None, description="Search result links grouped by search query.")

    # Search Result URLs whose contents failed to be parsed by the web scraper.
    content_parsing_failed_urls: Optional[List[str]] = Field(
        default=None, description="Search Result URLs whose contents failed to be parsed by the web scraper.")

    # Report Details fields.
    report_creation_date_readable_str: Optional[str] = Field(
        default=None, description="Date string when report was created. Note that report is only created after status is complete.")
    report_publish_cutoff_date: Optional[datetime] = Field(
        None, description="Publish Date cutoff beyond which report is created. This can be 3 months, 6 months, 12 months etc. before report creation date.")
    report_publish_cutoff_date_readable_str: Optional[str] = Field(
        default=None, description="Report Publish Date human readable string value.")
    details: Optional[List[ReportDetail]] = Field(
        default=None, description="Report details associated with the lead.")

    # Chosen Outreach Email template.
    chosen_outreach_email_template: Optional[ChosenOutreachEmailTemplate] = Field(
        default=None, description="Outreach Email template that matches this Lead's profile.")

    # Outreach fields.
    personalized_emails: Optional[List[PersonalizedEmail]] = Field(
        default=None, description="List of Personalized emails that will be used for outreach.")
    personalized_emails_tokens_used: Optional[OpenAITokenUsage] = Field(
        default=None, description="Total Open AI tokens used in generating personalized emails.")

    # Methods.
    def get_all_highlights(self):
        """Returns all highlights for given report."""
        all_highlights: List[LeadResearchReport.ReportDetail.Highlight] = []
        for report_detail in self.details:
            all_highlights.extend(report_detail.highlights)
        return all_highlights


class OutreachEmailTemplate(BaseModel):
    """Email template created by a user for outreach."""
    id: Optional[PyObjectId] = Field(
        alias="_id", default=None, description="MongoDB generated unique identifier for Outreach Email Template.")
    user_id: Optional[str] = Field(
        default=None, description="User ID of the user who created the email template.")
    creation_date: Optional[datetime] = Field(
        default=None, description="Date in UTC timezone when this document was inserted in the database.")
    creation_date_readable_str: Optional[str] = Field(
        default=None, description="Human Readable Date string when this document was inserted in the database.")
    name: Optional[str] = Field(
        default=None, description="User provided name to reference this template.")
    persona_role_titles: Optional[List[str]] = Field(
        default=None, description="Role Titles for the persona this template is targeting. Can be more than one title.")
    description: Optional[str] = Field(
        default=None, description="Free form text describing the persona's skillset or specific interests.")
    message: Optional[str] = Field(
        default=None, description="Message template used for outreach to role titles above.")
    last_updated_date: Optional[datetime] = Field(
        default=None, description="Date in UTC timezone when this document was last updated in the database.")
    last_updated_date_readable_str: Optional[str] = Field(
        default=None, description="Human Readable Date string when this document was last updated in the database.")

    def to_persona_description_markdown(self) -> str:
        """Returns Persona description formatted as Markdown string."""
        return (
            "## Persona Details\n"
            f"ID: {self.id}\n"
            f"Role Titles: {self.persona_role_titles}\n"
            f"Description: {self.description if self.description else 'Unknown'}\n"
            "\n"
        )


class PersonProfile(BaseModel):
    """Profile of a person.

    Most of the information is from Proxycurl's Person LinkedIn Profile API response.

    Other fields will be enriched manually or using other sources.
    """

    class Date(BaseModel):
        """Representation of date in Proxycurl's API response."""
        day: int = Field(...)
        month: int = Field(...)
        year: int = Field(...)

    class Experience(BaseModel):
        """Professional Experience of person."""

        starts_at: Optional[datetime] = Field(
            default=None, description="Start date of job in UTC timezone.")
        ends_at: Optional[datetime] = Field(
            default=None, description="End date of job in UTC timezone.")
        company: Optional[str] = Field(
            default=None, description="Company name.")
        company_linkedin_profile_url: Optional[str] = Field(
            default=None, description="Company LinkedIn Page URL.")
        title: Optional[str] = Field(
            default=None, description="Role title of the person in this job."),
        description: Optional[str] = Field(
            default=None, description="Description of role responsibilities.")
        location: Optional[str] = Field(
            default=None, description="Country or City of the job")

        @field_validator('starts_at', 'ends_at', mode='before')
        @classmethod
        def parse_date_published(cls, v):
            """Convert date object to datetime object."""
            if not v:
                # Date is None, nothing to do here.
                return None
            if isinstance(v, datetime):
                # Already correct type, do nothing.
                # This happens when reading object from Database.
                return v

            # Field has Date format. Happens when reading object from Proxycurl API response.
            profile_date = PersonProfile.Date(**v)
            # Convert Date object to datetime object in UTC timezone.
            return Utils.create_utc_datetime(day=profile_date.day, month=profile_date.month, year=profile_date.year)

        def to_markdown(self) -> str:
            """Returns Markdown formatted string for given experience. Used for email template matching."""
            duration_str = ""
            if self.starts_at:
                duration_str = Utils.to_human_readable_date_str(
                    self.starts_at) + " - "

            if self.ends_at:
                duration_str += Utils.to_human_readable_date_str(self.ends_at)
            elif self.starts_at:
                # Start date exists but no end date, current experience.
                duration_str += "Current"

            return (
                "## Experience\n"
                f"Duration: {duration_str if duration_str != '' else 'Unknown'}\n"
                f"Company: {self.company if self.company else 'Unknown'}\n"
                f"Role Title: {self.title if self.title else 'Unknown'}\n"
                f"Role Description: {self.description if self.description else 'Unknown'}\n"
                "\n"
            )

    class Education(BaseModel):
        """Education details of this person."""
        starts_at: Optional[datetime] = Field(
            default=None, description="Start date of education")
        ends_at: Optional[datetime] = Field(
            default=None, description="End date of education")
        field_of_study: Optional[str] = Field(
            default=None, description="Field of Study")
        degree_name: Optional[str] = Field(
            default=None, description="Degree received")
        school: Optional[str] = Field(
            default=None, description="School where degree was received")
        school_linked_profile_url: Optional[str] = Field(
            default=None, description="LinkedIn profile URL of School where degree was received")
        description: Optional[str] = Field(
            default=None, description="Description of education experience.")

        @field_validator('starts_at', 'ends_at', mode='before')
        @classmethod
        def parse_date_published(cls, v):
            """Convert date object to datetime object."""
            if not v:
                # Date is None, nothing to do here.
                return None

            if isinstance(v, datetime):
                # Already correct type, do nothing.
                # This happens when reading object from Database.
                return v

            # Field has Date format. Happens when reading object from Proxycurl API response.
            profile_date = PersonProfile.Date(**v)
            # Convert Date object to datetime object in UTC timezone.
            return Utils.create_utc_datetime(day=profile_date.day, month=profile_date.month, year=profile_date.year)

        def to_markdown(self) -> str:
            """Returns Markdown formatted string for given education. Used for email template matching."""
            duration_str = ""
            if self.starts_at:
                duration_str = Utils.to_human_readable_date_str(
                    self.starts_at) + " - "

            if self.ends_at:
                duration_str += Utils.to_human_readable_date_str(self.ends_at)
            elif self.starts_at:
                # Start date exists but no end date, current experience.
                duration_str += "Current"

            return (
                "## Education\n"
                f"Duration: {duration_str if duration_str != '' else 'Unknown'}\n"
                f"School: {self.school if self.school else 'Unknown'}\n"
                f"Degree: {self.degree_name if self.degree_name else 'Unknown'}\n"
                f"Description: {self.description if self.description else 'Unknown'}\n"
                "\n"
            )

    class AccomplishmentOrg(BaseModel):
        """Defined by Proxycurl: https://nubela.co/proxycurl/docs#people-api-person-profile-endpoint-response-accomplishmentorg"""
        starts_at: Optional[datetime] = Field(
            default=None, description="Start date at org")
        ends_at: Optional[datetime] = Field(
            default=None, description="End date at org")
        org_name: Optional[str] = Field(default=None, description="Org name")
        title: Optional[str] = Field(default=None, description="Role Title")
        description: Optional[str] = Field(
            default=None, description="Role Description")

        @field_validator('starts_at', 'ends_at', mode='before')
        @classmethod
        def parse_date_published(cls, v):
            """Convert date object to datetime object."""
            if not v:
                # Date is None, nothing to do here.
                return None
            if isinstance(v, datetime):
                # Already correct type, do nothing.
                # This happens when reading object from Database.
                return v

            # Field has Date format. Happens when reading object from Proxycurl API response.
            profile_date = PersonProfile.Date(**v)
            # Convert Date object to datetime object in UTC timezone.
            return Utils.create_utc_datetime(day=profile_date.day, month=profile_date.month, year=profile_date.year)

    class Publication(BaseModel):
        """Defined by Proxycurl: https://nubela.co/proxycurl/docs#people-api-person-profile-endpoint-response-publication"""
        name: Optional[str] = Field(
            default=None, description="Name of publication")
        publisher: Optional[str] = Field(
            default=None, description="Publishing Organization Body")
        published_on: Optional[datetime] = Field(
            default=None, description="Date of publication in UTC timezone.")
        description: Optional[str] = Field(
            default=None, description="Description of publication")
        url: Optional[str] = Field(
            default=None, description="URL of publication")

        @field_validator('published_on', mode='before')
        @classmethod
        def parse_date_published(cls, v):
            """Convert date object to datetime object."""
            if not v:
                # Date is None, nothing to do here.
                return None
            if isinstance(v, datetime):
                # Already correct type, do nothing.
                # This happens when reading object from Database.
                return v

            # Field has Date format. Happens when reading object from Proxycurl API response.
            profile_date = PersonProfile.Date(**v)
            # Convert Date object to datetime object in UTC timezone.
            return Utils.create_utc_datetime(day=profile_date.day, month=profile_date.month, year=profile_date.year)

    class HonourAward(BaseModel):
        """Defined by Proxycurl: https://nubela.co/proxycurl/docs#people-api-person-profile-endpoint-response-honouraward"""
        title: Optional[str] = Field(
            default=None, description="Title of honor or award.")
        issuer: Optional[str] = Field(
            default=None, description="Organization that issued this award or honor.")
        issued_on: Optional[datetime] = Field(
            default=None, description="Date of issue in UTC timezone.")
        description: Optional[str] = Field(
            default=None, description="Description of honor or award")

        @field_validator('issued_on', mode='before')
        @classmethod
        def parse_date_published(cls, v):
            """Convert date object to datetime object."""
            if not v:
                # Date is None, nothing to do here.
                return None
            if isinstance(v, datetime):
                # Already correct type, do nothing.
                # This happens when reading object from Database.
                return v

            # Field has Date format. Happens when reading object from Proxycurl API response.
            profile_date = PersonProfile.Date(**v)
            # Convert Date object to datetime object in UTC timezone.
            return Utils.create_utc_datetime(day=profile_date.day, month=profile_date.month, year=profile_date.year)

    class Patent(BaseModel):
        """Defined by Proxycurl: https://nubela.co/proxycurl/docs#people-api-person-profile-endpoint-response-patent"""
        title: Optional[str] = Field(
            default=None, description="Title of the patent.")
        issuer: Optional[str] = Field(
            default=None, description="Organization that issued the patent.")
        issued_on: Optional[datetime] = Field(
            default=None, description="Date of issue of patent in UTC timezone.")
        description: Optional[str] = Field(
            default=None, description="Description of patent")
        application_number: Optional[str] = Field(
            default=None, description="Application number of patent")
        patent_number: Optional[str] = Field(
            default=None, description="Identifier of the patent.")
        url: Optional[str] = Field(
            default=None, description="URL of patent")

        @field_validator('issued_on', mode='before')
        @classmethod
        def parse_date_published(cls, v):
            """Convert date object to datetime object."""
            if not v:
                # Date is None, nothing to do here.
                return None
            if isinstance(v, datetime):
                # Already correct type, do nothing.
                # This happens when reading object from Database.
                return v

            # Field has Date format. Happens when reading object from Proxycurl API response.
            profile_date = PersonProfile.Date(**v)
            # Convert Date object to datetime object in UTC timezone.
            return Utils.create_utc_datetime(day=profile_date.day, month=profile_date.month, year=profile_date.year)

    class Project(BaseModel):
        """Defined by Proxycurl: https://nubela.co/proxycurl/docs#people-api-person-profile-endpoint-response-project"""
        starts_at: Optional[datetime] = Field(
            default=None, description="Start date of project")
        ends_at: Optional[datetime] = Field(
            default=None, description="End date of project")
        title: Optional[str] = Field(
            default=None, description="Title of the project.")
        description: Optional[str] = Field(
            default=None, description="Description of the project.")
        url: Optional[str] = Field(
            default=None, description="URL of the project.")

        @field_validator('starts_at', 'ends_at', mode='before')
        @classmethod
        def parse_date_published(cls, v):
            """Convert date object to datetime object."""
            if not v:
                # Date is None, nothing to do here.
                return None
            if isinstance(v, datetime):
                # Already correct type, do nothing.
                # This happens when reading object from Database.
                return v

            # Field has Date format. Happens when reading object from Proxycurl API response.
            profile_date = PersonProfile.Date(**v)
            # Convert Date object to datetime object in UTC timezone.
            return Utils.create_utc_datetime(day=profile_date.day, month=profile_date.month, year=profile_date.year)

    class Certification(BaseModel):
        """Defined by Proxycurl: https://nubela.co/proxycurl/docs#people-api-person-profile-endpoint-response-certification"""
        starts_at: Optional[datetime] = Field(
            default=None, description="Start date of certification")
        ends_at: Optional[datetime] = Field(
            default=None, description="End date of certification")
        name: Optional[str] = Field(
            default=None, description="Name of the course.")
        authority: Optional[str] = Field(
            default=None, description="Org body issuing ceritficate.")

        @field_validator('starts_at', 'ends_at', mode='before')
        @classmethod
        def parse_date_published(cls, v):
            """Convert date object to datetime object."""
            if not v:
                # Date is None, nothing to do here.
                return None
            if isinstance(v, datetime):
                # Already correct type, do nothing.
                # This happens when reading object from Database.
                return v

            # Field has Date format. Happens when reading object from Proxycurl API response.
            profile_date = PersonProfile.Date(**v)
            # Convert Date object to datetime object in UTC timezone.
            return Utils.create_utc_datetime(day=profile_date.day, month=profile_date.month, year=profile_date.year)

    class Article(BaseModel):
        """Defined by Proxycurl: https://nubela.co/proxycurl/docs#people-api-person-profile-endpoint-response-article"""
        title: Optional[str] = Field(
            default=None, description="Title of the article.")
        link: Optional[str] = Field(
            default=None, description="Link to the article.")
        published_date: Optional[datetime] = Field(
            default=None, description="Date when article was published.")
        author: Optional[str] = Field(
            default=None, description="Full name of author of article.")
        image_url: Optional[str] = Field(
            default=None, description="Image URL of the article.")

        @field_validator('published_date', mode='before')
        @classmethod
        def parse_date_published(cls, v):
            """Convert date object to datetime object."""
            if not v:
                # Date is None, nothing to do here.
                return None
            if isinstance(v, datetime):
                # Already correct type, do nothing.
                # This happens when reading object from Database.
                return v

            # Field has Date format. Happens when reading object from Proxycurl API response.
            profile_date = PersonProfile.Date(**v)
            # Convert Date object to datetime object in UTC timezone.
            return Utils.create_utc_datetime(day=profile_date.day, month=profile_date.month, year=profile_date.year)

    class PersonGroup(BaseModel):
        """Defined by Proxycurl: https://nubela.co/proxycurl/docs#people-api-person-profile-endpoint-response-persongroup"""
        name: Optional[str] = Field(
            default=None, description="Name of the LinkedIn group.")
        url: Optional[str] = Field(
            default=None, description="URL to the LinkedIn group.")

    id: Optional[PyObjectId] = Field(
        alias="_id", default=None, description="MongoDB generated unique identifier for the Person profile.")
    linkedin_url: Optional[str] = Field(
        default=None, description="URL of the LinkedIn profile.")
    creation_date: Optional[datetime] = Field(
        default=None, description="Date when this profile was created in the database in UTC timezone. Assume we synced this from Proxycurl on the same date.")

    public_identifier: str = Field(...,
                                   description="LinkedIn public Identifier of profile.")
    first_name: str = Field(..., description="First name of person.")
    last_name: str = Field(..., description="Last name of person.")
    full_name: str = Field(..., description="Full name of person.")
    follower_count: Optional[int] = Field(default=None,
                                          description="Follower count of the person.")
    occupation: Optional[str] = Field(
        default=None, description="Occupation of the person.")
    headline: Optional[str] = Field(
        default=None, description="Headline of the person's profile, has useful information about person's role sometimes.")
    summary: Optional[str] = Field(default=None,
                                   description="About section of person's profile, extremely useful.")
    country_full_name: Optional[str] = Field(
        default=None, description="Country where person lives.")
    city: Optional[str] = Field(
        default=None, description="City where the person resides.")
    state: Optional[str] = Field(
        default=None, description="State where this person resides.")
    experiences: List[Experience] = Field(
        ..., description="List of professional experiences of the person.")
    education: List[Education] = Field(...,
                                       description="Education experiences of the person.")
    accomplishment_organisations: List[AccomplishmentOrg] = Field(
        ..., description="List of organizations that this person is part of.")
    accomplishment_publications: List[Publication] = Field(
        ..., description="List of person's publications")
    accomplishment_honors_awards: List[HonourAward] = Field(
        ..., description="List of person's awards or honors")
    accomplishment_patents: List[Patent] = Field(
        ..., description="List of person's patents")
    accomplishment_projects: List[Project] = Field(
        ..., description="List of person's projects.")
    certifications: List[Certification] = Field(
        ..., description="List of person's certifications.")
    recommendations: List[str] = Field(
        ..., description="List of recommendations made by other users about this person.")
    articles: List[Article] = Field(
        ..., description="List of articles written by this person.")
    groups: List[PersonGroup] = Field(
        ..., description="List of LinekdIn groups this person is part of.")
    skills: List[str] = Field(...,
                              description="List of skills that this user has.")

    def get_company_and_role_title(self) -> Tuple[str, str]:
        """Returns current company and role title (at company) in that order for given person."""
        # Currently, we will assume that the first element in the experiences array that has end date None is the current employment.
        current_employment: Optional[PersonProfile.Experience] = None
        for exp in self.experiences:
            if exp.ends_at == None:
                # Current employment.
                current_employment = exp
                break
        if current_employment and current_employment.title and current_employment.company:
            return (current_employment.company, current_employment.title)

        raise ValueError(
            f"Failed to get current company and role title: Atleast one of Current Employment, Company name or Role title in: {current_employment} is None in Person Profile: {self}")

    def deprecated_get_company_and_role_title(self) -> Tuple[str, str]:
        # This is a rather unreliable way to check Role Title and Company.
        # ProxyCurl often returns occupation field to be the same as profile headline which is different from
        # what their API says, hence unreliable.
        # Profiles for which this failed include: https://www.linkedin.com/in/bhavishaggarwal/, https://www.linkedin.com/in/profilevamsikrishna/ and
        # https://www.linkedin.com/in/hemesh-singh-65441a133/. They all had different formats.
        match = re.search("(.+) at (.+)", self.occupation)
        if match:
            role_title: str = match.group(1)
            company_name: str = match.group(2)
            return (company_name, role_title)

        raise ValueError(
            f"Person Profile Occupation not in expected format for: {self}")

    def get_company_linkedin_url(self, company_name: str) -> str:
        """Returns company LinkedIn URL from person's experiences for given company name."""
        experience: Optional[PersonProfile.Experience] = next(
            filter(lambda e: e.company == company_name, self.experiences), None)
        if not experience:
            raise ValueError(
                f"Could not find experience in profile with company: {company_name}. Profile: {self}")
        return experience.company_linkedin_profile_url

    def to_markdown(self) -> str:
        """Returns Markdown representation of the person's profile. Will be used to match outreach email templates."""

        markdown: str = (
            f"Name: {self.full_name}\n"
            f"Occupation: {self.occupation}\n"
            f"Profile Headline:  {self.headline}\n"
            f"About: {self.summary if self.summary else 'Unknown'}\n"
            f"Skills: {str(self.skills) if len(self.skills) > 0 else 'Unknown'}\n"
            "\n"
        )
        for exp in self.experiences:
            markdown += exp.to_markdown()

        for ed in self.education:
            markdown += ed.to_markdown()

        return markdown


class CompanyProfile(BaseModel):
    """Company Profile.

    Most of the information is from Proxycurl's Company Profile API response.

    Other fields will be enriched manually or using other sources.
    """
    class Date(BaseModel):
        """Representation of date in Proxycurl's API response."""
        day: int = Field(...)
        month: int = Field(...)
        year: int = Field(...)

    class CompanyLocation(BaseModel):
        """Location of company."""
        country: Optional[str] = Field(
            default=None, description="Name of the country")
        city: Optional[str] = Field(
            default=None, description="Name of the city")
        postal_code: Optional[str] = Field(
            default=None, description="Postal code of address")
        line_1: Optional[str] = Field(
            default=None, description="First line of address")
        is_hq: Optional[bool] = Field(
            default=None, description="Whether the location is HQ or not.")
        state: Optional[str] = Field(
            default=None, description="State where location exists.")

    class CompanyType(str, Enum):
        """Types of Companies as defined in https://nubela.co/proxycurl/docs#company-api-company-profile-endpoint."""
        EDUCATIONAL = "EDUCATIONAL"
        GOVERNMENT_AGENCY = "GOVERNMENT_AGENCY"
        NON_PROFIT = "NON_PROFIT"
        PARTNERSHIP = "PARTNERSHIP"
        PRIVATELY_HELD = "PRIVATELY_HELD"
        PUBLIC_COMPANY = "PUBLIC_COMPANY"
        SELF_EMPLOYED = "SELF_EMPLOYED"
        SELF_OWNED = "SELF_OWNED"

    class Funding(BaseModel):
        """Funding information associated with given company."""

        class Investor(BaseModel):
            """Investor details."""
            class InvestorType(str, Enum):
                PERSON = "person"
                ORGANIZATION = "organization"

            linkedin_profile_url: Optional[str] = Field(
                default=None, description="LinkedIn URL of investor.")
            name: Optional[str] = Field(
                default=None, description="Name of the investor.")
            type: Optional[InvestorType] = Field(
                default=None, description="Type of the investor.")

        funding_type: Optional[str] = Field(
            default=None, description="Type of funding")
        money_raised: Optional[int] = Field(
            default=None, description="USD Amount raised in funding")
        announced_date: Optional[datetime] = Field(
            default=None, description="Date of announcement of funding.")
        number_of_investor: Optional[int] = Field(
            default=None, description="Number of investors in this round.")
        investor_list: List[Investor] = Field(
            default=[], description="List of investors in this round.")

        @field_validator('announced_date', mode='before')
        @classmethod
        def parse_date_published(cls, v):
            """Convert date object to datetime object."""
            if not v:
                # Date is None, nothing to do here.
                return None
            if isinstance(v, datetime):
                # Already correct type, do nothing.
                # This happens when reading object from Database.
                return v

            # Field has Date format. Happens when reading object from Proxycurl API response.
            company_profile_date = CompanyProfile.Date(**v)
            # Convert Date object to datetime object in UTC timezone.
            return Utils.create_utc_datetime(day=company_profile_date.day, month=company_profile_date.month, year=company_profile_date.year)

    id: Optional[PyObjectId] = Field(
        alias="_id", default=None, description="MongoDB generated unique identifier for the Company profile.")
    linkedin_url: Optional[str] = Field(
        default=None, description="URL of the Company LinkedIn profile.")
    creation_date: Optional[datetime] = Field(
        default=None, description="Date when this profile was created in the database in UTC timezone. Assume we synced this from Proxycurl on the same date.")

    linkedin_internal_id: Optional[str] = Field(
        default=None, description="LinkedIn's Internal and immutable ID of this Company profile.")
    name: Optional[str] = Field(
        default=None, description="Name of the company.")
    tagline: Optional[str] = Field(
        default=None, description="Short catchy phrase representing company brand.")
    universal_name_id: Optional[str] = Field(
        default=None, description="A unique numerical identifier for the company used in the LinkedIn platform.")
    profile_pic_url: Optional[str] = Field(
        default=None, description="URL of the company's profile picture.")
    search_id: Optional[str] = Field(
        default=None, description="Usable with Job listing endpoint to search for jobs posted in this company.")
    description: Optional[str] = Field(
        default=None, description="Textual description of the company.")
    website: Optional[str] = Field(
        default=None, description="Website of the company.")
    industry: Optional[str] = Field(
        default=None, description="Industry that the company operates under. Exhaustive list can be found in https://drive.google.com/file/d/12yvYLuru7CRv3wKOIkHs5Ldocz31gJSS/view.")
    # Optional[int] because companies like Microsoft have size array: [some large number, null] indicating no upper bound lol.
    company_size: Optional[List[Optional[int]]] = Field(
        default=None, description="Sequenced range of headcount (min count, max count)", min_length=2, max_length=2)
    company_size_on_linkedin: Optional[int] = Field(
        default=None, description="Size of the company as indicated on LinkedIn.")
    hq: Optional[CompanyLocation] = Field(
        default=None, description="Headquarters of company.")
    company_type: Optional[CompanyType] = Field(
        default=None, description="Type of Company.")
    founded_year: Optional[int] = Field(
        default=None, description="Year when this company was founded.")
    specialities: List[str] = Field(
        default=[], description="List of specialities. Example: search, ads, finance etc.")
    locations: List[CompanyLocation] = Field(
        default=[], description="List of company locations.")
    follower_count: Optional[int] = Field(
        default=None, description="Number of followers of LinkedIn profile.")
    funding_data: Optional[List[Funding]] = Field(
        default=None, description="Funding data for given company.")
    categories: Optional[List[str]] = Field(
        default=None, description="This attribute is fetched from the company's Crunchbase profile. Values for this attribute are free-form text, and there is no exhaustive list of categories. Consider the categories attribute as \"hints\" regarding the products or services offered by the company.")


class WebPageInfo(BaseModel):
    """Stores web page information."""
    id: Optional[PyObjectId] = Field(
        alias="_id", default=None, description="MongoDB generated unique identifier for Web page Info.")
    header: Optional[str] = Field(
        default=None, description="Header of the page in Markdown formatted text, None if no header exists.")
    body: str = Field(...,
                      description="Body of the page in Markdown formatted text.")
    footer: Optional[str] = Field(
        default=None, description="Footer of the page in Markdown formatted text, None if it does not exist.")
    body_chunks: Optional[List[str]] = Field(
        default=None, description="List of markdown formatted chunks that the page body is divided into.")

    def to_str(self) -> str:
        """Returns string representation of page structure."""
        str_repr = ""
        if self.header:
            str_repr += f"Header\n=================\n{self.header}\n"
        str_repr += f"Body\n=================\n{self.body}\n"
        if self.footer:
            str_repr += f"Footer\n=================\n{self.footer}\n"
        return str_repr

    def to_doc(self) -> str:
        """Returns document string."""
        doc: str = ""
        if self.header:
            doc += self.header
        doc += self.body
        if self.footer:
            doc += self.footer
        return doc

    def get_size_mb(self) -> float:
        """Returns size of given page in megabytes."""
        page_text: str = self.to_doc()
        return len(page_text.encode("utf-8"))/(1024.0 * 1024.0)


class LinkedInPost(BaseModel):
    """Stores LinkedIn Post information in the database."""
    class AuthorType(str, Enum):
        PERSON = "person"
        COMPANY = "company"

    id: Optional[PyObjectId] = Field(
        alias="_id", default=None, description="MongoDB generated unique identifier for LinkedIn Post.")
    creation_date: Optional[datetime] = Field(
        default=None, description="Date (in UTC timezone) when this profile was created in the database.")

    author_name: Optional[str] = Field(
        default=None, description="Name of the author of the LinkedIn Post.")
    author_type: Optional[AuthorType] = Field(
        default=None, description="Type of author.")
    author_profile_url: Optional[str] = Field(
        default=None, description="LinkedIn profile URL of author. Can be person or company profile.")
    author_headline: Optional[str] = Field(
        default=None, description="Headline string associated with Author's profile. Only set for 'person' author type.")
    author_follower_count: Optional[str] = Field(
        default=None, description="Follower count string (not integer) of the author. Only set for 'company' author type.")
    publish_date: Optional[datetime] = Field(
        default=None, description="Date when this post was published.")
    url: Optional[str] = Field(
        default=None, description="URL of the LinkedIn Post. Only set for Post, for repost it is None.")
    text: str = Field(
        default="", description="Text associacted with the post. Set to empty when it is a pure repost.")
    text_links: List[Tuple[str, str]] = Field(
        default=[], description="List of tuples of links shared in the text of the post. Example: https://lnkd.in/eEyZQE-w (linkedin link) or even external links like https://cloudbees.io.")
    card_links: List[Tuple[str, str]] = Field(
        default=[], description="List of tuples of heading + URLs shared as part of the post's card section at the end.")
    num_reactions: Optional[int] = Field(
        default=None, description="Number of reactions on the post. Only set for Post, None for repost.")
    num_comments: Optional[int] = Field(
        default=None, description="Number of comments on the post.  Only set for Post, None for repost.")

    repost: Optional["LinkedInPost"] = Field(
        default=None, description="Reference to the original post if this a repost else None.")


@deprecated(reason="This class is based on Piloterr's API response which we don't use.")
class LinkedInPostOld(BaseModel):
    """LinkedIn Post information.

    Most of the information is from Piloterr's API response.
    """

    class Comment(BaseModel):
        """Comment on a LinkedIn Post."""
        class CommentAuthor(BaseModel):
            """Author of the commenter on a LinkedIn post."""
            url: str = Field(...)
            headline: str = Field(...)
            full_name: str = Field(...)
            image_url: Optional[str] = None

        text: str = Field(...)
        author: CommentAuthor = Field(...)

    class PostAuthor(BaseModel):
        """Author of a LinkedIn post."""
        class ProfileType(Enum):
            PERSON = "person"
            ORGANIZATION = "organization"

        url: str = Field(...)
        full_name: str = Field(...)
        image_url: Optional[str] = None
        profile_type: ProfileType = Field(...)

        # To prevent encoding error, see https://stackoverflow.com/questions/65209934/pydantic-enum-field-does-not-get-converted-to-string.
        class Config:
            use_enum_values = True

        def is_person(self) -> bool:
            """Returns True if person and false otherwise."""
            return self.profile_type == LinkedInPostOld.PostAuthor.ProfileType.PERSON

    id: Optional[PyObjectId] = Field(
        alias="_id", default=None, description="MongoDB generated unique identifier for the LinkedIn Post.")
    creation_date: Optional[datetime] = Field(default=None,
                                              description="Date when post was created in the database. We will assume it was fetched from the API call on the same date."),
    post_id: str = Field(..., validation_alias="id",
                         description="Identifier of the post.")
    url: str = Field(..., description="URL of the post.")
    text: str = Field(..., description="Text associated with the post.")
    author: PostAuthor = Field(..., description="Author of the post.")
    comments: List[Comment] = Field(...,
                                    description="Sample list of comments left on the post.")
    hashtags: List[str] = Field(...,
                                description="List of all hashtags used in the post's text.")
    image_url: Optional[str] = Field(
        default=None, description="URL of image attached to the post.")
    like_count: int = Field(..., description="Number of likes on the post.")
    comments_count: int = Field(...,
                                description="Number of comments on the post."),
    date_published: datetime = Field(...,
                                     description="Date when post was published."),
    total_engagement: int = Field(...,
                                  description="Total engagment with the post."),
    mentioned_profiles: List[str] = Field(
        ..., description="LinkedIn profiles of persons or companies mentioned in the post.")

    @field_validator('date_published', mode='before')
    @classmethod
    def parse_date_published(cls, v):
        if isinstance(v, datetime):
            # Already correct type, do nothing.
            # This happens when reading object from Database.
            return v

        # Convert string to datetime object in UTC timezone.
        return Utils.convert_linkedin_post_time_to_utc(post_time=v)
