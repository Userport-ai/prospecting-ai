import asyncio
import json
import time
from datetime import datetime, timezone
from json import JSONDecodeError, loads
from typing import Dict, Any, List, Optional, Tuple

from google.api_core.exceptions import ResourceExhausted

from models.common import UserportPydanticBaseModel
from services.ai.ai_service import AIServiceFactory
from services.ai.ai_service_base import ThinkingBudget, AIService
from services.bigquery_service import BigQueryService
from services.django_callback_service import CallbackService
from services.linkedin_service import LinkedInService, RapidAPILinkedInActivities
from tasks.enrichment_task import AccountEnrichmentTask
from utils.loguru_setup import logger, set_trace_context
from utils.retry_utils import RetryableError, RetryConfig, with_retry
from json_repair import loads as repair_loads

# Enhanced retry configuration for AI operations
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

# API retry configuration
API_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=5.0,
    retryable_exceptions=[
        RetryableError,
        asyncio.TimeoutError,
        ConnectionError,
        Exception  # Allow retrying on general exceptions for API calls
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
    value_enum: Optional[str] = None
    confidence_score: Optional[float] = None
    rationale: Optional[str] = None
    generated_at: datetime
    error_details: Optional[Dict[str, Any]] = None
    status: str = "pending"


class CustomColumnTask(AccountEnrichmentTask):
    """Task for generating and updating custom column values with enhanced async patterns."""

    ENRICHMENT_TYPE = 'custom_column'

    def __init__(self, callback_service):
        """Initialize the task with required services."""
        super().__init__(callback_service)
        self.bq_service = BigQueryService()
        self._configure_ai_service()  # Initialize with default models
        self.linkedin_service = LinkedInService()
        self._init_metrics()

    def _init_metrics(self):
        """Initialize metrics for tracking task performance."""
        self.metrics = {
            "total_entities": 0,
            "successful_entities": 0,
            "failed_entities": 0,
            "processing_time": 0.0,
            "ai_errors": 0,
            "api_errors": 0,
            "avg_confidence_score": 0.0,
            "start_time": datetime.now(timezone.utc)
        }

    def _configure_ai_service(self, ai_config: Optional[Dict[str, Any]] = None) -> None:
        """Configure the AI service with factory pattern.

        Args:
            ai_config: Optional configuration containing model settings.
                       If provided, uses model specified in ai_config.
        """
        factory = AIServiceFactory()

        # Default model settings
        default_provider = "gemini"
        default_model = "gemini-2.5-flash-preview-04-17"

        # Check if we should use a custom model from ai_config
        if ai_config and ai_config.get('model'):
            model_name = ai_config['model']
            model_provider = AIService.get_modelprovider(model_name)

            if model_provider and model_name:
                logger.debug(f"Configuring with custom model: {model_name} from provider: {model_provider}")
                self.model = factory.create_service(model_provider, model_name=model_name)
                self.search_model = factory.create_service(model_provider, model_name=model_name, default_temperature=0.1)
                return

        # Fall back to default models if custom configuration isn't provided or valid
        self.model = factory.create_service(default_provider, model_name=default_model)
        self.search_model = factory.create_service(default_provider, model_name=default_model, default_temperature=0.1)

    @property
    def enrichment_type(self) -> str:
        """Get the enrichment type."""
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
            "ai_config": kwargs.get("ai_config"),
            "entity_type": kwargs.get("entity_type"),
            "batch_size": kwargs.get("batch_size", 10),
            "job_id": kwargs.get("job_id"),
            "concurrent_requests": kwargs.get("concurrent_requests", 5),
            "attempt_number": kwargs.get("attempt_number", 1),
            "max_retries": kwargs.get("max_retries", 3),
            "orchestration_data": kwargs.get("orchestration_data", {}),
        }

    async def execute(self, payload: Dict[str, Any]) -> (Dict[str, Any], Dict[str, Any]):
        """Execute the custom column generation task."""
        job_id = payload.get('job_id')
        column_id = payload.get('column_id')
        entity_ids = payload.get('entity_ids', [])
        column_config = payload.get('column_config', {})
        context_data = payload.get('context_data', {})
        batch_size = payload.get('batch_size', 10)
        concurrent_requests = 1 # payload.get('concurrent_requests', 2)
        ai_config = payload.get('ai_config')
        entity_type = payload.get('entity_type')
        current_stage = 'initialization'
        start_time = time.time()

        if ai_config and ai_config.get('model'):
            logger.info(f"Task using custom model configuration from ai_config: {ai_config.get('model')}")
            self._configure_ai_service(ai_config)

        # Update metrics
        self.metrics["total_entities"] = len(entity_ids)

        callback_service = await CallbackService.get_instance()

        logger.info(f"Starting custom column generation for job_id: {job_id}, column_id: {column_id}")
        logger.info(f"Processing {len(entity_ids)} entities with batch_size={batch_size}, concurrent_requests={concurrent_requests}")

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

            # Process entities in batches with concurrency control
            current_stage = 'processing'
            total_entities = len(entity_ids)
            processed_values = []
            failed_entities = []
            confidence_scores = []

            # Create semaphore for concurrency control
            semaphore = asyncio.Semaphore(concurrent_requests)

            # Create batches for processing
            batches = [entity_ids[i:i + batch_size] for i in range(0, total_entities, batch_size)]
            logger.info(f"Created {len(batches)} batches for processing")

            async def process_batch(batch_index: int, batch: List[str]) -> Tuple[List[CustomColumnValue], List[str]]:
                """Process a single batch of entities with semaphore control."""
                batch_values = []
                batch_failed = []

                async with semaphore:
                    logger.debug(f"Processing batch {batch_index+1}/{len(batches)} with {len(batch)} entities")
                    try:
                        # Generate values for batch
                        batch_result = await self._process_batch(
                            batch,
                            entity_type,
                            column_id,
                            column_config,
                            context_data,
                            ai_config
                        )

                        batch_values.extend(batch_result)

                        # Track failed entities in this batch
                        batch_failed = [v.entity_id for v in batch_result if v.status == "error"]

                        # Track confidence scores
                        for value in batch_result:
                            if value.status == "completed" and value.confidence_score is not None:
                                confidence_scores.append(value.confidence_score)

                        # Calculate progress for this batch
                        batch_completion = (batch_index + 1) / len(batches) * 80 + 10  # Scale to 10-90%

                        # Send progress callback for each batch
                        logger.debug(f"Batch {batch_index+1} completed: {len(batch_result)} processed, {len(batch_failed)} failed")

                        # Send batch completion callback
                        if batch_index % max(1, len(batches) // 10) == 0 or batch_index == len(batches) - 1:
                            await callback_service.send_callback(
                                job_id=job_id,
                                account_id=entity_ids[0],
                                status='processing',
                                enrichment_type=self.ENRICHMENT_TYPE,
                                source="custom_column",
                                completion_percentage=int(batch_completion),
                                processed_data={
                                    'stage': current_stage,
                                    'processed_count': (batch_index + 1) * batch_size,
                                    'total_count': total_entities,
                                    'batch_completed': batch_index + 1,
                                    'total_batches': len(batches)
                                }
                            )

                        return batch_values, batch_failed

                    except Exception as e:
                        logger.error(f"Error processing batch {batch_index}: {str(e)}", exc_info=True)
                        self.metrics["api_errors"] += 1
                        # Return failure for all entities in batch
                        error_values = []
                        for entity_id in batch:
                            error_values.append(CustomColumnValue(
                                column_id=column_id,
                                entity_id=entity_id,
                                error_details={"error": str(e), "batch_index": batch_index},
                                generated_at=datetime.utcnow(),
                                status="error"
                            ))

                        return error_values, batch

            # Execute all batches concurrently and gather results
            batch_tasks = [process_batch(i, batch) for i, batch in enumerate(batches)]
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            # Process results from all batches
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Batch processing exception: {str(result)}")
                    self.metrics["api_errors"] += 1
                    continue

                batch_values, batch_failed = result
                processed_values.extend(batch_values)
                failed_entities.extend(batch_failed)

            # Store results
            # current_stage = 'storing_results'
            # logger.info(f"Storing results for {len(processed_values)} processed values")
            # await self._store_results(
            #     job_id=job_id,
            #     column_id=column_id,
            #     values=processed_values
            # )

            # Calculate success metrics
            successful_count = len([v for v in processed_values if v.status == "completed"])
            failed_count = len([v for v in processed_values if v.status == "error"])

            # Update metrics
            self.metrics["successful_entities"] = successful_count
            self.metrics["failed_entities"] = failed_count
            self.metrics["processing_time"] = time.time() - start_time
            self.metrics["avg_confidence_score"] = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0

            orchestration_data = payload.get('orchestration_data', {})
            logger.debug(f"Custom column generation completed for job {job_id}: {self.metrics}, Orchestration data: {orchestration_data}")

            # Send completion callback
            await callback_service.send_callback(
                job_id=job_id,
                account_id=entity_ids[0],
                status='completed',
                enrichment_type=self.ENRICHMENT_TYPE,
                source="custom_column",
                completion_percentage=100,
                orchestration_data=orchestration_data if orchestration_data else None,
                processed_data={
                    'successful_count': successful_count,
                    'failed_count': failed_count,
                    'avg_confidence': self.metrics["avg_confidence_score"],
                    'processing_time_seconds': self.metrics["processing_time"],
                    'values': [v.dict() for v in processed_values]
                }
            )

            return None, {
                "status": "completed",
                "job_id": job_id,
                "column_id": column_id,
                "total_processed": len(processed_values),
                "successful_count": successful_count,
                "failed_count": failed_count,
                "metrics": self.metrics
            }

        except Exception as e:
            logger.error(f"Custom column generation failed for job {job_id}: {str(e)}", exc_info=True)
            error_details = {
                'error_type': type(e).__name__,
                'message': str(e),
                'stage': current_stage,
                'processing_time': time.time() - start_time
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

            # Do not store the result in callback requests as we want to re-run everytime for custom column
            return None, {
                "status": "failed",
                "job_id": job_id,
                "column_id": column_id,
                "error": str(e),
                "stage": current_stage
            }

    async def _process_batch(
            self,
            entity_ids: List[str],
            entity_type: str,
            column_id: str,
            column_config: Dict[str, Any],
            context_data: Dict[str, Any],
            ai_config: Dict[str, Any],
    ) -> List[CustomColumnValue]:
        """Process a batch of entities with enhanced concurrency and error handling."""
        results = []
        tasks = []

        # Process each entity in the batch concurrently
        for entity_id in entity_ids:
            # Set trace context for better debugging
            set_trace_context(account_id=entity_id)

            task = self._process_entity(
                entity_id=entity_id,
                entity_type=entity_type,
                column_id=column_id,
                column_config=column_config,
                context_data=context_data,
                ai_config=ai_config,
            )
            tasks.append(task)

        # Execute tasks concurrently and handle results/exceptions
        entity_results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(entity_results):
            entity_id = entity_ids[i]
            if isinstance(result, Exception):
                logger.error(f"Error processing entity {entity_id}: {str(result)}")
                results.append(CustomColumnValue(
                    column_id=column_id,
                    entity_id=entity_id,
                    error_details={"error": str(result)},
                    generated_at=datetime.utcnow(),
                    status="error"
                ))
                self.metrics["ai_errors"] += 1
            else:
                results.append(result)

        return results

    async def _process_entity(self, entity_id: str, column_id: str, column_config: Dict[str, Any],
                              context_data: Dict[str, Any], entity_type=None, ai_config=None) -> CustomColumnValue:
        """Process a single entity with retry logic."""
        try:
            # Generate value using AI with retry logic
            value = await self._generate_column_value(
                entity_id=entity_id,
                entity_type=entity_type,
                column_config=column_config,
                context_data=context_data,
                ai_config=ai_config,
            )

            return CustomColumnValue(
                column_id=column_id,
                entity_id=entity_id,
                **value,
                generated_at=datetime.utcnow(),
                status="completed"
            )

        except Exception as e:
            logger.error(f"Error processing entity {entity_id}: {str(e)}")
            return CustomColumnValue(
                column_id=column_id,
                entity_id=entity_id,
                error_details={"error": str(e)},
                generated_at=datetime.utcnow(),
                status="error"
            )

    @with_retry(retry_config=AI_RETRY_CONFIG, operation_name="generate_column_value")
    async def _generate_column_value(
            self,
            entity_id: str,
            entity_type: str,
            column_config: Dict[str, Any],
            context_data: Dict[str, Any],
            ai_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate a single column value using AI with enhanced error handling."""
        try:
            # Get entity context
            entity_context = context_data.get(entity_id, {})

            if not entity_context:
                logger.warning(f"No context data found for entity {entity_id}")

            lead_linkedin_url: Optional[str] = entity_context.get("lead_info", {}).get("linkedin_url")
            if ai_config and ai_config.get('use_linkedin_activity', False) and lead_linkedin_url:
                # Fetch LinkedIn Activities for the given lead and append it to entity context.
                linkedin_activities: RapidAPILinkedInActivities = await self.linkedin_service.fetch_recent_linkedin_activities(lead_linkedin_url=lead_linkedin_url)
                entity_context["enrichment_recent_linkedin_activities"] = linkedin_activities.model_dump()

            # Check if unstructured response is enabled
            unstructured_response = ai_config.get('unstructured_response', False)

            # Prepare system and user prompts with context
            system_prompt, user_prompt = self._create_generation_prompt(
                entity_id=entity_id,
                entity_type=entity_type,
                column_config=column_config,
                ai_config=ai_config,
                entity_context=entity_context,
                unstructured_response=unstructured_response,
            )

            # Generate value with AI service
            logger.debug(f"Generating column value for entity {entity_id}")
            start_time = time.time()
            if ai_config and ai_config.get('use_internet', False):
                # Use zero thinking budget by default for web search to prevent hallucination and simulated searches
                thinking_budget = ai_config.get('thinking_budget', ThinkingBudget.ZERO)
                temperature = ai_config.get('temperature', 0.0)

                combined_prompt = f"<system_prompt>{system_prompt}</system_prompt>\n\n{user_prompt}"
                response = await self.search_model.generate_search_content(combined_prompt,
                                                                           search_context_size="high",
                                                                           force_refresh=True,
                                                                           operation_tag='custom_column_with_internet',
                                                                           temperature=temperature,
                                                                           thinking_budget=thinking_budget)
            else:
                # For non-internet based generation, use the default thinking budget in the model
                thinking_budget = ai_config.get('thinking_budget', None)
                temperature = ai_config.get('temperature', 0.8)
                response = await self.model.generate_content(
                    is_json=not unstructured_response,
                    thinking_budget=thinking_budget,
                    temperature=temperature,
                    operation_tag='custom_column',
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    force_refresh=True
                )
            generation_time = time.time() - start_time
            logger.debug(f"Value generation for entity {entity_id} completed in {generation_time:.2f}s")

            # Validate and format response
            value = self._validate_response(response, column_config, unstructured_response)

            # Log the confidence score
            if 'confidence_score' in value:
                logger.debug(f"Entity {entity_id} confidence score: {value['confidence_score']}")

            if 'rationale' in value:
                logger.debug(f"Entity {entity_id} rationale: {value['rationale']}")

            return value

        except Exception as e:
            logger.error(f"Error generating column value for entity {entity_id}: {str(e)}", exc_info=True)
            self.metrics["ai_errors"] += 1
            raise RetryableError(f"AI generation failed: {str(e)}")

    def _create_generation_prompt(self, entity_id: str, column_config: Dict[str, Any],
                                  ai_config: Dict[str, Any],
                                  entity_context: Dict[str, Any],
                                  entity_type=None,
                                  unstructured_response=False) -> Tuple[str, str]:
        """Create system and user prompts for value generation.

        Returns:
            Tuple containing (system_prompt, user_prompt)
        """
        # Extract column description and expected values
        column_description = column_config.get('description', 'No description provided')
        question = column_config.get('question', '')
        response_type = column_config.get('response_type', 'string')
        expected_format = self._get_format_for_response_type(column_config)
        entity_type_str = entity_type if entity_type else "account/lead"

        # Get any examples from config
        examples = column_config.get('examples', [])
        examples_text = "\n".join([f"- {example}" for example in examples]) if examples else ""

        # Get any validation rules
        validation_rules = column_config.get('validation_rules', [])
        validation_text = "\n".join([f"- {rule}" for rule in validation_rules]) if validation_rules else ""

        internet_use_text = ""
        if ai_config and ai_config.get('use_internet', False):
            internet_use_text = "\nALWAYS use web research to find the answer and confirm that the answer you're giving is accurate. DO NOT SIMULATE Web searches, perform actual research.\n"
        else:
            internet_use_text = "\nOnly use the provided context and DO NOT use web research to find the answer.\n"

        # Define conditional sections
        examples_section = f"""
    If available, here are some examples to guide your response:
    <examples>
    {examples_text}
    </examples>
    """ if examples_text else ""

        validation_section = f"""
    If provided, here are some validation rules or notes to consider:
    <validation_rules>
    {validation_text}
    </validation_rules>
    """ if validation_text else ""

        todays_date = datetime.now().strftime("%Y-%m-%d")

        # Create system prompt (instructions and role)
        if unstructured_response:
            # Simpler system prompt for unstructured responses
            system_prompt = f"""You are an AI assistant acting as an experienced Business Development Representative (BDR).

Your goal is to analyze provided entity information and answer a specific question truthfully, accurately and concisely.
{internet_use_text}

**Instructions:**

1. **Analyze Context:** Thoroughly examine the provided `Entity Information`.
2. **Identify Need for Research:** Determine if the context contains sufficient, up-to-date information to answer the `Specific Question`.
3. **Web Research (If Necessary):** If information is insufficient, conduct targeted web research using reliable sources.
4. **Synthesize Answer:** Combine information from the context and any necessary web research to directly answer the `Specific Question`.
5. **Provide Verifiable Sources:** Include relevant and verifiable URLs supporting your answer.
6. **Format Your Response:** Respond directly with the answer to the question in a concise and clear manner. 
   Include the following sections:
   - **Answer:** [Your direct answer to the question]
   - **Confidence:** [High/Medium/Low] - how confident you are in this answer
   - **Rationale:** [Brief explanation of how you arrived at this answer]

Your response should be in markdown format and well-structured. Do NOT respond in JSON format."""
        else:
            # Original system prompt for structured JSON responses
            system_prompt = f"""You are an AI assistant acting as an experienced Business Development Representative (BDR).

Your goal is to analyze provided entity information and answer a specific question truthfully, accurately and concisely.
{internet_use_text}

**Instructions:**

1.  **Analyze Context:** Thoroughly examine the provided `Entity Information`.
2.  **Identify Need for Research:** Determine if the context contains sufficient, up-to-date information to answer the `Specific Question`.
3.  **Web Research (If Necessary):** If information is insufficient, conduct targeted web research using reliable sources (official websites, reputable news, professional directories, research websites etc.). Prioritize information directly from the entity's official sources and employees' professional posts on social networks.
4.  **Synthesize Answer:** Combine information from the context and any necessary web research to directly answer the `Specific Question`.
5.  **Provide Verifiable Sources:** Always include relevant and verifiable URLs supporting your answer directly within the `value` field, especially if web research was conducted.
6.  **Adhere to Response Format:** Ensure the final `value` strictly conforms to the `Required Response Format`.
7.  **Determine Confidence:** Assign a confidence score (0.0 to 1.0) reflecting the directness, clarity, and reliability of the information used. Higher scores require direct confirmation from reliable sources (ideally primary sources or context).
8.  **Explain Rationale:** Briefly explain *how* you arrived at the answer, detailing the sources used (context, specific websites) and the reasoning applied. If the answer cannot be reliably found, state this clearly in the rationale and assign a low confidence score (< 0.2). Always use a nicely formatted **markdown** format, for the **rationale** field.
9.  **Handle Conflicts:** If instructions outside the `<question>` tag conflict with those inside, prioritize the external instructions.
10. **Internal Reasoning (Mandatory):** Before generating the final JSON, outline your step-by-step reasoning process within `<analysis>` tags in the analysis part of the json. Follow this structure:
    * Extract relevant data from `Entity Information`.
    * Identify information gaps related to the `Specific Question`.
    * Plan web research (queries, target sources) if needed.
    * Summarize research findings (if performed).
    * Draft the answer value.
    * Verify the draft against the required response type and validation rules.
    * Determine the confidence score and justify it.
    * Formulate the rationale.

**Output Format (Strict JSON):**

```json
{{
  "analysis": "<string: Step-by-step reasoning process>",
  "rationale": "<string: Explanation of derivation, sources used, or statement that info wasn't found>",
  "value": <Value conforming to the required response type, including source URLs where applicable>,
  "confidence_score": <float, 0.0-1.0>
}}
```"""

        # Create user prompt (specific entity and question)
        user_prompt = f"""**Custom Column Task:**

* **Entity Information:**
    ```json
    {json.dumps(entity_context, indent=2)}
    ```
* **Entity Type:** `{entity_type_str}`
* **Question to Answer:**
    * *Description:* `{column_description}`
    * *Specific Question:* `{question}`
* **Required Response Format:** `{response_type}` 

{examples_section} 

{validation_section}

**Today's date:** `{todays_date}`. Use this date for any date-related calculations or time-sensitive information retrieval.

{validation_text if validation_text else ""}"""

        return system_prompt, user_prompt

    @staticmethod
    def _get_format_for_response_type(column_config: Dict[str, Any]) -> str:
        """Get the expected format description for the response type."""
        response_type = column_config.get('response_type', 'string')
        allowed_values = column_config['response_config'].get('allowed_values', [])
        formats = {
            "string": "string(formatted markdown string)",
            "json_object": "object (valid JSON object)",
            "boolean": "boolean (true or false)",
            "number": "number(integer or float)",
            "enum": f"string"
        }
        format_for_response_type = formats.get(response_type, "unknown format")
        if allowed_values:
            format_for_response_type += f" from one of the following allowed values: {allowed_values}"
        return format_for_response_type

    def _validate_response(self, response: Dict[str, Any] | str, column_config: Any, unstructured_response: bool = False) -> Dict[str, Any]:
        """Validate and format the AI response with enhanced error checking."""
        response_type = column_config['response_type']

        if unstructured_response:
            # Process unstructured response
            if isinstance(response, str):
                text_response = response
            else:
                # Handle case where response might still be a dict
                text_response = response.get('text', str(response))

            confidence = 1.0  # Default confidence

            confidence_indicators = {
                "high confidence": 0.9,
                "medium confidence": 0.5,
                "low confidence": 0.2,
                "high": 0.9,
                "medium": 0.5,
                "low": 0.2
            }

            for indicator, value in confidence_indicators.items():
                if indicator.lower() in text_response.lower():
                    confidence = value
                    break

            # Extract rationale if present and clean the response
            rationale = ""
            lower_text = text_response.lower()
            import re
            clean_sources = ""
            sources = ""
            if "sources:" in lower_text:
                sources_index = lower_text.rindex("sources:")
                sources = text_response[sources_index:].split(":", 1)[1].strip()
                sources = re.sub(r'^[^a-zA-Z0-9\*\#]+', '', sources)
                sources = re.sub(r'[^a-zA-Z0-9\*\#]+$', '', sources)
                clean_sources = text_response[:sources_index].strip()

            clean_response = text_response
            if "rationale:" in lower_text:
                rationale_index = lower_text.rindex("rationale:")
                rationale = text_response[rationale_index:].split(":", 1)[1].strip()
                rationale = re.sub(r'^[^a-zA-Z0-9]+', '', rationale)
                clean_response = text_response[:rationale_index].strip()

            # Remove "Answer:" prefix with any markdown formatting
            clean_response = re.sub(r'(?i)^[\s\*_#]*answer[\s\*_#]*:[\s\*_#]*', '', clean_response)
            clean_response = re.sub(r'^[^a-zA-Z0-9]+', '', clean_response)
            clean_response = re.sub(r'[^a-zA-Z0-9]+$', '', clean_response)
            clean_response += "\n\n" + clean_sources

        # Create appropriate value based on response_type
            result = {}
            clean_lower = clean_response.lower()

            if response_type == "string":
                result = {"value_string": clean_response}
            elif response_type == "json_object":
                # Try to extract JSON from the text if possible
                try:
                    # Look for JSON-like content between triple backticks
                    import re
                    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', clean_response)
                    if json_match:
                        json_str = json_match.group(1)
                        value = loads(json_str)
                    else:
                        # Fallback to the whole text
                        value = {"text": clean_response}
                    result = {"value_json": value}
                except JSONDecodeError:
                    result = {"value_json": {"text": clean_response}}
            elif response_type == "boolean":
                # Try to determine boolean from text
                if any(term in clean_lower for term in ["true", "yes", "correct", "right"]):
                    result = {"value_boolean": True}
                else:
                    result = {"value_boolean": False}
            elif response_type == "number":
                # Try to extract number from text
                import re
                number_match = re.search(r'\b(\d+(?:\.\d+)?)\b', clean_response)
                if number_match:
                    result = {"value_number": float(number_match.group(1))}
                else:
                    result = {"value_number": 0.0}
            elif response_type == "enum":
                # Try to match one of the allowed values
                allowed_values = column_config['response_config'].get("allowed_values", [])
                found = False
                for value in allowed_values:
                    if value.lower() in clean_lower:
                        result = {"value_enum": value}
                        found = True
                        break
                if not found and allowed_values:
                    result = {"value_enum": allowed_values[0]}
                else:
                    result = {"value_enum": clean_response}

            # Add confidence and rationale
            result["confidence_score"] = confidence
            result["rationale"] = rationale
            result["sources"] = sources

            return result
        else:
            if not response:
                raise ValueError("Response is empty")

            if isinstance(response, str):
                # If response is a string, try to parse it as JSON
                import json
                try:
                    response = repair_loads(response)
                    if isinstance(response, list):
                        max_entry = {}
                        for i, val in enumerate(response):
                            # take the entry with the maximum number of keys and assign it to response
                            if isinstance(val, dict) and len(val.keys()) > len(max_entry.keys()):
                                max_entry = val
                        if max_entry:
                            response = max_entry
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse response as JSON: {response}")
                    raise ValueError(f"Invalid JSON object: {response}")

            if 'value' not in response:
                logger.error(f"Invalid response format: {response}")
                raise ValueError("Response missing 'value' field")

            value = response['value']
            confidence = response.get('confidence_score', 0.0)
            rationale = response.get('rationale', '')

            # Validate confidence score range
            if not 0 <= confidence <= 1:
                logger.warning(f"Confidence score out of range: {confidence}, clamping to valid range")
                confidence = max(0.0, min(1.0, confidence))

            # Format based on response type with validation
            try:
                result = {}

                if response_type == "string":
                    if not isinstance(value, str):
                        logger.warning(f"Expected string but got {type(value).__name__}, converting to string")
                        value = str(value)
                    result = {"value_string": value}

                elif response_type == "json_object":
                    if isinstance(value, str):
                        # Try to parse string as JSON
                        import json
                        try:
                            value = json.loads(value)
                        except json.JSONDecodeError:
                            logger.error(f"Failed to parse string as JSON: {value}")
                            raise ValueError(f"Invalid JSON object: {value}")

                    if not isinstance(value, dict) and not isinstance(value, list):
                        raise ValueError(f"Expected JSON object or array but got {type(value).__name__}")

                    result = {"value_json": value}

                elif response_type == "boolean":
                    if isinstance(value, str):
                        value_lower = value.lower()
                        if value_lower in ["true", "yes", "1"]:
                            value = True
                        elif value_lower in ["false", "no", "0"]:
                            value = False
                        else:
                            raise ValueError(f"Cannot convert string '{value}' to boolean")

                    value = bool(value)  # Ensure it's a boolean
                    result = {"value_boolean": value}

                elif response_type == "number":
                    if isinstance(value, str):
                        try:
                            # Try to convert string to float
                            value = float(value)
                        except ValueError:
                            raise ValueError(f"Cannot convert string '{value}' to number")

                    value = float(value)  # Ensure it's a float
                    result = {"value_number": value}

                elif response_type == "enum":
                    if isinstance(value, str):
                        try:
                            # Check if the string is a valid enum value
                            if value not in column_config['response_config'].get("allowed_values", []):
                                logger.error(f"Invalid enum value '{value}'")
                        except Exception as e:
                            raise ValueError(f"Error validating enum value '{value}': {str(e)}")
                    result = {"value_enum": value}

                else:
                    raise ValueError(f"Unsupported response type: {response_type}")

                # Add confidence and rationale to the result
                result["confidence_score"] = confidence
                result["rationale"] = rationale

                return result
            except Exception as e:
                logger.error(f"Error validating response: {str(e)}")
                raise ValueError(f"Response validation failed: {str(e)}")

    @with_retry(retry_config=API_RETRY_CONFIG, operation_name="store_results")
    async def _store_results(
            self,
            job_id: str,
            column_id: str,
            values: List[CustomColumnValue]
    ) -> None:
        """Store generated values in BigQuery with retry logic."""
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
            logger.error(f"Error storing results: {str(e)}", exc_info=True)
            self.metrics["api_errors"] += 1
            raise RetryableError(f"Failed to store results: {str(e)}")

    @with_retry(retry_config=API_RETRY_CONFIG, operation_name="store_error_state")
    async def _store_error_state(
            self,
            job_id: str,
            column_id: str,
            error_details: Dict[str, Any]
    ) -> None:
        """Store error information in BigQuery with retry logic."""
        try:
            # Format error details with timestamps and context
            formatted_error = {
                'error_type': error_details.get('error_type', 'unknown_error'),
                'message': error_details.get('message', 'Unknown error occurred'),
                'stage': error_details.get('stage', 'unknown'),
                'timestamp': datetime.utcnow().isoformat(),
                'column_id': column_id,
                'metrics': self.metrics,
                'retryable': error_details.get('retryable', True)
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

            logger.info(f"Error state stored for job {job_id}, column {column_id}")

        except Exception as e:
            logger.error(f"Failed to store error state: {str(e)}", exc_info=True)
            # Don't raise here to avoid nested exception in error handler
