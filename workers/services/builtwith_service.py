import os
from datetime import datetime
from time import time
from typing import Optional, Dict, Any

from models.builtwith import EnrichmentResult, BuiltWithApiResponse, TechnologyProfile, EnrichmentError, TechnologyBase, \
    TechnologyDetail, QualityMetrics, MetaData
from services.api_cache_service import APICacheService, cached_request
from utils.retry_utils import RetryConfig, RetryableError, with_retry
from utils.loguru_setup import logger




class BuiltWithService:
    """Service for interacting with the BuiltWith API to fetch technology data."""

    RETRY_CONFIG = RetryConfig(
        max_attempts=3,
        base_delay=1.0,
        max_delay=30.0,
        retryable_exceptions=[
            RetryableError,
            ConnectionError,
            TimeoutError
        ]
    )

    def __init__(self, cache_service: APICacheService):
        """Initialize the BuiltWith service."""
        self.cache_service = cache_service

        self.api_key = os.getenv('BUILTWITH_API_KEY')
        if not self.api_key:
            raise ValueError("BUILTWITH_API_KEY environment variable is required")

        self.base_url = "https://api.builtwith.com/v21/api.json"
        self.cache_ttl_hours = 24 * 30  # Cache for 1 month

    @with_retry(retry_config=RETRY_CONFIG, operation_name="get_technology_profile")
    async def get_technology_profile(self, domain: str) -> EnrichmentResult:
        """Fetch and process technology profile for a domain."""
        if not domain:
            raise ValueError("Domain is required to get technology profile")

        try:
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
                builtwith_response = BuiltWithApiResponse(**response)

                if builtwith_response.Errors:
                    raise RetryableError(f"BuiltWith API errors: {builtwith_response.Errors}")

                tech_profile = self._process_technology_data(builtwith_response)
                quality_metrics = self._calculate_quality_metrics(tech_profile)

                return EnrichmentResult(
                    status="completed",
                    completion_percentage=100,
                    processed_data={
                        "profile": tech_profile.model_dump(),
                        "company_info": self._extract_company_info(builtwith_response.Results[0].Meta),
                        "attributes": builtwith_response.Attributes.model_dump() if builtwith_response.Attributes else {}
                    },
                    quality_metrics=quality_metrics
                )

            elif status_code == 429:
                raise RetryableError("Rate limit exceeded")
            else:
                logger.error(f"BuiltWith API error: {status_code} - {response}")
                raise RetryableError(f"API request failed with status {status_code}")

        except Exception as e:
            logger.error(f"Error fetching technology data for {domain}: {str(e)}", exc_info=True)
            return EnrichmentResult(
                status="failed",
                error=EnrichmentError(
                    message=str(e),
                    code="PROCESSING_ERROR",
                    details={"domain": domain}
                )
            )

    def _process_technology_data(self, response: BuiltWithApiResponse) -> TechnologyProfile:
        """Process and structure the raw API response data."""
        try:
            tech_profile = TechnologyProfile(
                meta={
                    'domain': response.Domain,
                    'first_indexed': self._format_timestamp(response.FirstIndexed),
                    'last_indexed': self._format_timestamp(response.LastIndexed)
                }
            )

            # Process all technologies from all results
            for result in response.Results:
                subdomain = result.SubDomain.lower() if result.SubDomain else None

                # Handle technologies directly in the result
                if result.Technologies:
                    for tech in result.Technologies:
                        self._process_single_technology(tech, tech_profile, subdomain)

                # Handle technologies in Result.Paths
                if result.Result and result.Result.Paths:
                    for path_index, path in enumerate(result.Result.Paths):
                        if path.Technologies:
                            for tech in path.Technologies:
                                if tech and tech.Name:
                                    tech.Paths = tech.Paths or []
                                    tech.Paths.append(f"path_{path_index}")
                                    self._process_single_technology(tech, tech_profile, subdomain)

            return tech_profile

        except Exception as e:
            logger.error(f"Error processing technology data: {str(e)}", exc_info=True)
            raise ValueError(f"Failed to process technology data: {str(e)}")

    def _process_single_technology(
            self,
            tech: TechnologyBase,
            tech_profile: TechnologyProfile,
            subdomain: Optional[str] = None
    ) -> None:
        """Process a single technology and update the profile."""

        # Exclude technologies which haven't been seen in a year's time
        if not tech.Name or (BuiltWithService.days_since_last_detected(tech) > 365):
            return

        tech_detail = self._create_technology_detail(tech, subdomain)
        tech_key = tech_detail.name.lower()

        # Update technologies list
        existing_tech = next(
            (t for t in tech_profile.technologies if t['name'].lower() == tech_key),
            None
        )

        if existing_tech:
            # Update existing technology
            if tech_detail.paths:
                existing_paths = set(existing_tech.get('paths', []))
                existing_paths.update(tech_detail.paths)
                existing_tech['paths'] = sorted(list(existing_paths))

            if subdomain and subdomain not in existing_tech.get('subdomains', []):
                existing_tech.setdefault('subdomains', []).append(subdomain)
        else:
            # Add new technology
            tech_data = tech_detail.model_dump(exclude_none=True)
            if subdomain:
                tech_data['subdomains'] = [subdomain]
            tech_profile.technologies.append(tech_data)

            # Process categories
            for category in tech.get_category_names():
                if category not in tech_profile.categories:
                    tech_profile.categories[category] = []
                if tech_detail.name not in tech_profile.categories[category]:
                    tech_profile.categories[category].append(tech_detail.name)

            # Track detection dates
            if tech_detail.first_detected:
                tech_profile.first_detected[tech_key] = tech_detail.first_detected
            if tech_detail.last_detected:
                tech_profile.last_detected[tech_key] = tech_detail.last_detected

            # Track confidence scores
            tech_profile.confidence_scores[tech_key] = tech_detail.confidence_score

            # Track premium technologies
            if tech_detail.is_premium:
                tech_profile.premium_technologies.append(tech_detail.name)

        # Update subdomain tracking
        if subdomain:
            if subdomain not in tech_profile.subdomains:
                tech_profile.subdomains[subdomain] = []
            if tech_detail.name not in tech_profile.subdomains[subdomain]:
                tech_profile.subdomains[subdomain].append(tech_detail.name)

    def _create_technology_detail(self, tech: TechnologyBase, subdomain: Optional[str] = None) -> TechnologyDetail:
        """Create a TechnologyDetail instance from raw technology data."""
        confidence_score = self._calculate_confidence_score(tech)

        return TechnologyDetail(
            name=tech.Name,
            description=tech.Description,
            categories=tech.get_category_names(),
            tag=tech.Tag,
            link=tech.Link,
            first_detected=self._format_timestamp(tech.FirstDetected),
            last_detected=self._format_timestamp(tech.LastDetected),
            is_premium=tech.IsPremium.lower() == 'yes' if tech.IsPremium else False,
            confidence_score=confidence_score,
            parent_technology=tech.Parent,
            paths=tech.Paths or [],
            subdomain=subdomain
        )

    @staticmethod
    def _calculate_confidence_score(technology: TechnologyBase) -> float:
        """Calculate a confidence score for a technology detection."""
        try:
            base_score = 0.5

            if technology.Live:
                base_score += 0.3

            if technology.LastDetected:
                try:
                    days_since_detection = BuiltWithService.days_since_last_detected(technology)

                    if days_since_detection <= 30:
                        base_score += 0.2
                    elif days_since_detection <= 90:
                        base_score += 0.15
                    elif days_since_detection <= 180:
                        base_score += 0.1
                    elif days_since_detection <= 365:
                        base_score += 0.05
                except Exception as e:
                    logger.warning(f"Error calculating date-based confidence: {str(e)}")

            # Add score for multiple path detections
            if technology.Paths:
                base_score += min(0.1, len(technology.Paths) * 0.02)

            # Additional confidence for technologies with categories
            if technology.Categories:
                base_score += min(0.1, len(technology.Categories) * 0.02)

            return min(1.0, base_score)

        except Exception as e:
            logger.warning(f"Error calculating confidence score: {str(e)}")
            return 0.5

    @staticmethod
    def days_since_last_detected(technology: TechnologyBase) -> int:
        last_detected = datetime.fromtimestamp(technology.LastDetected / 1000)
        days_since_detection = (datetime.now() - last_detected).days
        return days_since_detection

    @staticmethod
    def _calculate_quality_metrics(profile: TechnologyProfile) -> QualityMetrics:
        """Calculate quality metrics for the technology profile."""
        try:
            metrics = QualityMetrics(
                technology_count=len(profile.technologies),
                category_count=len(profile.categories),
                premium_count=len(profile.premium_technologies),
                subdomain_count=len(profile.subdomains)
            )

            # Calculate average confidence
            confidence_values = [score for score in profile.confidence_scores.values() if score is not None]
            metrics.average_confidence = sum(confidence_values) / len(confidence_values) if confidence_values else 0.0

            # Find earliest and latest detections
            first_detected_dates = [
                date for date in profile.first_detected.values()
                if date and isinstance(date, str)
            ]
            last_detected_dates = [
                date for date in profile.last_detected.values()
                if date and isinstance(date, str)
            ]

            metrics.earliest_detection = min(first_detected_dates) if first_detected_dates else None
            metrics.latest_detection = max(last_detected_dates) if last_detected_dates else None

            # Calculate coverage score
            coverage_score = 0.0

            # Factor 1: Number of technologies (40%)
            if metrics.technology_count >= 15:
                coverage_score += 0.4
            elif metrics.technology_count >= 8:
                coverage_score += 0.3
            elif metrics.technology_count >= 3:
                coverage_score += 0.2

            # Factor 2: Average confidence (30%)
            if metrics.average_confidence >= 0.8:
                coverage_score += 0.3
            elif metrics.average_confidence >= 0.6:
                coverage_score += 0.2
            elif metrics.average_confidence >= 0.4:
                coverage_score += 0.1

            # Factor 3: Category diversity (20%)
            category_ratio = metrics.category_count / max(metrics.technology_count, 1)
            if category_ratio >= 0.5:
                coverage_score += 0.2
            elif category_ratio >= 0.3:
                coverage_score += 0.1

            # Factor 4: Premium technologies (10%)
            if metrics.premium_count > 0:
                coverage_score += 0.1

            metrics.coverage_score = coverage_score

            # Determine quality rating
            if metrics.technology_count == 0:
                metrics.detection_quality = "insufficient_data"
            elif coverage_score >= 0.7:
                metrics.detection_quality = "high"
            elif coverage_score >= 0.4:
                metrics.detection_quality = "medium"
            else:
                metrics.detection_quality = "low"

            return metrics

        except Exception as e:
            logger.error(f"Error calculating quality metrics: {str(e)}", exc_info=True)
            return QualityMetrics()

    @staticmethod
    def _extract_company_info(meta: Optional[MetaData]) -> Dict[str, Any]:
        """Extract relevant company information from metadata."""
        if not meta:
            return {}

        return {
            "name": meta.CompanyName,
            "emails": meta.Emails,
            "phones": meta.Telephones,
            "location": {
                "city": meta.City,
                "state": meta.State,
                "postal_code": meta.Postcode,
                "country": meta.Country
            },
            "social_profiles": meta.Social,
            "contacts": [
                {
                    "name": person["Name"],
                    "type": person.get("Type"),
                    "email": person.get("Email")
                }
                for person in (meta.Names or [])
                if person.get("Name")
            ],
            "rankings": {
                "alexa": meta.ARank,
                "quantcast": meta.QRank
            },
            "vertical": meta.Vertical
        }

    @staticmethod
    def _format_timestamp(timestamp: Optional[int]) -> Optional[str]:
        """Convert Unix timestamp to ISO format string."""
        if not timestamp:
            return None

        try:
            # BuiltWith timestamps are in milliseconds
            return datetime.fromtimestamp(timestamp / 1000).isoformat()
        except Exception as e:
            logger.warning(f"Error formatting timestamp {timestamp}: {str(e)}")
            return None


