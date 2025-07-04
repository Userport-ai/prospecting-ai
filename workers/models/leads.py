from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from models.common import UserportPydanticBaseModel
from datetime import datetime
from utils.loguru_setup import logger


class ProxyCurlSearchResponse(BaseModel):
    """Response from ProxyCurl employee search API."""
    employees: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    next_page: Optional[str] = None
    previous_page: Optional[str] = None


class DateInfo(BaseModel):
    day: Optional[int] = None
    month: Optional[int] = None
    year: Optional[int] = None


class Education(BaseModel):
    school: Optional[str] = None
    degree_name: Optional[str] = None
    field_of_study: Optional[str] = None
    starts_at: Optional[DateInfo] = None
    ends_at: Optional[DateInfo] = None
    activities_and_societies: Optional[str] = None
    grade: Optional[str] = None
    logo_url: Optional[str] = None
    school_linkedin_profile_url: Optional[str] = None
    school_facebook_profile_url: Optional[str] = None
    description: Optional[str] = None


class Certification(BaseModel):
    name: Optional[str] = None
    authority: Optional[str] = None
    license_number: Optional[str] = None
    url: Optional[str] = None
    starts_at: Optional[DateInfo] = None
    ends_at: Optional[DateInfo] = None


class Publication(UserportPydanticBaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    publisher: Optional[str] = None
    published_on: Optional[DateInfo] = None


class HonorAward(UserportPydanticBaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    issuer: Optional[str] = None
    issued_on: Optional[DateInfo] = None


class Project(BaseModel):
    title: str
    description: Optional[str] = None
    url: Optional[str] = None
    starts_at: Optional[DateInfo] = None
    ends_at: Optional[DateInfo] = None


class LinkedInGroup(BaseModel):
    profile_pic_url: Optional[str] = None
    name: Optional[str] = None
    url: Optional[str] = None


class ProxyCurlPersonProfile(UserportPydanticBaseModel):
    class Experience(BaseModel):
        company: Optional[str] = None
        title: Optional[str] = None
        description: Optional[str] = None
        location: Optional[str] = None
        starts_at: Optional[DateInfo] = None
        ends_at: Optional[DateInfo] = None
        company_linkedin_profile_url: Optional[str] = None
        company_facebook_profile_url: Optional[str] = None
        logo_url: Optional[str] = None

        def get_formatted_date(self, date_info: Optional[DateInfo]) -> Optional[str]:
            """Returns date in YYYY-MM-DD format as a string."""
            if not date_info:
                return None
            year = date_info.year
            month = date_info.month
            day = date_info.day
            if not year or not month or not day:
                return None
            return f"{year:04d}-{month:02d}-{day:02d}"

        def get_date_time(self, date_info: Optional[DateInfo]) -> Optional[datetime]:
            if not date_info:
                return None

            return datetime(date_info.year, date_info.month, date_info.day)

    class Activity(BaseModel):
        title: Optional[str] = None
        link: Optional[str] = None
        activity_status: Optional[str] = None

    public_identifier: Optional[str] = Field(
        default=None, description="The vanity identifier of the LinkedIn profile. The vanity identifier comes after the /in/ part of the LinkedIn Profile URL in the following format: https://www.linkedin.com/in/<_identifier>")
    profile_pic_url: Optional[str] = Field(
        default=None, description="A temporary link to the user's profile picture that is valid for 30 minutes. The temporal nature of the link is by design to prevent having Proxycurl be the mirror for the images. The developer is expected to handle these images by downloading the image and re-hosting the image.")
    background_cover_image_url: Optional[str] = Field(default=None, description="Similar temporary URL as above.")
    full_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    follower_count: Optional[int] = None
    occupation: Optional[str] = None
    headline: Optional[str] = None
    summary: Optional[str] = None
    country: Optional[str] = None
    country_full_name: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    experiences: Optional[List[Experience]] = Field(default=None, description="History of employment experiences.")
    education: Optional[List[Education]] = Field(default=None, description="Education background of the user.")
    connections: Optional[int] = None

    languages_and_proficiencies: Optional[List[Dict[str, Any]]] = None
    accomplishment_organisations: Optional[List[Dict[str, Any]]] = None
    accomplishment_publications: Optional[List[Publication]] = None
    accomplishment_honors_awards: Optional[List[HonorAward]] = None
    accomplishment_patents: Optional[List[Dict[str, Any]]] = None
    accomplishment_courses: Optional[List[Dict[str, Any]]] = None
    accomplishment_projects: Optional[List[Project]] = None
    accomplishment_test_scores: Optional[List[Dict[str, Any]]] = None
    volunteer_work: Optional[List[Dict[str, Any]]] = None
    certifications: Optional[List[Certification]] = None
    activities: Optional[List[Activity]] = Field(default=None, description="Not guaranteed to return.")
    similarly_named_profiles: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    articles: Optional[List[Dict[str, Any]]] = Field(default=None, description="Not guaranteed to return.")
    groups: Optional[List[LinkedInGroup]] = Field(default=None, description="A list of LinkedIn groups that this user is a part of.")
    recommendations: Optional[List[str]] = Field(default=None, description="List of recommendations made by other users about this profile.")

    def get_latest_employment_start_date(self) -> Optional[datetime]:
        """Returns datetime object of latest employment start date."""
        if not self.experiences or len(self.experiences) == 0:
            return None
        experiences_with_start_date = list(filter(lambda exp: exp.starts_at is not None, self.experiences))
        if len(experiences_with_start_date) == 0:
            return None
        start_dates: List[datetime] = [datetime(exp.starts_at.year, exp.starts_at.month, exp.starts_at.day) for exp in experiences_with_start_date]
        return sorted(start_dates, reverse=True)[0]

    def get_current_employments(self) -> Optional[List[Experience]]:
        """Returns current employment from list of experiences.
        Since a person may have multiple roles at once (CEO, Investor, member of non profit etc.),
        we return a list.
        """
        if not self.experiences:
            return None
        return list(filter(lambda e: e.ends_at == None, self.experiences))


class ApolloLead(UserportPydanticBaseModel):
    """Lead data from Apollo."""
    class Employment(UserportPydanticBaseModel):
        title: Optional[str] = None
        organization_name: Optional[str] = None
        description: Optional[str] = None
        start_date: Optional[str] = Field(default=None, description="Format: 2024-03-01 i.e. YYYY-MM-DD")
        end_date: Optional[str] = Field(default=None, description="Format: 2024-03-01 i.e. YYYY-MM-DD")
        current: Optional[bool] = Field(default=None, description="Whether the employment is current, returned by Apollo in API response. None means not ended.")

        organization_id: Optional[str] = Field(default=None, description="Apollo Organization ID")

    class Technology(BaseModel):
        """Model for technology stack items"""
        category: Optional[str] = None
        name: Optional[str] = None
        uid: Optional[str] = None

    class FundingEvent(BaseModel):
        """Model for funding events"""
        amount: Optional[str] = None
        currency: Optional[str] = None
        date: Optional[datetime] = None
        id: Optional[str] = None
        investors: Optional[str] = None
        news_url: Optional[str] = None
        type: Optional[str] = None

    class Organization(BaseModel):
        """Enhanced organization model with all fields optional"""
        id: Optional[str] = None
        name: Optional[str] = None
        alexa_ranking: Optional[int] = None
        angellist_url: Optional[str] = None
        annual_revenue: Optional[int] = None
        annual_revenue_printed: Optional[str] = None
        blog_url: Optional[str] = None

        # Location information
        city: Optional[str] = None
        state: Optional[str] = None
        country: Optional[str] = None
        postal_code: Optional[str] = None
        street_address: Optional[str] = None
        raw_address: Optional[str] = None

        # Web presence
        website_url: Optional[str] = None
        primary_domain: Optional[str] = None
        linkedin_url: Optional[str] = None
        linkedin_uid: Optional[str] = None
        facebook_url: Optional[str] = None
        twitter_url: Optional[str] = None
        crunchbase_url: Optional[str] = None

        # Company details
        founded_year: Optional[int] = None
        estimated_num_employees: Optional[int] = None
        industry: Optional[str] = None
        industries: Optional[List[str]] = None
        secondary_industries: Optional[List[str]] = None
        industry_tag_hash: Optional[Dict[str, str]] = None
        industry_tag_id: Optional[str] = None

        # Technologies and keywords
        current_technologies: Optional[List["ApolloLead.Technology"]] = None
        technology_names: Optional[List[str]] = None
        keywords: Optional[List[str]] = None
        languages: Optional[List[str]] = None

        # Description and SEO
        short_description: Optional[str] = None
        seo_description: Optional[str] = None

        # Funding information
        funding_events: Optional[List["ApolloLead.FundingEvent"]] = None
        total_funding: Optional[int] = None
        total_funding_printed: Optional[str] = None
        latest_funding_round_date: Optional[datetime] = None
        latest_funding_stage: Optional[str] = None

        # Contact information
        phone: Optional[str] = None
        primary_phone: Optional[Any] = None

        # Organization structure
        num_suborganizations: Optional[int] = None
        suborganizations: Optional[List[str]] = None
        owned_by_organization_id: Optional[str] = None
        retail_location_count: Optional[int] = None

        # Org chart related
        org_chart_removed: Optional[bool] = None
        org_chart_root_people_ids: Optional[List[str]] = None
        org_chart_sector: Optional[str] = None
        org_chart_show_department_filter: Optional[bool] = None

        # Stock market information
        publicly_traded_symbol: Optional[str] = None
        publicly_traded_exchange: Optional[str] = None

        # Misc
        snippets_loaded: Optional[bool] = None
        logo_url: Optional[str] = None

        class Config:
            """Pydantic configuration"""
            arbitrary_types_allowed = True
            json_encoders = {
                datetime: lambda v: v.isoformat() if v else None
            }

    id: Optional[str] = Field(default=None, description="Apollo ID of the lead")
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    name: Optional[str] = None
    linkedin_url: Optional[str] = None
    title: Optional[str] = None
    email_status: Optional[str] = Field(default=None, description="e.g. unavailable, extrapolated, verified etc.")
    photo_url: Optional[str] = None
    twitter_url: Optional[str] = None
    github_url: Optional[str] = None
    facebook_url: Optional[str] = None
    extrapolated_email_confidence: Optional[float] = None
    headline: Optional[str] = None
    email: Optional[str] = Field(default=None, description="When not enriched, it is email_not_unlocked@domain.com otherwise email of lead.")
    organization_id: Optional[str] = None
    employment_history: Optional[List[Employment]] = None
    state: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    organization: Optional[Organization] = None
    departments: Optional[List[str]] = Field(default=None, description="e.g. master_engineering_technical, master_sales, master_operations etc.")
    subdepartments: Optional[List[str]] = Field(default=None, description="e.g. engineering_technical, software_development etc.")
    seniority: Optional[str] = Field(default=None, description="e.g. entry, senior, manager, head, vp, director, c_suite etc.")
    functions: Optional[List[str]] = Field(default=None, description="e.g. business development, consulting, human_resources, engineering etc.")


class SearchApolloLeadsResponse(UserportPydanticBaseModel):
    """Apollo Leads search response."""
    class Pagination(UserportPydanticBaseModel):
        page: Optional[int] = None
        per_page: Optional[int] = None
        total_entries: Optional[int] = None
        total_pages: Optional[int] = None

    pagination: Optional[Pagination] = None
    people: Optional[List[ApolloLead]] = None
    contacts: Optional[List[ApolloLead]] = Field(default=None, description="Same as people, just that these people have been added as contacts to Apollo org associated with the account.")

    def get_leads(self) -> List[ApolloLead]:
        """Returns all leads (people + contacts) from the given response."""
        all_leads = []
        if self.people:
            all_leads.extend(self.people)
        if self.contacts:
            all_leads.extend(self.contacts)
        return all_leads


class EnrichedLead(UserportPydanticBaseModel):
    class CurrentEmployment(UserportPydanticBaseModel):
        """Lead's current employment."""
        title: Optional[str] = None
        organization_name: Optional[str] = None
        description: Optional[str] = None
        start_date: Optional[str] = Field(default=None, description="Format: 2024-03-01 i.e. YYYY-MM-DD")
        end_date: Optional[str] = Field(default=None, description="Format: 2024-03-01 i.e. YYYY-MM-DD")
        location: Optional[str] = None
        seniority: Optional[str] = Field(default=None, description="e.g. entry, senior, manager, head, vp, director, c_suite etc.")
        departments: Optional[List[str]] = Field(default=None, description="e.g. master_engineering_technical, master_sales, master_operations etc.")
        subdepartments: Optional[List[str]] = Field(default=None, description="e.g. engineering_technical, software_development etc.")
        functions: Optional[List[str]] = Field(default=None, description="Apollo functions e.g. business development, consulting, human_resources, engineering etc.")

        apollo_organization_id: Optional[str] = Field(default=None, description="Apollo Organization ID")
        company_linkedin_profile_url: Optional[str] = None
        logo_url: Optional[str] = None

        def get_start_date_datetime(self) -> Optional[datetime]:
            if not self.start_date:
                return None
            return datetime.strptime(self.start_date, "%Y-%m-%d")

    class Employment(UserportPydanticBaseModel):
        title: Optional[str] = None
        organization_name: Optional[str] = None
        current: Optional[bool] = Field(default=None, description="Whether the employment is current, returns True if so and False otherwise.")
        description: Optional[str] = None
        start_date: Optional[str] = Field(default=None, description="Format: 2024-03-01 i.e. YYYY-MM-DD")
        end_date: Optional[str] = Field(default=None, description="Format: 2024-03-01 i.e. YYYY-MM-DD")
        location: Optional[str] = None

        apollo_organization_id: Optional[str] = Field(default=None, description="Apollo Organization ID")
        company_linkedin_profile_url: Optional[str] = None
        logo_url: Optional[str] = None

    class Organization(UserportPydanticBaseModel):
        name: Optional[str] = None
        website_url: Optional[str] = None
        linkedin_url: Optional[str] = None
        founded_year: Optional[int] = None
        primary_domain: Optional[str] = None

        twitter_url: Optional[str] = None
        facebook_url: Optional[str] = None
        logo_url: Optional[str] = None
        alexa_ranking: Optional[int] = None

        apollo_organization_id: Optional[str] = Field(default=None, description="Apollo organization ID.")
        linkedin_uid: Optional[str] = Field(default=None, description="LinkedIn Unique ID.")

    class Location(UserportPydanticBaseModel):
        city: Optional[str] = None
        state: Optional[str] = None
        country: Optional[str] = None
        country_full_name: Optional[str] = None

    class ContactInfo(UserportPydanticBaseModel):
        email: Optional[str] = None
        email_status: Optional[str] = Field(default=None, description="e.g. unavailable, extrapolated, verified etc.")
        extrapolated_email_confidence: Optional[float] = Field(default=None, description="e.g. 0.54")
        phone_numbers: Optional[List[str]] = None

    class SocialProfiles(UserportPydanticBaseModel):
        linkedin_url: Optional[str] = None
        twitter_url: Optional[str] = None
        facebook_url: Optional[str] = None
        github_url: Optional[str] = None

    class SocialMetrics(UserportPydanticBaseModel):
        connections: Optional[int] = None
        follower_count: Optional[int] = None

    class EnrichmentInfo(UserportPydanticBaseModel):
        class Quality(UserportPydanticBaseModel):
            has_detailed_employment: Optional[bool] = None

        last_enriched_at: Optional[str] = Field(default=None, description="Format: YYYY-MM-DD")
        enrichment_sources: Optional[List[str]] = None
        data_quality: Optional[Quality] = None

    id: Optional[str] = Field(default=None, description="ID of the field, right now same as Apollo ID.")
    linkedin_url: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    name: Optional[str] = None
    headline: Optional[str] = Field(default=None, description="LinkedIn profile headling")
    about: Optional[str] = Field(default=None, description="About Section in LinkedIn profile.")

    # Current role and history
    current_employment: Optional[CurrentEmployment] = Field(default=None)
    other_employments: Optional[List[Employment]] = Field(default=None)
    organization: Optional[Organization] = None

    contact_info: Optional[ContactInfo] = None
    location: Optional[Location] = Field(default=None, description="Lead's location details.")
    photo_url: Optional[str] = None
    social_profiles: Optional[SocialProfiles] = Field(default=None)
    social_metrics: Optional[SocialMetrics] = None

    # Education and skills
    education: Optional[List[Education]] = Field(default=None)
    projects: Optional[List[Project]] = Field(default=None)
    publications: Optional[List[Publication]] = Field(default=None)
    groups: Optional[List[LinkedInGroup]] = Field(default=None)
    certifications: Optional[List[Certification]] = Field(default=None)
    honor_awards: Optional[List[HonorAward]] = Field(default=None)
    volunteer_work: Optional[List[Dict[str, Any]]] = Field(default=None)
    recommendations: Optional[List[str]] = Field(default=None)

    enrichment_info: Optional[EnrichmentInfo] = None

    def get_lead_evaluation_serialization_fields(self) -> Dict[str, Any]:
        """Fields that will be used to serialize lead during evaluation."""
        return {
            "id": True,
            "name": True,
            "headline": True,
            "about": True,
            "current_employment": {
                "title": True,
                "organization_name": True,
                "description": True,
                "start_date": True,
                "seniority": True,
                "departments": True,
                "subdepartments": True,
                "functions": True,
                "location": True
            },
            "other_employments": {
                "__all__": {
                    "title": True,
                    "organization_name": True,
                    "description": True,
                    "start_date": True,
                    "end_date": True,
                    "location": True
                }
            },
            "location": {
                "city": True,
                "state": True,
                "country": True
            },
            "publications": {
                "__all__": {
                    "name": True,
                    "description": True,
                    "publisher": True,
                    "published_on": True
                }
            },
            "projects": {
                "__all__": {
                    "title": True,
                    "description": True,
                    "starts_at": True,
                    "ends_at": True
                }
            },
            "groups": {
                "__all__": {
                    "name": True
                }
            },
            "certifications": {
                "__all__": {
                    "name": True,
                    "authority": True,
                    "starts_at": True,
                    "ends_at": True
                }
            },
            "honor_awards": True,
            "recommendations": True
        }


class EvaluatedLead(UserportPydanticBaseModel):
    """Final evaluated Lead for fit."""
    id: Optional[str] = Field(default=None, description="Same ID as in Enriched Lead.")
    fit_score: Optional[float] = Field(default=None, description="Number between 0-100 (inclusive) where 0 indicates no fit and 100 indicates excellent fit")
    rationale: Optional[str] = None,
    matching_signals: Optional[List[str]] = None
    persona_match: Optional[str] = None
    # internal fields
    internal_analysis: Optional[str] = None


class EvaluateLeadsResult(UserportPydanticBaseModel):
    """Result of Evaluating Leads for fit."""
    evaluated_leads: Optional[List[EvaluatedLead]] = None
