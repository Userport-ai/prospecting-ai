from typing import Optional, Annotated, List
from pydantic.functional_validators import BeforeValidator
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

# Represents an ObjectId field in the database.
# It will be represented as a `str` on the model so that it can be serialized to JSON.
# The Before validator will convert ObjectId from DB into string so model validation does not
# throw an error.
PyObjectId = Annotated[str, BeforeValidator(str)]


class PersonInfo(BaseModel):
    """Information about a given Person."""
    id: Optional[PyObjectId] = Field(
        alias="_id", default=None, description="MongoDB generated unique identifier for the person.")
    full_name: str = Field(..., description="Full name of the person.")
    linkedin_profile_url: str = Field(...,
                                      description="LinkedIn profile URL of the person.")


class CompanyInfo(BaseModel):
    """Information about a given Company."""
    id: Optional[PyObjectId] = Field(
        alias="_id", default=None, description="MongoDB generated unique identifier for the company.")
    full_name: str = Field(..., description="Full name of the company.")
    linkedin_page_url: str = Field(...,
                                   description="LinkedIn page URL of the company.")


class Product(Enum):
    LAUNCH = "product_launch"
    UPDATE = "product_update"
    SUNSET = "product_sunset"
    OTHER = "product_other"


class LeaderAppointment(Enum):
    NEW_HIRE = "leader_new_hire"
    PROMOTION = "leader_promotion"
    OTHER = "leader_other"


class FinancialResults(Enum):
    QUARTER = "financial_results_quarter"
    ANNUAL = "financial_results_annual"
    OTHER = "financial_results_other"


class Collaboration(Enum):
    PARTNERSHIP = "collaboration_partnership"
    OTHER = "collaboration_other"


class Achievement(Enum):
    FUNDING_ANNOUNCEMENT = "achievement_funding_announcement"
    IPO_ANNOUNCEMENT = "achievement_ipo_announcement"
    RECOGNITION = "achievement_recognition"
    AWARD = "achievement_award"
    ANNIVERSARY = "achievement_anniversary"
    SALES_MILESTONE = "achievement_sales_milestone"
    USER_BASE_GROWTH = "achievement_user_base_growth"
    OTHER = "achievement_other"


class Event(Enum):
    CONFERENCE = "event_conference"
    WEBINAR = "event_webinar"
    TRADE_SHOW = "event_trade_show"
    OTHER = "event_other"


class Challenge(Enum):
    CRISIS_SITUATION = "challenge_crisis_situation"
    OTHER = "challenge_other"


class Rebranding(Enum):
    NAME = "rebrading_name"
    LOGO = "rebranding_logo"
    WEBSITE = "rebranding_website"
    BRAND_IDENTITY = "rebranding_identity"
    OTHER = "rebranding_other"


class SocialResponsibility(Enum):
    NEW_INITIATIVE = "social_responsibility_new_initiative"
    DONATION = "social_responsibility_donation"
    OTHER = "social_responsibility_other"


class BusinessExpansion(Enum):
    NEW_OFFICE = "business_expansion_new_office"
    GROWTH = "business_expansion_growth"
    NEW_MARKET_EXPANSION = "business_expansion_new_market_expansion"
    NEW_CUSTOMER_ACQUISITION = "business_expansion_new_customer_acquisition"
    OTHER = "business_expansion_other"


class Legal(Enum):
    REGULATION_COMPLIANCE = "legal_regulation_compliance"
    LAWSUIT = "legal_lawsuit"
    SETTLEMENT = "legal_settlement"


class InternalEvent(Enum):
    COMPANY_OFFSITE = "internal_event_company_offsite"
    EMPLOYEE_RECOGNITION = "internal_event_employee_recognition"
    EMPLOYEE_PROMOTION = "internal_event_employee_promotion"
    HIRING = "internal_event_hiring"


class PersonalThoughts(Enum):
    """Content that is personal thoughts of a person."""
    ADVICE = "personal_thoughts_advice"
    ANECDOTE = "personal_thoughts_anecdote"
    INDUSTRY_TRENDS = "personal_thoughts_industry_trends"
    OPINIONS = "personal_thoughts_opinions"
    OTHER = "personal_thoughts_other"


class ContentCategory(Enum):
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


class ContentType(Enum):
    """Categories of web content in the web result."""
    INTERVIEW_ARTICLE = "content_type_interview_article"
    INTERVIEW_VIDEO = "content_type_interview_video"
    PODCAST = "content_type_podcast"
    ARTICLE = "content_type_article"
    BLOG_POST = "content_type_blog_post"
    LINKEDIN_POST = "content_type_linkedin_post"
    OTHER = "content_type_other"


class WebSearchResult(BaseModel):
    """
    Contains results from scraping the web.

    The content from the web can be about a person or a company or both.
    """
    id: Optional[PyObjectId] = Field(
        alias="_id", default=None, description="MongoDB generated unique identifier for the document.")
    content_url: str = Field(...,
                             description="URL of content from search results on the web.")
    person_info_id: Optional[PyObjectId] = Field(
        default=None, description="PersonInfo Identifier used to search for this web result.")
    company_info_id: Optional[PyObjectId] = Field(
        default=None, description="CompanyInfo Identifier used to search for this web result.")
    search_query: str = Field(...,
                              description="Search query used to fetch this content.")
    is_scrapable: Optional[bool] = Field(
        default=None, description="Whether this piece of content is scrapable or not.")
    date_published: Optional[datetime] = Field(
        default=None, description="Date when this content was published in UTC timezone.")
    content_type: Optional[ContentType] = Field(default=None,
                                                description="Type of content found in this URL.")
    content_category: Optional[ContentCategory] = Field(
        default=None, description="Category of the content found")
    content_short_summary: Optional[str] = Field(
        default=None, description="A short summary of the content")
    is_relevant_content: Optional[bool] = Field(
        default=None, description="Whether content is relevant to given person and company.")
    not_relevant_content_reason: Optional[str] = Field(
        default=None, description="Why the content is not relevant to person and company.")
