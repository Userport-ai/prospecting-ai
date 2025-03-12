from typing import List, Optional, Dict, Any
from datetime import datetime
from models.common import UserportPydanticBaseModel
from pydantic import Field
from enum import StrEnum
from utils.loguru_setup import logger

# ------------RECENT DEVELOPMENTS------------


class WebSearchResult(UserportPydanticBaseModel):
    """Account recent development from Web Search results."""
    source: Optional[str] = Field(default=None, description="Jina, Company Website, Google etc.")
    url: Optional[str] = Field(default=None)
    type: Optional[str] = Field(default=None, description="Company Update, Parntership etc.")
    date: Optional[str] = Field(default=None)
    title: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)


class LinkedInPost(UserportPydanticBaseModel):
    """LinkedIn Post associated with a given account. Based on Brightdata's LinkedIn Post schema."""
    class TaggedEntity(UserportPydanticBaseModel):
        name: Optional[str] = Field(default=None)
        link: Optional[str] = Field(default=None, description="LinkedIn profile of person or company.")

    title: Optional[str] = Field(default=None, description="Likely name of account e.g. Lunos, Zoom etc.")
    text: Optional[str] = Field(default=None)
    time: Optional[str] = Field(default=None, description="Examples: 6d Edited, 1w etc.")
    date: Optional[datetime] = Field(default=None, description="Same as 'time' field but displayed in ISO format, Example:  2024-12-25T10:06:52.933Z")
    post_url: Optional[str] = Field(default=None)
    post_id: Optional[str] = Field(default=None)
    images: Optional[List[str]] = Field(default=None, description="URLs of images in Post.")
    videos: Optional[List[str]] = Field(default=None, description="URLs of videos in Post.")
    tagged_companies: Optional[List[TaggedEntity]] = Field(default=None)
    tagged_people: Optional[List[TaggedEntity]] = Field(default=None)
    likes_count: Optional[int] = Field(default=None)
    comments_count: Optional[int] = Field(default=None)


class RecentDevelopments(UserportPydanticBaseModel):
    """
    Recent developments associated with the given Account.
    """
    linkedin_posts:  Optional[List[LinkedInPost]] = Field(default=None)
    web_search_results: Optional[List[WebSearchResult]] = Field(default=None)


# ------------FINANCIALS------------


class PrivateFundingDetails(UserportPydanticBaseModel):
    """Private Funding Details associated with the Account."""
    class TotalFunding(UserportPydanticBaseModel):
        amount: Optional[float] = Field(default=None)
        currency: Optional[str] = Field(default=None)
        as_of_date: Optional[str] = Field(default=None)

    class FundingRound(UserportPydanticBaseModel):
        class Valuation(UserportPydanticBaseModel):
            amount: Optional[float] = Field(default=None)
            currency: Optional[str] = Field(default=None)
            type: Optional[str] = Field(default=None)

        series: Optional[str] = Field(default=None)
        amount: Optional[float] = Field(default=None)
        currency: Optional[str] = Field(default=None)
        date: Optional[str] = Field(default=None)
        lead_investors: Optional[List[str]] = Field(default=None)
        other_investors: Optional[List[str]] = Field(default=None)
        valuation: Optional[Valuation] = Field(default=None)

    total_funding: Optional[TotalFunding] = Field(default=None)
    funding_rounds: Optional[List[FundingRound]] = Field(default=None)


class PublicFinancials(UserportPydanticBaseModel):
    """Public Financial Details associated with the Account."""
    class StockDetails(UserportPydanticBaseModel):
        class MarketCap(UserportPydanticBaseModel):
            value: Optional[float] = Field(default=None)
            currency: Optional[str] = Field(default=None)
            as_of_date: Optional[str] = Field(default=None)

        exchange: Optional[str] = Field(default=None)
        ticker: Optional[str] = Field(default=None)
        market_cap: Optional[MarketCap] = Field(default=None)

    class FinancialMetrics(UserportPydanticBaseModel):
        class Revenue(UserportPydanticBaseModel):
            value: Optional[float] = Field(default=None)
            currency: Optional[str] = Field(default=None)
            period: Optional[str] = Field(default=None)

        class NetIncome(UserportPydanticBaseModel):
            value: Optional[float] = Field(default=None)
            currency: Optional[str] = Field(default=None)
            period: Optional[str] = Field(default=None)

    stock_details: Optional[StockDetails] = Field(default=None)
    financial_metrics: Optional[FinancialMetrics] = Field(default=None)


class Financials(UserportPydanticBaseModel):
    """Financials (Public/Private) associated with an Account."""
    type: Optional[str] = Field(default=None, description="private or public.")
    public_data: Optional[PublicFinancials] = Field(default=None)
    private_data: Optional[PrivateFundingDetails] = Field(default=None)

# ------------BASE ENRICHMENT------------


