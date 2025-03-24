from django.db import transaction
from django.utils import timezone
from app.models import Account
from app.models.custom_column import (
    CustomColumn, LeadCustomColumnValue, AccountCustomColumnValue
)
import logging
import json
from django.db.models import Count

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
            column_id = processed_data.get('column_id')
            request_id = data.get('request_id')

            # Log the callback
            logger.info(
                f"Received custom column callback: job_id={job_id}, status={status}, "
                f"column_id={column_id}, request_id={request_id}"
            )

            # Validate required fields
            if not all([job_id, account_id, status, column_id]):
                logger.error(f"Missing required fields in callback: {data}")
                return False

            with transaction.atomic():
                # Get account with lock to prevent race conditions
                account = Account.objects.select_for_update().get(id=account_id)

                # Get the custom column
                try:
                    column = CustomColumn.objects.select_for_update().get(id=column_id)
                except CustomColumn.DoesNotExist:
                    logger.error(f"Custom column {column_id} not found")
                    return False

                # Check for duplicate request (idempotency)
                if request_id:
                    if cls._is_duplicate_request(column, request_id):
                        logger.info(f"Duplicate request {request_id} - skipping processing")
                        return True

                # Handle pagination
                pagination = data.get('pagination')
                if pagination:
                    current_page = pagination.get('page', 1)
                    total_pages = pagination.get('total_pages', 1)

                    # Track processed pages to prevent duplicates
                    if not cls._should_process_page(column, current_page):
                        logger.info(f"Page {current_page} already processed for column {column_id}")
                        return True

                    # Process this page of values
                    cls._process_values_batch(
                        column=column,
                        values=processed_data.get('values', []),
                        entity_type=column.entity_type
                    )

                    # Update column metadata for pagination tracking
                    if current_page < total_pages:
                        cls._update_column_metadata(
                            column=column,
                            current_page=current_page,
                            processed_count=processed_data.get('processed_count', 0),
                            total_count=processed_data.get('total_count', 0)
                        )
                        return True

                # Handle based on status
                if status == 'processing':
                    cls._handle_processing_update(
                        column=column,
                        values=processed_data.get('values', []),
                        processed_count=processed_data.get('processed_count', 0),
                        total_count=processed_data.get('total_count', 0),
                        completion_percentage=data.get('completion_percentage', 0)
                    )
                elif status == 'completed':
                    cls._handle_completion(
                        column=column,
                        values=processed_data.get('values', [])
                    )
                elif status == 'failed':
                    cls._handle_failure(
                        column=column,
                        error_details=data.get('error_details', {})
                    )

                # Record processed request for idempotency
                if request_id:
                    cls._record_processed_request(column, request_id)

                return True

        except Exception as e:
            logger.error(f"Error handling custom column callback: {str(e)}", exc_info=True)
            return False

    @classmethod
    def _is_duplicate_request(cls, column, request_id):
        """Check if this request has already been processed."""
        # Store processed requests in the column's metadata
        metadata = column.settings or {}
        processed_requests = metadata.get('processed_requests', [])
        return request_id in processed_requests

    @classmethod
    def _record_processed_request(cls, column, request_id):
        """Record this request_id as processed for idempotency."""
        # Update the column's metadata to include this request_id
        metadata = column.settings or {}
        processed_requests = metadata.get('processed_requests', [])
        if request_id not in processed_requests:
            processed_requests.append(request_id)
            metadata['processed_requests'] = processed_requests
            column.settings = metadata
            column.save(update_fields=['settings', 'updated_at'])

    @classmethod
    def _should_process_page(cls, column, page):
        """Check if this page should be processed."""
        # Check the column's metadata for processed pages
        metadata = column.settings or {}
        processed_pages = metadata.get('processed_pages', [])
        return page not in processed_pages

    @classmethod
    def _update_column_metadata(cls, column, current_page, processed_count, total_count):
        """Update the column's metadata for pagination tracking."""
        metadata = column.settings or {}

        # Update processed pages
        processed_pages = metadata.get('processed_pages', [])
        if current_page not in processed_pages:
            processed_pages.append(current_page)

        # Update progress information
        metadata.update({
            'processed_pages': processed_pages,
            'processed_count': processed_count,
            'total_count': total_count,
            'last_update': timezone.now().isoformat()
        })

        # Save the updated metadata
        column.settings = metadata
        column.last_refresh = timezone.now()
        column.save(update_fields=['settings', 'last_refresh', 'updated_at'])

    @classmethod
    def _process_values_batch(cls, column, values, entity_type):
        """Process a batch of values from a callback."""
        if not values:
            return

        for value_data in values:
            entity_id = value_data.get('entity_id')
            if not entity_id:
                logger.warning(f"Missing entity_id in value data: {value_data}")
                continue

            try:
                if entity_type == CustomColumn.EntityType.LEAD:
                    cls._update_lead_value(column, entity_id, value_data)
                else:
                    cls._update_account_value(column, entity_id, value_data)
            except Exception as e:
                logger.error(
                    f"Error updating {entity_type} column value for {entity_id}: {str(e)}",
                    exc_info=True
                )

    @classmethod
    def _update_lead_value(cls, column, lead_id, value_data):
        """Update a lead custom column value."""
        status = value_data.get('status', LeadCustomColumnValue.Status.COMPLETED)

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
    def _update_account_value(cls, column, account_id, value_data):
        """Update an account custom column value."""
        status = value_data.get('status', AccountCustomColumnValue.Status.COMPLETED)

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
            'value_number': None
        }

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

    @classmethod
    def _handle_processing_update(cls, column, values, processed_count, total_count, completion_percentage):
        """Handle a processing update callback."""
        # Update column metadata for progress tracking
        metadata = column.settings or {}
        metadata.update({
            'status': 'processing',
            'processed_count': processed_count,
            'total_count': total_count,
            'completion_percentage': completion_percentage,
            'last_update': timezone.now().isoformat()
        })

        # Save the updated metadata
        column.settings = metadata
        column.last_refresh = timezone.now()
        column.save(update_fields=['settings', 'last_refresh', 'updated_at'])

        # Process any values included in this update
        if values:
            cls._process_values_batch(
                column=column,
                values=values,
                entity_type=column.entity_type
            )

    @classmethod
    def _handle_completion(cls, column, values):
        """Handle a completion callback."""
        # Process all values
        cls._process_values_batch(
            column=column,
            values=values,
            entity_type=column.entity_type
        )

        # Update column metadata
        metadata = column.settings or {}
        metadata.update({
            'status': 'completed',
            'completion_percentage': 100,
            'completed_at': timezone.now().isoformat(),
            'total_values': len(values)
        })

        # Save the updated metadata
        column.settings = metadata
        column.last_refresh = timezone.now()
        column.save(update_fields=['settings', 'last_refresh', 'updated_at'])

        # Log the completion
        logger.info(f"Custom column generation completed for column {column.id} with {len(values)} values")

    @classmethod
    def _handle_failure(cls, column, error_details):
        """Handle a failure callback."""
        # Update column metadata
        metadata = column.settings or {}
        metadata.update({
            'status': 'failed',
            'error_details': error_details,
            'failed_at': timezone.now().isoformat()
        })

        # Save the updated metadata
        column.settings = metadata
        column.last_refresh = timezone.now()
        column.save(update_fields=['settings', 'last_refresh', 'updated_at'])

        # Update any values that are still processing to error status
        if column.entity_type == CustomColumn.EntityType.LEAD:
            LeadCustomColumnValue.objects.filter(
                column=column,
                status=LeadCustomColumnValue.Status.PROCESSING
            ).update(
                status=LeadCustomColumnValue.Status.ERROR,
                error_details=error_details
            )
        else:
            AccountCustomColumnValue.objects.filter(
                column=column,
                status=AccountCustomColumnValue.Status.PROCESSING
            ).update(
                status=AccountCustomColumnValue.Status.ERROR,
                error_details=error_details
            )

        # Log the error
        logger.error(
            f"Custom column generation failed for column {column.id}: "
            f"{error_details.get('message', 'Unknown error')}"
        )