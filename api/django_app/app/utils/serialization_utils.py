# /app/utils/serialization.py
"""
Utility functions for serializers.

This module provides reusable functions for handling custom column values
in serializers.
"""

import datetime
from typing import Any, Dict

from app.models.custom_column import CustomColumn


def get_custom_column_values(obj: Any, values_attr: str = 'prefetched_custom_column_values') -> Dict[str, Dict[str, Any]]:
    """
    Format custom column values for an entity in a standardized way.

    Args:
        obj: The entity object (lead or account)
        values_attr: The attribute name containing the values (default: 'prefetched_custom_column_values')

    Returns:
        dict: Dictionary of formatted custom column values
    """
    # Get values, either prefetched or from related manager
    values = getattr(obj, values_attr, None)
    if values is None and hasattr(obj, 'custom_column_values'):
        # Fall back to related manager if prefetched values not available
        values = obj.custom_column_values.filter(
            status='completed'
        ).select_related('column')

    result = {}
    for value in values:
        # Determine which value field to use based on column's response_type
        if value.column.response_type == CustomColumn.ResponseType.STRING:
            val = value.value_string
        elif value.column.response_type == CustomColumn.ResponseType.JSON_OBJECT:
            val = value.value_json
        elif value.column.response_type == CustomColumn.ResponseType.BOOLEAN:
            val = value.value_boolean
        elif value.column.response_type == CustomColumn.ResponseType.NUMBER:
            val = value.value_number
        elif value.column.response_type == CustomColumn.ResponseType.ENUM:
            val = value.value_string
        else:
            val = None

        result[str(value.column_id)] = {
            'name': value.column.name,
            'description': value.column.description,
            'question': value.column.question,
            'value': val,
            'confidence': value.confidence_score,
            'rationale': value.rationale,
            'generated_at': value.generated_at.isoformat() if value.generated_at else None,
            'response_type': value.column.response_type
        }

    return result
def convert_datetimes_to_isoformat(obj):
    """
    Recursively traverses an object (dict, list) and converts
    datetime.datetime objects to ISO 8601 string format.
    Returns a new object with datetimes converted.
    """
    if isinstance(obj, dict):
        # Create a new dict to avoid modifying the original in place
        new_dict = {}
        for k, v in obj.items():
            new_dict[k] = convert_datetimes_to_isoformat(v)
        return new_dict
    elif isinstance(obj, list):
        # Create a new list
        new_list = []
        for item in obj:
            new_list.append(convert_datetimes_to_isoformat(item))
        return new_list
    elif isinstance(obj, datetime.datetime):
        # Convert datetime to ISO 8601 string format
        # Using timespec='microseconds' ensures precision if needed,
        # remove it if milliseconds or seconds are sufficient.
        # .isoformat() automatically includes timezone if present (like yours).
        return obj.isoformat(timespec='microseconds')
    else:
        # Return the object unchanged if it's not a dict, list, or datetime
        return obj