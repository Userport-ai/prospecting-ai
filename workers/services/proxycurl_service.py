from datetime import datetime, timezone
import os
import logging
import asyncio
import httpx
from typing import List, Optional, Dict, Any
from difflib import SequenceMatcher

from models.leads import ProxyCurlPersonProfile, ProxyCurlSearchResponse, EnrichedLead
from utils.retry_utils import RetryableError, RetryConfig, with_retry
from services.api_cache_service import APICacheService, cached_request

# Configure logging
logger = logging.getLogger(__name__)

PROXYCURL_RETRY_CONFIG = RetryConfig(
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


class ProxyCurlService:
    """Service for interacting with ProxyCurl APIs."""

    def __init__(self, cache_service: APICacheService):
        """Initialize ProxyCurl service with configuration."""
        self.PROXYCURL_BASE_URL = "https://nubela.co/proxycurl/api"
        self.proxycurl_api_key = os.getenv('PROXYCURL_API_KEY')
        if not self.proxycurl_api_key:
            raise ValueError("PROXYCURL_API_KEY environment variable is required")

        self.cache_service = cache_service
        self.API_TIMEOUT = 30.0  # timeout in seconds
        self.DEFAULT_CACHE_TTL = 24 * 30  # 30 days in hours

    @with_retry(retry_config=PROXYCURL_RETRY_CONFIG, operation_name="get_person_profile")
    async def get_person_profile(self, linkedin_url: str) -> Optional[ProxyCurlPersonProfile]:
        """Fetch person profile data from ProxyCurl API."""
        try:
            headers = {
                "Authorization": f"Bearer {self.proxycurl_api_key}",
                "Content-Type": "application/json"
            }
            endpoint = f"{self.PROXYCURL_BASE_URL}/v2/linkedin"
            params = {"url": linkedin_url}

            response_data, status_code = await cached_request(
                cache_service=self.cache_service,
                url=endpoint,
                params=params,
                headers=headers,
                ttl_hours=self.DEFAULT_CACHE_TTL
            )

            if status_code == 200:
                return ProxyCurlPersonProfile(**response_data)
            elif status_code == 429:
                raise RetryableError("Rate limit exceeded")
            else:
                logger.error(f"Failed to fetch profile for {linkedin_url}, status: {status_code}")
                return None

        except Exception as e:
            logger.error(f"Error fetching person profile: {str(e)}", exc_info=True)
            if isinstance(e, RetryableError):
                raise
            return None

    @with_retry(retry_config=PROXYCURL_RETRY_CONFIG, operation_name="search_employees")
    async def search_employees(
            self,
            company_url: str,
            role_pattern: Optional[str] = None,
            page_size: int = 5
    ) -> Optional[ProxyCurlSearchResponse]:
        """Search for company employees with optional role filtering."""
        try:
            headers = {
                "Authorization": f"Bearer {self.proxycurl_api_key}",
                "Content-Type": "application/json"
            }
            endpoint = f"{self.PROXYCURL_BASE_URL}/v2/linkedin/company/employees"

            params = {
                "url": company_url,
                "page_size": page_size,
                "enrich_profiles": "enrich"
            }
            if role_pattern:
                params["role_search"] = role_pattern

            response_data, status_code = await cached_request(
                cache_service=self.cache_service,
                url=endpoint,
                params=params,
                headers=headers,
                ttl_hours=self.DEFAULT_CACHE_TTL
            )

            if status_code == 200:
                return ProxyCurlSearchResponse(**response_data)
            elif status_code == 429:
                raise RetryableError("Rate limit exceeded")
            else:
                logger.error(f"Failed to search employees for {company_url}, status: {status_code}")
                return None

        except Exception as e:
            logger.error(f"Error searching employees: {str(e)}", exc_info=True)
            if isinstance(e, RetryableError):
                raise
            return None

    @with_retry(retry_config=PROXYCURL_RETRY_CONFIG, operation_name="get_company_profile")
    async def get_company_profile(self, linkedin_url: str) -> Optional[Dict[str, Any]]:
        """Fetch company profile data from ProxyCurl API."""
        try:
            headers = {
                "Authorization": f"Bearer {self.proxycurl_api_key}",
                "Content-Type": "application/json"
            }
            endpoint = f"{self.PROXYCURL_BASE_URL}/v2/linkedin/company"
            params = {"url": linkedin_url}

            response_data, status_code = await cached_request(
                cache_service=self.cache_service,
                url=endpoint,
                params=params,
                headers=headers,
                ttl_hours=self.DEFAULT_CACHE_TTL
            )

            if status_code == 200:
                return response_data
            elif status_code == 429:
                raise RetryableError("Rate limit exceeded")
            else:
                logger.error(f"Failed to fetch company profile for {linkedin_url}, status: {status_code}")
                return None

        except Exception as e:
            logger.error(f"Error fetching company profile: {str(e)}", exc_info=True)
            if isinstance(e, RetryableError):
                raise
            return None

    async def enrich_leads(self, leads: List[EnrichedLead]) -> List[EnrichedLead]:
        """Enrich multiple leads with ProxyCurl data."""
        enriched_leads: List[EnrichedLead] = []
        for lead in leads:
            try:
                linkedin_url = lead.linkedin_url
                if not linkedin_url:
                    logger.warning(f"Skipping proxycurl enrichment, no LinkedIn URL found for lead: {lead}")
                    enriched_leads.append(lead)
                    continue
                if not lead.organization or lead.organization.name:
                    logger.warning(f"Skipping proxycurl enrichment, Organization or name missing for lead: {lead}")
                    enriched_leads.append(lead)
                    continue

                proxycurl_lead: Optional[ProxyCurlPersonProfile] = await self.get_person_profile(linkedin_url)
                if not proxycurl_lead:
                    logger.warning(f"ProxyCurl profile not found for: {linkedin_url}, continue to next lead.")
                    enriched_leads.append(lead)
                    continue

                # Compute freshness date of current lead data and proxycurl data.
                # More fresh data will be preferred during merge.
                current_freshness_date: Optional[datetime] = lead.current_employment.get_start_date_datetime() if lead.current_employment else None
                proxycurl_freshness_date: Optional[datetime] = proxycurl_lead.get_latest_employment_start_date()

                # Find current employment that matches the best with current employment in the organization.
                current_organization_name = lead.organization.name
                proxycurl_current_employments = proxycurl_lead.get_current_employments()
                proxycurl_best_matched_employment: Optional[ProxyCurlPersonProfile.Experience] = self._best_organization_match(
                    linkedin_url=linkedin_url,
                    current_organization_name=current_organization_name,
                    proxycurl_current_employments=proxycurl_current_employments
                )

                if proxycurl_best_matched_employment:
                    # Proxycurl current employment organization matches current organization.
                    if proxycurl_freshness_date > current_freshness_date:
                        # Proxycurl data is fresher, let it take precedence.
                        lead.headline = proxycurl_lead.headline
                        lead.about = proxycurl_lead.summary
                        lead.current_employment = EnrichedLead.CurrentEmployment(
                            title=proxycurl_best_matched_employment.title,
                            organization_name=proxycurl_best_matched_employment.company,
                            description=proxycurl_best_matched_employment.description,
                            start_date=proxycurl_best_matched_employment.get_formatted_date(proxycurl_best_matched_employment.starts_at),
                            end_date=proxycurl_best_matched_employment.get_formatted_date(proxycurl_best_matched_employment.ends_at),
                            location=proxycurl_best_matched_employment.location,
                            apollo_organization_id=lead.current_employment.apollo_organization_id if lead.current_employment else None,
                            company_linkedin_profile_url=proxycurl_best_matched_employment.company_linkedin_profile_url,
                            logo_url=proxycurl_best_matched_employment.logo_url,
                            # Seniority, Department, Subdepartment and function are lost in this case.
                            # TODO: In the future, we should keep existing values of department etc. if they are still in the same function.
                        )
                        if proxycurl_lead.experiences and len(proxycurl_lead.experiences):
                            proxycurl_other_experiences = list(filter(lambda exp: exp.company != proxycurl_best_matched_employment.company, proxycurl_lead.experiences))
                            lead.other_employments = [
                                EnrichedLead.Employment(
                                    title=exp.title,
                                    organization_name=exp.company,
                                    current=exp.ends_at == None,
                                    description=exp.description,
                                    start_date=exp.get_formatted_date(exp.starts_at),
                                    end_date=exp.get_formatted_date(exp.ends_at),
                                    location=exp.location,
                                    company_linkedin_profile_url=exp.company_linkedin_profile_url,
                                    logo_url=exp.logo_url,
                                    # Apollo Organization ID is omitted here because it's hard to
                                    # extract from existing employments and not really needed for analysis.
                                )
                                for exp in proxycurl_other_experiences]

                        lead.location = EnrichedLead.Location(
                            city=proxycurl_lead.city,
                            state=proxycurl_lead.state,
                            country=proxycurl_lead.country,
                            country_full_name=proxycurl_lead.country_full_name
                        )
                    else:
                        # Proxycurl is stale. Keep majority of fields as is,
                        # we can still update description of each role from Proxycurl.
                        # Descriptions usually contain valuable information about tools,
                        # or background of the lead.
                        lead = self._update_employment_descriptions_from_proxycurl(lead=lead, proxycurl_lead=proxycurl_lead)

                else:
                    # Proxycurl current employment organization did not match with current organization.
                    if proxycurl_freshness_date > current_freshness_date:
                        # Proxycurl is fresher, this means the current enriched lead
                        # is not even in the current organization. Skip them.
                        logger.error(f"Skipping lead: {linkedin_url}, Proxycurl current employment:" +
                                     f"{proxycurl_best_matched_employment} and doesn't match current organization in lead: {current_organization_name}")
                        continue
                    else:
                        # Proxycurl is stale, keep existing fields as is. We can still update
                        # description of each role from Proxycurl.
                        # Descriptions usually contain valuable information about responsibilities, tools,
                        # or achievements in past employments.
                        lead = self._update_employment_descriptions_from_proxycurl(lead=lead, proxycurl_lead=proxycurl_lead)

                # Proxycurl fields that need to be merged regardless of freshness etc.
                lead.about = proxycurl_lead.summary
                lead.photo_url = proxycurl_lead.profile_pic_url
                lead.education = proxycurl_lead.education
                lead.certifications = proxycurl_lead.certifications
                lead.projects = proxycurl_lead.accomplishment_projects
                lead.publications = proxycurl_lead.accomplishment_publications
                lead.honor_awards = proxycurl_lead.accomplishment_honors_awards
                lead.groups = proxycurl_lead.groups
                lead.volunteer_work = proxycurl_lead.volunteer_work
                lead.recommendations = proxycurl_lead.recommendations
                lead.social_metrics = EnrichedLead.SocialMetrics(
                    connections=proxycurl_lead.connections,
                    follower_count=proxycurl_lead.follower_count
                )

                if lead.enrichment_info:
                    lead.enrichment_info.last_enriched_at = datetime.now(timezone.utc)
                    if lead.enrichment_info.enrichment_sources:
                        lead.enrichment_info.enrichment_sources.append("proxycurl")
                    else:
                        lead.enrichment_info.enrichment_sources = ["proxycurl"]
                    if lead.enrichment_info.data_quality:
                        lead.enrichment_info.data_quality.proxycurl_has_fresher_data = proxycurl_freshness_date > current_freshness_date
                    else:
                        lead.enrichment_info.data_quality = EnrichedLead.EnrichmentInfo.Quality(
                            has_detailed_employment=lead.current_employment and lead.other_employments and len(lead.other_employments) > 0,
                            proxycurl_has_fresher_data=proxycurl_freshness_date > current_freshness_date
                        )
                else:
                    lead.enrichment_info = EnrichedLead.EnrichmentInfo(
                        last_enriched_at=datetime.now(timezone.utc),
                        enrichment_sources=["proxycurl"],
                        data_quality=EnrichedLead.EnrichmentInfo.Quality(
                            has_detailed_employment=lead.current_employment and lead.other_employments and len(lead.other_employments) > 0,
                            proxycurl_has_fresher_data=proxycurl_freshness_date > current_freshness_date
                        )
                    )

                enriched_leads.append(lead)

            except Exception as e:
                logger.error(f"Error enriching lead: {str(e)}", exc_info=True)
                enriched_leads.append(lead)

        return enriched_leads

    def _best_organization_match(self, linkedin_url: str, current_organization_name: str, proxycurl_current_employments: List[ProxyCurlPersonProfile.Experience]) -> Optional[ProxyCurlPersonProfile.Experience]:
        """Finds the Proxycurl employment who organization name best matches the current organization name.
        If none of them match to a high degree, returns None.
        """
        if not proxycurl_current_employments:
            logger.warning(f"Proxycurl current employees are None for {linkedin_url}")
            return None
        employments_with_names_and_start_dates = list(filter(lambda emp: emp.company != None and emp.starts_at != None, proxycurl_current_employments))
        if len(employments_with_names_and_start_dates) == 0:
            logger.warning(f"None of the proxcurl current employments in {linkedin_url} have names or start dates: {proxycurl_current_employments}")
            return None

        employments_with_sequence_matches = [(emp, SequenceMatcher(emp.company, current_organization_name).ratio()) for emp in employments_with_names_and_start_dates]
        filter_cutoff = 0.7
        filtered_employments_with_sequence_matches = list(filter(lambda emp: emp[1] >= filter_cutoff, employments_with_sequence_matches))
        if len(filtered_employments_with_sequence_matches) == 0:
            logger.debug(f"None of the proxycurl current employment in {linkedin_url} were above name match cutoff: {filter_cutoff} : {employments_with_sequence_matches}")
            return None

        # Sort by descending order of sequence match score and then start date.
        # We do this since we can get multiple employments with the same company, and so the same score
        # but in these case the latest company should be returned.
        sorted_employments_with_sequence_matches = sorted(employments_with_sequence_matches, key=lambda e: (e[1], e[0].get_date_time(e[0].starts_at)), reverse=True)
        return sorted_employments_with_sequence_matches[0][0]

    def _update_employment_descriptions_from_proxycurl(self, lead: EnrichedLead, proxycurl_lead: ProxyCurlPersonProfile) -> EnrichedLead:
        """
        Update other employments in enriched lead with descriptions from Proxycurl.
        Descriptions usually contain valuable information about responsibilities, tools,
        or achievements in past employments.
        """
        if not lead.other_employments or len(lead.other_employments) == 0:
            # Nothing to update here.
            return lead
        if not proxycurl_lead.experiences or len(proxycurl_lead.experiences) == 0:
            # Nothing to update here.
            return lead

        sequence_match_cutoff = 0.7
        for emp in lead.other_employments:
            org_name = emp.organization_name
            if not org_name:
                continue
            for exp in proxycurl_lead.experiences:
                exp_org_name = exp.company
                if not exp_org_name:
                    continue
                if SequenceMatcher(org_name, exp_org_name).ratio() >= sequence_match_cutoff:
                    # Found experience, update relevant fields from Proxycurl.
                    emp.description = exp.description
                    emp.location = exp.location
                    emp.company_linkedin_profile_url = exp.company_linkedin_profile_url
                    emp.logo_url = exp.logo_url

        return lead
