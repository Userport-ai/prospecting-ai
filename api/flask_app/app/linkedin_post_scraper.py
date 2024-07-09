import os
import re
import requests
from datetime import datetime
from typing import Optional, List
from enum import Enum
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator
from utils import Utils
load_dotenv()


class LinkedInPost(BaseModel):
    """LinkedIn Post information.

    Mostly using Fields from Piloterr's API response.

    """

    class Comment(BaseModel):
        class CommentAuthor(BaseModel):
            url: str = Field(...)
            headline: str = Field(...)
            full_name: str = Field(...)
            image_url: Optional[str] = None

        """Comment on a LinkedIn Post."""
        text: str = Field(...)
        author: CommentAuthor = Field(...)

    class PostAuthor(BaseModel):
        """Author of a LinkedIn post."""
        class ProfileType(Enum):
            PERSON = "person"
            ORGANIZATION = "organization"

        url: str = Field(...)
        full_name: str = Field(...)
        image_url: Optional[str] = None
        profile_type: ProfileType = Field(...)

        def is_person(self) -> bool:
            """Returns True if person and false otherwise."""
            return self.profile_type == Author.ProfileType.PERSON

    post_id: str = Field(..., validation_alias="id")
    url: str = Field(...)
    text: str = Field(...)
    author: PostAuthor = Field(...)
    comments: List[Comment] = Field(...)
    hashtags: List[str] = Field(...)
    image_url: Optional[str] = None
    like_count: int = Field(...)
    comments_count: int = Field(...),
    date_published: datetime = Field(...),
    total_engagement: int = Field(...),
    mentioned_profiles: List[str] = Field(...)

    @field_validator('date_published', mode='before')
    @classmethod
    def parse_date_published(cls, v):
        # Convert string to datetime object.
        if not isinstance(v, str):
            raise ValueError(
                f"Expected string for date_published, got type: {type(v)} with value: {v}")

        # Convert to datetime object in UTC timezone.
        return Utils.convert_linkedin_post_time_to_utc(post_time=v)


class LinkedInPostScraper:
    """Python wrapper around Piloterr APIs"""

    PILOTERR_API_KEY = os.getenv("PILOTERR_API_KEY")
    PILOTERR_POST_ENDPOINT = "https://piloterr.com/api/v2/linkedin/post/info"

    @staticmethod
    def fetch_linkedin_post(post_url: str) -> Optional[LinkedInPost]:
        """Fetches and returns LinkedIn post information for given URL.

        Post url must be of this format: https://www.linkedin.com/posts/a2kapur_macro-activity-7150910641900244992-0B5E

        Args:
            post_url [string]: URL of the LinkedIn post.

        Returns:
            Dictionary of LinkedIn Post if found, else None.
        """
        if not LinkedInPostScraper._is_valid_post(post_url):
            raise ValueError(f"Invalid LinkedIn post URL format: {post_url}")

        headers = {
            'Content-Type': 'application/json',
            'x-api-key': LinkedInPostScraper.PILOTERR_API_KEY
        }
        params = {
            'query': LinkedInPostScraper._get_post_id(post_url),
        }
        try:
            response = requests.get(
                LinkedInPostScraper.PILOTERR_POST_ENDPOINT, headers=headers, params=params)
        except Exception as e:
            raise ValueError(f"Failed to fetch post from Piloterr: {e}")

        status_code = response.status_code
        if status_code != 200:
            if status_code == 404:
                # Post not found, return None.
                return None

            raise ValueError(
                f"Got invalid status code: {status_code} when fetching LinkedIn post for url:  {post_url}")

        try:
            data = response.json()
        except Exception as e:
            raise ValueError(
                f"Failed to get JSON response when fetching LinkedIn post for url: {post_url}")

        return LinkedInPost(**data)

    @staticmethod
    def _get_post_id(post_url: str) -> str:
        """Extracts Post ID from given LinkedIn Post URL."""
        match = re.search("activity-(\d+)-", post_url)

        if not match:
            raise ValueError(
                f"Could not find post ID in LinkedIn post URL: {post_url}")
        # Access the captured group and convert to integer
        return match.group(1)

    @staticmethod
    def _is_valid_post(post_url: str) -> bool:
        """Returns true if valid linkedin post and false otherwise."""
        if "linkedin.com/posts" not in post_url or "activity-" not in post_url:
            raise False
        return True


if __name__ == "__main__":
    # import json
    # data = None
    # with open("../example_linkedin_posts/post_1.json", "r") as f:
    #     data = f.read()

    # post_data = json.loads(data)
    # lpost = LinkedInPost(**post_data)
    # print(lpost)

    # post_url = 'https://www.linkedin.com/posts/a2kapur_macro-activity-7150910641900244992-0B5E'
    # post_url = 'https://www.linkedin.com/posts/aniket-bajpai_forbes30under30-forbesunder30-growth-activity-7064856579463942144-RptV'
    # post_url = 'https://www.linkedin.com/posts/plaid-_were-with-plaids-ceo-zachary-perret-on-activity-7207003883506651136-gnif/?t=%7Bseek_to_second_number%7D'
    # post not found.
    # post_url = 'https://www.linkedin.com/posts/plaid-_there-is-still-a-chance-to-catch-up-on-everything-activity-7211762498528555009-vHps/'

    post_url = 'https://www.linkedin.com/posts/a16z_on-this-episode-of-in-the-vault-plaid-ceo-activity-7212156930234941441-6bFX/'
    post_data = LinkedInPostScraper.fetch_linkedin_post(post_url)
    print(post_data)
