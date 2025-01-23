from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field


class UserportPydanticBaseModel(BaseModel):
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class OpenAITokenUsage(UserportPydanticBaseModel):
    """Token usage when calling OpenAI models."""
    operation_tag: str = Field(..., description="Tag describing operation")
    prompt_tokens: int = Field(..., description="Prompt tokens used")
    completion_tokens: int = Field(..., description="Completion tokens used")
    total_tokens: int = Field(..., description="Total tokens used")
    total_cost_in_usd: float = Field(..., description="Total cost in USD")

    def add_tokens(self, another: Optional["OpenAITokenUsage"]) -> None:
        """Add tokens from another instance."""
        if not another:
            return
        self.prompt_tokens += another.prompt_tokens
        self.completion_tokens += another.completion_tokens
        self.total_tokens += another.total_tokens
        self.total_cost_in_usd += another.total_cost_in_usd


class LinkedInActivity(UserportPydanticBaseModel):
    """LinkedIn activity (post, comment, reaction)."""

    class Type(str, Enum):
        POST = "post"
        COMMENT = "comment"
        REACTION = "reaction"

    id: Optional[str] = Field(default=None, description="Activity ID")
    creation_date: Optional[datetime] = Field(default=None, description="Creation date")
    person_linkedin_url: str = Field(..., description="Person's LinkedIn URL")
    activity_url: Optional[str] = Field(default=None, description="Activity URL")
    type: "LinkedInActivity.Type" = Field(..., description="Activity type")
    content_md: str = Field(..., description="Content in markdown format")


class ContentDetails(UserportPydanticBaseModel):
    """Processed activity content."""

    class ProcessingStatus(str, Enum):
        NEW = "started"
        FAILED_MISSING_PUBLISH_DATE = "failed_missing_publish_date"
        FAILED_STALE_PUBLISH_DATE = "failed_stale_publish_date"
        FAILED_UNRELATED_TO_COMPANY = "failed_unrelated_to_company"
        COMPLETE = "complete"

    class AuthorType(str, Enum):
        PERSON = "person"
        COMPANY = "company"

    class Category(str, Enum):
        PERSONAL_THOUGHTS = "personal_thoughts"
        INDUSTRY_UPDATE = "industry_update"
        COMPANY_NEWS = "company_news"
        PRODUCT_UPDATE = "product_update"
        SOCIAL_UPDATE = "social_update"
        OTHER = "other"

    id: Optional[str] = Field(default=None, description="Content ID")
    url: str = Field(..., description="Content URL")
    person_name: Optional[str] = Field(..., description="Person name")
    company_name: str = Field(..., description="Company name")
    person_role_title: str = Field(..., description="Person's role")
    linkedin_activity_ref_id: Optional[str] = Field(default=None)
    linkedin_activity_type: Optional[LinkedInActivity.Type] = Field(default=None)

    processing_status: ProcessingStatus = Field(...)
    publish_date: Optional[datetime] = Field(default=None)
    publish_date_readable_str: Optional[str] = Field(default=None)

    author: Optional[str] = Field(default=None)
    author_type: Optional[AuthorType] = Field(default=None)
    author_linkedin_url: Optional[str] = Field(default=None)

    detailed_summary: Optional[str] = Field(default=None)
    concise_summary: Optional[str] = Field(default=None)
    one_line_summary: Optional[str] = Field(default=None)

    category: Optional[Category] = Field(default=None)
    category_reason: Optional[str] = Field(default=None)

    focus_on_company: bool = Field(default=False)
    focus_on_company_reason: Optional[str] = Field(default=None)

    main_colleague: Optional[str] = Field(default=None)
    main_colleague_reason: Optional[str] = Field(default=None)

    product_associations: Optional[List[str]] = Field(default=None)
    hashtags: Optional[List[str]] = Field(default=None)

    num_linkedin_reactions: Optional[int] = Field(default=None)
    num_linkedin_comments: Optional[int] = Field(default=None)
    num_linkedin_reposts: Optional[int] = Field(default=None)

    openai_tokens_used: Optional[OpenAITokenUsage] = Field(default=None)


