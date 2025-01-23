from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from models.common import UserportPydanticBaseModel


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
    employees: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    next_page: Optional[str] = None
    previous_page: Optional[str] = None
