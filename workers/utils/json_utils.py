from datetime import datetime


class JSONUtils:
    def serialize_datetime(obj):
        """
        Custom serializer for datetime objects.
        Converts datetime objects to ISO 8601 format.
        """
        if isinstance(obj, datetime):
            return obj.isoformat()
        return obj
