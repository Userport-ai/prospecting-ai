from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, validator

class TechnologyCategory(BaseModel):
    """Represents a technology category from BuiltWith."""
    name: str
    technologies: List[str] = Field(default_factory=list)

class TechnologyDetection(BaseModel):
    """Represents detection information for a specific technology."""
    first_detected: Optional[str]
    last_detected: Optional[str]
    confidence_score: float = Field(default=0.5)
    paths: List[str] = Field(default_factory=list)
    is_live: bool = Field(default=False)

class TechnologyProfile(BaseModel):
    """Represents the complete technology profile for a domain."""
    categories: Dict[str, List[str]] = Field(default_factory=dict)
    technologies: List[str] = Field(default_factory=list)
    first_detected: Dict[str, Optional[str]] = Field(default_factory=dict)
    last_detected: Dict[str, Optional[str]] = Field(default_factory=dict)
    confidence_scores: Dict[str, float] = Field(default_factory=dict)
    meta: Dict[str, Optional[str]] = Field(default_factory=dict)

    @validator('meta')
    def ensure_meta_fields(cls, v):
        """Ensure required meta fields exist."""
        v.setdefault('domain', None)
        v.setdefault('last_scan', None)
        return v

class QualityMetrics(BaseModel):
    """Quality metrics for technology enrichment data."""
    technology_count: int = Field(default=0)
    category_count: int = Field(default=0)
    average_confidence: float = Field(default=0.0)
    detection_quality: str = Field(default='insufficient_data')
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class EnrichmentResult(BaseModel):
    """Result of technology enrichment process."""
    job_id: str
    account_id: str
    enrichment_type: str
    source: str = Field(default='builtwith')
    status: str
    completion_percentage: int = Field(default=0)
    processed_data: Dict[str, Any] = Field(default_factory=dict)
    error_details: Optional[Dict[str, str]] = None

class EnrichmentSummary(BaseModel):
    """Summary of technology enrichment process."""
    status: str
    job_id: str
    account_id: str
    technologies_found: int = Field(default=0)
    categories_found: int = Field(default=0)
    quality_metrics: QualityMetrics
    processing_time: float
    error: Optional[str] = None
    stage: Optional[str] = None

class BuiltWithResponse(BaseModel):
    """Raw response from BuiltWith API."""
    class Technology(BaseModel):
        Name: str
        Categories: List[Dict[str, str]] = Field(default_factory=list)
        FirstDetected: Optional[str]
        LastDetected: Optional[str]
        Live: Optional[bool]
        Paths: List[str] = Field(default_factory=list)

    class Result(BaseModel):
        Result: List[Technology] = Field(default_factory=list)
        LastScan: Optional[str]

    Domain: str
    Results: List[Result] = Field(default_factory=list)