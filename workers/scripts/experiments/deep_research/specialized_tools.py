#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Specialized research tools for integrating external data sources like BuiltWith and Apollo.
These tools use BigQuery caching for API requests to save costs and improve performance.
"""

import os
import sys
import asyncio
from typing import Dict, Any, Optional, List, Callable, Tuple
from langchain_core.tools import Tool, StructuredTool
from pydantic import BaseModel, Field

# Add parent directory to path to import from workers modules
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../'))

try:
    from services.builtwith_service import BuiltWithService
    from services.ai.api_cache_service import APICacheService, cached_request
    from services.bigquery_service import BigQueryService
    from utils.loguru_setup import logger
except ImportError:
    logger = None
    APICacheService = None
    BuiltWithService = None
    BigQueryService = None
    cached_request = None
    import logging
    logger = logging.getLogger(__name__)


class BuiltWithToolInput(BaseModel):
    """Input model for BuiltWith tool."""
    domain: str = Field(description="The domain name or URL to fetch technology information for")


class ApolloToolInput(BaseModel):
    """Input model for Apollo tool."""
    company_info: str = Field(
        description="Company domain, name, or JSON with both. Examples: 'acme.com', 'Acme Corp', '{\"domain\": \"acme.com\", \"company_name\": \"Acme Corp\"}'"
    )


# Initialize shared cache service and BigQuery service
_cache_service = None
_bq_service = None

def get_cache_service() -> APICacheService:
    """Get or initialize the cache service."""
    global _cache_service
    if _cache_service is None:
        _bq_service = BigQueryService()
        _cache_service = APICacheService(bq_service=_bq_service)
    return _cache_service


async def cached_request_with_json(
    cache_service: APICacheService,
    url: str,
    method: str = "GET",
    params: Optional[Dict[str, Any]] = None,
    json_data: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, Any]] = None,
    tenant_id: Optional[str] = None,
    ttl_hours: Optional[int] = 24,
    force_refresh: bool = False
) -> Tuple[Dict[str, Any], int]:
    """
    Enhanced cached request that supports JSON body for POST requests.
    """
    # For caching purposes, treat JSON body as params
    cache_params = params or {}
    if json_data:
        cache_params = {**cache_params, **json_data}
    
    if not force_refresh:
        cached = await cache_service.get_cached_response(
            url=url,
            method=method,
            params=cache_params,
            headers=headers,
            tenant_id=tenant_id
        )
        
        if cached:
            logger.info(f"Cache hit for {url}")
            return cached["data"], cached["status_code"]
    
    logger.info(f"Cache miss for {url}, making fresh request")
    
    try:
        async with cache_service.connection_pool.acquire_connection() as client:
            request_kwargs = {
                "method": method,
                "url": url,
                "headers": headers,
            }
            
            if params:
                request_kwargs["params"] = params
            if json_data:
                request_kwargs["json"] = json_data
            
            response = await client.request(**request_kwargs)
            response_data = response.json() if response.content else {}
            
            # Cache successful responses
            if response.status_code < 400:
                await cache_service.cache_response(
                    url=url,
                    response_data=response_data,
                    status_code=response.status_code,
                    method=method,
                    params=cache_params,
                    headers=headers,
                    tenant_id=tenant_id,
                    ttl_hours=ttl_hours
                )
            
            return response_data, response.status_code
    except Exception as e:
        logger.error(f"Error making request to {url}: {str(e)}")
        raise


def create_builtwith_tool() -> Tool:
    """Create a tool for fetching technology stack information from BuiltWith with BigQuery caching."""
    cache_service = get_cache_service()
    
    def builtwith_wrapper(domain: str) -> str:
        """Synchronous wrapper for the async BuiltWith function."""
        # Create a new event loop for this thread if needed
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Run the async function
        return loop.run_until_complete(_get_technology_profile_async(domain))
    
    async def _get_technology_profile_async(domain: str) -> str:
        """Fetch technology profile for a domain using cached requests."""
        api_key = os.getenv('BUILTWITH_API_KEY')
        if not api_key:
            return "BuiltWith API key not configured"
        
        try:
            # Extract domain from URL if needed
            if domain.startswith('http'):
                from urllib.parse import urlparse
                parsed = urlparse(domain)
                domain = parsed.netloc.replace('www.', '')
            
            logger.info(f"Fetching BuiltWith data for domain: {domain}")
            
            # Use cached_request to benefit from BigQuery caching
            response, status_code = await cached_request(
                cache_service=cache_service,
                url="https://api.builtwith.com/v21/api.json",
                method='GET',
                params={
                    'KEY': api_key,
                    'LOOKUP': domain
                },
                headers={'Content-Type': 'application/json'},
                ttl_hours=24 * 30  # Cache for 30 days
            )
            
            if status_code == 200:
                tech_stack = _format_builtwith_response(response)
                return tech_stack
            else:
                error_msg = response.get('Errors', ['Unknown error'])[0] if isinstance(response, dict) else 'Unknown error'
                return f"Could not retrieve technology data for {domain}: {error_msg}"
                
        except Exception as e:
            logger.error(f"Error using BuiltWith tool: {str(e)}")
            return f"Error retrieving technology data: {str(e)}"
    
    def _format_builtwith_response(data: Dict[str, Any]) -> str:
        """Format BuiltWith API response into readable text."""
        output = []
        
        # Check for errors
        if data.get('Errors'):
            return f"BuiltWith Error: {', '.join(data['Errors'])}"
        
        # Get results
        results = data.get('Results', [])
        if not results:
            return "No technology data found"
        
        result = results[0]
        paths = result.get('Paths', [])
        
        if not paths:
            return "No technology paths found"
        
        # Use the most recent path (first one)
        current_path = paths[0]
        technologies = current_path.get('Technologies', [])
        
        # Meta information
        meta = result.get('Meta', {})
        output.append(f"Technology Profile for {domain}")
        output.append(f"Last detected: {current_path.get('FirstDetected', 'Unknown')}")
        output.append("")
        
        if technologies:
            output.append("CURRENT TECHNOLOGIES:")
            # Group by category
            categories = {}
            for tech in technologies:
                category = tech.get('Categories', ['Other'])[0] if tech.get('Categories') else 'Other'
                if category not in categories:
                    categories[category] = []
                categories[category].append(tech.get('Name', 'Unknown'))
            
            for category, names in sorted(categories.items()):
                output.append(f"\n{category}:")
                for name in names:
                    output.append(f"  - {name}")
        
        # Spend information if available
        if current_path.get('Spend'):
            output.append(f"\nESTIMATED MONTHLY SPEND: ${current_path['Spend']}")
        
        return "\n".join(output)
    
    return Tool(
        name="builtwith_technology",
        description="Get detailed technology stack information for a company's website using BuiltWith. Input should be a domain name (e.g., 'acme.com')",
        func=builtwith_wrapper
    )


def create_apollo_tool(apollo_api_key: Optional[str] = None) -> Tool:
    """Create a tool for enriching company profiles using Apollo.io with BigQuery caching."""
    api_key = apollo_api_key or os.environ.get("APOLLO_API_KEY")
    if not api_key:
        logger.warning("Apollo API key not provided")
        return None
    
    cache_service = get_cache_service()
    
    def apollo_wrapper(company_info: str) -> str:
        """Synchronous wrapper for the async Apollo function."""
        # Create a new event loop for this thread if needed
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Run the async function
        return loop.run_until_complete(_get_company_profile_async(company_info))
    
    async def _get_company_profile_async(company_info: str) -> str:
        """Fetch company profile from Apollo using cached requests."""
        try:
            import json
            
            # Parse input
            if company_info.startswith('{'):
                data = json.loads(company_info)
                domain = data.get('domain', '')
                company_name = data.get('company_name', '')
            else:
                # Assume it's either a domain or company name
                if '.' in company_info and ' ' not in company_info:
                    domain = company_info
                    company_name = ''
                else:
                    domain = ''
                    company_name = company_info
            
            logger.info(f"Fetching Apollo data for: {company_name or domain}")
            
            # Prepare request parameters
            headers = {
                "accept": "application/json",
                "Cache-Control": "no-cache",
                "Content-Type": "application/json",
                "x-api-key": api_key
            }
            
            params = {}
            if domain:
                params['organization_domain'] = domain
            if company_name:
                params['organization_name'] = company_name
            
            # Use cached_request_with_json to benefit from BigQuery caching
            # Note: For Apollo POST requests, params should be in the body
            response, status_code = await cached_request_with_json(
                cache_service=cache_service,
                url="https://api.apollo.io/v1/mixed_companies/search",
                method='POST',
                params={},  # Empty URL params
                json_data=params,  # API params go in the request body
                headers=headers,
                ttl_hours=24 * 30  # Cache for 7 days
            )
            
            if status_code == 200:
                return _format_apollo_profile(response)
            else:
                error_msg = response.get('error', 'Unknown error') if isinstance(response, dict) else 'Unknown error'
                return f"Error fetching Apollo data: {status_code} - {error_msg}"
                        
        except Exception as e:
            logger.error(f"Error using Apollo tool: {str(e)}")
            return f"Error retrieving company profile: {str(e)}"
    
    def _format_apollo_profile(data: Dict[str, Any]) -> str:
        """Format Apollo response into readable text."""
        output = []
        
        organizations = data.get('organizations', [])
        if not organizations:
            organizations = data.get('accounts', [])
        
        if not organizations:
            return "No company data found in Apollo"
        
        # Take the first matching organization
        org = organizations[0]
        
        output.append(f"Company Profile: {org.get('name', 'Unknown Company')}")
        output.append(f"Domain: {org.get('website_url', org.get('website', 'N/A'))}")
        output.append("")
        
        # Basic information
        output.append("BASIC INFORMATION:")
        output.append(f"  Industry: {org.get('industry', 'N/A')}")
        output.append(f"  Description: {org.get('short_description', org.get('description', 'N/A'))}")
        output.append(f"  Founded: {org.get('founded_year', 'N/A')}")
        output.append(f"  Employees: {org.get('employee_count', org.get('estimated_num_employees', 'N/A'))}")
        output.append(f"  Revenue: {org.get('annual_revenue', org.get('estimated_annual_revenue', 'N/A'))}")
        
        # Location
        location = org.get('location', {})
        if isinstance(location, dict):
            location_str = location.get('display_value', 'N/A')
        else:
            location_str = str(location) if location else 'N/A'
        output.append(f"  Location: {location_str}")
        
        # Social profiles
        output.append("\nSOCIAL PROFILES:")
        output.append(f"  LinkedIn: {org.get('linkedin_url', 'N/A')}")
        output.append(f"  Twitter: {org.get('twitter_url', 'N/A')}")
        output.append(f"  Facebook: {org.get('facebook_url', 'N/A')}")
        
        # Funding information
        funding = org.get('funding', {})
        if funding or org.get('total_funding') or org.get('funding_stage'):
            output.append("\nFUNDING:")
            output.append(f"  Total Funding: {org.get('total_funding', funding.get('total_funding', 'N/A'))}")
            output.append(f"  Funding Stage: {org.get('funding_stage', funding.get('funding_stage', 'N/A'))}")
            output.append(f"  Latest Round: {org.get('latest_funding_amount', funding.get('latest_funding_amount', 'N/A'))}")
            output.append(f"  Latest Date: {org.get('latest_funding_date', funding.get('latest_funding_date', 'N/A'))}")
        
        # Technologies
        technologies = org.get('technologies', [])
        if technologies:
            output.append("\nTECHNOLOGIES:")
            for tech in technologies:
                output.append(f"  - {tech}")
        
        # Keywords/Tags
        keywords = org.get('keywords', [])
        if keywords:
            output.append("\nKEYWORDS:")
            for keyword in keywords:
                output.append(f"  - {keyword}")
        
        return "\n".join(output)
    
    return Tool(
        name="apollo_company_profile",
        description="Get enriched company profile data including LinkedIn information from Apollo.io. Input can be domain, company name, or JSON with both.",
        func=apollo_wrapper
    )


def create_specialized_tools(apollo_api_key: Optional[str] = None) -> List[Tool]:
    """Create a list of specialized research tools with BigQuery caching."""
    tools = []
    
    # Add BuiltWith tool
    try:
        builtwith_tool = create_builtwith_tool()
        if builtwith_tool:
            tools.append(builtwith_tool)
            logger.info("BuiltWith tool initialized successfully with BigQuery caching")
    except Exception as e:
        logger.warning(f"Could not initialize BuiltWith tool: {str(e)}")
    
    # Add Apollo tool
    try:
        apollo_tool = create_apollo_tool(apollo_api_key)
        if apollo_tool:
            tools.append(apollo_tool)
            logger.info("Apollo tool initialized successfully with BigQuery caching")
    except Exception as e:
        logger.warning(f"Could not initialize Apollo tool: {str(e)}")
    
    return tools