from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
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
    person_name: str = Field(..., description="Person name")
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