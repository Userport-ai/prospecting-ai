import os
from typing import Optional

from google.cloud import bigquery

from utils.loguru_setup import logger
from services.ai_cache_service import AICacheService
from services.ai_service_base import AIService
from services.gemini_service import GeminiService
from services.openai_service import OpenAIService


class AIServiceFactory:
    """Factory for creating AI service instances with integrated caching."""

    # ===============================
    # Initialization
    # ===============================

    def __init__(
            self
    ):
        """
        Initialize the factory with optional BigQuery settings for caching.

        If caching is enabled, will use:
        - GOOGLE_CLOUD_PROJECT env var if project_id not provided
        - BIGQUERY_DATASET env var (default: 'userport_enrichment') if dataset not provided
        """
        self.cache_service = None

        # Get project ID from args or environment
        self.project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
        if not self.project_id:
            raise ValueError("Project ID must be provided or GOOGLE_CLOUD_PROJECT environment variable must be set")

        # Get dataset from args or environment
        self.dataset = os.getenv('BIGQUERY_DATASET', 'userport_enrichment')

        # Initialize BigQuery client
        try:
            bigquery_client = bigquery.Client(project=self.project_id)
            self.cache_service = AICacheService(
                client=bigquery_client,
                project_id=self.project_id,
                dataset=self.dataset
            )
        except Exception as e:
            logger.error(f"Failed to initialize BigQuery client: {str(e)}")
            raise

    # ===============================
    # Service Creation
    # ===============================

    def create_service(
            self,
            provider: str = "openai",
            tenant_id: Optional[str] = None,
            model_name: Optional[str] = None,
            cache_ttl_hours: Optional[int] = 24,
            default_temperature: Optional[float] = 0.2
    ) -> AIService:
        """
        Create an AI service instance with optional caching.

        Args:
            provider: AI provider ("openai" or "gemini")
            model_name: Optional model name to use
            tenant_id: Optional tenant ID for multi-tenancy
            cache_ttl_hours: Cache TTL in hours (only used if caching is enabled)
            default_temperature: Default temperature setting (0.0 for deterministic outputs)

        Returns:
            AIService instance (OpenAIService or GeminiService)
        """
        service: AIService

        if provider.lower() == "openai":
            service = OpenAIService(
                model_name=model_name,
                cache_service=self.cache_service,
                tenant_id=tenant_id,
                default_temperature=default_temperature
            )
        elif provider.lower() == "gemini":
            service = GeminiService(
                model_name=model_name,
                cache_service=self.cache_service,
                tenant_id=tenant_id,
                default_temperature=default_temperature
            )
        else:
            raise ValueError(f"Unsupported AI provider: {provider}")

        # Set cache TTL if caching is enabled
        if self.cache_service and cache_ttl_hours is not None:
            service.cache_ttl_hours = cache_ttl_hours

        return service

    # ===============================
    # Resource Management
    # ===============================

    async def close(self):
        """Close any resources used by the factory."""
        pass