import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional

from google.api_core.exceptions import ResourceExhausted

from models.common import UserportPydanticBaseModel
from services.ai_service import AIServiceFactory
from services.bigquery_service import BigQueryService
from services.django_callback_service import CallbackService
from tasks.enrichment_task import AccountEnrichmentTask
from utils.retry_utils import RetryableError, RetryConfig, with_retry
from utils.loguru_setup import logger



# Retry configuration for AI operations
AI_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=2.0,
    max_delay=30.0,
    retryable_exceptions=[
        RetryableError,
        ResourceExhausted,
        ValueError,
        RuntimeError,
        TimeoutError,
        ConnectionError
    ]
)

class CustomColumnValue(UserportPydanticBaseModel):
    """Model for custom column value."""
    column_id: str
    entity_id: str
    value_string: Optional[str] = None
    value_json: Optional[Dict[str, Any]] = None
    value_boolean: Optional[bool] = None
    value_number: Optional[float] = None
    confidence_score: Optional[float] = None
    generated_at: datetime
    error_details: Optional[Dict[str, Any]] = None
    status: str = "pending"

class CustomColumnTask(AccountEnrichmentTask):
    """Task for generating and updating custom column values."""

    ENRICHMENT_TYPE = 'custom_column'

    def __init__(self, callback_service):
        """Initialize the task with required services."""
        super(callback_service)
        self.bq_service = BigQueryService()
        self._configure_ai_service()

    def _configure_ai_service(self) -> None:
        """Configure the AI service."""
        self.model = AIServiceFactory().create_service("gemini")

    @property
    def enrichment_type(self) -> str:
        return self.ENRICHMENT_TYPE

    @property
    def task_name(self) -> str:
        """Get the task identifier."""
        return "custom_column"

    async def create_task_payload(self, **kwargs) -> Dict[str, Any]:
        """Create a standardized task payload."""
        required_fields = ['column_id', 'entity_ids', 'column_config', 'context_data']
        missing_fields = [field for field in required_fields if field not in kwargs]

        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

        return {
            "column_id": kwargs["column_id"],
            "entity_ids": kwargs["entity_ids"],
            "column_config": kwargs["column_config"],
            "context_data": kwargs["context_data"],
            "tenant_id": kwargs.get("tenant_id"),
            "batch_size": kwargs.get("batch_size", 10),
            "job_id": kwargs.get("job_id"),
            "attempt_number": kwargs.get("attempt_number", 1),
            "max_retries": kwargs.get("max_retries", 3)
        }

    async def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the custom column generation task."""
        job_id = payload.get('job_id')
        column_id = payload.get('column_id')
        entity_ids = payload.get('entity_ids', [])
        column_config = payload.get('column_config', {})
        context_data = payload.get('context_data', {})
        batch_size = payload.get('batch_size', 10)
        current_stage = 'initialization'
        callback_service = await CallbackService.get_instance()

        logger.info(f"Starting custom column generation for job_id: {job_id}, column_id: {column_id}")

        try:
            # Initial processing callback
            await callback_service.send_callback(
                job_id=job_id,
                account_id=entity_ids[0] if entity_ids else None,
                status='processing',
                enrichment_type=self.ENRICHMENT_TYPE,
                source="custom_column",
                completion_percentage=10,
                processed_data={'stage': current_stage}
            )

            # Process entities in batches
            current_stage = 'processing'
            total_entities = len(entity_ids)
            processed_values = []
            failed_entities = []

            for i in range(0, total_entities, batch_size):
                batch = entity_ids[i:i + batch_size]

                # Generate values for batch
                batch_values = await self._process_batch(
                    batch,
                    column_id,
                    column_config,
                    context_data
                )

                processed_values.extend(batch_values)

                # Calculate progress
                completion = int((i + len(batch)) / total_entities * 100)

                # Send progress callback
                await callback_service.send_callback(
                    job_id=job_id,
                    account_id=entity_ids[0],
                    status='processing',
                    enrichment_type=self.ENRICHMENT_TYPE,
                    source="custom_column",
                    completion_percentage=completion,
                    processed_data={
                        'stage': current_stage,
                        'processed_count': i + len(batch),
                        'total_count': total_entities
                    }
                )

            # Store results
            current_stage = 'storing_results'
            await self._store_results(
                job_id=job_id,
                column_id=column_id,
                values=processed_values
            )

            # Calculate success metrics
            successful_count = len([v for v in processed_values if v.status == "completed"])
            failed_count = len([v for v in processed_values if v.status == "error"])

            # Send completion callback
            await callback_service.send_callback(
                job_id=job_id,
                account_id=entity_ids[0],
                status='completed',
                enrichment_type=self.ENRICHMENT_TYPE,
                source="custom_column",
                completion_percentage=100,
                processed_data={
                    'successful_count': successful_count,
                    'failed_count': failed_count,
                    'values': [v.dict() for v in processed_values]
                }
            )

            return {
                "status": "completed",
                "job_id": job_id,
                "column_id": column_id,
                "total_processed": len(processed_values),
                "successful_count": successful_count,
                "failed_count": failed_count
            }

        except Exception as e:
            logger.error(f"Custom column generation failed for job {job_id}: {str(e)}", exc_info=True)
            error_details = {
                'error_type': type(e).__name__,
                'message': str(e),
                'stage': current_stage
            }

            # Store error state
            await self._store_error_state(job_id, column_id, error_details)

            # Send failure callback
            await callback_service.send_callback(
                job_id=job_id,
                account_id=entity_ids[0] if entity_ids else None,
                status='failed',
                enrichment_type=self.ENRICHMENT_TYPE,
                source="custom_column",
                error_details=error_details,
                processed_data={'stage': current_stage}
            )

            return {
                "status": "failed",
                "job_id": job_id,
                "column_id": column_id,
                "error": str(e),
                "stage": current_stage
            }

    async def _process_batch(
            self,
            entity_ids: List[str],
            column_id: str,
            column_config: Dict[str, Any],
            context_data: Dict[str, Any]
    ) -> List[CustomColumnValue]:
        """Process a batch of entities."""
        results = []

        for entity_id in entity_ids:
            try:
                # Generate value using AI
                value = await self._generate_column_value(
                    entity_id=entity_id,
                    column_config=column_config,
                    context_data=context_data
                )

                results.append(CustomColumnValue(
                    column_id=column_id,
                    entity_id=entity_id,
                    **value,
                    generated_at=datetime.utcnow(),
                    status="completed"
                ))

            except Exception as e:
                logger.error(f"Error processing entity {entity_id}: {str(e)}")
                results.append(CustomColumnValue(
                    column_id=column_id,
                    entity_id=entity_id,
                    error_details={"error": str(e)},
                    generated_at=datetime.utcnow(),
                    status="error"
                ))

        return results

    @with_retry(retry_config=AI_RETRY_CONFIG, operation_name="generate_column_value")
    async def _generate_column_value(
            self,
            entity_id: str,
            column_config: Dict[str, Any],
            context_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate a single column value using AI."""
        try:
            # Prepare prompt with context
            prompt = self._create_generation_prompt(
                entity_id=entity_id,
                column_config=column_config,
                context_data=context_data
            )

            # Generate value
            response = await self.model.generate_content(prompt, is_json=True)

            # Validate and format response
            value = self._validate_response(response, column_config['response_type'])

            return value

        except Exception as e:
            logger.error(f"Error generating column value: {str(e)}")
            raise

    def _create_generation_prompt(
            self,
            entity_id: str,
            column_config: Dict[str, Any],
            context_data: Dict[str, Any]
    ) -> str:
        """Create the prompt for value generation."""
        return f"""Generate a value for the following custom column:

Column Configuration:
{column_config}

Entity Context:
{context_data.get(entity_id, {})}

Response Requirements:
1. Response must match the configured response_type: {column_config['response_type']}
2. Include a confidence score between 0 and 1
3. Provide rationale for the generated value

Return as JSON:
{{
    "value": <typed_value>,
    "confidence_score": float,
    "rationale": string
}}"""

    def _validate_response(self, response: Dict[str, Any], response_type: str) -> Dict[str, Any]:
        """Validate and format the AI response."""
        if not response or 'value' not in response:
            raise ValueError("Invalid response format")

        value = response['value']
        confidence = response.get('confidence_score', 0.0)

        # Format based on response type
        if response_type == "string":
            return {"value_string": str(value), "confidence_score": confidence}
        elif response_type == "json_object":
            return {"value_json": value, "confidence_score": confidence}
        elif response_type == "boolean":
            return {"value_boolean": bool(value), "confidence_score": confidence}
        elif response_type == "number":
            return {"value_number": float(value), "confidence_score": confidence}
        else:
            raise ValueError(f"Unsupported response type: {response_type}")

    async def _store_results(
            self,
            job_id: str,
            column_id: str,
            values: List[CustomColumnValue]
    ) -> None:
        """Store generated values in BigQuery."""
        try:
            for value in values:
                await self.bq_service.insert_enrichment_raw_data(
                    job_id=job_id,
                    entity_id=value.entity_id,
                    source='custom_column',
                    raw_data={
                        'column_id': column_id,
                        'value': value.dict(exclude_none=True)
                    },
                    processed_data=value.dict(exclude={'error_details'})
                )
        except Exception as e:
            logger.error(f"Error storing results: {str(e)}")
            raise

    async def _store_error_state(
            self,
            job_id: str,
            column_id: str,
            error_details: Dict[str, Any]
    ) -> None:
        """Store error information in BigQuery."""
        try:
            formatted_error = {
                'error_type': error_details.get('error_type', 'unknown_error'),
                'message': error_details.get('message', 'Unknown error occurred'),
                'stage': error_details.get('stage', 'unknown'),
                'timestamp': datetime.utcnow().isoformat(),
                'column_id': column_id
            }

            await self.bq_service.insert_enrichment_raw_data(
                job_id=job_id,
                entity_id=column_id,
                source='custom_column',
                raw_data={},
                processed_data={},
                status='failed',
                error_details=formatted_error
            )

        except Exception as e:
            logger.error(f"Failed to store error state: {str(e)}")