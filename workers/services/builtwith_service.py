import logging
import os
from typing import Dict, Any, Optional

from services.api_cache_service import APICacheService, cached_request
from utils.retry_utils import RetryConfig, RetryableError, with_retry

logger = logging.getLogger(__name__)

class BuiltWithService:
    """Service for interacting with the BuiltWith API to fetch technology data."""

    # Retry configuration for API calls
    RETRY_CONFIG = RetryConfig(
        max_attempts=3,
        base_delay=1.0,
        max_delay=5.0,
        retryable_exceptions=[
            RetryableError,
            ConnectionError,
            TimeoutError
        ]
    )

    def __init__(self, cache_service: APICacheService):
        """Initialize the BuiltWith service.

        Args:
            cache_service: Service for caching API responses
        """
        self.api_key = os.getenv('BUILTWITH_API_KEY')
        if not self.api_key:
            raise ValueError("BUILTWITH_API_KEY environment variable is required")
        
        self.cache_service = cache_service
        self.base_url = "https://api.builtwith.com/v19/api.json"
        self.cache_ttl_hours = 24 * 7  # Cache for 1 week

    @with_retry(retry_config=RETRY_CONFIG, operation_name="get_technology_profile")
    async def get_technology_profile(self, domain: str) -> Dict[str, Any]:
        """Fetch technology profile for a domain from BuiltWith API.

        Args:
            domain: The domain to fetch technology data for

        Returns:
            Dict containing the technology profile data

        Raises:
            RetryableError: If the API request fails with a retryable error
            ValueError: If the domain is invalid or response is malformed
        """
        if not domain:
            raise ValueError("Domain is required")

        try:
            # Use cached_request to handle caching
            response, status_code = await cached_request(
                cache_service=self.cache_service,
                url=self.base_url,
                method='GET',
                params={
                    'KEY': self.api_key,
                    'LOOKUP': domain
                },
                headers={'Content-Type': 'application/json'},
                ttl_hours=self.cache_ttl_hours
            )

            if status_code == 200:
                return self._process_technology_data(response)
            elif status_code == 429:
                raise RetryableError("Rate limit exceeded")
            else:
                logger.error(f"BuiltWith API error: {status_code} - {response}")
                raise RetryableError(f"API request failed with status {status_code}")

        except Exception as e:
            logger.error(f"Error fetching technology data for {domain}: {str(e)}")
            raise

    def _process_technology_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process and structure the raw API response data.

        Args:
            raw_data: Raw API response data

        Returns:
            Dict containing structured technology data
        """
        try:
            # Extract the first result (most recent scan)
            if not raw_data.get('Results'):
                return {
                    'categories': {},
                    'technologies': [],
                    'first_detected': {},
                    'last_detected': {},
                    'confidence_scores': {},
                    'meta': {
                        'domain': raw_data.get('Domain'),
                        'last_scan': None
                    }
                }

            result = raw_data['Results'][0]
            technologies = result.get('Result', [])

            # Structure the data
            structured_data = {
                'categories': {},
                'technologies': [],
                'first_detected': {},
                'last_detected': {},
                'confidence_scores': {},
                'meta': {
                    'domain': raw_data.get('Domain'),
                    'last_scan': result.get('LastScan')
                }
            }

            # Process each technology
            for tech in technologies:
                name = tech.get('Name')
                if not name:
                    continue

                category = tech.get('Categories', [{}])[0].get('Name', 'Uncategorized')
                
                # Add to categories
                if category not in structured_data['categories']:
                    structured_data['categories'][category] = []
                if name not in structured_data['categories'][category]:
                    structured_data['categories'][category].append(name)

                # Add to technologies list
                if name not in structured_data['technologies']:
                    structured_data['technologies'].append(name)

                # Track detection dates
                structured_data['first_detected'][name] = tech.get('FirstDetected')
                structured_data['last_detected'][name] = tech.get('LastDetected')

                # Calculate confidence score (based on detection consistency)
                confidence = self._calculate_confidence_score(tech)
                structured_data['confidence_scores'][name] = confidence

            return structured_data

        except Exception as e:
            logger.error(f"Error processing technology data: {str(e)}")
            raise ValueError(f"Failed to process technology data: {str(e)}")

    def _calculate_confidence_score(self, technology: Dict[str, Any]) -> float:
        """Calculate a confidence score for a technology detection.

        Args:
            technology: Technology data from API

        Returns:
            float: Confidence score between 0 and 1
        """
        try:
            # Factors that influence confidence:
            # 1. Detection consistency (Live vs Dead)
            # 2. Recent detection
            # 3. Number of paths detected on

            base_score = 0.5  # Start with base score

            # Add score for live detection
            if technology.get('Live'):
                base_score += 0.3
            
            # Add score for recent detection
            if technology.get('LastDetected') and technology.get('FirstDetected'):
                # If it's been detected consistently over time
                base_score += 0.1

            # Add score for multiple path detections
            paths = technology.get('Paths', [])
            if len(paths) > 1:
                base_score += min(0.1, len(paths) * 0.02)  # Cap at 0.1

            return min(1.0, base_score)  # Ensure score doesn't exceed 1.0

        except Exception as e:
            logger.warning(f"Error calculating confidence score: {str(e)}")
            return 0.5  # Return default score on error