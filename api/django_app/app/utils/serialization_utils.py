# /app/utils/serialization.py
import datetime

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