# import asyncio
# import json
# import os
# import uuid
#
# from services.api_cache_service import APICacheService
#
# async def setup_cache_service() -> APICacheService:
#     """Initialize the cache service."""
#     project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
#     dataset = os.getenv('BIGQUERY_DATASET', 'userport_enrichment')
#     bq_service = BigQueryService()
#
#     # Initialize cache service
#
#     return APICacheService(
#             client=bq_service.client,
#             project_id=project_id,
#             dataset=dataset
#         )
#
#
# async def test_builtwith_service(domain: str) -> None:
#     """Test the BuiltWith service with a given domain."""
#     try:
#         # Initialize cache service
#         cache_service = await setup_cache_service()
#
#         # Initialize BuiltWith service
#         builtwith_service = BuiltWithService(cache_service=cache_service)
#
#         logger.info(f"Starting technology profile fetch for domain: {domain}")
#
#         # Fetch technology profile
#         result = await builtwith_service.get_technology_profile(
#             domain=domain,
#         )
#
#         # Print results in a structured way
#         print("\n=== Technology Profile Results ===")
#         print(f"Status: {result.status}")
#         print(f"Completion: {result.completion_percentage}%")
#
#         if result.error:
#             print("\nError Details:")
#             print(f"Message: {result.error.message}")
#             print(f"Code: {result.error.code}")
#             print(f"Details: {result.error.details}")
#         else:
#             # Print quality metrics
#             if result.quality_metrics:
#                 print("\nQuality Metrics:")
#                 print(f"Technology Count: {result.quality_metrics.technology_count}")
#                 print(f"Category Count: {result.quality_metrics.category_count}")
#                 print(f"Premium Count: {result.quality_metrics.premium_count}")
#                 print(f"Average Confidence: {result.quality_metrics.average_confidence:.2f}")
#                 print(f"Detection Quality: {result.quality_metrics.detection_quality}")
#                 print(f"Coverage Score: {result.quality_metrics.coverage_score:.2f}")
#
#             # Print technology categories
#             if result.processed_data.get('profile', {}).get('categories'):
#                 print("\nTechnology Categories:")
#                 for category, technologies in result.processed_data['profile']['categories'].items():
#                     print(f"\n{category}:")
#                     for tech in technologies:
#                         print(f"  - {tech}")
#
#             # Print premium technologies
#             if result.processed_data.get('profile', {}).get('premium_technologies'):
#                 print("\nPremium Technologies:")
#                 for tech in result.processed_data['profile']['premium_technologies']:
#                     print(f"  - {tech}")
#
#             # Save results to file for detailed inspection
#             output_file = f"builtwith_results_{domain.replace('.', '_')}.json"
#             with open(output_file, 'w') as f:
#                 json.dump(result.model_dump(), f, indent=2)
#             print(f"\nFull results saved to: {output_file}")
#
#     except Exception as e:
#         logger.error(f"Error during test: {str(e)}", exc_info=True)
#         raise
#
# async def main():
#     """Main function to run the test."""
#     # Get domain from environment variable or use default
#     test_domain = "lumos.com"
#
#     print(f"\nStarting BuiltWith Service Test")
#     print(f"Testing domain: {test_domain}")
#     print("=" * 50)
#
#     await test_builtwith_service(test_domain)
#
# if __name__ == "__main__":
#     # Check if BUILTWITH_API_KEY is set
#     # if not os.getenv('BUILTWITH_API_KEY'):
#     #     print("Error: BUILTWITH_API_KEY environment variable is not set")
#     #     exit(1)
#
#     # Run the test
#     # Logging configuration is now in utils/loguru_setup.py
#
#     from dotenv import load_dotenv
#     load_dotenv()
#
#     asyncio.run(main())
