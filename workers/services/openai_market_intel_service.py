from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from utils.loguru_setup import logger
from services.ai_service import AIService

class Competitor(BaseModel):
    name: str
    description: str
    source: str

class Customer(BaseModel):
    name: str
    description: str
    source: str

class RecentEvent(BaseModel):
    title: str
    description: str
    date: str
    source: str

class CompanyIntelligence(BaseModel):
    competitors: List[Competitor]
    customers: List[Customer]
    recent_events: List[RecentEvent]

class OpenAISearchService:
    """Service for using OpenAI's web search capability with structured output to gather market intelligence."""

    def __init__(self, openai_service: AIService):
        """Initialize the OpenAI search service.

        Args:
            openai_service: Configured OpenAIService instance
        """
        self.openai_service = openai_service

    async def fetch_company_intelligence(self, website: str) -> Dict[str, Any]:
        """
        Fetch competitor and customer intelligence for a company website using OpenAI with web search.

        Args:
            website: The company website URL

        Returns:
            Dict containing competitors, customers, and recent events
        """
        try:
            logger.debug(f"Fetching company intelligence for website: {website}")

            # Set up the search prompt
            prompt = self._create_intelligence_prompt(website)

            # Use the Responses API with web search and structured output
            result = await self.openai_service.generate_structured_search_content(
                prompt=prompt,
                response_schema=CompanyIntelligence,
                search_context_size="medium",  # Default for balance between quality and speed
                operation_tag="market_intelligence"
            )

            # Validate and parse the response
            if not result or not isinstance(result, dict):
                logger.warning(f"Invalid response format from OpenAI search: {type(result)}")
                return self._get_empty_intelligence()

            logger.debug(f"Successfully fetched company intelligence for {website}")
            return result

        except Exception as e:
            logger.error(f"Error fetching company intelligence: {str(e)}", exc_info=True)
            return self._get_empty_intelligence()

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
        return intelligence_data.get("citations", [])

    def _create_intelligence_prompt(self, website: str) -> str:
        """Create prompt for the intelligence gathering."""
        return f"""
Perform a comprehensive search to compile detailed information about the competitors, customers, and recent events related to the website {website}. Use data from both the company's own website and other reputable sources. Present the output strictly as plain JSON with no additional text. Use the following structure:

{{
        "competitors": [
    {{
        "name": "Competitor Name",
      "description": "A brief description of the competitor and its offerings.",
      "source": "URL or reference to the source"
    }},
    ...
  ],
  "customers": [
    {{
        "name": "Customer Name",
      "description": "A brief description of how this customer uses or benefits from the service.",
      "source": "URL or reference to the source"
    }},
    ...
  ],
  "recent_events": [
    {{
        "title": "Event Title",
      "description": "A brief description of the event and its significance.",
      "date": "YYYY-MM-DD",
      "source": "URL or reference to the source"
    }},
    ...
  ]
}}

Ensure that:
- The JSON is properly formatted.
- Each entry is supported by at least one reputable source.
- The output includes multiple examples for each category.
- There is no additional commentary or text outside the JSON structure.
- Try and give 10 results each for competitors and customers and at least 3 most recent events for recent_events
"""

    def _get_empty_intelligence(self) -> Dict[str, Any]:
        """Return an empty intelligence data structure."""
        return {
            "competitors": [],
            "customers": [],
            "recent_events": []
        }