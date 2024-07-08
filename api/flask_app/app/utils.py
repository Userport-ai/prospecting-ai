from datetime import datetime, timezone


class Utils:
    """Class with common utility functions."""

    @staticmethod
    def convert_linkedin_post_time_to_utc(post_time: str) -> datetime:
        """Converts LinkedIn Post publish time string to a dateimte object in UTC timezone.

        We return UTC timezone because MongoDB stores datetime objects in UTC timezone, so we want to be
        consisent per https://www.mongodb.com/docs/languages/python/pymongo-driver/current/data-formats/dates-and-times/.

        Since we are using Python 3.9.1, it is not handled by default, we need
        to do some processing.

        Answer taken from https://stackoverflow.com/questions/127803/how-do-i-parse-an-iso-8601-formatted-date-and-time.

        Returns:
            datetime object in UTC timezone.
        """
        return datetime.fromisoformat(post_time.replace('Z', '+00:00')).astimezone(timezone.utc)


if __name__ == "__main__":
    # UTC time
    post_time: str = "2024-06-27T18:16:47.537Z"

    # UTC+05:30 time.
    # post_time: str = "2023-06-20T12:30:45+05:30"
    dt = Utils.convert_linkedin_post_time_to_utc(post_time)
    print(dt.tzinfo)
