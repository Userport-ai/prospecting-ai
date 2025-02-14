from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional, Any, Union

from pydantic import BaseModel, Field, model_validator

class Category(BaseModel):
    """Model for technology categories."""
    name: str = Field(alias="Name")
    confidence: Optional[float] = Field(alias="Confidence", default=None)

    @model_validator(mode='before')
    @classmethod
    def handle_string_input(cls, value: Any) -> Dict[str, Any]:
        """Handle when category is provided as a string instead of dict."""
        if isinstance(value, str):
            return {"Name": value, "Confidence": None}
        return value

class SpendHistory(BaseModel):
    """Model for spend history data."""
    D: Optional[int] = None  # Date timestamp
    S: Optional[int] = None  # Spend amount

class TechnologyBase(BaseModel):
    """Base model for technology-related data."""
    Name: Optional[str] = None
    Description: Optional[str] = None
    Link: Optional[str] = None
    Tag: Optional[str] = None
    FirstDetected: Optional[int] = None
    LastDetected: Optional[int] = None
    Categories: List[Union[Category, str]] = Field(default_factory=list)
    Parent: Optional[str] = None
    IsPremium: Optional[str] = None
    Live: Optional[bool] = None
    Paths: Optional[List[str]] = Field(default_factory=list)

    def get_category_names(self) -> List[str]:
        """Extract category names from Categories list."""
        if not self.Categories:
            return []
        return [cat.name if isinstance(cat, Category) else cat for cat in self.Categories]

    @model_validator(mode='before')
    @classmethod
    def normalize_categories(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Handle different category formats in the input."""
        if 'Categories' in values:
            categories = values['Categories']
            if isinstance(categories, list):
                normalized = []
                for cat in categories:
                    if isinstance(cat, str):
                        normalized.append({"Name": cat})
                    else:
                        normalized.append(cat)
                values['Categories'] = normalized
        return values

class PathTechnologies(BaseModel):
    """Model for technologies within a path."""
    Technologies: Optional[List[TechnologyBase]] = Field(default_factory=list)

class ResultData(BaseModel):
    """Model for the Result object data."""
    IsDB: Optional[str] = None
    Spend: Optional[int] = None
    Paths: Optional[List[PathTechnologies]] = Field(default_factory=list)

class ResultGroup(BaseModel):
    """Model for a group of results."""
    Result: Optional[ResultData] = None
    FirstIndexed: Optional[int] = None
    Meta: Optional[MetaData] = None
    LastIndexed: Optional[int] = None
    Domain: Optional[str] = None
    Url: Optional[str] = None
    SubDomain: Optional[str] = None
    Technologies: Optional[List[TechnologyBase]] = Field(default_factory=list)

class MetaAttributes(BaseModel):
    """Model for additional metadata attributes."""
    Employees: int = 0
    MJRank: int = 0
    MJTLDRank: int = 0
    RefSN: int = 0
    RefIP: int = 0
    Followers: int = 0
    Sitemap: int = 0
    GTMTags: int = 0
    QubitTags: int = 0
    TealiumTags: int = 0
    AdobeTags: int = 0
    CDimensions: int = 0
    CGoals: int = 0
    CMetrics: int = 0
    ProductCount: int = 0

class MetaData(BaseModel):
    """Model for BuiltWith metadata."""
    Majestic: Optional[int] = None
    Umbrella: Optional[int] = None
    Vertical: Optional[str] = None
    Social: Optional[List[str]] = Field(default_factory=list)
    CompanyName: Optional[str] = None
    Telephones: Optional[List[str]] = Field(default_factory=list)
    Emails: Optional[List[str]] = Field(default_factory=list)
    City: Optional[str] = None
    State: Optional[str] = None
    Postcode: Optional[str] = None
    Country: Optional[str] = None
    Names: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    ARank: Optional[int] = None
    QRank: Optional[int] = None

class BuiltWithApiResponse(BaseModel):
    """Complete model for BuiltWith API response."""
    Results: Optional[List[ResultGroup]] = Field(default_factory=list)
    Domain: Optional[str] = None
    Attributes: Optional[MetaAttributes] = None
    FirstIndexed: Optional[int] = None
    LastIndexed: Optional[int] = None
    Lookup: Optional[str] = None
    SalesRevenue: Optional[int] = 0
    Errors: Optional[List[str]] = Field(default_factory=list)
    Trust: Optional[Any] = None

class TechnologyProfile(BaseModel):
    """Processed technology profile."""
    categories: Dict[str, List[str]] = Field(default_factory=dict)
    technologies: List[Dict[str, Any]] = Field(default_factory=list)
    first_detected: Dict[str, Optional[str]] = Field(default_factory=dict)
    last_detected: Dict[str, Optional[str]] = Field(default_factory=dict)
    confidence_scores: Dict[str, float] = Field(default_factory=dict)
    premium_technologies: List[str] = Field(default_factory=list)
    subdomains: Dict[str, List[str]] = Field(default_factory=dict)
    meta: Dict[str, Any] = Field(default_factory=dict)
    company_info: Dict[str, Any] = Field(default_factory=dict)

class TechnologyDetail(BaseModel):
    """Detailed information about a specific technology."""
    name: str
    description: Optional[str] = None
    categories: List[str] = Field(default_factory=list)
    tag: Optional[str] = None
    link: Optional[str] = None
    first_detected: Optional[str] = None
    last_detected: Optional[str] = None
    is_premium: bool = False
    confidence_score: float = 0.0
    parent_technology: Optional[str] = None
    paths: List[str] = Field(default_factory=list)
    subdomain: Optional[str] = None

class QualityMetrics(BaseModel):
    """Quality metrics for technology enrichment."""
    technology_count: int = 0
    category_count: int = 0
    premium_count: int = 0
    subdomain_count: int = 0
    average_confidence: float = 0.0
    detection_quality: str = 'insufficient_data'
    earliest_detection: Optional[str] = None
    latest_detection: Optional[str] = None
    coverage_score: float = 0.0
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class EnrichmentError(BaseModel):
    """Error information for enrichment process."""
    message: str
    code: str
    details: Optional[Dict[str, Any]] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class EnrichmentResult(BaseModel):
    """Complete enrichment process result."""
    job_id: str
    account_id: str
    enrichment_type: str = "technology_profile"
    source: str = "builtwith"
    status: str = "pending"
    completion_percentage: int = 0
    processed_data: Dict[str, Any] = Field(default_factory=dict)
    quality_metrics: Optional[QualityMetrics] = None
    error: Optional[EnrichmentError] = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())