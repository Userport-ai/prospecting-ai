"""Deep Research package for efficient prospecting research."""

from .data_models import (
    ProspectingTarget, SellingProduct, QualificationSignal, MatchedSignal,
    ProspectingResult, FitLevel, ResearchStatus, ConfidenceLevel
)
from .research_engine import ProspectingResearchEngine
from .workflow import ProspectingWorkflow
from .database import DatabaseManager
from .utils import load_targets_from_csv
from .main import research_single_target, batch_research_targets, main

__all__ = [
    'ProspectingTarget', 'SellingProduct', 'QualificationSignal', 'MatchedSignal',
    'ProspectingResult', 'FitLevel', 'ResearchStatus', 'ConfidenceLevel',
    'ProspectingResearchEngine', 'ProspectingWorkflow', 'DatabaseManager',
    'load_targets_from_csv', 'research_single_target', 'batch_research_targets', 'main'
]