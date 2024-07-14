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


class CurrentEmployment(BaseModel):
    """Details about person's current employment.

    Used when searching for information related to the person on the web.
    """
    person_profile_id: PyObjectId = Field(
        ..., description="PersonProfile identifier of this person.")
    date_synced: datetime = Field(
        ..., description="Date when this information was last synced from LinkedIn profile.")
    full_name: str = Field(..., description="Person's full name.")
    role_title: str = Field(...,
                            description="Person's role title at company.")
    person_profile_url: str = Field(...,
                                    description="LinkedIn profile URL of the person.")
    company_name: str = Field(..., description="Company name.")
    company_linkedin_profile_url: str = Field(
        ..., description="Company LinkedIn profile URL.")


class Product(str, Enum):
    LAUNCH = "product_launch"
    UPDATE = "product_update"
    SUNSET = "product_sunset"
    OTHER = "product_other"


class LeaderAppointment(str, Enum):
    NEW_HIRE = "leader_new_hire"
    PROMOTION = "leader_promotion"
    OTHER = "leader_other"


class FinancialResults(str, Enum):
    QUARTER = "financial_results_quarter"
    ANNUAL = "financial_results_annual"
    OTHER = "financial_results_other"


class Collaboration(str, Enum):
    PARTNERSHIP = "collaboration_partnership"
    OTHER = "collaboration_other"


class Achievement(str, Enum):
    FUNDING_ANNOUNCEMENT = "achievement_funding_announcement"
    IPO_ANNOUNCEMENT = "achievement_ipo_announcement"
    RECOGNITION = "achievement_recognition"
    AWARD = "achievement_award"
    ANNIVERSARY = "achievement_anniversary"
    SALES_MILESTONE = "achievement_sales_milestone"
    USER_BASE_GROWTH = "achievement_user_base_growth"
    OTHER = "achievement_other"


class Event(str, Enum):
    CONFERENCE = "event_conference"
    WEBINAR = "event_webinar"
    TRADE_SHOW = "event_trade_show"
    OTHER = "event_other"


class Challenge(str, Enum):
    CRISIS_SITUATION = "challenge_crisis_situation"
    OTHER = "challenge_other"


class Rebranding(str, Enum):
    NAME = "rebrading_name"
    LOGO = "rebranding_logo"
    WEBSITE = "rebranding_website"
    BRAND_IDENTITY = "rebranding_identity"
    OTHER = "rebranding_other"


class SocialResponsibility(str, Enum):
    NEW_INITIATIVE = "social_responsibility_new_initiative"
    DONATION = "social_responsibility_donation"
    OTHER = "social_responsibility_other"


class BusinessExpansion(str, Enum):
    NEW_OFFICE = "business_expansion_new_office"
    GROWTH = "business_expansion_growth"
    NEW_MARKET_EXPANSION = "business_expansion_new_market_expansion"
    NEW_CUSTOMER_ACQUISITION = "business_expansion_new_customer_acquisition"
    OTHER = "business_expansion_other"


class Legal(str, Enum):
    REGULATION_COMPLIANCE = "legal_regulation_compliance"
    LAWSUIT = "legal_lawsuit"
    SETTLEMENT = "legal_settlement"


class InternalEvent(str, Enum):
    COMPANY_OFFSITE = "internal_event_company_offsite"
    EMPLOYEE_RECOGNITION = "internal_event_employee_recognition"
    EMPLOYEE_PROMOTION = "internal_event_employee_promotion"
    HIRING = "internal_event_hiring"


class PersonalThoughts(str, Enum):
    """Content that is personal thoughts of a person."""
    ADVICE = "personal_thoughts_advice"
    ANECDOTE = "personal_thoughts_anecdote"
    INDUSTRY_TRENDS = "personal_thoughts_industry_trends"
    OPINIONS = "personal_thoughts_opinions"
    OTHER = "personal_thoughts_other"


