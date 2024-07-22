from typing import Optional, Annotated, List, Literal, Union
from pydantic.functional_validators import BeforeValidator
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from utils import Utils
from enum import Enum

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


class PersonCurrentEmployment(BaseModel):
    """Details about person's current employment.

    This information is used as input when searching for information related to the person and their company on the web.
    """
    full_name: str = Field(..., description="Person's full name.")
    company_name: str = Field(
        ..., description="Company name where the person is currently employed.")
    role_title: str = Field(...,
                            description="Role title of person at the company.")
    person_profile_id: PyObjectId = Field(
        ..., description="PersonProfile reference of this person.")


class SearchEngineWorkflowMetadata(BaseModel):
    """Metdata when using search engine for fetching web pages."""
    type: Literal["search_engine"]
    name: str = Field(..., description="Name of the search engine used.")
    query: str = Field(..., description="Query used for search.")

    @staticmethod
    def create(name: str, query: str):
        return SearchEngineWorkflowMetadata(type="search_engine", name=name, query=query)


class CompanyWebsiteWorkflowMetadata(BaseModel):
    """Metdata when using company website for scraping web pages."""
    type: Literal["company_website"]

    @staticmethod
    def create():
        return CompanyWebsiteWorkflowMetadata(type="company_website")


"""Metadata associated with the different workflows to fetch information on the web."""
WorkflowMetadata = Union[SearchEngineWorkflowMetadata,
                         CompanyWebsiteWorkflowMetadata]


class LinkedInPostReference(BaseModel):
    """Reference to LinkedIn Post details in Database."""
    type: Literal["linkedin_post"]
    id: PyObjectId = Field(...,
                           description="Identifier for stored LinkedIn post in database.")

    @staticmethod
    def create(id: PyObjectId):
        return LinkedInPostReference(type="linkedin_post", id=id)


class WebPageReference(BaseModel):
    """Reference to Web page details in Database."""
    type: Literal["web_page"]
    id: PyObjectId = Field(...,
                           description="Identifier for stored WebPageInfo in database.")


class ContentTypeEnum(str, Enum):
    """Enum values associated with ContentTypeSource class."""
    ARTICLE = "article"
    BLOG_POST = "blog_post"
    ANNOUCEMENT = "announcement"
    INTERVIEW = "interview"
    PODCAST = "podcast"
    PANEL_DISCUSSION = "panel_discussion"
    LINKEDIN_POST = "linkedin_post"


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


"""Extra information about the content that is stored separately and can be processed independently of fetching the content again."""
ContentSource = Union[LinkedInPostReference, WebPageReference]


class PageContentInfo(BaseModel):
    """
    Contains details of content related to a lead or company (or both) found using various workflow.

    Example workflows:
    1. Using search engine to find page and then scrape it manually or using an API (e.g. LinkedIn posts).
    2. Scraping company website directly.
    3. Calling specific APIs like Crunchbase, NYSE for information about the company.

    In the future, we can add more workflows.
    """

    id: Optional[PyObjectId] = Field(
        alias="_id", default=None, description="MongoDB generated unique identifier for web search result.")
    creation_date: datetime = Field(
        ..., description="Date in UTC timezone when this document was inserted in the database.")
    source: Optional[ContentSource] = Field(
        default=None, description="Reference to the content source which is stored in a separate collection.")
    url: Optional[str] = Field(
        default=None, description="URL of the content if any.")
    workflow_metadata: WorkflowMetadata = Field(...,
                                                description="Metadata associated with workflow to fetch this content.")
    person_name: Optional[str] = Field(
        default=None, description="Full name of person. Populated only when the workflow was explicitly searching for person information and None when searching for only company information.")
    company_name: Optional[str] = Field(
        default=None, description="Company name used when searching content. Should mostly be populated, there may be some exceptions that are not known as of now.")
    person_role_title: Optional[str] = Field(
        default=None, description="Role title of person at company. Populated only when person_name is populated and None otherwise.")
    person_profile_id: Optional[PyObjectId] = Field(
        default=None, description="PersonProfile reference of this person. Populated only when person_name is populated and None otherwise.")
    # TODO: Add a company profile ID once CompanyProfile is defined.

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

    openai_tokens_used: Optional[OpenAITokenUsage] = Field(
        default=None, description="Total Open AI tokens used in fetching this content info.")
    schema_version: Optional[int] = Field(default=None,
                                          description="Schema version for this collection.")

    # To prevent encoding error, see https://stackoverflow.com/questions/65209934/pydantic-enum-field-does-not-get-converted-to-string.
    class Config:
        use_enum_values = True


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
        alias="_id", default=None, description="MongoDB generated unique identifier for the LinkedIn Post.")
    linkedin_url: Optional[str] = Field(
        default=None, description="URL of the LinkedIn profile.")
    date_synced: Optional[datetime] = Field(
        default=None, description="Date when this profile was synced from LinkedIn in UTC timezone.")
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
            return self.profile_type == LinkedInPost.PostAuthor.ProfileType.PERSON

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

    schema_version: Optional[int] = Field(default=None,
                                          description="Schema version for this collection.")

    @field_validator('date_published', mode='before')
    @classmethod
    def parse_date_published(cls, v):
        if isinstance(v, datetime):
            # Already correct type, do nothing.
            # This happens when reading object from Database.
            return v

        # Convert string to datetime object in UTC timezone.
        return Utils.convert_linkedin_post_time_to_utc(post_time=v)
