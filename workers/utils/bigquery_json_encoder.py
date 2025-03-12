import json
from datetime import datetime, date
from enum import Enum
from typing import Any
from utils.loguru_setup import logger



class BigQueryJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle datetime, date, enum, and other special types."""

    def default(self, obj: Any) -> Any:
        # Handle datetime objects
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()

        # Handle Enum objects
        if isinstance(obj, Enum):
            return obj.value

        # Handle sets by converting to list
        if isinstance(obj, set):
            return list(obj)

        # Handle bytes by decoding to string
        if isinstance(obj, bytes):
            return obj.decode('utf-8')

        # Let the base class handle anything we don't explicitly handle
        return super().default(obj)

def safe_json_dumps(obj: Any, **kwargs) -> str:
    """
    Safely convert object to JSON string, handling special types.

    Args:
        obj: The object to serialize
        **kwargs: Additional arguments to pass to json.dumps()

    Returns:
        str: JSON string representation of the object
    """
    try:
        return json.dumps(obj, cls=BigQueryJSONEncoder, **kwargs)
    except (TypeError, ValueError) as e:
        logger.warning(f"Error in JSON serialization: {str(e)}")
        return json.dumps({"error": "Data serialization failed", "original_error": str(e)})
