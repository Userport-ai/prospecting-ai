from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class ContactInfo(BaseModel):
    """Contact information for a lead"""
    email: Optional[str] = None
    email_status: Optional[str] = None
    phone_numbers: Optional[List[str]] = Field(default_factory=list)


class Location(BaseModel):
    """Location information"""
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None


class CurrentEmployment(BaseModel):
    """Current employment details"""
    title: Optional[str] = None
    organization_name: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[str] = None
    location: Optional[str] = None
    department: Optional[str] = None
    seniority: Optional[str] = None
    functions: List[str] = Field(default_factory=list)
    subdepartments: List[str] = Field(default_factory=list)


class DataQuality(BaseModel):
    """Data quality metrics"""
    existence_level: Optional[str] = None
    email_domain_catchall: bool = False
    profile_photo_url: Optional[str] = None
    last_updated: Optional[str] = None


class EngagementData(BaseModel):
    """Engagement metrics"""
    intent_strength: Optional[float] = None
    show_intent: bool = False
    last_activity_date: Optional[str] = None


class EvaluationData(BaseModel):
    """Evaluation metrics and analysis"""
    fit_score: Optional[float] = None
    matching_signals: List[str] = Field(default_factory=list)
    overall_analysis: List[str] = Field(default_factory=list)
    persona_match: Optional[str] = None
    rationale: Optional[str] = None
    recommended_approach: Optional[str] = None
    key_insights: List[str] = Field(default_factory=list)


class StructuredLead(BaseModel):
    """Core lead information"""
    id: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    headline: Optional[str] = None
    about: Optional[str] = None
    linkedin_url: Optional[str] = None
    contact_info: ContactInfo = Field(default_factory=ContactInfo)
    current_employment: CurrentEmployment = Field(default_factory=CurrentEmployment)
    organization: Optional[Dict[str, Any]] = None
    location: Location = Field(default_factory=Location)
    education: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    projects: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    publications: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    groups: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    certifications: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    honor_awards: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    social_profiles: Optional[Dict[str, Any]] = None
    other_employments: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    data_quality: DataQuality = Field(default_factory=DataQuality)
    engagement_data: EngagementData = Field(default_factory=EngagementData)


class ProcessedData(BaseModel):
    """Complete processed data structure"""
    all_leads: List[Dict[str, Any]] = Field(default_factory=list)
    structured_leads: List[StructuredLead] = Field(default_factory=list)
    qualified_leads: List[Dict[str, Any]] = Field(default_factory=list)
    score_distribution: Optional[Dict[str, Any]] = None
    source: str = "proxycurl"


class PaginationData(BaseModel):
    """Pagination information"""
    page: int = 1
    total_pages: int = 1


class EnrichmentCallbackData(BaseModel):
    """Main callback data structure"""
    job_id: Optional[str] = None
    account_id: UUID
    lead_id: Optional[UUID] = None
    status: str
    enrichment_type: str
    processed_data: ProcessedData = Field(default_factory=ProcessedData)
    pagination: Optional[PaginationData] = None
    source: str = "proxycurl"
    completion_percentage: Optional[int] = None
    quality_score: Optional[float] = None
    error_details: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class EnrichmentData(BaseModel):
    """Enrichment data for leads"""
    linkedin_url: Optional[str] = None
    headline: Optional[str] = None
    about: Optional[str] = None
    location: Optional[Location] = None
    current_employment: Optional[CurrentEmployment] = None
    organization: Optional[Dict[str, Any]] = None
    contact_info: Optional[ContactInfo] = None
    education: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    projects: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    publications: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    groups: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    certifications: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    honor_awards: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    social_profiles: Optional[Dict[str, Any]] = None
    employment_history: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    data_quality: Optional[DataQuality] = None
    engagement_data: Optional[EngagementData] = None
    evaluation: Optional[EvaluationData] = None
    data_source: str = "proxycurl"
    enriched_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class CustomFields(BaseModel):
    """Custom fields including evaluation data"""
    evaluation: EvaluationData = Field(default_factory=EvaluationData)