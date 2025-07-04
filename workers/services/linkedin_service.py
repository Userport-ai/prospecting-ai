import os
import json
import asyncio
import httpx
from enum import Enum
from typing import Optional, List, Dict, Union, Any

from services.ai.api_cache_service import cached_request, APICacheService
from services.bigquery_service import BigQueryService
from utils.retry_utils import RetryableError, RetryConfig, with_retry
from utils.loguru_setup import logger
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from dateutil import parser
from dateutil.relativedelta import relativedelta


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
        ActorRunFailed,
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


class RapidAPIImage(BaseModel):
    url: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None


class RapidAPIAuthor(BaseModel):
    """Rapid API Author definition."""
    id: Optional[int] = Field(default=None, description="ID of the Author in LinkedIn, example: 47272776")
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    headline: Optional[str] = None
    username: Optional[str] = Field(default=None, description="LinkedIn username of the author")
    url: Optional[str] = Field(default=None, description="Full LinkedIn URL of the author")

    profilePictures: Optional[List[RapidAPIImage]] = None
    urn: Optional[str] = Field(default=None, description="Example: urn:li:fsd_profile:ACoAAALRU0gBuEAgLlZcahYXe2CfV4RUpfhWTYA")


class RapidAPICompany(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = Field(default=None, description="Company page URL, Example: https://www.linkedin.com/company/jetri-education-consulting/")
    urn: Optional[str] = Field(default=None, description="Company URN, example: 38151421")
    username: Optional[str] = Field(default=None, description="Company username, example: hirist-tech")
    companyLogo: Optional[List[RapidAPIImage]] = None


class RapidAPIVideo(BaseModel):
    url: Optional[str] = None
    poster: Optional[str] = None
    duration: Optional[int] = None
    # Omitting two other fields "thumbnails" and "video" since we don't know the types.


class RapidAPIPersonMention(BaseModel):
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    urn: Optional[str] = None
    publicIdentifier: Optional[str] = Field(default=None, description="Example: pramathsinha")


class RapidAPICompanyMention(BaseModel):
    id: Optional[int] = Field(default=None, description="LinkedIn ID of company")
    name: Optional[str] = None
    publicIdentifier: Optional[str] = Field(default=None, description="Example: https:www.linkedin.comschoolindian-school-of-business")
    url: Optional[str] = Field(default=None, description="Example: https://www.linkedin.com/school/indian-school-of-business/")


class RapidAPIReaction(BaseModel):
    class Comment(BaseModel):
        text: Optional[str] = None
        author: Optional[RapidAPIAuthor] = None
        company: Optional[RapidAPICompany] = None

    action: Optional[str] = Field(default=None, description="Example: Anant S. likes this")
    entityType: Optional[str] = Field(default=None, description="Example: post")
    author: Optional[RapidAPIAuthor] = None
    company: Optional[RapidAPICompany] = None
    text: Optional[str] = None

    totalReactionCount: Optional[int] = None
    likeCount: Optional[int] = None
    empathyCount: Optional[int] = None
    praiseCount: Optional[int] = None
    repostsCount: Optional[int] = None
    postUrl: Optional[str] = Field(default=None, description="URL of the post")
    postedAt: Optional[str] = Field(default=None, description="Example: 2d, 1w, 2mo etc.")
    postedDate: Optional[str] = Field(default=None, description="Example: 2025-05-05 03:37:40.122 +0000 UTC")
    shareUrn: Optional[str] = Field(default=None, description="Example: 7325000704052383745")
    urn: Optional[str] = Field(default=None, description="Example: 7325000705495179264")

    image: Optional[List[RapidAPIImage]] = Field(default=None, description="Images linked to the post content")
    video: Optional[List[RapidAPIVideo]] = Field(default=None, description="Images linked to the post content")
    comment: Optional[Comment] = None
    article: Optional[Dict[str, Any]] = None


class RapidAPIReactionsData(BaseModel):
    items: List[RapidAPIReaction] = Field(..., description="List of Reactions of given user")
    paginationToken: Optional[str] = Field(default=None, description="Paginationation token for the next page")


class RapidAPIPost(BaseModel):
    author: Optional[RapidAPIAuthor] = None
    company: Optional[RapidAPICompany] = None
    reposted: Optional[bool] = Field(default=None, description="Whether post has been reposted or not, None is the same as False based on observed data in prod.")
    text: Optional[str] = None
    resharedPost: Optional['RapidAPIPost'] = None
    postedAt: Optional[str] = Field(default=None, description="Example: 2d, 1w, 2mo etc.")
    postedDate: Optional[str] = Field(default=None, description="Example: 2025-05-05 03:37:40.122 +0000 UTC")
    postedDateTimestamp: Optional[int] = Field(default=None, description="Example: 1738726140340")
    mentions: Optional[List[RapidAPIPersonMention]] = Field(default=None, description="Persons mentioned in the post")
    companyMentions: Optional[List[RapidAPICompanyMention]] = Field(default=None, description="Companies mentioned in the post")

    totalReactionCount: Optional[int] = None
    likeCount: Optional[int] = None
    empathyCount: Optional[int] = None
    InterestCount: Optional[int] = None
    praiseCount: Optional[int] = None
    repostsCount: Optional[int] = None
    commentsCount: Optional[int] = None
    postUrl: Optional[str] = Field(default=None, description="URL of the post")
    shareUrl: Optional[str] = None
    isBrandPartnership: Optional[bool] = None
    urn: Optional[str] = Field(default=None, description="Example: 7325000705495179264")

    document: Optional[Dict[str, Any]] = None
    celebration: Optional[Dict[str, Any]] = None
    poll: Optional[Dict[str, Any]] = None
    article: Optional[Dict[str, Any]] = None
    entity: Optional[Dict[str, Any]] = None


class RapidAPIComment(BaseModel):
    class CommentActivityInfo(BaseModel):
        text: Optional[str] = None
        totalReactionCount: Optional[int] = None
        likeCount: Optional[int] = None

    author: Optional[RapidAPIAuthor] = None
    company: Optional[RapidAPICompany] = None
    text: Optional[str] = None
    resharedPost: Optional['RapidAPIPost'] = None
    highlightedComments: Optional[List[str]] = Field(default=None, description="Lead's comment on the post which is the main highlight")
    highlightedCommentsActivityCounts: Optional[List[CommentActivityInfo]] = None
    postedAt: Optional[str] = Field(default=None, description="Example: 2d, 1w, 2mo etc.")
    postedDate: Optional[str] = Field(default=None, description="Example: 2025-05-05 03:37:40.122 +0000 UTC")
    commentedDate: Optional[str] = Field(default=None, description="Example: 2025-05-05 03:37:40.122 +0000 UTC")

    totalReactionCount: Optional[int] = None
    appreciationCount: Optional[int] = None
    likeCount: Optional[int] = None
    empathyCount: Optional[int] = None
    InterestCount: Optional[int] = None
    praiseCount: Optional[int] = None
    repostsCount: Optional[int] = None
    commentsCount: Optional[int] = None
    postUrl: Optional[str] = Field(default=None, description="URL of the post")
    commentUrl: Optional[str] = Field(default=None, description="URL of the specific comment made by lead")
    urn: Optional[str] = Field(default=None, description="Example: 7325000705495179264")

    image: Optional[List[RapidAPIImage]] = Field(default=None, description="Images linked to the post content")
    video: Optional[List[RapidAPIVideo]] = Field(default=None, description="Images linked to the post content")
    article: Optional[Dict[str, Any]] = None


class RapidAPIResponse(BaseModel):
    success: bool = Field(..., description="Whether the request succeeded or not.")
    message: Optional[str] = None
    data: Optional[Union[RapidAPIReactionsData, List[RapidAPIPost], List[RapidAPIComment]]] = None


class RapidAPILinkedInActivities(BaseModel):
    """LinkedIn activities consisting of Posts, Comments and Reactions from given lead."""
    posts: List[RapidAPIPost] = Field(default=[])
    comments: List[RapidAPIComment] = Field(default=[])
    reactions: List[RapidAPIReaction] = Field(default=[])


class LinkedInService:
    """Service class for handling LinkedIn for data like posts, comments and reactions."""

    def __init__(self):
        self.APIFY_BASE_URL = "https://api.apify.com/v2/"
        self.apify_api_key = os.getenv('APIFY_API_KEY')
        self.LINKEDIN_REACTIONS_ACTOR_NAME = "apimaestro~linkedin-profile-reactions"
        self.API_TIMEOUT = 30.0  # timeout in seconds.
        self.cache_service = APICacheService(bq_service=BigQueryService())
        self.RAPID_API_CHEAPER_BASE_URL = "https://linkedin-api8.p.rapidapi.com/"
        self.rapid_api_key = os.getenv("RAPID_API_KEY")
        self.cache_ttl_hours = 24*7  # Cache for 7 days

    @with_retry(retry_config=LINKEDIN_RETRY_CONFIG, operation_name="_fetch_linkedin_reactions")
    async def fetch_reactions(self, lead_linkedin_url: str, force_refresh: bool = False) -> List[LinkedInReaction]:
        """Fetch LinkedIn Reactions for given Lead's LinkedIn URL."""
        try:
            lead_username: str = self._get_username(lead_linkedin_url=lead_linkedin_url)

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
                        ttl_hours=self.cache_ttl_hours
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
            raise ActorRunFailed(f"LinkedIn Reactions Run for lead URL: {lead_linkedin_url} failed with error: {str(e)}")

    async def fetch_recent_linkedin_activities(self, lead_linkedin_url: str) -> RapidAPILinkedInActivities:
        """Fetches latest Posts, Comments and Reactions from given lead's profile."""
        linkedin_activities = RapidAPILinkedInActivities(posts=[], comments=[], reactions=[])
        # Use 3 months as default cutoff.
        cutoff_timestamp: int = datetime.now(timezone.utc) - relativedelta(months=3)
        try:
            posts = await self.fetch_rapid_api_linkedin_posts(lead_linkedin_url=lead_linkedin_url, cutoff_timestamp=cutoff_timestamp)
            linkedin_activities.posts = posts
        except Exception as e:
            logger.error(f"{str(e)}")

        try:
            comments = await self.fetch_rapid_api_linkedin_comments(lead_linkedin_url=lead_linkedin_url, cutoff_timestamp=cutoff_timestamp)
            linkedin_activities.comments = comments
        except Exception as e:
            logger.error(f"{str(e)}")

        try:
            reactions = await self.fetch_rapid_api_linkedin_reactions(lead_linkedin_url=lead_linkedin_url, cutoff_timestamp=cutoff_timestamp)
            linkedin_activities.reactions = reactions
        except Exception as e:
            logger.error(f"{str(e)}")

        return linkedin_activities

    async def fetch_rapid_api_linkedin_posts(self, lead_linkedin_url: str, cutoff_timestamp: Optional[datetime]) -> List[RapidAPIPost]:
        """Fetch Posts of given lead from Rapid API service after provided cutoff timestamp if any."""
        try:
            lead_username: str = self._get_username(lead_linkedin_url=lead_linkedin_url)
            endpoint = f"{self.RAPID_API_CHEAPER_BASE_URL}get-profile-posts"
            params = {
                "username": lead_username,
                "start": 0
            }
            rapid_api_response: RapidAPIResponse = await self._fetch_rapidapi_linkedin_activity_response_with_retry(endpoint=endpoint, params=params)
            if not isinstance(rapid_api_response.data, list):
                raise ValueError(f"Expected list type in Rapid API response data for LinkedIn posts, got {type(rapid_api_response.data)}")
            posts: List[RapidAPIPost] = rapid_api_response.data
            logger.debug(f"Got {len(posts)} LinkedIn posts from Rapid API from Lead URL: {lead_linkedin_url}")

            if cutoff_timestamp:
                # Filter posts after cutoff.
                posts = list(filter(lambda p: self._get_datetime(p.postedDate) >= cutoff_timestamp, posts))
                logger.debug(f"Got {len(posts)} LinkedIn posts after filtering for cutoff timestamp: {cutoff_timestamp} from Lead URL: {lead_linkedin_url}")
            return posts
        except Exception as e:
            raise ValueError(f"Fetching Rapid API LinkedIn Posts for Lead URL: {lead_linkedin_url} failed with error: {str(e)}")

    async def fetch_rapid_api_linkedin_comments(self, lead_linkedin_url: str, cutoff_timestamp: Optional[datetime]) -> List[RapidAPIComment]:
        """Fetch Comments of given lead from Rapid API service after provided cutoff timestamp if any."""
        try:
            lead_username: str = self._get_username(lead_linkedin_url=lead_linkedin_url)
            endpoint = f"{self.RAPID_API_CHEAPER_BASE_URL}get-profile-comments"
            params = {
                "username": lead_username,
            }
            rapid_api_response: RapidAPIResponse = await self._fetch_rapidapi_linkedin_activity_response_with_retry(endpoint=endpoint, params=params)
            if not isinstance(rapid_api_response.data, list):
                raise ValueError(f"Expected list type in Rapid API response data for LinkedIn comments, got {type(rapid_api_response.data)}")
            comments: List[RapidAPIComment] = rapid_api_response.data
            logger.debug(f"Got {len(comments)} LinkedIn comments from Rapid API from Lead URL: {lead_linkedin_url}")

            if cutoff_timestamp:
                # Filter comments after cutoff.
                comments = list(filter(lambda c: self._get_datetime(c.postedDate) >= cutoff_timestamp, comments))
                logger.debug(f"Got {len(comments)} LinkedIn comments after filtering for cutoff timestamp: {cutoff_timestamp} from Lead URL: {lead_linkedin_url}")
            return comments
        except Exception as e:
            raise ValueError(f"Fetching Rapid API LinkedIn Comments for Lead URL: {lead_linkedin_url} failed with error: {str(e)}")

    async def fetch_rapid_api_linkedin_reactions(self, lead_linkedin_url: str,  cutoff_timestamp: Optional[datetime]) -> List[RapidAPIReaction]:
        """Fetch Reactions of given lead from Rapid API service after provided cutoff timestamp if any."""
        try:
            lead_username: str = self._get_username(lead_linkedin_url=lead_linkedin_url)
            endpoint = f"{self.RAPID_API_CHEAPER_BASE_URL}get-profile-likes"
            params = {
                "username": lead_username,
                "start": 0
            }
            rapid_api_response: RapidAPIResponse = await self._fetch_rapidapi_linkedin_activity_response_with_retry(endpoint=endpoint, params=params)
            reactions: List[RapidAPIReaction] = rapid_api_response.data.items
            logger.debug(f"Got {len(reactions)} LinkedIn Reactions from Rapid API for Lead URL: {lead_linkedin_url}")

            if cutoff_timestamp:
                # Filter reactions after cutoff.
                reactions = list(filter(lambda r: self._get_datetime(r.postedDate) >= cutoff_timestamp, reactions))
                logger.debug(f"Got {len(reactions)} LinkedIn Reactions after filtering for cutoff timestamp: {cutoff_timestamp} from Lead URL: {lead_linkedin_url}")

            return reactions
        except Exception as e:
            raise ValueError(f"Fetching Rapid API LinkedIn Reactions for Lead URL: {lead_linkedin_url} failed with error: {str(e)}")

    async def _fetch_rapidapi_linkedin_activity_response_with_retry(self, endpoint: str, params: str) -> RapidAPIResponse:
        """Helper to manually retry RapidAPI responses if they received a 200 but success field is false.

        The response is stored in cache since it had a 200 success code but we want to retry and force refresh in this case.

        See https://rapidapi.com/rockapis-rockapis-default/api/linkedin-api8.
        """
        force_refresh = False
        for i in range(LINKEDIN_RETRY_CONFIG.max_attempts):
            rapid_api_response: RapidAPIResponse = await self._fetch_rapidapi_linkedin_activity_response(endpoint=endpoint, params=params, force_refresh=force_refresh)
            if not rapid_api_response.success:
                logger.error(f"Rapid API LinkedIn Activity failed in attempt number: {i+1} with response: {rapid_api_response}")
                force_refresh = True
                continue

            # Successful response.
            return rapid_api_response

        raise ValueError(f"Rapid API LinkedIn Activity failed after all attempts with response: {rapid_api_response}")

    @with_retry(retry_config=LINKEDIN_RETRY_CONFIG, operation_name="_rapid_api_fetch_linkedin_activity")
    async def _fetch_rapidapi_linkedin_activity_response(self, endpoint: str, params: str, force_refresh: bool) -> RapidAPIResponse:
        """Helper to fetch Rapid API LinkedIn Activity response for given endpoint."""
        headers = {
            "x-rapidapi-host": "linkedin-api8.p.rapidapi.com",
            "x-rapidapi-key": self.rapid_api_key
        }

        response, status_code = await cached_request(
            cache_service=self.cache_service,
            url=endpoint,
            method='GET',
            params=params,
            headers=headers,
            force_refresh=force_refresh,
            ttl_hours=self.cache_ttl_hours
        )
        if status_code == 200:
            return RapidAPIResponse(**response)

        raise RetryableError(f"Cache request for LinkedIn Activity URL: {endpoint} and params: {params} failed with status code: {status_code}")

    def _get_username(self, lead_linkedin_url: str) -> str:
        lead_linkedin_url = lead_linkedin_url.strip("/")
        url_list: List[str] = lead_linkedin_url.split("/in/")
        if len(url_list) != 2:
            raise ValueError(f"Invalid lead LinkedIn URL format : {lead_linkedin_url}")
        lead_username = url_list[1]
        return lead_username

    def _get_datetime(self, date_str: Optional[str]) -> datetime:
        """Helper to convert date string in the format '2025-05-05 03:37:40.122 +0000 UTC' to datetime object."""
        try:
            cleaned_date_str = date_str.replace(" UTC", "")
            return parser.parse(cleaned_date_str)
        except Exception as e:
            logger.error(f"Failed to convert date string: {date_str} to datetime object: {str(e)}")
            return datetime.min.replace(tzinfo=timezone.utc)
