#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Apollo API integration for sourcing companies based on filters.
Replaces CSV dependency with programmatic company discovery.
"""

import os
import json
import time
import asyncio
import aiohttp
import logging
from typing import List, Dict, Any, Optional, Tuple, Union

from .data_models import ProspectingTarget

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ApolloCompanySource:
    """
    Uses Apollo API to search for companies based on specified criteria.
    Provides a programmatic alternative to CSV-based company lists.
    """
    
    # Apollo API endpoints
    COMPANY_SEARCH_URL = "https://api.apollo.io/api/v1/mixed_companies/search"
    
    def __init__(
        self, 
        api_key: Optional[str] = None,
        concurrency_limit: int = 3,
        rate_limit_delay: float = 1.0,
        cache_results: bool = True,
        cache_ttl: int = 3600  # 1 hour cache TTL
    ):
        """
        Initialize the Apollo company source.
        
        Args:
            api_key: Apollo API key. If not provided, will look for APOLLO_ORG_SEARCH_API_KEY env var
            concurrency_limit: Maximum number of concurrent API requests
            rate_limit_delay: Delay between API requests in seconds
            cache_results: Whether to cache API results to minimize repeat calls
            cache_ttl: Cache time-to-live in seconds
        """
        self.api_key = api_key or os.environ.get("APOLLO_ORG_SEARCH_API_KEY")
        if not self.api_key:
            logger.warning("Apollo API key not provided. Set APOLLO_ORG_SEARCH_API_KEY env var or pass to constructor.")
        
        self.semaphore = asyncio.Semaphore(concurrency_limit)
        self.rate_limit_delay = rate_limit_delay
        self.cache_results = cache_results
        self.cache_ttl = cache_ttl
        self.request_cache = {}  # Simple in-memory cache
        
        self._session = None
    
    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30)  # 30 second timeout
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session
    
    async def close(self):
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
    
    def _get_cache_key(self, params: Dict[str, Any]) -> str:
        """Generate a cache key from API parameters."""
        return json.dumps(params, sort_keys=True)
    
    def _is_cache_valid(self, timestamp: float) -> bool:
        """Check if a cached result is still valid based on TTL."""
        return (time.time() - timestamp) < self.cache_ttl
    
    async def search_companies(
        self,
        # Industry filters
        industries: Optional[List[str]] = None,  # organization_industries[] in Apollo API
        sub_industries: Optional[List[str]] = None,  # organization_sub_industries[] in Apollo API
        
        # Company size filters
        employee_count_min: Optional[int] = None,
        employee_count_max: Optional[int] = None,
        
        # Employee range as string format for Apollo API
        employee_ranges: Optional[List[str]] = None,  # organization_num_employees_ranges[] in Apollo API, e.g., ["1,10", "250,500"]
        
        # Funding filters
        funding_stage: Optional[List[str]] = None,  # e.g., ["series_a", "series_b"]
        funding_amount_min: Optional[int] = None,
        funding_amount_max: Optional[int] = None,
        funding_raised_min: Optional[int] = None,
        funding_raised_max: Optional[int] = None,
        
        # Revenue filters
        revenue_min: Optional[int] = None,  # e.g., 300000
        revenue_max: Optional[int] = None,  # e.g., 50000000
        
        # Company type filters
        b2b: Optional[bool] = None,
        b2c: Optional[bool] = None,
        is_public: Optional[bool] = None,
        
        # Location filters
        locations: Optional[List[str]] = None,  # e.g., ["texas", "tokyo", "spain"]
        exclude_locations: Optional[List[str]] = None,  # e.g., ["minnesota", "ireland"]
        countries: Optional[List[str]] = None,  # For backward compatibility
        
        # Technology filters
        technologies: Optional[List[str]] = None,  # e.g., ["salesforce", "google_analytics"]
        
        # Specific company filters
        company_name: Optional[str] = None,  # e.g., "apollo" or "mining"
        company_ids: Optional[List[str]] = None,  # e.g., ["5e66b6381e05b4008c8331b8"]
        
        # Keyword filters
        keyword_tags: Optional[List[str]] = None,  # e.g., ["mining", "sales strategy"]
        
        # Pagination
        page: int = 1,
        per_page: int = 100,  # Increased from 25 to 100 (Apollo max)
        
        # Search options
        keywords: Optional[str] = None,  # For backward compatibility
        custom_keywords: Optional[Dict[str, List[str]]] = None,  # For backward compatibility
        exclude_keywords: Optional[List[str]] = None,  # For backward compatibility
        sort_by: str = "recently_updated",
        sort_direction: str = "desc"
    ) -> Tuple[List[ProspectingTarget], Dict[str, Any]]:
        """
        Search for companies based on specified filters using Apollo API.
        
        This method accepts standard parameter names that are mapped to Apollo API's specific parameter format.
        The input parameters use a simplified naming scheme (e.g., 'industries'), which will be converted 
        to Apollo's format (e.g., 'organization_industries[]') internally.
        
        Args:
            industries: List of industry names (maps to organization_industries[])
            sub_industries: List of sub-industry names (maps to organization_sub_industries[])
            employee_count_min: Minimum employee count
            employee_count_max: Maximum employee count
            employee_ranges: List of employee count ranges (maps to organization_num_employees_ranges[])
            funding_stage: List of funding stages (maps to funding_stages[])
            funding_amount_min: Minimum funding amount
            funding_amount_max: Maximum funding amount
            funding_raised_min: Minimum total funding raised
            funding_raised_max: Maximum total funding raised
            b2b: Whether the company is B2B (maps to organization_is_b2b)
            b2c: Whether the company is B2C (maps to organization_is_b2c)
            is_public: Whether the company is publicly traded (maps to organization_is_public)
            countries: List of countries to include (maps to organization_locations[])
            page: Page number for pagination
            per_page: Results per page
            keywords: General keywords to search for (maps to q_keywords)
            custom_keywords: Custom keywords with field targeting
            exclude_keywords: Keywords to exclude (maps to q_not_keywords)
            sort_by: Field to sort by
            sort_direction: Sort direction (asc or desc)
            
        Returns:
            A tuple containing (list of ProspectingTarget objects, pagination metadata)
        """
        if not self.api_key:
            raise ValueError("Apollo API key is required")
        
        params = {
            "page": page,
            "per_page": per_page
        }
        
        # Add sorting options
        if sort_by:
            params["sort_by"] = sort_by
        if sort_direction:
            params["sort_direction"] = sort_direction
        
        if industries:
            params["organization_industries"] = industries
        if sub_industries:
            params["organization_sub_industries"] = sub_industries
            
        if employee_ranges:
            params["organization_num_employees_ranges"] = employee_ranges
        elif employee_count_min is not None or employee_count_max is not None:
            emp_range = f"{employee_count_min or 1},{employee_count_max or 100000}"
            params["organization_num_employees_ranges"] = [emp_range]
            
        if revenue_min is not None:
            params["revenue_range[min]"] = revenue_min
        if revenue_max is not None:
            params["revenue_range[max]"] = revenue_max
            
        if funding_stage:
            params["funding_stages"] = funding_stage
        
        if b2b is not None:
            params["organization_is_b2b"] = b2b
        if b2c is not None:
            params["organization_is_b2c"] = b2c
        if is_public is not None:
            params["organization_is_public"] = is_public
            
        if locations:
            params["organization_locations"] = locations
        if exclude_locations:
            params["organization_not_locations"] = exclude_locations
        elif countries:
            params["organization_locations"] = countries
            
        if technologies:
            params["currently_using_any_of_technology_uids"] = technologies
            
        if company_name:
            params["q_organization_name"] = company_name
        if company_ids:
            params["organization_ids"] = company_ids
            
        if keyword_tags:
            params["q_organization_keyword_tags"] = keyword_tags
            
        if keywords:
            params["q_keywords"] = keywords
        if exclude_keywords:
            params["q_not_keywords"] = exclude_keywords
        
        
        # Check cache before making API call
        cache_key = self._get_cache_key(params)
        if self.cache_results and cache_key in self.request_cache:
            cached_result, timestamp = self.request_cache[cache_key]
            if self._is_cache_valid(timestamp):
                logger.info(f"Using cached Apollo API result for {cache_key}")
                return cached_result  
        
        # Make API request with rate limiting
        async with self.semaphore:
            try:
                response_data = await self._make_api_request(self.COMPANY_SEARCH_URL, params)
                
                # Process API response into ProspectingTarget objects
                targets, metadata = self._process_search_response(response_data)
                
                # Cache the result
                if self.cache_results:
                    self.request_cache[cache_key] = ((targets, metadata), time.time())
                
                return targets, metadata
                
            except Exception as e:
                logger.error(f"Error searching Apollo companies: {str(e)}")
                return [], {"pagination": {"total_entries": 0, "total_pages": 0}}
    
    async def _make_api_request(self, url: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make a request to the Apollo API with proper error handling."""
        if not self.api_key:
            raise ValueError("Apollo API key is required")
        
        # Header format exactly as shown in the example
        headers = {
            "accept": "application/json",
            "Cache-Control": "no-cache",
            "Content-Type": "application/json",
            "x-api-key": self.api_key  # Pass as x-api-key header
        }
        
        session = await self.get_session()
        
        try:
            await asyncio.sleep(self.rate_limit_delay)
            
            # Convert array parameters to query params as Apollo expects
            url_params = []
            json_params = {}
            
            from urllib.parse import quote
            
            for key, value in params.items():
                if isinstance(value, list):
                    # For array parameters, add them as query parameters with URL encoding
                    for item in value:
                        url_params.append(f"{key}[]={quote(str(item))}")
                else:
                    # Non-array parameters go in the JSON body
                    json_params[key] = value
            
            # Construct final URL with query parameters
            if url_params:
                url = f"{url}?{'&'.join(url_params)}"
            
            # Debug output for troubleshooting
            logger.info(f"Making Apollo API request to: {url}")
            logger.info(f"Headers: {headers}")
            logger.info(f"JSON body: {json.dumps(json_params, default=str, indent=2)}")
            
            async with session.post(url, json=json_params, headers=headers) as response:
                status_code = response.status
                logger.info(f"Apollo API response status: {status_code}")
                
                # Get response data
                data = await response.json()
                
                # Handle different status codes properly
                if status_code == 200:
                    # Check for API errors in successful responses
                    if "errors" in data and data["errors"]:
                        error_msg = "; ".join(data["errors"])
                        raise ValueError(f"Apollo API error: {error_msg}")
                    
                    # Log response details for debugging
                    if "organizations" in data:
                        org_count = len(data.get("organizations", []))
                        logger.info(f"Apollo API returned {org_count} organizations")
                        
                        # Log first few results if available
                        if org_count > 0:
                            sample = data["organizations"][:2]
                            logger.info(f"Sample results: {json.dumps(sample, default=str)[:500]}...")
                    
                    return data
                elif status_code == 429:
                    # Rate limit exceeded
                    logger.warning("Apollo API rate limit exceeded. Implementing exponential backoff.")
                    await asyncio.sleep(self.rate_limit_delay * 2)  # Exponential backoff
                    return await self._make_api_request(url, params)  # Retry
                else:
                    # Other error status codes
                    error_msg = data.get("errors", ["Unknown error"])[0] if isinstance(data, dict) else "Unknown error"
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=status_code,
                        message=error_msg,
                        headers=response.headers
                    )
                
        except aiohttp.ClientResponseError as e:
            logger.error(f"Apollo API HTTP error: {e.status} - {e.message}")
            raise
            
        except Exception as e:
            logger.error(f"Error making Apollo API request: {str(e)}")
            raise
    
    @staticmethod
    def debug_convert_params(apollo_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Debug utility to demonstrate parameter conversion.
        Converts Apollo API style parameters to standard parameters.
        
        Args:
            apollo_params: Dictionary of Apollo API style parameters
            
        Returns:
            Dictionary of standard parameters
        """
        standard_params = {}
        
        for key, value in apollo_params.items():
            # Handle array parameters by removing the [] suffix
            if key.endswith('[]'):
                standard_key = key[:-2]
                standard_params[standard_key] = value
            # Handle range parameters by extracting min/max
            elif '[min]' in key:
                base_key = key.split('[')[0]
                if base_key not in standard_params:
                    standard_params[base_key] = {}
                standard_params[base_key]['min'] = value
            elif '[max]' in key:
                base_key = key.split('[')[0]
                if base_key not in standard_params:
                    standard_params[base_key] = {}
                standard_params[base_key]['max'] = value
            else:
                standard_params[key] = value
        
        # Map specific Apollo parameters to their standard equivalents
        param_mapping = {
            "organization_industries": "industries",
            "organization_sub_industries": "sub_industries",
            "organization_num_employees_ranges": "employee_ranges",
            "organization_is_b2b": "b2b",
            "organization_is_b2c": "b2c",
            "organization_is_public": "is_public",
            "organization_locations": "locations",
            "organization_not_locations": "exclude_locations",
            "q_keywords": "keywords",
            "q_not_keywords": "exclude_keywords",
            "q_organization_name": "company_name",
            "organization_ids": "company_ids",
            "currently_using_any_of_technology_uids": "technologies",
            "funding_stages": "funding_stage",
            "revenue_range": "revenue"
        }
        
        # Apply the mapping
        mapped_params = {}
        for key, value in standard_params.items():
            if key in param_mapping:
                mapped_params[param_mapping[key]] = value
            else:
                mapped_params[key] = value
                
        return mapped_params
    
    def _process_search_response(self, response_data: Dict[str, Any]) -> Tuple[List[ProspectingTarget], Dict[str, Any]]:
        """Process Apollo API response into ProspectingTarget objects."""
        targets = []
        
        # Process both 'organizations' and 'accounts' from the response
        organizations = response_data.get("organizations", [])
        accounts = response_data.get("accounts", [])
        
        # Fallback for compatibility
        if not organizations and not accounts:
            organizations = response_data.get("companies", [])
            
        # Log the response structure for debugging
        logger.info(f"Apollo API response keys: {list(response_data.keys())}")
        logger.info(f"Found {len(organizations)} organizations and {len(accounts)} accounts in response")
        
        # Add additional debugging information about the response
        total_entries = response_data.get("pagination", {}).get("total_entries", 0)
        logger.info(f"Total available entries: {total_entries}")
        
        # Extract pagination metadata
        pagination = response_data.get("pagination", {})
        metadata = {
            "pagination": pagination,
            "applied_filters": {},  # Apollo doesn't return search_criteria
            "total_count": pagination.get("total_entries", 0)
        }
        
        # Show detailed debug info about the response
        if "errors" in response_data:
            logger.error(f"Apollo API errors in response: {response_data.get('errors')}")
        
        # Process organizations
        for org in organizations:
            company_name = org.get("name", "")
            website = org.get("website_url", "")
            
            if not company_name or not website:
                continue
            
            industry = org.get("industry", "")
            description = org.get("short_description", "")
            
            additional_info = {
                "apollo_id": org.get("id"),
                "linkedin_url": org.get("linkedin_url"),
                "founded_year": org.get("founded_year"),
                "location": org.get("location"),
                "employee_count": org.get("employee_count"),
                "annual_revenue": org.get("annual_revenue"),
                "funding": {
                    "total_funding": org.get("total_funding"),
                    "funding_stage": org.get("funding_stage"),
                    "latest_funding_round": org.get("latest_funding_round"),
                    "latest_funding_amount": org.get("latest_funding_amount"),
                    "latest_funding_date": org.get("latest_funding_date")
                },
                "technologies": org.get("technologies", []),
                "phone": org.get("phone"),
                "keywords": org.get("keywords", []),
                "source": "organization"
            }
            
            target = ProspectingTarget(
                company_name=company_name,
                website=website,
                industry=industry,
                description=description,
                additional_info=additional_info
            )
            
            targets.append(target)
        
        # Process accounts
        for account in accounts:
            company_name = account.get("name", "")
            website = account.get("website", "")
            
            if not company_name or not website:
                continue
            
            industry = account.get("industry", "")
            description = account.get("description", "")
            
            additional_info = {
                "apollo_id": account.get("id"),
                "linkedin_url": account.get("linkedin_url"),
                "location": account.get("location", {}).get("display_value", "") if isinstance(account.get("location"), dict) else account.get("location", ""),
                "employee_count": account.get("estimated_num_employees"),
                "annual_revenue": account.get("estimated_annual_revenue"),
                "technologies": account.get("technologies", []),
                "phone": account.get("phone"),
                "source": "account"
            }
            
            target = ProspectingTarget(
                company_name=company_name,
                website=website,
                industry=industry,
                description=description,
                additional_info=additional_info
            )
            
            targets.append(target)
        
        return targets, metadata
    
    async def derive_initial_filters(
        self, 
        product_name: str,
        product_description: str,
        model,
        also_explain: bool = False
    ) -> Union[Dict[str, Any], Tuple[Dict[str, Any], str]]:
        """
        Use AI to derive initial search filters based on selling product.
        Performs a research step to understand product and suggest optimal filters.
        
        Args:
            product_name: The name of the product being sold
            product_description: Description of the product
            model: LLM to use for deriving filters
            also_explain: If True, return explanation along with filters
            
        Returns:
            Dictionary of suggested Apollo search filters,
            or tuple of (filters, explanation) if also_explain=True
        """
        prompt = f"""
        You are an expert at B2B sales targeting and market research. I need you to:
        1. Research and analyze a product/company to understand its value proposition
        2. Identify the ideal customer profile based on this analysis
        3. Provide specific Apollo API search filters to find similar companies
        
        First, research the product with only the information provided. Think deeply about:
        - What problem does this product solve?
        - Who would benefit most from this product?
        - What industries/company types would have these problems?
        - What size companies would be ideal targets?
        - What regions or countries should be targeted?
        
        PRODUCT INFORMATION:
        Name: {product_name}
        Description: {product_description}
        
        Part 1: Provide your analysis of the ideal customer profile in 3-5 bullet points.
        
        Part 2: Based on your analysis, provide search filters in JSON format with these fields:
        
        {{{{
            "industries": ["industry1", "industry2"],  // List of relevant industries (be specific)
            "sub_industries": ["subindustry1", "subindustry2"],  // List of relevant sub-industries
            "employee_count_min": 50,  // Minimum employee count (integer)
            "employee_count_max": 5000,  // Maximum employee count (integer)
            "funding_stage": ["series_a", "series_b", "series_c"],  // List of funding stages
            "funding_amount_min": 1000000,  // Minimum funding amount in USD
            "funding_amount_max": 100000000,  // Maximum funding amount in USD
            "b2b": true,  // Boolean if B2B is relevant
            "b2c": false,  // Boolean if B2C is relevant
            "countries": ["United States", "Canada"],  // List of target countries
            "keywords": "cloud platform security",  // Keywords to search across all fields (space-separated)
            "keyword_tags": ["cloud computing", "data security"],  // Organization keyword tags to match
            "exclude_keywords": ["gaming", "blockchain"]  // Keywords to exclude
        }}}}
        
        Only include filters that are directly relevant to finding potential customers for this product.
        If a filter isn't relevant or you're not sure about a value, omit that field entirely.
        
        Format your response as follows:
        
        ## Ideal Customer Profile Analysis
        - [Your analysis point 1]
        - [Your analysis point 2]
        - [Your analysis point 3]
        ...
        
        ## Recommended Apollo Search Filters
        ```json
        {{{{
          "industries": ["example1", "example2"],
          "employee_count_min": 100,
          "keywords": "example keywords"
        }}}}
        ```
        """
        
        # Make request to LLM
        try:
            response = await model.ainvoke(prompt)
            content = response.content
            
            # Extract JSON and analysis from response
            import re
            import json
            
            # Save the complete analysis for display
            analysis = ""
            analysis_match = re.search(r'## Ideal Customer Profile Analysis([\s\S]*?)## Recommended', content)
            if analysis_match:
                analysis = analysis_match.group(1).strip()
            
            # Extract JSON
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_match = re.search(r'{\s*"[^"]+"\s*:[\s\S]*?}', content)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    logger.warning("Could not extract JSON from LLM response, using default filters")
                    json_str = '{}'
            
            # Parse JSON
            try:
                filters = json.loads(json_str)
            except json.JSONDecodeError:
                logger.warning(f"JSON parsing error, using default filters. Raw JSON: {json_str}")
                filters = {}
            
            # Validate and clean filters
            clean_filters = {}
            for key, value in filters.items():
                if value is not None and value != "" and value != [] and value != {}:
                    clean_filters[key] = value
            
            # Ensure there's at least something in the filters
            if not clean_filters:
                clean_filters = {
                    "employee_count_min": 50,  # Target mid-sized and larger companies by default
                    "b2b": True  # Assume B2B focus by default
                }
            
            # Combine all parts of the analysis with filters for display
            try:
                # Convert generic filters to Apollo-specific format
                apollo_filters = {}
                
                # Map the standard filters to Apollo-specific params
                if "industries" in clean_filters:
                    apollo_filters["organization_industries"] = clean_filters["industries"]
                
                if "employee_count_min" in clean_filters or "employee_count_max" in clean_filters:
                    min_emp = clean_filters.get("employee_count_min", 1)
                    max_emp = clean_filters.get("employee_count_max", 100000)
                    apollo_filters["organization_num_employees_ranges"] = [f"{min_emp},{max_emp}"]
                
                if "b2b" in clean_filters:
                    apollo_filters["organization_is_b2b"] = clean_filters["b2b"]
                    
                if "b2c" in clean_filters:
                    apollo_filters["organization_is_b2c"] = clean_filters["b2c"]
                    
                if "countries" in clean_filters:
                    apollo_filters["organization_locations"] = clean_filters["countries"]
                    
                if "keywords" in clean_filters:
                    key_str = clean_filters["keywords"]
                    if isinstance(key_str, str):
                        apollo_filters["q_keywords"] = key_str
                    
                if "exclude_keywords" in clean_filters:
                    apollo_filters["q_not_keywords"] = clean_filters["exclude_keywords"]
                
                # Format both the standard filters and Apollo filters for display
                std_json_str = json.dumps(clean_filters, indent=2)
                apollo_json_str = json.dumps(apollo_filters, indent=2)
                
                filter_explanation = (
                    "## Ideal Customer Profile Analysis\n" + 
                    analysis + 
                    "\n\n## Recommended Search Filters\n" + 
                    std_json_str + 
                    "\n\n## Apollo API Parameters\n" + 
                    apollo_json_str
                )
                
                clean_filters = apollo_filters
                
            except Exception as e:
                logger.error(f"Error formatting filter explanation: {str(e)}")
                filter_explanation = "## Ideal Customer Profile Analysis\n" + analysis + "\n\n## Recommended Search Filters\nError formatting JSON."
            
            if also_explain:
                return clean_filters, filter_explanation
            else:
                return clean_filters
            
        except Exception as e:
            logger.error(f"Error deriving filters: {str(e)}")
            # Return minimal default filters
            default_filters = {
                "employee_count_min": 50,  # Target mid-sized and larger companies by default
                "b2b": True  # Assume B2B focus by default
            }
            
            if also_explain:
                return default_filters, "Error deriving filters. Using default filters targeting mid-sized B2B companies."
            else:
                return default_filters
    
    async def get_companies_for_product(
        self,
        product_name: str,
        product_description: str,
        model,
        max_companies: int = 10,
        use_ai_filters: bool = True,
        manual_filters: Optional[Dict[str, Any]] = None,
        interactive: bool = False,
        include_filter_explanation: bool = False
    ) -> Union[List[ProspectingTarget], Tuple[List[ProspectingTarget], Dict[str, Any], str]]:
        """
        Get a list of companies that match the given product.
        
        Note: This method has multiple return types:
        - If include_filter_explanation=False, returns List[ProspectingTarget]
        - If include_filter_explanation=True, returns Tuple[List[ProspectingTarget], Dict[str, Any], str]
        
        Args:
            product_name: The name of the product being sold
            product_description: Description of the product
            model: LLM model for deriving filters
            max_companies: Maximum number of companies to return
            use_ai_filters: Whether to use AI to derive filters
            manual_filters: Manual filters to use (overrides AI filters)
            interactive: Whether to use interactive filter confirmation mode
            include_filter_explanation: Whether to return filter explanation
            
        Returns:
            List of ProspectingTarget objects, or
            Tuple of (targets, filters, explanation) if include_filter_explanation=True
        """
        
        # Helper function to convert Apollo-style params to standard params
        def convert_apollo_params(apollo_params):
            """Convert Apollo-style params with array notation to standard params."""
            standard_params = {}
            
            for key, value in apollo_params.items():
                # Handle array parameters by removing the [] suffix
                if key.endswith('[]'):
                    standard_key = key[:-2]
                    standard_params[standard_key] = value
                # Handle range parameters by extracting min/max
                elif '[min]' in key:
                    base_key = key.split('[')[0]
                    if base_key not in standard_params:
                        standard_params[base_key] = {}
                    standard_params[base_key]['min'] = value
                elif '[max]' in key:
                    base_key = key.split('[')[0]
                    if base_key not in standard_params:
                        standard_params[base_key] = {}
                    standard_params[base_key]['max'] = value
                else:
                    standard_params[key] = value
            
            # Map specific Apollo parameters to their standard equivalents
            param_mapping = {
                "organization_industries": "industries",
                "organization_sub_industries": "sub_industries",
                "organization_num_employees_ranges": "employee_ranges",
                "organization_is_b2b": "b2b",
                "organization_is_b2c": "b2c",
                "organization_is_public": "is_public",
                "organization_locations": "locations",
                "organization_not_locations": "exclude_locations",
                "q_keywords": "keywords",
                "q_not_keywords": "exclude_keywords",
                "q_organization_name": "company_name",
                "organization_ids": "company_ids",
                "currently_using_any_of_technology_uids": "technologies",
                "funding_stages": "funding_stage",
                "revenue_range": "revenue",
                "q_organization_keyword_tags": "keyword_tags"
            }
            
            # Apply the mapping
            mapped_params = {}
            for key, value in standard_params.items():
                if key in param_mapping:
                    mapped_params[param_mapping[key]] = value
                else:
                    mapped_params[key] = value
                    
            return mapped_params
        # Use default max companies from config if not specified
        if max_companies is None:
            try:
                from .config import APOLLO_API_CONFIG
                max_companies = APOLLO_API_CONFIG.get("default_max_companies", 10)
            except ImportError:
                max_companies = 10
        
        # Determine search filters
        filter_explanation = ""
        
        if manual_filters:
            # Use manual filters if provided
            search_filters = manual_filters
            logger.info(f"Using manual filters: {search_filters}")
            filter_explanation = "Using provided manual filters."
        elif use_ai_filters:
            # Use AI to derive filters with explanation
            logger.info("Deriving filters from product information using AI...")
            if include_filter_explanation or interactive:
                search_filters, filter_explanation = await self.derive_initial_filters(
                    product_name, 
                    product_description,
                    model,
                    also_explain=True
                )
            else:
                search_filters = await self.derive_initial_filters(
                    product_name, 
                    product_description,
                    model
                )
            
            logger.info(f"AI-derived filters: {search_filters}")
            
            # If interactive mode, allow user to confirm/edit filters
            if interactive:
                print("\n=== IDEAL CUSTOMER PROFILE ANALYSIS ===\n")
                print(filter_explanation)
                print("\n=== CONFIRM SEARCH FILTERS ===\n")
                
                # Handle interactive filter confirmation
                confirmed = input("\nUse these filters? (y/n/e) [y=yes, n=no, e=edit]: ").lower()
                
                if confirmed == 'n':
                    print("Using default filters instead.")
                    search_filters = {
                        "employee_count_min": 50,
                        "b2b": True
                    }
                
                elif confirmed == 'e':
                    print("\nLet's edit the filters:")
                    
                    # Industries
                    if "industries" in search_filters:
                        industries_str = ", ".join(search_filters["industries"])
                        new_industries = input(f"Industries (comma-separated, press Enter to keep [{industries_str}]): ")
                        if new_industries.strip():
                            search_filters["industries"] = [i.strip() for i in new_industries.split(",")]
                    else:
                        new_industries = input("Industries (comma-separated, optional): ")
                        if new_industries.strip():
                            search_filters["industries"] = [i.strip() for i in new_industries.split(",")]
                    
                    # Employee count
                    emp_min = search_filters.get("employee_count_min", 50)
                    new_emp_min = input(f"Minimum employee count (press Enter to keep [{emp_min}]): ")
                    if new_emp_min.strip() and new_emp_min.isdigit():
                        search_filters["employee_count_min"] = int(new_emp_min)
                    
                    emp_max = search_filters.get("employee_count_max", "")
                    new_emp_max = input(f"Maximum employee count (press Enter to keep [{emp_max}]): ")
                    if new_emp_max.strip() and new_emp_max.isdigit():
                        search_filters["employee_count_max"] = int(new_emp_max)
                    
                    # B2B/B2C
                    b2b = "yes" if search_filters.get("b2b", True) else "no"
                    new_b2b = input(f"Is this a B2B product? (yes/no, press Enter to keep [{b2b}]): ")
                    if new_b2b.strip().lower() in ["yes", "y", "true"]:
                        search_filters["b2b"] = True
                    elif new_b2b.strip().lower() in ["no", "n", "false"]:
                        search_filters["b2b"] = False
                    
                    # Countries
                    if "countries" in search_filters:
                        countries_str = ", ".join(search_filters["countries"])
                        new_countries = input(f"Countries (comma-separated, press Enter to keep [{countries_str}]): ")
                        if new_countries.strip():
                            search_filters["countries"] = [c.strip() for c in new_countries.split(",")]
                    else:
                        new_countries = input("Countries (comma-separated, optional): ")
                        if new_countries.strip():
                            search_filters["countries"] = [c.strip() for c in new_countries.split(",")]
                    
                    # Keywords
                    keywords = search_filters.get("keywords", "")
                    new_keywords = input(f"Keywords (space-separated, press Enter to keep [{keywords}]): ")
                    if new_keywords.strip():
                        search_filters["keywords"] = new_keywords
                    
                    print("\nUpdated filters:")
                    for k, v in search_filters.items():
                        print(f"  {k}: {v}")
        else:
            # Use minimal default filters
            search_filters = {
                "employee_count_min": 50,
                "b2b": True
            }
            logger.info("Using default filters")
            filter_explanation = "Using default filters targeting mid-sized B2B companies."
        
        # Set per_page to 100 (Apollo API supports up to 100 per page)
        per_page = min(100, max_companies)
        max_pages = (max_companies + per_page - 1) // per_page
        
        # Gather results across pages
        all_targets = []
        for page in range(1, max_pages + 1):
            if len(all_targets) >= max_companies:
                break
                
            # Update page in search filters
            search_params = {**search_filters, "page": page, "per_page": per_page}
            
            # Convert Apollo-style parameters to standard parameters
            standard_params = convert_apollo_params(search_params)
            
            # Make search request with converted parameters
            targets, metadata = await self.search_companies(**standard_params)
            
            # Add to results
            all_targets.extend(targets)
            
            # Check if we've reached the end of results
            total_pages = metadata.get("pagination", {}).get("total_pages", 0)
            if page >= total_pages:
                logger.info(f"Reached the end of results at page {page} of {total_pages}")
                break
                
            # Log progress
            logger.info(f"Retrieved {len(targets)} targets from page {page}. Moving to next page.")
                
            # Short delay between pages
            await asyncio.sleep(self.rate_limit_delay)
        
        # Limit to requested number
        limited_targets = all_targets[:max_companies]
        
        # Return additional information if requested
        if include_filter_explanation:
            return limited_targets, search_filters, filter_explanation
        else:
            return limited_targets