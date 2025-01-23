from datetime import datetime
import os
import logging
import asyncio
import httpx
from typing import List, Optional, Dict, Any

from models.leads import ProxyCurlEmployeeProfile, ProxyCurlSearchResponse
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
    async def get_person_profile(self, linkedin_url: str) -> Optional[ProxyCurlEmployeeProfile]:
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
                return ProxyCurlEmployeeProfile(**response_data)
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

    async def enrich_leads(self, leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enrich multiple leads with ProxyCurl data."""
        enriched_leads = []
        for lead in leads:
            try:
                linkedin_url = lead.get('linkedin_url')
                if not linkedin_url:
                    logger.warning(f"No LinkedIn URL found for lead {lead.get('lead_id', 'unknown')}")
                    enriched_leads.append(lead)
                    continue

                profile = await self.get_person_profile(linkedin_url)
                if not profile:
                    enriched_leads.append(lead)
                    continue

                # Merge profile data with lead data, preferring ProxyCurl data
                enriched_lead = lead.copy()
                profile_dict = profile.dict(exclude_none=True)

                # Preserve all original fields
                original_fields = [
                    'lead_id', 'linkedin_url', 'contact_info', 'data_quality',
                    'engagement_data', 'company', 'social_profiles'
                ]
                for field in original_fields:
                    if field in lead:
                        enriched_lead[field] = lead[field]

                # Apollo fields that should be preserved as-is
                apollo_preserve_fields = [
                    'lead_id', 'id', 'email', 'email_status', 'email_domain_catchall',
                    'extrapolated_email_confidence', 'revealed_for_current_team',
                    'departments', 'functions', 'subdepartments', 'intent_strength',
                    'show_intent', 'existence_level'
                ]

                for field in apollo_preserve_fields:
                    if field in lead:
                        enriched_lead[field] = lead[field]

                # Direct field mappings (prefer ProxyCurl data)
                field_mappings = {
                    'full_name': 'name',
                    'first_name': 'first_name',
                    'last_name': 'last_name',
                    'headline': 'headline',
                    'occupation': 'title',
                    'profile_pic_url': 'photo_url',
                    'public_identifier': 'linkedin_uid'
                }

                # Update basic fields
                for pc_field, apollo_field in field_mappings.items():
                    if profile_dict.get(pc_field):
                        enriched_lead[apollo_field] = profile_dict[pc_field]

                # Merge location data
                if any(profile_dict.get(f) for f in ['city', 'state', 'country']):
                    enriched_lead.update({
                        'city': profile_dict.get('city') or lead.get('city'),
                        'state': profile_dict.get('state') or lead.get('state'),
                        'country': profile_dict.get('country') or lead.get('country'),
                        'country_full_name': profile_dict.get('country_full_name')
                    })

                # Merge current role (preserve Apollo's structured data)
                existing_role = lead.get('employment_history', [{}])[0] if lead.get('employment_history') else {}
                current_experience = next((exp for exp in profile_dict.get('experiences', []) if not exp.get('ends_at')), {})

                if current_experience or existing_role:
                    enriched_lead['current_role'] = {
                        'title': current_experience.get('title') or existing_role.get('title'),
                        'company': current_experience.get('company') or existing_role.get('organization_name'),
                        'description': current_experience.get('description'),
                        'start_date': current_experience.get('starts_at'),
                        'end_date': current_experience.get('ends_at'),
                        'current': existing_role.get('current', True),
                        'department': lead.get('departments', [None])[0],
                        'seniority': lead.get('seniority'),
                        'functions': lead.get('functions', []),
                        'subdepartments': lead.get('subdepartments', [])
                    }

                # Merge organization/company data
                enriched_lead['organization'] = {
                    **lead.get('organization', {}),
                    'linkedin_url': profile_dict.get('company_linkedin_profile_url') or lead.get('organization', {}).get('linkedin_url')
                }

                # Merge employment history
                if profile_dict.get('experiences'):
                    enriched_lead['employment_history'] = [
                        {
                            'title': exp.get('title'),
                            'organization_name': exp.get('company'),
                            'description': exp.get('description'),
                            'location': exp.get('location'),
                            'start_date': exp.get('starts_at'),
                            'end_date': exp.get('ends_at'),
                            'current': not exp.get('ends_at', True),
                            'company_linkedin_url': exp.get('company_linkedin_profile_url')
                        }
                        for exp in profile_dict['experiences']
                    ]

                # Add education history
                if profile_dict.get('education'):
                    enriched_lead['education'] = [
                        {
                            'school': edu.get('school'),
                            'degree': edu.get('degree_name'),
                            'field_of_study': edu.get('field_of_study'),
                            'start_date': edu.get('starts_at'),
                            'end_date': edu.get('ends_at'),
                            'activities': edu.get('activities_and_societies'),
                            'grade': edu.get('grade'),
                            'school_linkedin_url': edu.get('school_linkedin_profile_url')
                        }
                        for edu in profile_dict['education']
                    ]

                # Add certifications
                if profile_dict.get('certifications'):
                    enriched_lead['certifications'] = profile_dict['certifications']

                # Add social profiles
                enriched_lead['social_profiles'] = {
                    'linkedin_url': lead.get('linkedin_url'),
                    'facebook_url': lead.get('facebook_url') or profile_dict.get('facebook_url'),
                    'twitter_url': lead.get('twitter_url') or profile_dict.get('twitter_url'),
                    'github_url': lead.get('github_url') or profile_dict.get('github_url')
                }

                # Add additional ProxyCurl data if available
                if profile_dict.get('summary'):
                    enriched_lead['summary'] = profile_dict['summary']

                if profile_dict.get('accomplishment_projects'):
                    enriched_lead['projects'] = profile_dict['accomplishment_projects']

                if profile_dict.get('groups'):
                    enriched_lead['groups'] = profile_dict['groups']

                if profile_dict.get('volunteer_work'):
                    enriched_lead['volunteer_work'] = profile_dict['volunteer_work']

                if profile_dict.get('recommendations'):
                    enriched_lead['recommendations'] = profile_dict['recommendations']

                if profile_dict.get('activities'):
                    enriched_lead['activities'] = profile_dict['activities']

                # Add social metrics
                enriched_lead['social_metrics'] = {
                    'connections': profile_dict.get('connections'),
                    'follower_count': profile_dict.get('follower_count'),
                }

                # Add enrichment metadata
                enriched_lead['enrichment_info'] = {
                    'last_enriched': datetime.utcnow().isoformat(),
                    'enrichment_source': 'proxycurl',
                    'data_quality': {
                        'has_detailed_employment': bool(profile_dict.get('experiences')),
                        'has_education': bool(profile_dict.get('education')),
                        'has_summary': bool(profile_dict.get('summary')),
                    }
                }

                # Merge location data
                if any(profile_dict.get(f) for f in ['city', 'state', 'country']):
                    enriched_lead['location'] = {
                        **enriched_lead.get('location', {}),
                        'city': profile_dict.get('city') or enriched_lead.get('location', {}).get('city'),
                        'state': profile_dict.get('state') or enriched_lead.get('location', {}).get('state'),
                        'country': profile_dict.get('country') or enriched_lead.get('location', {}).get('country'),
                        'country_full_name': profile_dict.get('country_full_name')
                    }

                # Merge current role while preserving Apollo-specific fields
                if profile_dict.get('experiences'):
                    current_experience = next((exp for exp in profile_dict['experiences'] if not exp.get('ends_at')), {})
                    if current_experience:
                        existing_role = enriched_lead.get('current_role', {})
                        enriched_lead['current_role'] = {
                            'title': current_experience.get('title') or existing_role.get('title'),
                            'company': current_experience.get('company') or existing_role.get('company'),
                            'description': current_experience.get('description'),
                            'start_date': current_experience.get('starts_at'),
                            'location': current_experience.get('location'),
                            # Preserve Apollo-specific fields
                            'department': existing_role.get('department'),
                            'seniority': existing_role.get('seniority'),
                            'functions': existing_role.get('functions', []),
                            'subdepartments': existing_role.get('subdepartments', [])
                        }

                # Merge professional info
                enriched_lead['professional_info'] = {
                    **enriched_lead.get('professional_info', {}),
                    'skills': list(set(profile_dict.get('skills', []) + enriched_lead.get('professional_info', {}).get('skills', []))),
                    'languages': list(set(profile_dict.get('languages', []) + enriched_lead.get('professional_info', {}).get('languages', []))),
                    'certifications': profile_dict.get('certifications', []) or enriched_lead.get('professional_info', {}).get('certifications', [])
                }

                # Merge social presence and profiles
                enriched_lead['social_presence'] = {
                    **enriched_lead.get('social_presence', {}),
                    'connections': profile_dict.get('connections') or enriched_lead.get('social_presence', {}).get('connections'),
                    'follower_count': profile_dict.get('follower_count') or enriched_lead.get('social_presence', {}).get('follower_count'),
                    'profile_pic_url': profile_dict.get('profile_pic_url') or enriched_lead.get('social_presence', {}).get('profile_pic_url')
                }

                # Preserve and enhance social profiles
                enriched_lead['social_profiles'] = {
                    **enriched_lead.get('social_profiles', {}),
                    'linkedin_url': profile_dict.get('linkedin_url') or enriched_lead.get('social_profiles', {}).get('linkedin_url'),
                    'twitter_url': profile_dict.get('twitter_url') or enriched_lead.get('social_profiles', {}).get('twitter_url'),
                    'facebook_url': profile_dict.get('facebook_url') or enriched_lead.get('social_profiles', {}).get('facebook_url'),
                    'github_url': profile_dict.get('github_url') or enriched_lead.get('social_profiles', {}).get('github_url')
                }

                # Merge career history (preferring ProxyCurl's more detailed data)
                if profile_dict.get('experiences'):
                    enriched_lead['experience_history'] = [
                        {
                            'title': exp.get('title'),
                            'company': exp.get('company'),
                            'description': exp.get('description'),
                            'location': exp.get('location'),
                            'start_date': exp.get('starts_at'),
                            'end_date': exp.get('ends_at'),
                            'company_linkedin_url': exp.get('company_linkedin_profile_url')
                        }
                        for exp in profile_dict['experiences']
                    ]

                # Merge education (preferring ProxyCurl's more detailed data)
                if profile_dict.get('education'):
                    enriched_lead['education'] = [
                        {
                            'degree': edu.get('degree_name'),
                            'field_of_study': edu.get('field_of_study'),
                            'school': edu.get('school'),
                            'start_date': edu.get('starts_at'),
                            'end_date': edu.get('ends_at'),
                            'description': edu.get('description')
                        }
                        for edu in profile_dict['education']
                    ]

                # Add additional ProxyCurl-specific data
                if profile_dict.get('groups'):
                    enriched_lead['groups'] = profile_dict['groups']

                if profile_dict.get('accomplishment_projects'):
                    enriched_lead['projects'] = profile_dict['accomplishment_projects']

                if profile_dict.get('accomplishment_publications'):
                    enriched_lead['publications'] = profile_dict['accomplishment_publications']

                if profile_dict.get('volunteer_work'):
                    enriched_lead['volunteer_work'] = profile_dict['volunteer_work']

                # Add source and timestamp information
                enriched_lead['enrichment_info'] = {
                    'last_enriched': datetime.utcnow().isoformat(),
                    'enrichment_source': 'proxycurl'
                }

                enriched_leads.append(enriched_lead)

            except Exception as e:
                logger.error(f"Error enriching lead: {str(e)}", exc_info=True)
                enriched_leads.append(lead)

        return enriched_leads
