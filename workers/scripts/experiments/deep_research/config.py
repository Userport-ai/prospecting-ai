"""Configuration settings for the deep research prospecting tool."""
TIMEOUTS = {
    # Agent timeouts
    "agent_max_iterations": 8,        # Reduced from 12 to 8 to speed up processing
    "agent_execution_time": 300,      # 5 minutes max per agent execution (reduced from 10 minutes)
    
    # Step timeouts
    "research_step": 300,             # 5 minutes per research step (reduced from 20 minutes)
    "validation_step": 120,           # 2 minutes for validation (reduced from 10 minutes)
    
    # Overall workflow timeouts
    "account_research": 900,          # 15 minutes per account (reduced from 1 hour)
    "batch_processing": 36000         # 10 hours for the entire batch
}

# LLM model configurations
DEFAULT_MODEL = "gemini-2.5-flash-preview-04-17"

# Research step configuration
MAX_QUALIFICATION_SIGNALS = 4  # Maximum number of qualification signals to process

# Fit score mapping for fit levels
FIT_LEVEL_SCORES = {
    "excellent": 0.9,
    "good": 0.7,
    "moderate": 0.5,
    "poor": 0.3,
    "unsuitable": 0.1,
    "unknown": 0.5
}

# Signal weight configuration
SIGNAL_WEIGHT = 0.4  # Weight given to signal score (increased from 0.3 for more importance)
BASE_SCORE_WEIGHT = 1 - SIGNAL_WEIGHT  # Weight given to base fit score

# Apollo API configuration
APOLLO_API_CONFIG = {
    "concurrency_limit": 3,
    "rate_limit_delay": 1.0,
    "cache_results": True,
    "cache_ttl": 3600,
    "default_max_companies": 100,
    "default_filters": {
        "employee_count_min": 50,
        "b2b": True
    }
}

# Company filters for various product types
COMMON_FILTER_TEMPLATES = {
    "b2b_saas": {
        "employee_count_min": 50,
        "employee_count_max": 10000,
        "b2b": True,
        "countries": ["United States", "Canada", "United Kingdom", "Australia"]
    },
    "enterprise": {
        "employee_count_min": 1000,
        "is_public": True,
        "b2b": True
    },
    "startup_focused": {
        "employee_count_min": 10,
        "employee_count_max": 200,
        "funding_stage": ["seed", "series_a", "series_b"]
    },
    "financial_services": {
        "industries": ["Financial Services"],
        "employee_count_min": 100
    }
}