class BrightDataAccount(UserportPydanticBaseModel):
    """Bright Data account returned as part of data collection process."""
    class Input(UserportPydanticBaseModel):
        url: str = Field(...)

    class Funding(UserportPydanticBaseModel):
        last_round_date: Optional[datetime] = Field(default=None)
        last_round_type: Optional[str] = Field(default=None)
        rounds: Optional[int] = Field(default=None)
        last_round_raised: Optional[str] = Field(default=None)

    input: Input = Field(...)
    id: Optional[str] = Field(default=None)
    name: Optional[str] = Field(default=None)
    employees_in_linkedin: Optional[int] = Field(default=None)
    about: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)
    specialties: Optional[str] = Field(default=None)
    company_size: Optional[str] = Field(default=None)
    organization_type: Optional[str] = Field(default=None, description="Privately held, Public Company etc.")
    industries: Optional[str] = Field(default=None)
    website: Optional[str] = Field(default=None)
    crunchbase_url: Optional[str] = Field(default=None)
    founded: Optional[int] = Field(default=None)
    headquarters: Optional[str] = Field(default=None)
    logo: Optional[str] = Field(default=None)
    url: Optional[str] = Field(default=None)  # LinkedIn URL of the Account.
    slogan: Optional[str] = Field(default=None)
    funding: Optional[Funding] = Field(default=None)
    investors: Optional[List[str]] = Field(default=None)
    formatted_locations: Optional[List[str]] = Field(default=None)
    country_codes_array: Optional[List[str]] = Field(default=None)
    timestamp: Optional[datetime] = Field(default=None)

    # LinkedIn Posts from the Account.
    updates: Optional[List[LinkedInPost]] = Field(default=None)

    # In case the page is invalid, these fields are populated.
    warning: Optional[str] = Field(default=None, description="Example warning text: 4XX page - dead page")
    warning_code: Optional[str] = Field(default=None, description="Example code: dead_page")


class SearchApolloOrganizationsResponse(UserportPydanticBaseModel):
    """Apollo Leads search response."""
    class Pagination(UserportPydanticBaseModel):
        page: Optional[int] = None
        per_page: Optional[int] = None
        total_entries: Optional[int] = None
        total_pages: Optional[int] = None

    class Account(UserportPydanticBaseModel):
        linkedin_url: Optional[str] = None
        organization_id: Optional[str] = None

    class Organization(UserportPydanticBaseModel):
        id: Optional[str] = None
        linkedin_url: Optional[str] = None

    pagination: Optional[Pagination] = None
    accounts: Optional[List[Account]] = Field(default=None, description="These are Apollo Companies that have been added to our Apollo account's database during prospecting.")
    organizations: Optional[List[Organization]] = Field(
        default=None, description="These are Apollo Companies that have NOT been added to our Apollo account's database but are available in Apollo's public database..")

    def get_all_organizations(self) -> List[Organization]:
        """Returns all organizations (accounts + organizations) from the given response."""
        orgs_from_accounts = []
        if self.accounts:
            orgs_from_accounts = [SearchApolloOrganizationsResponse.Organization(id=acc.organization_id, linkedin_url=acc.linkedin_url) for acc in self.accounts]
        other_orgs = self.organizations if self.organizations else []
        return orgs_from_accounts + other_orgs

# ------------Main Account Information------------


class AccountInfo(UserportPydanticBaseModel):
    """Account information that are relevant for Userport."""
    name: Optional[str] = Field(default=None)
    website: Optional[str] = Field(default=None)
    linkedin_url: Optional[str] = Field(default=None)
    employee_count: Optional[int] = Field(default=None)
    about: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)
    slogan: Optional[str] = Field(default=None)
    industries: Optional[str] = Field(default=None)
    categories: Optional[str] = Field(default=None)
    headquarters: Optional[str] = Field(default=None)
    company_size: Optional[str] = Field(default=None)
    organization_type: Optional[str] = Field(default=None, description="Privately held, Public Company etc.")
    founded_year: Optional[int] = Field(default=None)
    logo: Optional[str] = Field(default=None)
    crunchbase_url: Optional[str] = Field(default=None)
    locations: Optional[List[str]] = Field(default=None)
    location_country_codes: Optional[List[str]] = Field(default=None)

    technologies: Optional[List[str]] = Field(default=None)
    customers: Optional[List[str]] = Field(default=None)
    competitors: Optional[List[str]] = Field(default=None)

    financials: Optional[Financials] = Field(default=None)
    tech_profile: Optional[Any] = Field(default=None)

    # Recent developments associated with the Account.
    recent_developments: Optional[RecentDevelopments] = Field(default=None)

    def formatted_hq(self) -> Optional[str]:
        """Returns Formatted string of the Headquarters of the Account."""
        if not self.headquarters:
            return None

        hq = self.headquarters
        if not self.location_country_codes or len(self.location_country_codes) == 0:
            # Country Code not present, just return City and state of HQ.
            return hq
        country_code = self.location_country_codes[0]

        return f"{hq}, {country_code}"
