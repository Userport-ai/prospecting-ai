# /app/utils/serialization.py
"""
Utility functions for serializers.

This module provides reusable functions for handling custom column values
in serializers.
"""

import datetime
from typing import Any, Dict

from app.models.custom_column import CustomColumn


def get_custom_column_values(obj):
    """
    Extracts custom column values from an entity (Account or Lead).
    Returns all valid custom columns with values where available, and null values for columns
    that don't have values. This ensures the frontend can render all available columns.

    Args:
        obj: The model instance (Account or Lead)

    Returns:
        Dict with column_id as key and column data as values, including empty ones
    """

    result = {}
    tenant_id = obj.tenant_id

    # Determine entity type
    if obj.__class__.__name__ == 'Account':
        entity_type = CustomColumn.EntityType.ACCOUNT
        from app.models.custom_column import AccountCustomColumnValue as ColumnValueModel
    else:  # Lead
        entity_type = CustomColumn.EntityType.LEAD
        from app.models.custom_column import LeadCustomColumnValue as ColumnValueModel

    # Get all active custom columns for this entity type and tenant
    columns = CustomColumn.objects.filter(
        tenant_id=tenant_id,
        entity_type=entity_type,
        is_active=True,
        deleted_at__isnull=True
    )

    # Process all columns (with or without values)
    for column in columns:
        column_data = {
            'id': str(column.id),
            'name': column.name,
            'description': column.description or '',
            'response_type': column.response_type,
            'value': None  # Default to None
        }

        # Add to result dict immediately
        result[str(column.id)] = column_data

    # Now get the values that exist and update the result
    # Check if we have prefetched values
    prefetched_values = getattr(obj, 'prefetched_custom_column_values', None)

    if prefetched_values:
        # Use prefetched values if available
        values = prefetched_values
    else:
        # Fall back to related manager if prefetched values not available
        values = obj.custom_column_values.filter(
            status='completed',
            column__deleted_at__isnull=True,
        ).select_related('column')

    # Update the result with actual values where they exist
    for value in values:
        column_id = str(value.column.id)

        # Skip if the column isn't in our results (should never happen, but just in case)
        if column_id not in result:
            continue

        # Extract the value based on column type
        if value.value_string is not None:
            result[column_id]['value'] = value.value_string
        elif value.value_number is not None:
            result[column_id]['value'] = value.value_number
        elif value.value_boolean is not None:
            result[column_id]['value'] = value.value_boolean
        elif value.value_json is not None:
            result[column_id]['value'] = value.value_json

    return result


def convert_datetimes_to_isoformat(data: Any) -> Any:
    """
    Recursively converts all datetime objects to ISO format strings.

    Args:
        data: Any data structure that might contain datetime objects

    Returns:
        The same data structure with datetime objects converted to strings
    """
    import datetime

    if isinstance(data, datetime.datetime):
        return data.isoformat()
    elif isinstance(data, dict):
        return {k: convert_datetimes_to_isoformat(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [convert_datetimes_to_isoformat(item) for item in data]
    elif isinstance(data, tuple):
        return tuple(convert_datetimes_to_isoformat(item) for item in data)
    else:
        return data