class LeadResearchReport(UserportPydanticBaseModel):
    """Lead research report model."""

    class Status(str, Enum):
        NEW = "new"
        BASIC_PROFILE_FETCHED = "basic_profile_fetched"
        ACTIVITY_PROCESSING = "activity_processing"
        CONTENT_PROCESSING = "content_processing"
        REPORT_GENERATION = "report_generation"
        COMPLETE = "complete"
        FAILED = "failed"

    class Insights(UserportPydanticBaseModel):
        """Lead insights from activity analysis."""

        class PersonalityTraits(UserportPydanticBaseModel):
            description: str
            evidence: List[str]

        class AreasOfInterest(UserportPydanticBaseModel):
            description: str
            supporting_activities: List[str]

        class OutreachRecommendation(BaseModel):
            approach: str = Field(description="2-3 sentences describing recommended approach")
            key_topics: List[str] = Field(description="3-5 topics they care most about")
            conversation_starters: List[str] = Field(description="Specific talking points based on activities")
            best_channels: List[str] = Field(description="Recommended outreach channels in order of preference")
            timing_preferences: str = Field(description="When they seem most active/responsive")
            cautions: List[str] = Field(description="Topics or approaches to avoid if any")

        recommended_approach: Optional["LeadResearchReport.Insights.OutreachRecommendation"] = Field(default=None)

        personality_traits: Optional[PersonalityTraits] = Field(default=None)
        areas_of_interest: Optional[List[AreasOfInterest]] = Field(default=None)
        engaged_colleagues: Optional[List[str]] = Field(default=None)
        engaged_products: Optional[List[str]] = Field(default=None)
        total_engaged_activities: Optional[int] = Field(default=None)
        num_company_related_activities: Optional[int] = Field(default=None)
        total_tokens_used: Optional[OpenAITokenUsage] = Field(default=None)

    class PersonalizedEmail(UserportPydanticBaseModel):
        """Personalized outreach email."""
        id: str = Field(...)
        creation_date: datetime = Field(...)
        highlight_id: str = Field(...)
        highlight_url: str = Field(...)
        email_subject: str = Field(...)
        email_body: str = Field(...)
        tokens_used: Optional[OpenAITokenUsage] = Field(default=None)

    id: Optional[str] = Field(default=None)
    user_id: str = Field(...)
    account_id: str = Field(...)
    person_linkedin_url: str = Field(...)
    status: Status = Field(...)

    person_name: Optional[str] = Field(default=None)
    company_name: Optional[str] = Field(default=None)
    person_role_title: Optional[str] = Field(default=None)

    processed_activities: Optional[List[ContentDetails]] = Field(default=None)
    insights: Optional[Insights] = Field(default=None)
    personalized_emails: Optional[List[PersonalizedEmail]] = Field(default=None)

    creation_date: Optional[datetime] = Field(default=None)
    completion_date: Optional[datetime] = Field(default=None)
    error_message: Optional[str] = Field(default=None)


