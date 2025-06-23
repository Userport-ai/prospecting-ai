from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field

class ContactInfo(BaseModel):
    """Contact information for a lead"""
    email: Optional[str] = None
    email_status: Optional[str] = None
    phone_numbers: Optional[List[str]] = None

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
    functions: Optional[List[str]] = None
    subdepartments: Optional[List[str]] = None

class DataQuality(BaseModel):
    """Data quality metrics"""
    existence_level: Optional[str] = None
    email_domain_catchall: Optional[bool] = None
    profile_photo_url: Optional[str] = None
    last_updated: Optional[str] = None

class EngagementData(BaseModel):
    """Engagement metrics"""
    intent_strength: Optional[float] = None
    show_intent: Optional[bool] = None
    last_activity_date: Optional[str] = None

class EvaluationData(BaseModel):
    """Evaluation metrics and analysis"""
    fit_score: Optional[float] = None
    matching_signals: Optional[List[str]] = None
    overall_analysis: Optional[List[str]] = None
    persona_match: Optional[str] = None
    rationale: Optional[str] = None
    recommended_approach: Optional[str] = None
    key_insights: Optional[List[str]] = None

class StructuredLead(BaseModel):
    """Core lead information"""
    id: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    headline: Optional[str] = None
    about: Optional[str] = None
    linkedin_url: Optional[str] = None
    contact_info: Optional[ContactInfo] = None
    current_employment: Optional[CurrentEmployment] = None
    organization: Optional[Dict[str, Any]] = None
    location: Optional[Location] = None
    education: Optional[List[Dict[str, Any]]] = None
    projects: Optional[List[Dict[str, Any]]] = None
    publications: Optional[List[Dict[str, Any]]] = None
    groups: Optional[List[Dict[str, Any]]] = None
    certifications: Optional[List[Dict[str, Any]]] = None
    honor_awards: Optional[List[Dict[str, Any]]] = None
    social_profiles: Optional[Dict[str, Any]] = None
    other_employments: Optional[List[Dict[str, Any]]] = None
    data_quality: Optional[DataQuality] = None
    engagement_data: Optional[EngagementData] = None

class ProcessedData(BaseModel):
    """Complete processed data structure"""
    all_leads: Optional[List[Dict[str, Any]]] = None
    structured_leads: Optional[List[StructuredLead]] = None
    qualified_leads: Optional[List[Dict[str, Any]]] = None
    score_distribution: Optional[Dict[str, Any]] = None
    source: Optional[str] = None

class PaginationData(BaseModel):
    """Pagination information"""
    page: Optional[int] = None
    total_pages: Optional[int] = None

class EnrichmentCallbackData(BaseModel):
    """Main callback data structure"""
    job_id: Optional[str] = None
    account_id: Optional[UUID] = None  
    lead_id: Optional[UUID] = None
    status: Optional[str] = None       
    enrichment_type: Optional[str] = None  
    processed_data: Optional[ProcessedData] = None
    pagination: Optional[PaginationData] = None
    source: Optional[str] = None
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
    education: Optional[List[Dict[str, Any]]] = None
    projects: Optional[List[Dict[str, Any]]] = None
    publications: Optional[List[Dict[str, Any]]] = None
    groups: Optional[List[Dict[str, Any]]] = None
    certifications: Optional[List[Dict[str, Any]]] = None
    honor_awards: Optional[List[Dict[str, Any]]] = None
    social_profiles: Optional[Dict[str, Any]] = None
    employment_history: Optional[List[Dict[str, Any]]] = None
    data_quality: Optional[DataQuality] = None
    engagement_data: Optional[EngagementData] = None
    evaluation: Optional[EvaluationData] = None
    data_source: Optional[str] = None
    enriched_at: Optional[str] = None

class CustomFields(BaseModel):
    """Custom fields including evaluation data"""
    evaluation: Optional[EvaluationData] = None