import re
from datetime import datetime, timezone
import pytz
from typing import Optional, List
import gzip


class Utils:
    """Class with common utility functions."""

    @staticmethod
    def get_first_heading_in_markdown(markdown_text: str, level: int = 1) -> Optional[str]:
        """Returns first heading of given level (1 = h1, 2= h2 and so on) from given markdown text. If no heading found, returns None.

        We use our own regex for headings because MarkdownHeaderTextSplitter doesn't detect headings accurately all the time.
        """
        header = "#" * level
        # H1 pattern
        pattern = r'((?<!#)(' + header + r')\s.*)'
        matches = re.findall(pattern, markdown_text, re.MULTILINE)
        if len(matches) == 0:
            return None
        # First group of first match contains the matched string.
        return matches[0][0]

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

    @staticmethod
    def create_utc_datetime(day: int, month: int, year: int) -> datetime:
        """Converts given date to dateimte with UTC timezone."""

        # Create a naive datetime object
        naive_date = datetime(year, month, day)

        # Get the UTC timezone
        utc_timezone = pytz.UTC

        # Localize the naive datetime to UTC
        utc_datetime = utc_timezone.localize(naive_date)

        return utc_datetime

    @staticmethod
    def create_utc_time_now() -> datetime:
        """Returns UTC time now."""
        return datetime.now(pytz.UTC)

    @staticmethod
    def to_human_readable_date_str(dt: datetime) -> str:
        """Returns human readable date string."""
        return dt.strftime("%d %B, %Y")

    def load_all_user_agents() -> List[str]:
        """Loads all user agents from file and returns them as a list of strings."""
        all_agents = []
        with gzip.open("app/user_agents.txt.gz", 'rt') as f:
            for line in f.readlines():
                all_agents.append(line.strip())
        return all_agents

    @staticmethod
    def remove_spaces_and_trailing_slashes(url: str) -> str:
        """Helper to remove extra whitespaces (leading or trailing) and trailing slashes in given URL string."""
        return url.strip().rstrip("/")


if __name__ == "__main__":
    # UTC time
    post_time: str = "2024-06-27T18:16:47.537Z"

    # UTC+05:30 time.
    # post_time: str = "2023-06-20T12:30:45+05:30"
    # dt = Utils.convert_linkedin_post_time_to_utc(post_time)
    # print(dt.tzinfo)

    utc_date = Utils.create_utc_datetime(7, 6, 2023)
    print(utc_date.tzinfo)
