import logging
import os
import json
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

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
            input_data: Optional[Dict[str, Any]] = None,
    ):
        """Initialize insights generator."""
        self.lead_research_report_id = lead_research_report_id
        self.person_name = person_name
        self.company_name = company_name
        self.company_description = company_description
        self.person_role_title = person_role_title
        self.person_about_me = person_about_me or "Not available"
        self.input_data = input_data

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

            if self.input_data:
                # Recommend personalization signals.
                signals_response = await self._provide_personalization_signals(content_details=all_content_details)
                if "personalizations" in signals_response:
                    signals = signals_response["personalizations"]
                    logger.debug(f"For person: {self.person_name}, company name: {self.company_name}, Signals found are: {signals}")
                    insights.personalization_signals = [LeadResearchReport.Insights.PersonalizationSignal(description=signal.get(
                        "signal"), reason=signal.get("reason"), outreach_message=signal.get("personalized_outreach_message")) for signal in signals]
                    logger.debug(f"Provided personalization signals for {self.person_name}: company name: {self.company_name}")
                else:
                    logger.debug(f"Personalization signals missing for {self.person_name}: comapny name: {self.company_name} in response: {signals_response}")
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
        lead_data = json.dumps(self.input_data.get('lead_data'), indent=2)
        account_data = json.dumps(self.input_data.get('account_data'), indent=2)
        product_data = json.dumps(self.input_data.get('product_data'), indent=2)
        date_now = datetime.strftime(datetime.now(timezone.utc), "%Y-%m-%d")
        lead_engagements = json.dumps([cd.model_dump() for cd in content_details], indent=2, default=str)
        try:
            prompt = f"""
You're a highly intelligent B2B Sales Development Representative tasked with performing outreach for Leads.

You recognize that the only way to get responses to outreach is by personalizing your outreach message to the Lead.
The definition of a personalization is to find the best Signals associated with a Lead or their Company that can make your product very relevant way to them.

You will be provided the following inputs delimited by triple quotes below:
1. Details of the Product you are selling including its description, Target Personas and a Sales Playbook with guidelines for Outreach.
2. Details of the Lead's Company including Technologies used, their Competitors, their Customers, Employee Count etc.
3. Details of the Lead including Current employment, Description of Role, Employment history, Education, Projects etc.
4. Details of recent LinkedIn Activities that the Lead has engaged with i.e. has posted, reposted, commented or liked.

Your goal is to use the Sales Playbook to identify the best Signals in the Lead or their Company and craft a personalized message using the specific guideline provided in the Playbook.
The date today is {date_now}. Use it compute any time related Signals (e.g. Recent Lead promotion, Joining company, Anniversary at Company etc.) that might be relevant.

Return as JSON:
{{
    "personalizations": [
        {{
            "signal": string (Cite the Signal used),
            "reason": string (Explain why this Signal was chosen),
            "personalized_outreach_message" string,
        }}
    ]
}}
1. Return ONLY valid JSON without codeblocks, additional comments or anything else.
2. If a field is not available, use null.
3. Do not include any other information or pleasantries or anything else outside the JSON.

\"\"\"
Product Details:
{product_data}

Lead's Company Details:
{account_data}

Lead Details:
{lead_data}

### Lead's engagement on LinkedIn
{lead_engagements}

\"\"\"
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
