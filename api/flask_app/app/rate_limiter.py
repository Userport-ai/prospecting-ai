
import logging
from typing import List, Optional
from pydantic import BaseModel, Field
from flask import request, g
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from app.models import UsageTier, User
from app.database import Database

# Global instance of Rate limiter in the app.
rate_limiter = Limiter(get_remote_address)

logger = logging.getLogger()


class RateLimitConfig(BaseModel):
    """Describes configuration of rate limits based on given request configurations."""

    class Request(BaseModel):
        """Limits configuration based on request path and method."""
        class Limit(BaseModel):
            """
            Limit defined based on Usage tier.

            #rate-limit-string-notation..
            Values are defined using string notation in https://flask-limiter.readthedocs.io/en/stable/configuration.html
            """
            usage_tier: UsageTier = Field(...,
                                          description="Usage Tier defined by the app.")
            value: str = Field(..., description="Rate Limit values in string notation expected by Flask Limiter. Multiple limits will be delimiter separated.")

        path: str = Field(...,
                          description="Request path. For example: /api/v1/leads.")
        method: str = Field(..., description="Request method")
        limits: List[Limit] = Field(...,
                                    description="Limits for each usage tier.")

    requests: List[Request] = Field(
        ..., description="List of usage tiers in this configuration.")


# Module level constant that defines the current rate limit configuration for the different APIs.
RATE_LIMIT_CONFIG = RateLimitConfig(
    # Add APIs to the requests list to enable Rate limiting for them.
    requests=[
        RateLimitConfig.Request(
            # Create lead research report API.
            path="/api/v1/lead-research-reports",
            method="POST",
            limits=[
                RateLimitConfig.Request.Limit(
                    usage_tier=UsageTier.FREE,
                    value="5 per 5 minutes;15 per day"
                ),
                RateLimitConfig.Request.Limit(
                    usage_tier=UsageTier.ALPHA_TESTERS,
                    value="10 per 5 minutes;50 per day"
                ),
            ]
        ),
        RateLimitConfig.Request(
            # Create personalized email API.
            path="/api/v1/lead-research-reports/personalized-emails",
            method="POST",
            limits=[
                RateLimitConfig.Request.Limit(
                    usage_tier=UsageTier.FREE,
                    value="3 per minute;20 per day"
                ),
                RateLimitConfig.Request.Limit(
                    usage_tier=UsageTier.ALPHA_TESTERS,
                    value="5 per minute;50 per day"
                ),
            ]
        )
    ]
)


def get_value() -> Optional[str]:
    """Determines rate limit value depending on the method and usage tier of the logged in user.

    Assumes that this always called by Flask Limiter decorator so Flask request context is always present.

    Returns Rate limit string in the format expected by Flask-Limiter.
    Reference: https://flask-limiter.readthedocs.io/en/stable/index.html#dynamically-loaded-limit-string-s
    """
    matched_config_request: Optional[RateLimitConfig.Request] = None
    for config_req in RATE_LIMIT_CONFIG.requests:
        if request.path == config_req.path and request.method == config_req.method:
            # Found a match.
            matched_config_request = config_req
            break
    if not matched_config_request:
        # Method not found, fallback to default rate limit in original config.
        logger.error(
            f"Expected to find request path: {request.path} and method: {request.method} in rate limit config but wasn't found: {RATE_LIMIT_CONFIG}")
        return None

    # Get usage tier of current user.
    db = Database()
    user_id: str = g.user["uid"]
    user: User = db.get_user(user_id=user_id, projection={"usage_tier": 1})
    if not user.usage_tier:
        # This is corrupt state, throw an exception.
        raise Exception(
            f"Usage Tier is None for User ID: {user_id} when for request: {request}")

    if user.usage_tier not in [lim.usage_tier for lim in matched_config_request.limits]:
        # User's usage tier not found in limit config, fallback to default rate limit in original config.
        logger.error(
            f"Did not find User's usage tier: {user.usage_tier} found in User ID: {user_id} in Rate limit config: {RATE_LIMIT_CONFIG}")
        return None

    matched_tier = list(filter(lambda lim: lim.usage_tier ==
                        user.usage_tier, matched_config_request.limits))[0]
    return matched_tier.value