class BrightDataAccount(UserportPydanticBaseModel):
    """Bright Data account returned as part of data collection process."""
    class Input(UserportPydanticBaseModel):
        url: str = Field(...)

    class Funding(UserportPydanticBaseModel):
        last_round_date: Optional[datetime] = Field(default=None)
        last_round_type: Optional[str] = Field(default=None)
        rounds: Optional[int] = Field(default=None)
        last_round_raised: Optional[str] = Field(default=None)

    class LinkedInPost(UserportPydanticBaseModel):
        class TaggedEntity(UserportPydanticBaseModel):
            name: Optional[str] = Field(default=None)
            link: Optional[str] = Field(default=None, description="LinkedIn profile of person or company.")

        title: Optional[str] = Field(default=None, description="Likely name of account e.g. Lunos, Zoom etc.")
        text: Optional[str] = Field(default=None)
        time: Optional[str] = Field(default=None, description="Examples: 6d Edited, 1w etc.")
        date: Optional[datetime] = Field(default=None, description="Same as 'time' field but displayed in ISO format, Example:  2024-12-25T10:06:52.933Z")
        post_url: Optional[str] = Field(default=None)
        post_id: Optional[str] = Field(default=None)
        images: Optional[List[str]] = Field(default=None, description="URLs of images in Post.")
        videos: Optional[List[str]] = Field(default=None, description="URLs of videos in Post.")
        tagged_companies: Optional[List[TaggedEntity]] = Field(default=None)
        tagged_people: Optional[List[TaggedEntity]] = Field(default=None)
        likes_count: Optional[int] = Field(default=None)
        comments_count: Optional[int] = Field(default=None)

    input: Input = Field(...)
    id: Optional[str] = Field(default=None)
    name: Optional[str] = Field(default=None)
    employees_in_linkedin: Optional[int] = Field(default=None)
    about: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)
    specialties: Optional[str] = Field(default=None)
    company_size: Optional[str] = Field(default=None)
    organization_type: Optional[str] = Field(default=None)
    industries: Optional[str] = Field(default=None)
    website: Optional[str] = Field(default=None)
    crunchbase_url: Optional[str] = Field(default=None)
    founded: Optional[int] = Field(default=None)
    headquarters: Optional[str] = Field(default=None)
    logo: Optional[str] = Field(default=None)
    url: Optional[str] = Field(default=None)  # LinkedIn URL of the Account.
    slogan: Optional[str] = Field(default=None)
    funding: Optional[Funding] = Field(default=None)
    investors: Optional[List[str]] = Field(default=None)
    formatted_locations: Optional[List[str]] = Field(default=None)
    country_codes_array: Optional[List[str]] = Field(default=None)
    timestamp: Optional[datetime] = Field(default=None)

    # LinkedIn Posts from the Account.
    updates: Optional[List[LinkedInPost]] = Field(default=None)

    # In case the page is invalid, these fields are populated.
    warning: Optional[str] = Field(default=None, description="Example warning text: 4XX page - dead page")
    warning_code: Optional[str] = Field(default=None, description="Example code: dead_page")


class AccountInfo(UserportPydanticBaseModel):
    """Account information that are relevant for Userport."""
    name: Optional[str] = Field(default=None)
    website: Optional[str] = Field(default=None)
    linkedin_url: Optional[str] = Field(default=None)
    employee_count: Optional[int] = Field(default=None)
    about: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)
    slogan: Optional[str] = Field(default=None)
    industries: Optional[str] = Field(default=None)
    specialities: Optional[str] = Field(default=None)
    headquarters: Optional[str] = Field(default=None)
    company_size: Optional[str] = Field(default=None)
    organization_type: Optional[str] = Field(default=None)
    founded_year: Optional[int] = Field(default=None)
    logo: Optional[str] = Field(default=None)
    crunchbase_url: Optional[str] = Field(default=None)
    locations: Optional[List[str]] = Field(default=None)
    location_country_codes: Optional[List[str]] = Field(default=None)

from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class DateInfo(BaseModel):
    day: Optional[int] = None
    month: Optional[int] = None
    year: Optional[int] = None

class Experience(BaseModel):
    company: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    starts_at: Optional[DateInfo] = None
    ends_at: Optional[DateInfo] = None
    company_linkedin_profile_url: Optional[str] = None
    company_facebook_profile_url: Optional[str] = None
    logo_url: Optional[str] = None

class Education(BaseModel):
    school: Optional[str] = None
    degree_name: Optional[str] = None
    field_of_study: Optional[str] = None
    starts_at: Optional[DateInfo] = None
    ends_at: Optional[DateInfo] = None
    activities_and_societies: Optional[str] = None
    grade: Optional[str] = None
    logo_url: Optional[str] = None
    school_linkedin_profile_url: Optional[str] = None
    description: Optional[str] = None

class Certification(BaseModel):
    name: str
    authority: Optional[str] = None
    license_number: Optional[str] = None
    url: Optional[str] = None
    starts_at: Optional[DateInfo] = None
    ends_at: Optional[DateInfo] = None

class Project(BaseModel):
    title: str
    description: Optional[str] = None
    url: Optional[str] = None
    starts_at: Optional[DateInfo] = None
    ends_at: Optional[DateInfo] = None

class Activity(BaseModel):
    title: Optional[str] = None
    link: Optional[str] = None
    activity_status: Optional[str] = None

