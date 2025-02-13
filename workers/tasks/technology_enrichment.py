import logging
import time
from datetime import datetime
from typing import Dict, Any, Tuple, Optional

from services.api_cache_service import APICacheService
from services.bigquery_service import BigQueryService
from services.builtwith_service import BuiltWithService
from utils.url_utils import UrlUtils
from models.technology_enrichment import (
    TechnologyProfile,
    QualityMetrics,
    EnrichmentResult,
    EnrichmentSummary
)
from .enrichment_task import AccountEnrichmentTask

logger = logging.getLogger(__name__)

class TechnologyEnrichmentTask(AccountEnrichmentTask):
    """Task for enriching account data with technology stack information from BuiltWith."""

    ENRICHMENT_TYPE = 'technology_info'

    def __init__(self, callback_service):
        """Initialize the task with required services."""
        super().__init__(callback_service)
        self.callback_svc = callback_service
        self.bq_service = BigQueryService()
        self.cache_service = APICacheService(
            client=self.bq_service.client,
            project_id=self.project_id,
            dataset=self.dataset
        )
        self.builtwith_service = BuiltWithService(self.cache_service)

    @property
    def enrichment_type(self) -> str:
        return self.ENRICHMENT_TYPE

    @property
    def task_name(self) -> str:
        return "technology_enrichment_builtwith"

    async def create_task_payload(self, **kwargs) -> Dict[str, Any]:
        """Create a standardized task payload.

        Args:
            **kwargs: Must include account_id and account_data

        Returns:
            Dict containing the task payload
        """
        required_fields = ['account_id', 'account_data']
        missing_fields = [field for field in required_fields if field not in kwargs]

        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

        return {
            "account_id": kwargs["account_id"],
            "account_data": kwargs["account_data"],
            "tenant_id": kwargs.get("tenant_id"),
            "job_id": kwargs.get("job_id")
        }

    async def execute(self, payload: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Execute the technology enrichment task.

        Args:
            payload: Task payload containing account information

        Returns:
            Tuple of (result, summary) dictionaries
        """
        start_time = time.time()
        job_id = payload.get('job_id')
        account_id = payload.get('account_id')
        account_data = payload.get('account_data', {})
        current_stage = 'initialization'

        website = account_data.get('website')
        if not website:
            raise ValueError("Account website is required for technology enrichment")

        domain = UrlUtils.extract_domain(website)
        logger.info(f"Starting technology enrichment for job_id: {job_id}, account_id: {account_id}, domain: {domain}")

        try:
            # Send initial processing callback
            initial_result = EnrichmentResult(
                job_id=job_id,
                account_id=account_id,
                enrichment_type=self.ENRICHMENT_TYPE,
                source="builtwith",
                status='processing',
                completion_percentage=10,
                processed_data={'stage': current_stage}
            )
            await self.callback_svc.send_callback(**initial_result.model_dump())

            # Fetch technology data
            current_stage = 'fetching_technology_data'
            technology_data: TechnologyProfile = await self.builtwith_service.get_technology_profile(domain)

            progress_result = EnrichmentResult(
                job_id=job_id,
                account_id=account_id,
                enrichment_type=self.ENRICHMENT_TYPE,
                source="builtwith",
                status='processing',
                completion_percentage=50,
                processed_data={
                    'stage': current_stage,
                    'technologies_found': len(technology_data.technologies)
                }
            )
            await self.callback_svc.send_callback(**progress_result.model_dump())

            # Calculate quality metrics
            quality_metrics = self._calculate_quality_metrics(technology_data)

            # Store results
            current_stage = 'storing_results'
            processing_time = time.time() - start_time

            # Prepare the final result
            result = EnrichmentResult(
                job_id=job_id,
                account_id=account_id,
                enrichment_type=self.ENRICHMENT_TYPE,
                source="builtwith",
                status='completed',
                completion_percentage=100,
                processed_data={
                    'technology_data': technology_data.model_dump(),
                    'quality_metrics': quality_metrics.model_dump(),
                    'processing_time': processing_time
                }
            )

            # Store in BigQuery
            await self.bq_service.insert_enrichment_raw_data(
                job_id=job_id,
                entity_id=account_id,
                source='builtwith',
                raw_data=technology_data.model_dump(),
                processed_data={
                    'technologies': technology_data.technologies,
                    'categories': technology_data.categories,
                    'quality_metrics': quality_metrics.model_dump()
                }
            )

            summary = EnrichmentSummary(
                status="completed",
                job_id=job_id,
                account_id=account_id,
                technologies_found=len(technology_data.technologies),
                categories_found=len(technology_data.categories),
                quality_metrics=quality_metrics,
                processing_time=processing_time
            )

            return result.model_dump(), summary.model_dump()

        except Exception as e:
            logger.error(f"Technology enrichment failed for job {job_id}: {str(e)}", exc_info=True)
            error_details = {
                'error_type': type(e).__name__,
                'message': str(e),
                'stage': current_stage
            }

            await self._store_error_state(job_id, account_id, error_details)
            
            error_result = EnrichmentResult(
                job_id=job_id,
                account_id=account_id,
                enrichment_type=self.ENRICHMENT_TYPE,
                source="builtwith",
                status='failed',
                error_details=error_details,
                processed_data={'stage': current_stage}
            )
            await self.callback_svc.send_callback(**error_result.model_dump())

            error_summary = EnrichmentSummary(
                status="failed",
                job_id=job_id,
                account_id=account_id,
                quality_metrics=QualityMetrics(),
                processing_time=time.time() - start_time,
                error=str(e),
                stage=current_stage
            )

            return None, error_summary.model_dump()

    def _calculate_quality_metrics(self, technology_data: TechnologyProfile) -> QualityMetrics:
        """Calculate quality metrics for the technology data.

        Args:
            technology_data: Processed technology data

        Returns:
            QualityMetrics containing quality metrics
        """
        if not technology_data.technologies:
            return QualityMetrics()

        # Calculate average confidence
        avg_confidence = (sum(technology_data.confidence_scores.values()) / 
                        len(technology_data.confidence_scores) 
                        if technology_data.confidence_scores else 0.0)

        # Determine detection quality
        if len(technology_data.technologies) >= 5 and avg_confidence >= 0.7:
            detection_quality = 'high'
        elif len(technology_data.technologies) >= 3 and avg_confidence >= 0.5:
            detection_quality = 'medium'
        else:
            detection_quality = 'low'

        return QualityMetrics(
            technology_count=len(technology_data.technologies),
            category_count=len(technology_data.categories),
            average_confidence=round(avg_confidence, 3),
            detection_quality=detection_quality,
            timestamp=datetime.utcnow().isoformat()
        )