class ContentCategory(str, Enum):
    """Categories of different types of content on the web."""
    PRODUCT = Product
    LEADER_APPOINTMENT = LeaderAppointment
    FINANCIAL_RESULTS = FinancialResults
    COLLABORATION = Collaboration
    ACHIEVEMENT = Achievement
    EVENT = Event
    CHALLENGE = Challenge
    REBRANDING = Rebranding
    SOCIAL_RESPONSIBILITY = SocialResponsibility
    BUSINESS_EXPANSION = BusinessExpansion
    LEGAL = Legal
    INTERNAL_EVENT = InternalEvent
    PERSONAL_THOUGHTS = PersonalThoughts
    OTHER = "content_category_other"


class ContentType(str, Enum):
    """Categories of web content in the web result."""
    INTERVIEW_ARTICLE = "content_type_interview_article"
    INTERVIEW_VIDEO = "content_type_interview_video"
    PODCAST = "content_type_podcast"
    ARTICLE = "content_type_article"
    BLOG_POST = "content_type_blog_post"
    LINKEDIN_POST = "content_type_linkedin_post"
    OTHER = "content_type_other"


class SearchEngineMetadata(BaseModel):
    """Metdata when using search engine for searching web."""
    type: Literal["search_engine"]
    name: str = Field(..., description="Name of the search engine used.")
    query: str = Field(..., description="Query used for search.")

    @staticmethod
    def create(name: str, query: str):
        return SearchEngineMetadata(type="search_engine", name=name, query=query)


class CompanyWebsiteMetadata(BaseModel):
    """Metdata when using company website for scraping information."""
    type: Literal["company_website"]

    @staticmethod
    def create():
        return CompanyWebsiteMetadata(type="company_website")


"""Metadata associated with the different workflows to fetch information on the web."""
WebSearchMetadata = Union[SearchEngineMetadata, CompanyWebsiteMetadata]


class LinkedInPostReference(BaseModel):
    """Reference to LinkedIn Post details in Database."""
    type: Literal["linkedin_post"]
    id: PyObjectId = Field(...,
                           description="Identifier for stored LinkedIn post in database.")

    @staticmethod
    def create(id: PyObjectId):
        return LinkedInPostReference(type="linkedin_post", id=id)


class HTMLPageReference(BaseModel):
    """Reference to HTML page details in Database."""
    type: Literal["html_page"]
    id: PyObjectId = Field(...,
                           description="Identifier for stored HTML Page in database.")


"""Extra information about the content that is stored separately and can be processed independently of fetching the content again."""
ContentExtraReference = Union[LinkedInPostReference, HTMLPageReference]


class WebSearchResult(BaseModel):
    """
    Contains results from scraping the web.

    The content from the web can be about a person or a company or both.

    It can be fetched in multiple ways:
    1. Using search engines.
    2. Scraping websites.
    3. Calling specific APIs like Crunchbase, NYSE.
    4. Asking LLMs directly.
    """

    id: Optional[PyObjectId] = Field(
        alias="_id", default=None, description="MongoDB generated unique identifier for web search result.")
    current_employment: CurrentEmployment = Field(
        ..., description="Current employment defails of the person who is being searched for.")
    web_search_metadata: WebSearchMetadata = Field(...,
                                                   description="Metadata associated with web search process to get this result.")
    url: str = Field(...,
                     description="URL from searching on the web.")
    created_on: datetime = Field(
        ..., description="Date in UTC timezone when this document was inserted in the db.")
    content_publish_date: Optional[datetime] = Field(
        default=None, description="Date when this content was published in UTC timezone.")
    content_type: Optional[ContentType] = Field(default=None,
                                                description="Type of content found in this URL.")
    content_category: Optional[ContentCategory] = Field(
        default=None, description="Category of the content found")
    content_short_summary: Optional[str] = Field(
        default=None, description="A short summary of the content")
    content_extra_reference: Optional[ContentExtraReference] = Field(
        default=None, description="Reference to extra details regarding content stored in a different collection.")
    is_relevant_content: Optional[bool] = Field(
        default=None, description="Whether content is relevant to given person and company.")
    not_relevant_content_reason: Optional[str] = Field(
        default=None, description="Why the content is not relevant to person and company.")

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
    fetch_date: Optional[datetime] = Field(default=None,
                                           description="Date when post was fetched from API call."),
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
