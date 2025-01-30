import logging
import os
from typing import List, Optional, Dict, Any

from google.api_core.exceptions import ResourceExhausted

from models.lead_activities import LeadResearchReport, ContentDetails, OpenAITokenUsage
from services.ai_service import AIServiceFactory
from utils.retry_utils import RetryConfig, RetryableError, with_retry

logger = logging.getLogger(__name__)


GEMINI_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=2.0,
    max_delay=30.0,
    retryable_exceptions=[
        RetryableError,
        ResourceExhausted,
        ValueError,
        RuntimeError,
        TimeoutError,
        ConnectionError
    ]
)


class LeadInsights:
    """Generate insights about a lead from their LinkedIn activities."""

    def __init__(
            self,
            lead_research_report_id: str,
            person_name: str,
            company_name: str,
            company_description: str,
            person_role_title: str,
            person_about_me: Optional[str] = None,
            lead: Optional[Dict[str, Any]] = None,
            product: Optional[Dict[str, Any]] = None
    ):
        """Initialize insights generator."""
        self.lead_research_report_id = lead_research_report_id
        self.person_name = person_name
        self.company_name = company_name
        self.company_description = company_description
        self.person_role_title = person_role_title
        self.person_about_me = person_about_me or "Not available"
        self.lead = lead
        self.product = product

        self.GEMINI_API_TOKEN = os.getenv("GEMINI_API_TOKEN")
        if not self.GEMINI_API_TOKEN:
            raise ValueError("GEMINI_API_TOKEN environment variable required")

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

            # Generate outreach recommendations
            outreach = await self._analyze_outreach_approach(all_content_details)
            logger.debug(f"Outreach analysis for {self.person_name}: {outreach}")
            if outreach:
                insights.recommended_approach = LeadResearchReport.Insights.OutreachRecommendation(
                    approach=outreach.get("approach", ""),
                    key_topics=outreach.get("key_topics", []),
                    conversation_starters=outreach.get("conversation_starters", []),
                    best_channels=outreach.get("best_channels", []),
                    timing_preferences=outreach.get("timing_preferences", ""),
                    cautions=outreach.get("cautions", [])
                )
                prompt_tokens += outreach.get("prompt_tokens", 0)
                completion_tokens += outreach.get("completion_tokens", 0)
                total_cost += outreach.get("cost", 0.0)

            if self.lead and self.product:
                # Find personalization signals.
                signals = self._provide_personalization_signals(content_details=all_content_details)
                insights.personalization_signals = [LeadResearchReport.Insights.PersonalizationSignal(description=signal.get(
                    "description"), reason=signal.get("reason"), outreach_message=signal.get("outreach_message")) for signal in signals]
                logger.debug(f"Provided personalization signals for {self.person_name}: company name: {self.company_name}")
            else:
                logger.debug(f"Skipping personalization signals since one of Lead or Product is None for {self.person_name}, company: {self.company_name}")

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

    @with_retry(retry_config=GEMINI_RETRY_CONFIG, operation_name="_provide_personalization_signals")
    async def _provide_personalization_signals(self, content_details: List[ContentDetails]) -> Dict[str, Any]:
        """Provide personalization signals for outreach."""
        logger.debug(f"Provide personalization signals for {self.person_name} at {self.company_name}")
        try:
            prompt = f"""
You are a Sales person who is tasked with outbound sales to a given prospect.
You are super intelligent and recognize that the only way to get responses to cold outreach is by personalizing your outreach message to the prospect.
The definition of a personalization is to take all the context associated with a Prospect and their Company and finding those pieces of information (also called signals or triggers) that can tie in the product you are selling in a very relevant way for the prospect. In your outreach, you will reference these signals to appear relevant to the Prospect.

The signals or triggers that matter to the product you are selling can be found in the Sales playbook. It provides different outreach approaches depending on the signals found in the context associated with the Prospect.

Below we have provided all the context associated with the Prospect: their Professional profile, details about their Company, their recent Social media activities etc.
We have also provided details about the Product you are selling and the associated Sales Playbook that encodes the personalization approach for different signals that could be found in the context.

Using the Context and the Sales playbook as a guide, figure out the best signals that you can reference to make your outreach super personalized to the Prospect.
Return as JSON:
{{
    "personalization_signals": [
        {{
            "description": string,
            "reason": string (Feel free to cite a source as evidence),
            "outreach_message" string (outreach message referencing the signal),
        }}
    ]
}}

````
## Context

### Prospect and their Company's Details
{self.lead}

### Prospect's engagement on LinkedIn
{[cd.model_dump() for cd in content_details]}


## Product and Sales Playbook Description
{self.product}
```
            """
            logger.info(f"Personalization Signals prompt: {prompt}")
            return await self.model.generate_content(prompt)
        except Exception as e:
            logger.error(f"Error providing personalization signals for {self.person_name} at {self.company_name} with error: {str(e)}", exc_info=True)
            return {}

    @with_retry(retry_config=GEMINI_RETRY_CONFIG, operation_name="_analyze_outreach_approach")
    async def _analyze_outreach_approach(self, content_details: List[ContentDetails]) -> Dict[str, Any]:
        """Analyze and recommend personalized outreach approach."""
        logger.debug(f"Analyzing outreach approach for {self.person_name} at {self.company_name}")
        try:
            # Combine relevant activity details
            activity_summaries = "\n\n".join([
                cd.detailed_summary for cd in content_details
                if cd.detailed_summary
            ])

            # Construct comprehensive context
            context = f"""
Person: {self.person_name}
Role: {self.person_role_title}
Company: {self.company_name}
Company Description: {self.company_description}
About: {self.person_about_me}

Recent Activities:
{activity_summaries}
"""

            prompt = f"""Analyze the following information and recommend a personalized outreach approach:

{context}

Consider:
1. Their communication style and preferences based on activity patterns
2. Topics they engage with most frequently
3. Best conversation starters based on recent activities
4. Optimal channels and timing based on their engagement patterns
5. Any potential sensitivities or topics to avoid

Return as JSON:
{{
    "approach": string (2-3 sentences describing recommended approach),
    "key_topics": [string] (3-5 topics they care most about),
    "conversation_starters": [string] (3 specific talking points based on their activities),
    "best_channels": [string] (recommended outreach channels in order of preference),
    "timing_preferences": string (when they seem most active/responsive),
    "cautions": [string] (list of topics or approaches to avoid),
    "prompt_tokens": number,
    "completion_tokens": number,
    "cost": number
}}"""

            return await self.model.generate_content(prompt)

        except Exception as e:
            logger.error(f"Error analyzing outreach approach: {str(e)}", exc_info=True)
            return {}

    @with_retry(retry_config=GEMINI_RETRY_CONFIG, operation_name="_analyze_personality")
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

            return await self.model.generate_content(prompt)

        except Exception as e:
            logger.error(f"Error analyzing personality: {str(e)}", exc_info=True)
            return {}

    @with_retry(retry_config=GEMINI_RETRY_CONFIG, operation_name="_analyze_interests")
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

            return await self.model.generate_content(prompt)

        except Exception as e:
            logger.error(f"Error analyzing interests: {str(e)}", exc_info=True)
            return {}

    @with_retry(retry_config=GEMINI_RETRY_CONFIG, operation_name="_analyze_engaged_colleagues")
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

            return await self.model.generate_content(prompt)
        except Exception as e:
            logger.error(f"Error analyzing colleague engagement: {str(e)}", exc_info=True)
            return {}

    @with_retry(retry_config=GEMINI_RETRY_CONFIG, operation_name="_analyze_product_engagement")
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

            return await self.model.generate_content(prompt)

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
