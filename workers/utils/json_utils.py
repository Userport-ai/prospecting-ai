from datetime import datetime
from utils.loguru_setup import logger


class JSONUtils:
    def serialize_datetime(obj):
        """
        Custom serializer for datetime objects.
        Converts datetime objects to ISO 8601 format.
        """
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} not serializable")
