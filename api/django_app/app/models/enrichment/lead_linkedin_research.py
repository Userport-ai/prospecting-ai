from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field


class LinkedInResearchInputData(BaseModel):
    class LeadData(BaseModel):
        name: Optional[str] = None
        headline: Optional[str] = None
        about: Optional[str] = None
        location: Optional[Dict[str, Any]] = None
        current_employment: Optional[Dict[str, Any]] = None
        employment_history: Optional[List[Dict[str, Any]]] = None
        education: Optional[List[Dict[str, Any]]] = None
        projects: Optional[List[Dict[str, Any]]] = None
        publications: Optional[List[Dict[str, Any]]] = None
        groups: Optional[List[Dict[str, Any]]] = None
        certifications: Optional[List[Dict[str, Any]]] = None
        honor_awards: Optional[List[Dict[str, Any]]] = None

    class AccountData(BaseModel):
        name: Optional[str] = None
        industry: Optional[str] = None
        location: Optional[str] = None
        employee_count: Optional[int] = None
        company_type: Optional[str] = None
        founded_year: Optional[int] = None
        technologies: Optional[List[str]] = None
        competitors: Optional[List[str]] = None
        customers: Optional[List[str]] = None
        funding_details: Optional[Dict[str, Any]] = None

    class ProductData(BaseModel):
        name: Optional[str] = None
        description: Optional[str] = None
        persona_role_titles: Optional[Dict[str, Any]] = None
        playbook_description: Optional[str] = None

    lead_data: Optional[LeadData] = None
    account_data: Optional[AccountData] = None
    product_data: Optional[ProductData] = None


class LinkedInActivity(BaseModel):
    type: Optional[str] = None
    date: Optional[str] = None
    url: Optional[str] = None
    category: Optional[str] = None
    category_reason: Optional[str] = None
    detailed_summary: Optional[str] = None
    concise_summary: Optional[str] = None
    one_line_summary: Optional[str] = None
    author: Optional[str] = None
    author_type: Optional[str] = None
    focus_on_company: Optional[bool] = None
    focus_on_company_reason: Optional[str] = None
    reactions: Optional[int] = None
    comments: Optional[int] = None
    reposts: Optional[int] = None
    product_associations: Optional[List[str]] = None
    hashtags: Optional[List[str]] = None
    main_colleague: Optional[str] = None
    main_colleague_reason: Optional[str] = None
    processing_status: Optional[str] = None


class LinkedInProfile(BaseModel):
    company_name: Optional[str] = None
    person_role_title: Optional[str] = None
    linkedin_url: Optional[str] = None
    last_activity_date: Optional[str] = None


class PersonalityTraits(BaseModel):
    description: Optional[str] = None
    evidence: Optional[List[str]] = None


class RecommendedApproach(BaseModel):
    approach: Optional[str] = None
    key_topics: Optional[List[str]] = None
    conversation_starters: Optional[List[str]] = None
    best_channels: Optional[List[str]] = None
    timing_preferences: Optional[str] = None
    cautions: Optional[List[str]] = None


class PersonalizationSignal(BaseModel):
    description: Optional[str] = None
    reason: Optional[str] = None
    outreach_message: Optional[str] = None


class AreaOfInterest(BaseModel):
    description: Optional[str] = None
    supporting_activities: Optional[List[str]] = None


class EnrichmentMetadata(BaseModel):
    num_company_related_activities: Optional[int] = None
    last_enriched: str = Field(default_factory=lambda: datetime.now().isoformat())


class PersonalityInsights(BaseModel):
    traits: Optional[PersonalityTraits] = None
    recommended_approach: Optional[RecommendedApproach] = None
    areas_of_interest: Optional[List[AreaOfInterest]] = None
    engaged_colleagues: Optional[List[str]] = None
    engaged_products: Optional[List[str]] = None
    personalization_signals: Optional[List[PersonalizationSignal]] = None


class LinkedInEnrichmentData(BaseModel):
    metadata: Optional[EnrichmentMetadata]
    linkedin_profile: Optional[LinkedInProfile] = None
    activities: Optional[List[LinkedInActivity]]
    insights: Optional[Dict[str, Any]] = None
    source: str = "linkedin"
