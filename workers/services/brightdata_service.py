
import os
import logging
import asyncio
import httpx
import json
from typing import List
from utils.retry_utils import RetryableError, RetryConfig, with_retry
from models.accounts import BrightDataAccount
from pydantic import BaseModel, Field

# Configure logging
logger = logging.getLogger(__name__)

BRIGHTDATA_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=20.0,
    retryable_exceptions=[
        RetryableError,
        asyncio.TimeoutError,
        ConnectionError,
        httpx.ConnectTimeout,
        httpx.ConnectError,
    ]
)


class TriggerDataCollectionResponse(BaseModel):
    snapshot_id: str = Field(...)


class BrightDataService:
    """Service class for handling BrightData operations for account enrichment data."""

    def __init__(self):
        self.BRIGHTDATA_URL = "https://api.brightdata.com/datasets/v3/"
        self.brightdata_api_key = os.getenv('BRIGHTDATA_API_KEY')
        self.API_TIMEOUT = 30.0  # timeout in seconds.

    @with_retry(retry_config=BRIGHTDATA_RETRY_CONFIG, operation_name="_brightdata_trigger_data_collection")
    async def trigger_account_data_collection(self, account_linkedin_urls: List[str]) -> str:
        """Triggers Data collection for given Account LinkedIn URLs and returns Snapshot ID that client will use to poll collection status."""
        with httpx.Client() as client:
            logger.debug(f"Triggering Account data collection for URLs:m{account_linkedin_urls}")
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.brightdata_api_key}"}
            data = [{"url": url} for url in account_linkedin_urls]
            json_data = json.dumps(data)
            endpoint = f"{self.BRIGHTDATA_URL}trigger?dataset_id=gd_l1vikfnt1wgvvqz95w&include_errors=true"
            response = client.post(url=endpoint, headers=headers, data=json_data, timeout=self.API_TIMEOUT)
            response.raise_for_status()
            result = TriggerDataCollectionResponse(**response.json())
            return result.snapshot_id

    async def collect_account_data(self, snapshot_id: str) -> List[BrightDataAccount]:
        """
        Collect Account data triggered using given Snapshot ID.

        Reference: https://docs.brightdata.com/scraping-automation/web-scraper-api/error-list-by-endpoint#download-snapshot.
        """
        try:
            with httpx.Client() as client:
                headers = {"Authorization": f"Bearer {self.brightdata_api_key}"}
                endpoint = f"{self.BRIGHTDATA_URL}snapshot/{snapshot_id}?format=json"
                for _ in range(30):  # Loop for a maximum of 30 attempts or 300 seconds in total/
                    response = client.get(url=endpoint, headers=headers, timeout=self.API_TIMEOUT)
                    response.raise_for_status()
                    if response.status_code == 202:
                        # Collection still in progress, wait for 10 seconds and retry.
                        # Use sleep_with_context to preserve trace context
                        from utils.async_utils import sleep_with_context
                        await sleep_with_context(10)
                    else:
                        # Successful response.
                        results: List = response.json()
                        if not isinstance(results, list):
                            raise ValueError(f"Expected List response, got: {results}")
                        return [BrightDataAccount(**res) for res in results]

            raise ValueError(f"Failed to collect Account data for Snapshot ID: {snapshot_id}")
        except Exception as e:
            logger.error(f"Failed to Collect Data for Snapshot ID: {snapshot_id} with error: {str(e)}", exc_info=True)
            raise
