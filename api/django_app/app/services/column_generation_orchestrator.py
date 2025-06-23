"""
Column Generation Orchestration Service.

This service manages the sequential generation of dependent custom columns,
ensuring that columns are generated in the correct order with proper context.
"""

import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from django.utils import timezone
from django.db import transaction
from django.db.models import Q

from app.models.custom_column import CustomColumn, CustomColumnDependency
from app.services.dependency_graph_service import DependencyGraphService
from app.models.common import BaseMixin  # For generating unique IDs
from app.utils.custom_column_utils import (
    get_entity_context_data, get_column_config, trigger_custom_column_generation
)
from app.services.worker_service import WorkerService
from app.models import Lead, Account

logger = logging.getLogger(__name__)


class ColumnGenerationOrchestrator:
    """
    Service for orchestrating the generation of dependent custom columns.
    
    This orchestrator ensures that columns are generated in the correct order,
    waiting for dependencies to complete before starting dependent columns.
    """
    
    @classmethod
    def start_orchestrated_generation(
        cls,
        tenant_id: str,
        entity_ids: List[str],
        column_ids: Optional[List[str]] = None,
        entity_type: Optional[str] = None,
        batch_size: int = 1
    ) -> Dict[str, Any]:
        """
        Start the orchestrated generation of custom columns.
        
        Args:
            tenant_id: The tenant ID
            entity_ids: List of entity IDs to process
            column_ids: Optional list of specific column IDs to generate (if None, uses all active columns)
            entity_type: Either 'lead' or 'account' (required if column_ids not provided)
            batch_size: Number of entities to process in each batch
            
        Returns:
            Dictionary with orchestration information
        """
        # Create a unique orchestration ID
        orchestration_id = str(uuid.uuid4())

        logger.debug(f"Starting orchestrated generation {orchestration_id} for columns: {column_ids} ")
        # Get columns to generate
        if column_ids:
            columns = CustomColumn.objects.filter(
                id__in=column_ids,
                tenant_id=tenant_id
            )
        elif entity_type:
            columns = CustomColumn.objects.filter(
                tenant_id=tenant_id,
                entity_type=entity_type,
                is_active=True,
                deleted_at__isnull=True
            )
        else:
            logger.error("Either column_ids or entity_type must be provided")
            return {
                "error": "Either column_ids or entity_type must be provided",
                "orchestration_id": orchestration_id,
                "status": "failed"
            }
            
        if not columns.exists():
            logger.warning(f"No columns found for orchestration")
            return {
                "message": "No columns found to generate",
                "orchestration_id": orchestration_id,
                "status": "completed"
            }
            
        # Sort columns by dependencies
        try:
            column_list = list(columns)
            sorted_columns = cls._sort_columns_by_dependencies(column_list)
            
            logger.info(f"Sorted {len(sorted_columns)} columns for orchestrated generation, {sorted_columns}")
            
            # Start the first column in the chain
            if sorted_columns:
                first_column = sorted_columns[0]
                remaining_columns = sorted_columns[1:]
                
                # Generate the first column
                result = cls._generate_column(
                    tenant_id=tenant_id,
                    column=first_column,
                    entity_ids=entity_ids,
                    batch_size=batch_size,
                    orchestration_id=orchestration_id,
                    next_columns=remaining_columns
                )
                
                return {
                    "orchestration_id": orchestration_id,
                    "status": "started",
                    "columns_count": len(sorted_columns),
                    "first_column": str(first_column.id),
                    "first_job_id": result.get("job_id"),
                    "message": f"Started orchestrated generation of {len(sorted_columns)} columns"
                }
            else:
                return {
                    "orchestration_id": orchestration_id,
                    "status": "completed",
                    "message": "No columns to generate after dependency sorting"
                }
                
        except Exception as e:
            logger.error(f"Error starting orchestrated generation: {str(e)}", exc_info=True)
            return {
                "error": f"Failed to start orchestration: {str(e)}",
                "orchestration_id": orchestration_id,
                "status": "failed"
            }
    
    @classmethod
    def _sort_columns_by_dependencies(cls, columns: List[CustomColumn]) -> List[CustomColumn]:
        """
        Sort columns by dependencies so they can be generated in order.
        
        Args:
            columns: List of CustomColumn objects
            
        Returns:
            Sorted list of CustomColumn objects (dependencies first)
        """
        # Get IDs of all columns
        column_ids = [str(col.id) for col in columns]
        
        try:
            # Use the dependency service to sort the columns
            sorted_ids = DependencyGraphService.topological_sort(column_ids)

            # Create a mapping of ID to column
            id_to_column = {str(col.id): col for col in columns}
            
            # Return columns in sorted order
            return [id_to_column[col_id] for col_id in sorted_ids]
            
        except ValueError as e:
            # If there's a cycle in the dependencies, log it and return columns in original order
            logger.error(f"Error sorting columns by dependencies: {str(e)}")
            return columns
    
    @classmethod
    def _generate_column(
        cls,
        tenant_id: str,
        column: CustomColumn,
        entity_ids: List[str],
        batch_size: int,
        orchestration_id: str,
        next_columns: List[CustomColumn] = None
    ) -> Dict[str, Any]:
        """
        Generate values for a specific column.
        
        Args:
            tenant_id: The tenant ID
            column: The CustomColumn to generate values for
            entity_ids: List of entity IDs to process
            batch_size: Number of entities to process in each batch
            orchestration_id: ID of the orchestration process
            next_columns: List of columns to generate after this one
            
        Returns:
            Dictionary with generation job information
        """
        try:
            # Create a request ID and job ID
            request_id = str(uuid.uuid4())
            job_id = str(uuid.uuid4())
            
            # Get context data for the column
            context_data = get_entity_context_data(tenant_id, column, entity_ids)
            
            # Get the column configuration
            column_config = get_column_config(column)
            
            # Create the payload with orchestration information
            payload = {
                "column_id": str(column.id),
                "entity_ids": entity_ids,
                "column_config": column_config,
                "context_data": context_data,
                "tenant_id": tenant_id,
                "batch_size": batch_size,
                "job_id": job_id,
                "concurrent_requests": 5,
                "request_id": request_id,
                "orchestration_id": orchestration_id,
                "orchestration_data": {
                    "next_columns": [str(col.id) for col in (next_columns or [])],
                    "entity_ids": entity_ids,
                    "batch_size": batch_size,
                    "tenant_id": tenant_id,
                }
            }
            
            # If AI config is present, include it
            if column.ai_config:
                payload["ai_config"] = column.ai_config
                
            # Trigger the worker service
            worker_service = WorkerService()
            response = worker_service.trigger_custom_column_generation(payload)
            
            logger.info(f"Started generation for column {column.id} with job {job_id}")
            
            return {
                "column_id": str(column.id),
                "job_id": response.get("job_id", job_id),
                "request_id": request_id,
                "entity_count": len(entity_ids),
                "next_columns_count": len(next_columns) if next_columns else 0
            }
            
        except Exception as e:
            logger.error(f"Error generating column {column.id}: {str(e)}", exc_info=True)
            return {
                "error": f"Failed to generate column {column.id}: {str(e)}",
                "column_id": str(column.id),
                "status": "failed"
            }
    
    @classmethod
    async def handle_column_completion(
        cls,
        orchestration_id: str,
        column_id: str,
        status: str,
        entity_ids: List[str],
        batch_size: int,
        next_column_ids: List[str]
    ) -> Dict[str, Any]:
        """
        Handle the completion of a column generation and trigger the next one if needed.
        
        Args:
            orchestration_id: ID of the orchestration process
            column_id: ID of the completed column
            status: Status of the completed job (completed, failed, etc.)
            entity_ids: List of entity IDs that were processed
            batch_size: Batch size used for processing
            next_column_ids: IDs of columns to generate next
            
        Returns:
            Dictionary with information about the next step
        """
        logger.info(f"Handling completion of column {column_id} in orchestration {orchestration_id}")
        
        # If the generation failed, log it and stop the orchestration
        if status != 'completed':
            logger.error(f"Column {column_id} generation failed with status {status}")
            return {
                "orchestration_id": orchestration_id,
                "status": "failed",
                "message": f"Column {column_id} generation failed with status {status}"
            }
            
        # If there are no more columns to generate, the orchestration is complete
        if not next_column_ids:
            logger.info(f"Orchestration {orchestration_id} completed successfully")
            return {
                "orchestration_id": orchestration_id,
                "status": "completed",
                "message": "All columns generated successfully"
            }
            
        # Get the next column
        next_column_id = next_column_ids[0]
        remaining_column_ids = next_column_ids[1:]
        
        try:
            # Get the next column
            next_column = CustomColumn.objects.get(id=next_column_id)
            
            # Generate the next column
            result = cls._generate_column(
                tenant_id=next_column.tenant_id,
                column=next_column,
                entity_ids=entity_ids,
                batch_size=batch_size,
                orchestration_id=orchestration_id,
                next_columns=[CustomColumn.objects.get(id=col_id) for col_id in remaining_column_ids]
            )
            
            return {
                "orchestration_id": orchestration_id,
                "status": "in_progress",
                "next_column": next_column_id,
                "next_job_id": result.get("job_id"),
                "remaining_columns": len(remaining_column_ids),
                "message": f"Started generation of next column {next_column_id}"
            }
            
        except Exception as e:
            logger.error(f"Error triggering next column {next_column_id}: {str(e)}", exc_info=True)
            return {
                "orchestration_id": orchestration_id,
                "status": "failed",
                "error": f"Failed to trigger next column {next_column_id}: {str(e)}"
            }