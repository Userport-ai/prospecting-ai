from typing import Dict, Any, List
from pydantic import BaseModel, Field

from services.ai.ai_service_base import ThinkingBudget
from utils.loguru_setup import logger
from services.ai.ai_service import AIService

class Competitor(BaseModel):
    name: str = Field(alias="company_name")
    description: str
    source: str

    class Config:
        populate_by_name = True

class Customer(BaseModel):
    name: str = Field(alias="company_name")
    description: str
    source: str

    class Config:
        populate_by_name = True

class RecentEvent(BaseModel):
    title: str = Field(alias="event_title")
    description: str
    date: str
    source: str

    class Config:
        populate_by_name = True

class CompetitorIntelligence(BaseModel):
    competitors: List[Competitor]

class CustomerEventIntelligence(BaseModel):
    customers: List[Customer]
    recent_events: List[RecentEvent]

class AICompanyIntelService:
    """Service for using OpenAI/Gemini web search capability with structured output to gather market intelligence."""

    def __init__(self, ai_service: AIService):
        """Initialize the Gemini search service.

        Args:
            ai_service: Configured AIService instance
        """
        self.ai_service = ai_service

    async def fetch_company_intelligence(self, website: str) -> Dict[str, Any]:
        """
        Fetch competitor and customer intelligence for a company website using Gemini/Open AI with web search.

        Args:
            website: The company website URL

        Returns:
            Dict containing competitors, customers, and recent events
        """
        try:
            logger.debug(f"Fetching company intelligence for website: {website}")

            # Fetch competitors separately
            competitors_result = await self.fetch_competitors(website)

            # Fetch customers and recent events together
            customers_events_result = await self.fetch_customers_and_events(website)

            # Combine the results
            combined_result = {
                "competitors": competitors_result.get("competitors", []),
                "customers": customers_events_result.get("customers", []),
                "recent_events": customers_events_result.get("recent_events", [])
            }

            logger.debug(f"Successfully fetched company intelligence for {website}")
            return combined_result

        except Exception as e:
            logger.error(f"Error fetching company intelligence: {str(e)}", exc_info=True)
            return self._get_empty_intelligence()

    async def fetch_competitors(self, website: str) -> Dict[str, Any]:
        """
        Fetch only competitor intelligence for a company website.

        Args:
            website: The company website URL

        Returns:
            Dict containing competitor data
        """
        try:
            logger.debug(f"Fetching competitor intelligence for website: {website}")

            # Set up the competitors prompt
            prompt = self._create_competitors_prompt(website)

            # Use the AI service with web search and structured output
            result = await self.ai_service.generate_structured_search_content(
                prompt=prompt,
                response_schema=CompetitorIntelligence,
                search_context_size="medium",
                operation_tag="competitor_intelligence",
                thinking_budget=ThinkingBudget.ZERO,
                temperature=0.1
            )

            logger.debug(f"Successfully fetched competitor intelligence for {website}")
            return result

        except Exception as e:
            logger.error(f"Error fetching competitor intelligence: {str(e)}", exc_info=True)
            return {"competitors": []}

    async def fetch_customers_and_events(self, website: str) -> Dict[str, Any]:
        """
        Fetch customer and recent event intelligence for a company website.

        Args:
            website: The company website URL

        Returns:
            Dict containing customer and recent event data
        """
        try:
            logger.debug(f"Fetching customer and event intelligence for website: {website}")

            # Set up the customers and events prompt
            prompt = self._create_customers_events_prompt(website)

            # Use web search and structured output
            result = await self.ai_service.generate_structured_search_content(
                prompt=prompt,
                response_schema=CustomerEventIntelligence,
                search_context_size="medium",
                operation_tag="customer_event_intelligence",
                thinking_budget=ThinkingBudget.ZERO,
                temperature=0.1
            )

            logger.debug(f"Successfully fetched customer and event intelligence for {website}")
            return result

        except Exception as e:
            logger.error(f"Error fetching customer and event intelligence: {str(e)}", exc_info=True)
            return {"customers": [], "recent_events": []}

    def extract_competitor_names(self, intelligence_data: Dict[str, Any]) -> List[str]:
        """Extract competitor names from intelligence data."""
        competitors = []
        for competitor in intelligence_data.get("competitors", []):
            if competitor and isinstance(competitor, dict) and competitor.get("name"):
                competitors.append(competitor["name"])
        return competitors

    def extract_customer_names(self, intelligence_data: Dict[str, Any]) -> List[str]:
        """Extract customer names from intelligence data."""
        customers = []
        for customer in intelligence_data.get("customers", []):
            if customer and isinstance(customer, dict) and customer.get("name"):
                customers.append(customer["name"])
        return customers

    def extract_recent_events(self, intelligence_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract recent events from intelligence data."""
        events = []
        for event in intelligence_data.get("recent_events", []):
            if event and isinstance(event, dict) and event.get("title") and event.get("description"):
                events.append({
                    "title": event.get("title"),
                    "description": event.get("description"),
                    "date": event.get("date"),
                    "source": event.get("source")
                })
        return events

    def extract_citations(self, intelligence_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract citations from intelligence data if present."""
        return intelligence_data.get("citations", [])

    def _create_competitors_prompt(self, website: str) -> str:
        """Create prompt for the competitor intelligence gathering."""
        return f"""
Perform a comprehensive search to identify the main competitors of the company associated with the website {website}.

Focus only on direct competitors in the same industry or market segment. For each competitor:
- Provide the company name under the "name" field.
- Give a brief description of what they do under the "description" field.
- Include the source where you found this information under the "source" field.

Give at least 10 results in ranked order of most direct competitors first.

The response must follow this exact JSON structure:
{{
  "competitors": [
    {{
      "name": "Competitor Name",
      "description": "Description of what they do",
      "source": "URL or reference"
    }}
  ]
}}

Ensure that:
- Field names are exactly as specified: "name", "description", and "source".
- The JSON is properly formatted with the "competitors" array.
- Each entry is supported by at least one reputable source.
- There is no additional commentary or text outside the JSON structure.
"""

    def _create_customers_events_prompt(self, website: str) -> str:
        """Create prompt for the customer and recent events intelligence gathering."""
        return f"""
Perform a comprehensive search to compile detailed information about:

1. Notable customers of the company associated with website {website}:
   - Provide the customer company name under the "name" field.
   - Give a brief description of what they do under the "description" field.
   - Include the source where you found this information under the "source" field.

2. Recent significant events related to the company (past 6 months):
   - Include news, product launches, events, acquisitions, leadership changes, funding rounds, layoffs.

The response must follow this exact JSON structure:
{{
  "customers": [
    {{
      "name": "Customer Name",
      "description": "Description of what they do",
      "source": "URL or reference"
    }}
  ],
  "recent_events": [
    {{
      "title": "Event Title",
      "description": "Event Description",
      "date": "Event Date in yyyy-mm-dd format",
      "source": "URL or reference"
    }}
  ]
}}

Ensure that:
- Field names are exactly as specified: "name", "description", "source", "title", "date".
- The JSON is properly formatted with "customers" and "recent_events" arrays.
- Give at least 10 customer results.
- Give at least 3 most recent events.
- Each entry is supported by at least one reputable source.
- There is no additional commentary or text outside the JSON structure.
- Keep the events in reverse chronological order (most recent first).
- Make sure no event is older than 6 months.
"""

    def _get_empty_intelligence(self) -> Dict[str, Any]:
        """Return an empty intelligence data structure."""
        return {
            "competitors": [],
            "customers": [],
            "recent_events": []
        }