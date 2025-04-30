from django.db import transaction
from django.utils import timezone
from app.models import Account
from app.models.custom_column import (
    CustomColumn, LeadCustomColumnValue, AccountCustomColumnValue
)
import logging
import json
import asyncio
from django.db.models import Count
from app.services.column_generation_orchestrator import ColumnGenerationOrchestrator

logger = logging.getLogger(__name__)


class CustomColumnCallbackHandler:
    """Handler for custom column generation callbacks."""

    @classmethod
    def handle_callback(cls, data):
        """Process custom column callback data."""
        try:
            # Extract core data
            job_id = data.get('job_id')
            account_id = data.get('account_id')
            status = data.get('status')
            processed_data = data.get('processed_data', {})
            values = processed_data.get('values', [])
            completion_percentage = data.get('completion_percentage', 0)

            # Check for orchestration data
            orchestration_data = data.get('orchestration_data', {})
            logger.debug(f"Orchestration data: {orchestration_data}, status: {status}")
            column_id = values[0].get('column_id') if values else None # Get column_id from the first value
            # If this is a completion callback and has orchestration data, handle next steps
            if status == 'completed' and orchestration_data :
                logger.info(f"Handling completed column {column_id} with orchestration data")

                # Extract orchestration data
                next_column_ids = orchestration_data.get('next_columns', [])
                entity_ids = orchestration_data.get('entity_ids', [])
                batch_size = orchestration_data.get('batch_size', 10)
                tenant_id = orchestration_data.get('tenant_id')

                # If there are next columns to process, trigger them
                if next_column_ids and entity_ids and tenant_id:
                    try:
                        logger.info(f"Triggering next column {next_column_ids[0]} in orchestration")

                        # Process the next column in the orchestration chain
                        from app.utils.custom_column_utils import trigger_custom_column_generation

                        # Trigger the next column
                        next_column_id = next_column_ids[0]
                        remaining_column_ids = next_column_ids[1:]

                        # Create orchestration data for the next column
                        next_orchestration_data = {
                            'next_columns': remaining_column_ids,
                            'entity_ids': entity_ids,
                            'batch_size': batch_size,
                            'tenant_id': tenant_id
                        }

                        # Trigger the next column with updated orchestration data
                        trigger_custom_column_generation(
                            tenant_id=tenant_id,
                            column_id=next_column_id,
                            entity_ids=entity_ids,
                            batch_size=batch_size,
                            orchestration_data=next_orchestration_data
                        )

                        logger.info(f"Successfully triggered next column {next_column_id} in orchestration")
                    except Exception as e:
                        logger.error(f"Error triggering next column in orchestration: {str(e)}", exc_info=True)

            # Log the callback
            logger.info(
                f"Received custom column callback: job_id={job_id}, status={status}, "
                f"values_count={len(values)}, completion_percentage={completion_percentage}"
            )

            # Validate required fields
            if not all([job_id, account_id, status]):
                logger.error(f"Missing required fields in callback: {data}")
                return False

            # Handle progress updates without values - these are just informational
            if status == 'processing' and not values:
                logger.info(f"Processing progress update: {completion_percentage}% complete")

                # If we have a column_id in the processed_data, update that column's timestamp
                if column_id:
                    try:
                        column = CustomColumn.objects.get(id=column_id)
                        column.last_refresh = timezone.now()
                        column.save(update_fields=['last_refresh', 'updated_at'])
                        logger.info(f"Updated last_refresh for column {column_id} for progress update")
                    except CustomColumn.DoesNotExist:
                        logger.warning(f"Column {column_id} not found for progress update")
                        pass  # Continue anyway

                return True  # Successfully processed the progress update

            # If there are no values but status is not 'processing', only log a warning
            if not values and status != 'completed':
                logger.warning(f"No values provided in callback with status '{status}': {data}")
                # Still return success to avoid retries for empty but valid callbacks
                return True

            # For callbacks with values, continue normal processing
            # Group values by column_id
            values_by_column = {}
            for value in values:
                column_id = value.get('column_id')
                if not column_id:
                    logger.warning(f"Missing column_id in value data: {value}")
                    continue
                if column_id not in values_by_column:
                    values_by_column[column_id] = []
                values_by_column[column_id].append(value)

            # If we have grouped values, process them
            if values_by_column:
                with transaction.atomic():
                    # Get account with lock to prevent race conditions

                    # Get all referenced columns
                    column_ids = list(values_by_column.keys())
                    columns = {
                        str(col.id): col for col in CustomColumn.objects.filter(id__in=column_ids)
                    }

                    # Check if all columns were found
                    missing_columns = set(column_ids) - set(columns.keys())
                    if missing_columns:
                        logger.error(f"Custom columns not found: {missing_columns}")
                        # Continue with available columns rather than failing completely

                    # Process each column's values
                    for column_id, column_values in values_by_column.items():
                        if column_id not in columns:
                            logger.warning(f"Skipping values for missing column {column_id}")
                            continue

                        column = columns[column_id]

                        # Just process values immediately without any tracking
                        cls._process_values_batch(
                            column=column,
                            values=column_values,
                            entity_type=column.entity_type
                        )

                        # Update the column's last_refresh timestamp
                        column.last_refresh = timezone.now()
                        column.save(update_fields=['last_refresh', 'updated_at'])

            return True

        except Exception as e:
            logger.error(f"Error handling custom column callback: {str(e)}", exc_info=True)
            return False

    @classmethod
    def _process_values_batch(cls, column, values, entity_type):
        """Process a batch of values from a callback."""
        if not values:
            return

        logger.info(f"Processing {len(values)} values for column {column.id} (entity_type: {entity_type})")

        for value_data in values:
            entity_id = value_data.get('entity_id')
            if not entity_id:
                logger.warning(f"Missing entity_id in value data: {value_data}")
                continue

            # Get the value status from the data
            if entity_type == CustomColumn.EntityType.LEAD:
                status_enum = LeadCustomColumnValue.Status
            else:
                status_enum = AccountCustomColumnValue.Status

            status = value_data.get('status', status_enum.COMPLETED)

            try:
                if entity_type == CustomColumn.EntityType.LEAD:
                    cls._update_lead_value(column, entity_id, value_data, status)
                else:
                    cls._update_account_value(column, entity_id, value_data, status)
            except Exception as e:
                logger.error(
                    f"Error updating {entity_type} column value for {entity_id}: {str(e)}",
                    exc_info=True
                )

    @classmethod
    def _update_lead_value(cls, column, lead_id, value_data, status):
        """Update a lead custom column value."""
        # Get the appropriate value field based on response type
        value_fields = cls._get_value_fields(column.response_type, value_data)

        # Update the lead custom column value
        LeadCustomColumnValue.objects.update_or_create(
            column=column,
            lead_id=lead_id,
            defaults={
                'tenant': column.tenant,
                **value_fields,
                'confidence_score': value_data.get('confidence_score'),
                'raw_response': value_data.get('raw_response'),
                'generation_metadata': value_data.get('generation_metadata'),
                'error_details': value_data.get('error_details'),
                'status': status
            }
        )

    @classmethod
    def _update_account_value(cls, column, account_id, value_data, status):
        """Update an account custom column value."""
        # Get the appropriate value field based on response type
        value_fields = cls._get_value_fields(column.response_type, value_data)

        # Update the account custom column value
        AccountCustomColumnValue.objects.update_or_create(
            column=column,
            account_id=account_id,
            defaults={
                'tenant': column.tenant,
                **value_fields,
                'confidence_score': value_data.get('confidence_score'),
                'raw_response': value_data.get('raw_response'),
                'generation_metadata': value_data.get('generation_metadata'),
                'error_details': value_data.get('error_details'),
                'status': status
            }
        )

    @classmethod
    def _get_value_fields(cls, response_type, value_data):
        """Get the appropriate value field based on response type."""
        value_fields = {
            'value_string': None,
            'value_json': None,
            'value_boolean': None,
            'value_number': None,
            'rationale': value_data.get('rationale')
        }

        # Check for value_enum and map it to value_string for ENUM type
        value_enum = value_data.get('value_enum')
        if value_enum is not None and response_type == CustomColumn.ResponseType.ENUM:
            value_data['value_string'] = value_enum

        if response_type == CustomColumn.ResponseType.STRING:
            value_fields['value_string'] = value_data.get('value_string')
        elif response_type == CustomColumn.ResponseType.JSON_OBJECT:
            value_fields['value_json'] = value_data.get('value_json')
        elif response_type == CustomColumn.ResponseType.BOOLEAN:
            value_fields['value_boolean'] = value_data.get('value_boolean')
        elif response_type == CustomColumn.ResponseType.NUMBER:
            value_fields['value_number'] = value_data.get('value_number')
        elif response_type == CustomColumn.ResponseType.ENUM:
            value_fields['value_string'] = value_data.get('value_string')

        return value_fields
