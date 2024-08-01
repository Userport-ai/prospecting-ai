from typing import Optional, Annotated, List, Tuple
from deprecated import deprecated
from pydantic.functional_validators import BeforeValidator
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from app.utils import Utils
from enum import Enum
import re

# Represents an ObjectId field in the database.
# It will be represented as a `str` on the model so that it can be serialized to JSON.
# The Before validator will convert ObjectId from DB into string so model validation does not
# throw an error.
PyObjectId = Annotated[str, BeforeValidator(str)]


class OpenAITokenUsage(BaseModel):
    """Token usage when calling workflows using Open AI models."""
    url: str = Field(...,
                     description="URL for which tokens are being tracked.")
    operation_tag: str = Field(
        ..., description="Tag describing the operation for which cost is computed.")
    prompt_tokens: int = Field(..., description="Prompt tokens used")
    completion_tokens: int = Field(..., description="Completion tokens used")
    total_tokens: int = Field(..., description="Total tokens used")
    total_cost_in_usd: float = Field(...,
                                     description="Total cost of tokens used.")


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
    PANEL_DISCUSSION = "panel_discussion"
    LINKEDIN_POST = "linkedin_post"
    NONE_OF_THE_ABOVE = "none_of_the_above"


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


class ContentDetails(BaseModel):
    """
    Contains details related to a lead or company (or both) found using various workflows.

    Example workflows:
    1. Using search engine to find page and then scrape it manually or using an API (e.g. LinkedIn posts).
    2. Scraping company website directly.
    3. Calling specific APIs like Crunchbase, NYSE for information about the company.

    In the future, we can add more workflows if needed.
    """

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
    requesting_user_contact: bool = Field(
        default=False, description="Whether the page is requesting user contact information in exchange for access to white paper, case study, webinar etc. Always False for LinkedIn posts.")
    focus_on_company: bool = Field(
        default=False, description="Whether the content is focused on Company.")
    focus_on_person: bool = Field(
        default=False, description="Whether the content is focused on Person.")
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
    """Report containing lead research."""

    class Status(str, Enum):
        IN_PROGRESS = "in_progress"
        COMPLETE = "complete"

    class ReportDetail(BaseModel):
        """Details associated with the report."""
        class Highlight(BaseModel):
            """Highhlight associated with report."""
            id: Optional[PyObjectId] = Field(
                alias="_id", default=None, description="MongoDB generated unique identifier for each Content details.")
            category: ContentCategoryEnum = Field(...,
                                                  description="Category of the content. Field is repeated at outer level too.")
            concise_summary: str = Field(...,
                                         description="Concise summary of the content.")
            publish_date: datetime = Field(...,
                                           description="Publish date of the content.")
            url: str = Field(..., description="URL of the content.")

        category: ContentCategoryEnum = Field(...,
                                              description="Category of the highlights.")
        highlights: List[Highlight] = Field(
            ..., description="List of Highlights associated with given category.")

    """Research report associated with a lead."""
    id: Optional[PyObjectId] = Field(
        alias="_id", default=None, description="MongoDB generated unique identifier for Lead Research Report.")
    creation_date: Optional[datetime] = Field(
        default=None, description="Date in UTC timezone when this document was inserted in the database.")
    person_linkedin_url: Optional[str] = Field(
        default=None, description="LinkedIn URL of the person's profile.")
    person_profile_id: Optional[str] = Field(
        default=None, description="PersonProfile reference of this lead.")
    company_profile_id: Optional[str] = Field(
        default=None, description="Reference ID to the Company Profile that is stored in the database.")
    status: Optional[Status] = Field(
        default=None, description="Status of the report at given point in time.")
    cutoff_publish_date: Optional[datetime] = Field(
        default=None, description="Publish Date cutoff beyond which report is created. This can be 3 months, 6 months, 12 months etc. before date of report creation.")
    # TODO: Add user and organization information.

    details: List[ReportDetail] = Field(
        default=[], description="Report details associated with the lead.")


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
        match = re.search("(.+) at (.+)", self.occupation)
        if not match:
            raise ValueError(
                f"Person Profile occupation not in expected formar: {self}")
        role_title: str = match.group(1)
        company_name: str = match.group(2)
        return (company_name, role_title)

    def get_company_linkedin_url(self, company_name: str) -> str:
        """Returns company LinkedIn URL from person's experiences for given company name."""
        experience: Optional[PersonProfile.Experience] = next(
            filter(lambda e: e.company == company_name, self.experiences), None)
        if not experience:
            raise ValueError(
                f"Could not find experience in profile with company: {company_name}. Profile: {self}")
        return experience.company_linkedin_profile_url


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
    company_size: Optional[List[int]] = Field(
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
