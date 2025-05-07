import os
import json
import asyncio
import httpx
from enum import Enum
from typing import Optional, List

from services.ai.api_cache_service import cached_request, APICacheService
from services.bigquery_service import BigQueryService
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
        self.cache_service = APICacheService(bq_service=BigQueryService())

    @with_retry(retry_config=LINKEDIN_RETRY_CONFIG, operation_name="_fetch_linkedin_reactions")
    async def fetch_reactions(self, lead_linkedin_url: str, force_refresh: bool=False) -> List[LinkedInReaction]:
        """Fetch LinkedIn Reactions for given Lead's LinkedIn URL."""
        try:
            lead_linkedin_url = lead_linkedin_url.strip("/")
            url_list: List[str] = lead_linkedin_url.split("/in/")
            if len(url_list) != 2:
                raise ValueError(f"Invalid lead LinkedIn URL format: {lead_linkedin_url}")
            lead_username = url_list[1]

            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Authorization': f'Bearer {self.apify_api_key}'
            }

            # Use a cache lookup URL with the username as a query parameter for consistent lookups
            cache_url = f"{self.APIFY_BASE_URL}custom/linkedin-reactions"
            cache_params = {"username": lead_username}

            if not force_refresh:
                try:
                    # Try to get cached data first
                    cached_data, status_code = await cached_request(
                        cache_service=self.cache_service,
                        url=cache_url,
                        params=cache_params,
                        method="GET",
                        headers=headers,
                        ttl_hours=24*7  # Cache for 7 days
                    )

                    if status_code < 400 and cached_data:
                        logger.debug(f"Using cached LinkedIn reactions for: {lead_linkedin_url}")
                        reactions = [LinkedInReaction(**r_dict) for r_dict in cached_data]
                        return reactions
                except Exception as e:
                    logger.debug(f"Cache retrieval failed, proceeding with fresh data: {str(e)}")

            logger.debug(f"Getting fresh LinkedIn reactions for: {lead_linkedin_url}")

            async with httpx.AsyncClient() as client:
                endpoint = f"{self.APIFY_BASE_URL}acts/{self.LINKEDIN_REACTIONS_ACTOR_NAME}/runs"
                json_data = {"username": lead_username}

                response = await client.post(
                    url=endpoint,
                    headers=headers,
                    json=json_data,  # Use json parameter instead of data
                    timeout=self.API_TIMEOUT
                )
                response.raise_for_status()
                run_response = StartRunResponse(**response.json())
                run_id = run_response.data.id

                # Poll for completion
                for i in range(30):
                    status_endpoint = f"{self.APIFY_BASE_URL}acts/{self.LINKEDIN_REACTIONS_ACTOR_NAME}/runs/{run_id}"
                    logger.debug(f"Checking status, attempt {i+1}")
                    response = await client.get(
                        url=status_endpoint,
                        headers=headers,
                        timeout=self.API_TIMEOUT
                    )
                    response.raise_for_status()
                    run_response = StartRunResponse(**response.json())

                    if run_response.data.status == StartRunResponse.Status.FAILED:
                        raise ValueError(f"Run failed: {response.json()}")
                    if run_response.data.status == StartRunResponse.Status.SUCCEEDED:
                        break
                    await asyncio.sleep(10)

                dataset_id = run_response.data.defaultDatasetId
                dataset_endpoint = f"{self.APIFY_BASE_URL}datasets/{dataset_id}/items"
                response = await client.get(
                    url=dataset_endpoint,
                    headers=headers,
                    timeout=self.API_TIMEOUT
                )
                response.raise_for_status()
                reactions_data = response.json()

                await self.cache_service.cache_response(
                    url=cache_url,
                    params=cache_params,
                    response_data=reactions_data,
                    status_code=200,
                    method="GET",
                    headers=headers,
                    ttl_hours=24
                )

                reactions = [LinkedInReaction(**r_dict) for r_dict in reactions_data]
                logger.debug(f"Fetched {len(reactions)} reactions from: {lead_linkedin_url}")
                return reactions

        except Exception as e:
            raise ActorRunFailed(f"LinkedIn Reactions Run failed for {lead_linkedin_url}: {str(e)}")