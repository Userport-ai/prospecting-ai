#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Data models for the deep research prospecting tool.
"""

import json
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime

try:
    from json_repair import loads as repair_loads
except ImportError:
    import json
    repair_loads = json.loads
    print("Warning: json_repair not found, using standard json.loads instead")


class ResearchStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class FitLevel(str, Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    MODERATE = "moderate"
    POOR = "poor"
    UNSUITABLE = "unsuitable"
    UNKNOWN = "unknown"


@dataclass
class ProspectingTarget:
    """A target company for prospecting analysis"""
    company_name: str
    website: str
    industry: str = ""
    description: str = ""
    additional_info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QualificationSignal:
    name: str
    description: str
    importance: int = 5  # Scale of 1-5, with 5 being most important
    is_confirmed: bool = False
    detection_instructions: str = ""  # Instructions for detecting this signal in research
    
    def __str__(self):
        return f"{self.name} - {self.description} (Importance: {self.importance})"


@dataclass
class MatchedSignal:
    name: str
    description: str = ""
    importance: int = 5  # Scale of 1-5, with 5 being most important
    evidence: str = ""  # Evidence from research supporting this match


@dataclass
class SellingProduct:
    name: str
    website: str
    description: str = ""
    value_proposition: str = ""
    key_features: List[str] = field(default_factory=list)
    target_industries: List[str] = field(default_factory=list)
    ideal_customer_profile: str = ""
    competitor_alternatives: List[str] = field(default_factory=list)
    qualification_signals: List[QualificationSignal] = field(default_factory=list)
    additional_info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResearchStepResult:
    step_id: str
    question: str
    answer: str
    status: ResearchStatus = ResearchStatus.PENDING
    confidence: float = 0.0
    confidence_level: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    sources: List[str] = field(default_factory=list)
    validation_status: Optional[str] = None
    validation_notes: Optional[str] = None
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProspectingResult:
    target: ProspectingTarget
    selling_product: SellingProduct
    fit_level: FitLevel = FitLevel.UNKNOWN
    fit_score: float = 0.0  # 0.0 to 1.0
    fit_explanation: str = ""
    pain_points: List[str] = field(default_factory=list)
    value_propositions: List[str] = field(default_factory=list)
    objection_handling: List[str] = field(default_factory=list)
    key_decision_makers: List[str] = field(default_factory=list)
    matched_signals: List[MatchedSignal] = field(default_factory=list)  # List of qualification signals that match
    steps: Dict[str, ResearchStepResult] = field(default_factory=dict)
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    overall_status: ResearchStatus = ResearchStatus.PENDING
    total_time_seconds: float = 0.0  # Total time spent on research in seconds
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        # Convert Enum types to strings for better JSON serialization
        result["fit_level"] = self.fit_level.value if isinstance(self.fit_level, Enum) else self.fit_level
        result["overall_status"] = self.overall_status.value if isinstance(self.overall_status, Enum) else self.overall_status
        
        # Ensure matched_signals are properly serialized
        if "matched_signals" in result and result["matched_signals"]:
            result["matched_signals"] = [asdict(signal) for signal in self.matched_signals]
            
        return result
    
    def mark_completed(self, start_time: float = None):
        """Mark research as completed and calculate time taken if start_time provided"""
        self.completed_at = datetime.now().isoformat()
        self.overall_status = ResearchStatus.COMPLETED
        
        if start_time is not None:
            import time
            self.total_time_seconds = time.time() - start_time


class ResearchStep:
    """A step in the research workflow"""
    
    def __init__(
        self,
        step_id: str,
        question: str,
        prompt_template: str,
        depends_on: List[str] = None,
        validate_with_search: bool = False  # Default validation disabled for speed
    ):
        self.step_id = step_id
        self.question = question
        self.prompt_template = prompt_template
        self.depends_on = depends_on or []
        self.validate_with_search = validate_with_search