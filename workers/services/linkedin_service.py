import os
import json
import asyncio
import httpx
from enum import Enum
from typing import Optional, List, Dict
from utils.retry_utils import RetryableError, RetryConfig, with_retry
from utils.loguru_setup import logger
from pydantic import BaseModel, Field


class ActorRunFailed(Exception):
    pass


LINKEDIN_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=20.0,
    retryable_exceptions=[
        RetryableError,
        asyncio.TimeoutError,
        ConnectionError,
        httpx.ConnectTimeout,
        httpx.ConnectError,
        ActorRunFailed
    ]
)


class StartRunResponse(BaseModel):
    """Standard response format of running an Apify Actor."""
    class Status(str, Enum):
        SUCCEEDED = "SUCCEEDED"
        FAILED = "FAILED"

    class RunActorData(BaseModel):
        id: str = Field(..., description="Run ID")
        defaultDatasetId: str = Field(..., description="Dataset ID")
        status: str = Field(..., description="Status of run.")
    data: RunActorData = Field(...)


class LinkedInReaction(BaseModel):
    class Author(BaseModel):
        firstName: Optional[str] = None
        lastName: Optional[str] = None
        headline: Optional[str] = None
        profile_url: Optional[str] = Field(default=None, description="LinkedIn Profile URL of the author")
        profile_picture: Optional[str] = Field(default=None, description="Profile pic URL of the author")

    class PostStats(BaseModel):
        totalReactionCount: Optional[int] = Field(default=None, description="Example: 25")
        like: Optional[int] = Field(default=None, description="Example: 12")
        appreciation: Optional[int] = None
        empathy: Optional[int] = None
        interest: Optional[int] = None
        praise: Optional[int] = None
        comments: Optional[int] = None
        reposts: Optional[int] = None

    class Timestamps(BaseModel):
        date: Optional[str] = Field(default=None, description="Example: 2025-05-06 08:02:30")
        relative: Optional[str] = Field(default=None, description="Example: 1w")
        timestamp: Optional[int] = Field(default=None, description="Example: 1746511350875")

    class Image(BaseModel):
        url: Optional[str] = Field(default=None, description="Image URL")
        width: Optional[int] = Field(default=None, description="Example: 1200")
        height: Optional[int] = Field(default=None, description="Example: 630")

    class Article(BaseModel):
        title: Optional[str] = Field(default=None, description="Article title")
        url: Optional[str] = Field(default=None, description="URL to article")
        source: Optional[str] = Field(default=None, description="Not sure what this is, ex: jamma.it")

    action: Optional[str] = Field(default=None, description="Example: Cristiano Azzolini Di Maggio likes this")
    text: Optional[str] = Field(default=None, description="Main text in the post")
    post_url: Optional[str] = Field(default=None)
    pagination_token: Optional[str] = Field(default=None)
    source_profile: Optional[str] = Field(default=None, description="Lead's LinkedIn profile URL")
    author: Optional[Author] = Field(default=None)
    post_stats: Optional[PostStats] = Field(default=None)
    timestamps: Optional[Timestamps] = Field(default=None)
    images: Optional[List[Image]] = Field(default=None)
    article: Optional[Article] = Field(default=None)


class LinkedInService:
    """Service class for handling LinkedIn for data like posts, comments and reactions."""

    def __init__(self):
        self.APIFY_BASE_URL = "https://api.apify.com/v2/"
        self.apify_api_key = os.getenv('APIFY_API_KEY')
        self.LINKEDIN_REACTIONS_ACTOR_NAME = "apimaestro~linkedin-profile-reactions"
        self.API_TIMEOUT = 30.0  # timeout in seconds.

    @with_retry(retry_config=LINKEDIN_RETRY_CONFIG, operation_name="_fetch_linkedin_reactions")
    async def fetch_reactions(self, lead_linkedin_url: str) -> List[LinkedInReaction]:
        """Fetch LinkedIn Reactions for given Lead's LinkedIn URL."""
        try:
            lead_linkedin_url = lead_linkedin_url.strip("/")
            url_list: List[str] = lead_linkedin_url.split("/in/")
            if len(url_list) != 2:
                raise ValueError(f"Invalid lead LinkedIn URL format : {lead_linkedin_url}")
            lead_username = url_list[1]

            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Authorization': f'Bearer {self.apify_api_key}'
            }

            async with httpx.AsyncClient() as client:
                logger.debug(f"Triggering LinkedIn Reactions Actor Run for Lead URL: {lead_linkedin_url}")
                data = {"username": lead_username}
                json_data = json.dumps(data)
                endpoint = f"{self.APIFY_BASE_URL}acts/{self.LINKEDIN_REACTIONS_ACTOR_NAME}/runs"
                logger.debug(f"json data: {json_data}")
                response = await client.post(url=endpoint, headers=headers, data=json_data, timeout=self.API_TIMEOUT)
                response.raise_for_status()
                run_response = StartRunResponse(**response.json())

                # Wait for run to finish.
                for i in range(30):  # Loop for a maximums of 30 attempts or 300 seconds in total.
                    run_id: str = run_response.data.id
                    endpoint = f"{self.APIFY_BASE_URL}acts/{self.LINKEDIN_REACTIONS_ACTOR_NAME}/runs/{run_id}"
                    logger.debug(f"Checking LinkedIn Reactions Run status in attempt number: {i+1}")
                    response = await client.get(url=endpoint, headers=headers, timeout=self.API_TIMEOUT)
                    response.raise_for_status()
                    run_response = StartRunResponse(**response.json())
                    if run_response.data.status == StartRunResponse.Status.FAILED:
                        raise ValueError(f"Run response is in failed state: {response.json()}")
                    if run_response.data.status == StartRunResponse.Status.SUCCEEDED:
                        # Run complete.
                        break

                     # Collection still in progress, wait for 10 seconds and retry.
                    await asyncio.sleep(10)

                # Collect Run data.
                dataset_id = run_response.data.defaultDatasetId
                endpoint = f"{self.APIFY_BASE_URL}datasets/{dataset_id}/items"
                response = await client.get(url=endpoint, headers=headers, timeout=self.API_TIMEOUT)
                response.raise_for_status()
                reactions: List[LinkedInReaction] = [LinkedInReaction(**r_dict) for r_dict in response.json()]
                logger.debug(f"Successfully fetched {len(reactions)} from Lead URL: {lead_linkedin_url}")
                return reactions

        except Exception as e:
            raise ActorRunFailed(f"LinkedIn Reactions Run for lead URL: {lead_linkedin_url} failed with error: {str(e)}")
