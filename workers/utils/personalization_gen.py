import logging
from typing import List, Optional, Dict, Any

from models.lead_activities import LeadResearchReport, ContentDetails, OpenAITokenUsage
from services.ai_service import AIServiceFactory

logger = logging.getLogger(__name__)


class LeadInsights:
    """Generate insights about a lead from their LinkedIn activities."""

    def __init__(
            self,
            lead_research_report_id: str,
            person_name: str,
            company_name: str,
            company_description: str,
            person_role_title: str,
            person_about_me: Optional[str] = None
    ):
        """Initialize insights generator."""
        self.lead_research_report_id = lead_research_report_id
        self.person_name = person_name
        self.company_name = company_name
        self.company_description = company_description
        self.person_role_title = person_role_title
        self.person_about_me = person_about_me or "Not available"

        self.model = AIServiceFactory.create_service("openai")

        self.operation_tag = "insights_generation"

    async def generate(self, all_content_details: List[ContentDetails]) -> LeadResearchReport.Insights:
        """Generate comprehensive insights from activities."""
        insights = LeadResearchReport.Insights()

        try:
            total_tokens = 0
            prompt_tokens = 0
            completion_tokens = 0
            total_cost = 0.0

            # Generate personality insights
            personality = await self._analyze_personality(all_content_details)
            if personality:
                insights.personality_traits = LeadResearchReport.Insights.PersonalityTraits(
                    description=personality.get("description", ""),
                    evidence=personality.get("evidence", [])
                )
                prompt_tokens += personality.get("prompt_tokens", 0)
                completion_tokens += personality.get("completion_tokens", 0)
                total_cost += personality.get("cost", 0.0)

            # Generate areas of interest
            interests = await self._analyze_interests(all_content_details)
            if interests:
                insights.areas_of_interest = [
                    LeadResearchReport.Insights.AreasOfInterest(
                        description=area.get("description", ""),
                        supporting_activities=area.get("activities", [])
                    )
                    for area in interests.get("areas", [])
                ]
                prompt_tokens += interests.get("prompt_tokens", 0)
                completion_tokens += interests.get("completion_tokens", 0)
                total_cost += interests.get("cost", 0.0)

            # Extract engaged colleagues
            colleagues = await self._analyze_engaged_colleagues(all_content_details)
            insights.engaged_colleagues = colleagues.get("colleagues", [])
            prompt_tokens += colleagues.get("prompt_tokens", 0)
            completion_tokens += colleagues.get("completion_tokens", 0)
            total_cost += colleagues.get("cost", 0.0)

            # Extract product engagement
            products = await self._analyze_product_engagement(all_content_details)
            insights.engaged_products = products.get("products", [])
            prompt_tokens += products.get("prompt_tokens", 0)
            completion_tokens += products.get("completion_tokens", 0)
            total_cost += products.get("cost", 0.0)

            # Calculate activity metrics
            insights.total_engaged_activities = len(all_content_details)
            insights.num_company_related_activities = len([
                cd for cd in all_content_details if cd.focus_on_company
            ])

            # Store token usage
            total_tokens = prompt_tokens + completion_tokens
            insights.total_tokens_used = OpenAITokenUsage(
                operation_tag=self.operation_tag,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                total_cost_in_usd=total_cost
            )

            return insights

        except Exception as e:
            logger.error(f"Error generating insights: {str(e)}", exc_info=True)
            return insights

    async def _analyze_personality(self, content_details: List[ContentDetails]) -> Dict[str, Any]:
        """Analyze personality traits from activities."""
        try:
            summaries = "\n\n".join([
                cd.one_line_summary for cd in content_details
                if cd.one_line_summary
            ])

            prompt = f"""Analyze {self.person_name}'s personality traits based on their LinkedIn activities:

{summaries}

Identify key personality traits and supporting evidence.

Return as JSON:
{{
    "description": string (2-3 sentences describing personality),
    "evidence": [string] (list of specific examples supporting traits),
    "prompt_tokens": number,
    "completion_tokens": number,
    "cost": number
}}"""

            response = await self.model.generate_content(prompt)
            return response

        except Exception as e:
            logger.error(f"Error analyzing personality: {str(e)}", exc_info=True)
            return {}

    async def _analyze_interests(self, content_details: List[ContentDetails]) -> Dict[str, Any]:
        """Analyze areas of interest from activities."""
        try:
            summaries = "\n\n".join([
                cd.detailed_summary for cd in content_details
                if cd.detailed_summary
            ])

            prompt = f"""Analyze {self.person_name}'s areas of interest based on LinkedIn activities:

{summaries}

Identify 3-5 key areas of professional interest.

Return as JSON:
{{
    "areas": [
        {{
            "description": string (area description),
            "activities": [string] (relevant activity summaries)
        }}
    ],
    "prompt_tokens": number,
    "completion_tokens": number,
    "cost": number
}}"""

            response = await self.model.generate_content(prompt)
            return response

        except Exception as e:
            logger.error(f"Error analyzing interests: {str(e)}", exc_info=True)
            return {}

    async def _analyze_engaged_colleagues(self, content_details: List[ContentDetails]) -> Dict[str, Any]:
        """Analyze colleague engagement patterns."""
        try:
            colleagues = []
            for cd in content_details:
                if cd.main_colleague:
                    colleagues.append(cd.main_colleague)

            if not colleagues:
                return {}

            prompt = f"""Analyze {self.person_name}'s engagement with colleagues at {self.company_name}:

Colleagues mentioned: {', '.join(colleagues)}

Return as JSON:
{{
    "colleagues": [string] (list of colleagues ordered by engagement frequency),
    "prompt_tokens": number,
    "completion_tokens": number,
    "cost": number
}}"""

            response = await self.model.generate_content(prompt)
            return response

        except Exception as e:
            logger.error(f"Error analyzing colleague engagement: {str(e)}", exc_info=True)
            return {}

    async def _analyze_product_engagement(self, content_details: List[ContentDetails]) -> Dict[str, Any]:
        """Analyze product engagement patterns."""
        try:
            products = []
            for cd in content_details:
                if cd.product_associations:
                    products.extend(cd.product_associations)

            if not products:
                return {}

            prompt = f"""Analyze {self.person_name}'s engagement with {self.company_name} products:

Products mentioned: {', '.join(products)}

Return as JSON:
{{
    "products": [string] (list of products ordered by engagement frequency),
    "prompt_tokens": number,
    "completion_tokens": number,
    "cost": number
}}"""

            response = await self.model.generate_content(prompt)

            return response

        except Exception as e:
            logger.error(f"Error analyzing product engagement: {str(e)}", exc_info=True)
            return {}

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON from AI response."""
        try:
            # Clean response text
            text = response.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

            import json
            return json.loads(text)

        except Exception as e:
            logger.error(f"Error parsing JSON response: {str(e)}")
            return {}