class ProxyCurlPersonProfile(UserportPydanticBaseModel):
    profile_url: str = Field(..., description="LinkedIn profile URL")
    public_identifier: Optional[str] = None
    full_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    headline: Optional[str] = None
    summary: Optional[str] = None
    country: Optional[str] = None
    country_full_name: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    occupation: Optional[str] = None
    connections: Optional[int] = None
    follower_count: Optional[int] = None
    background_cover_image_url: Optional[str] = None
    profile_pic_url: Optional[str] = None
    experiences: Optional[List[Experience]] = Field(default_factory=list)
    education: Optional[List[Education]] = Field(default_factory=list)
    languages: Optional[List[str]] = Field(default_factory=list)
    accomplishment_organisations: Optional[List[str]] = Field(default_factory=list)
    accomplishment_publications: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    accomplishment_honors_awards: Optional[List[str]] = Field(default_factory=list)
    accomplishment_patents: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    accomplishment_courses: Optional[List[str]] = Field(default_factory=list)
    accomplishment_projects: Optional[List[Project]] = Field(default_factory=list)
    accomplishment_test_scores: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    volunteer_work: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    certifications: Optional[List[Certification]] = Field(default_factory=list)
    activities: Optional[List[Activity]] = Field(default_factory=list)
    similarly_named_profiles: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    articles: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    groups: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    recommendations: Optional[List[str]] = Field(default_factory=list)

class ApolloOrganization(UserportPydanticBaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    website_url: Optional[str] = None
    blog_url: Optional[str] = None
    facebook_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    twitter_url: Optional[str] = None
    logo_url: Optional[str] = None
    primary_domain: Optional[str] = None
    linkedin_uid: Optional[str] = None
    founded_year: Optional[int] = None

class ApolloEmploymentHistory(UserportPydanticBaseModel):
    id: Optional[str] = None
    organization_id: Optional[str] = None
    organization_name: Optional[str] = None
    title: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    current: Optional[bool] = None
    description: Optional[str] = None

class EnrichedLead(UserportPydanticBaseModel):
    # Apollo fields
    lead_id: Optional[str] = None
    id: Optional[str] = None
    email: Optional[str] = None
    email_status: Optional[str] = None
    email_domain_catchall: Optional[bool] = None
    revealed_for_current_team: Optional[bool] = None
    departments: Optional[List[str]] = Field(default_factory=list)
    functions: Optional[List[str]] = Field(default_factory=list)
    subdepartments: Optional[List[str]] = Field(default_factory=list)
    intent_strength: Optional[str] = None
    show_intent: Optional[bool] = None

    # Common fields (enriched)
    name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    headline: Optional[str] = None
    title: Optional[str] = None
    photo_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    country_full_name: Optional[str] = None

    # Organization
    organization: Optional[ApolloOrganization] = None

    # Current role and history
    current_role: Optional[Dict[str, Any]] = Field(default_factory=dict)
    employment_history: Optional[List[ApolloEmploymentHistory]] = Field(default_factory=list)

    # Education and skills
    education: Optional[List[Education]] = Field(default_factory=list)
    certifications: Optional[List[Certification]] = Field(default_factory=list)

    # Social profiles
    social_profiles: Optional[Dict[str, Any]] = Field(default_factory=dict)
    social_metrics: Optional[Dict[str, Any]] = Field(default_factory=dict)

    # Additional enriched data
    summary: Optional[str] = None
    projects: Optional[List[Project]] = Field(default_factory=list)
    groups: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    volunteer_work: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    recommendations: Optional[List[str]] = Field(default_factory=list)
    activities: Optional[List[Activity]] = Field(default_factory=list)

    # Enrichment metadata
    enrichment_info: Optional[Dict[str, Any]] = Field(default_factory=dict)

class ProxyCurlEmployeeProfile(BaseModel):
    """Employee profile from ProxyCurl API."""
    profile_url: Optional[str] = Field(None, description="LinkedIn profile URL")
    full_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    headline: Optional[str] = None
    summary: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    experiences: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    education: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    languages: Optional[List[str]] = Field(default_factory=list)
    skills: Optional[List[str]] = Field(default_factory=list)
    certifications: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    connections: Optional[int] = None
    follower_count: Optional[int] = None
    profile_pic_url: Optional[str] = None

class ProxyCurlSearchResponse(BaseModel):
    """Response from ProxyCurl employee search API."""
    employees: Optional[List[Dict[str, Any]]]= Field(default_factory=list)
    next_page: Optional[str] = None
    previous_page: Optional[str] = None
