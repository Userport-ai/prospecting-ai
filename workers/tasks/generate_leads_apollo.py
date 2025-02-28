import asyncio
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from typing import Dict, Any, List, Optional, Union

from services.ai_service import AIServiceFactory
from services.api_cache_service import APICacheService, cached_request
from services.bigquery_service import BigQueryService
from services.jina_service import JinaService
from services.proxycurl_service import ProxyCurlService
from services.builtwith_service import BuiltWithService
from utils.retry_utils import RetryableError, RetryConfig, with_retry
from utils.url_utils import UrlUtils
from models.leads import ApolloLead, SearchApolloLeadsResponse, EnrichedLead, EvaluateLeadsResult, EvaluatedLead
from models.accounts import SearchApolloOrganizationsResponse
from .enrichment_task import AccountEnrichmentTask

logger = logging.getLogger(__name__)


@dataclass
class ApolloConfig:
    """Centralized configuration management."""
    max_employees: int = 1000
    batch_size: int = 100
    ai_batch_size: int = 5
    fit_score_threshold: float = 0.0
    cache_ttl_hours: int = 24 * 30
    concurrent_requests: int = 4
    ai_concurrent_requests: int = 4
    max_retries: int = 3
    retry_delay: float = 1.0
    max_retry_delay: float = 5.0
    enrich_leads: bool = True
    confidence_threshold: int = 50
    min_fit_threshold: int = 50

    # Configuration parameters for scoring
    seniority_thresholds: Dict[str, float] = field(default_factory=lambda: {
        'c_suite': 50,
        'vp': 55,
        'head': 60,
        'director': 65,
        'manager': 70,
        'senior': 80,
        'default': 65
    })

    function_match_boost: float = 0.9  # Reduce threshold by 10%
    department_match_boost: float = 0.9  # Reduce threshold by 10%
    recent_promotion_boost: float = 0.85  # Reduce threshold by 15%
    company_size_adjustments: Dict[str, float] = field(default_factory=lambda: {
        'enterprise': 0.9,  # Reduce threshold by 10% for enterprise
        'mid_market': 1.0,  # No adjustment for mid-market
        'small': 1.1  # Increase threshold by 10% for small companies
    })


AI_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=5.0,
    retryable_exceptions=[
        RetryableError,
        asyncio.TimeoutError,
        ConnectionError,
        Exception  # Allow everything to be retryable here
    ]
)


@dataclass
class ProcessingMetrics:
    """Track processing metrics for monitoring."""
    total_leads_processed: int = 0
    successful_leads: int = 0
    failed_leads: int = 0
    processing_time: float = 0.0
    api_errors: int = 0
    ai_errors: int = 0
    enriched_leads: int = 0  # New: Track enriched leads
    enrichment_errors: int = 0  # New: Track enrichment errors


@dataclass
class PromptTemplates:
    """Store prompt templates for AI analysis of leads."""
    LEAD_EVALUATION_PROMPT = """
    You're an experienced SDR tasked with evaluating leads.
    Evaluate potential leads based on the given product and persona criteria. Rate each lead's fit.
    1. Evaluate each lead independently, without referring to the other leads.
    2. Use the given product and persona information to evaluate each lead. Consider how likely the lead is to have the pain point the product is solving.
    3. You can assume that the account is already qualified and have a good potential fit, you're only evaluating leads.
    4. Rationale and analysis should highlight and quote specific instances from the data that supports the score.
    5. Consider their role titles in conjunction with the content including their background, about them, descriptions provided before deciding on persona fit. Often titles are abstract and may not describe their role comprehensively.
    6. The role and responsibility of a certain role title also depends on the size of the company. So consider that before concluding anything.
    7. Analyze the lead's information, focusing on how their background, role, or responsibilities relate to the product.
    8. Assign a Fit Score from 0 to 1, where 1 indicates a perfect fit and 0 indicates no alignment.
    9. Identify the best matching persona type (e.g., end_user, buyer, influencer) or use null if none apply.
    10. Recommend an engagement approach tailored to this lead.
    11. Provide an overall analysis summarizing the lead's potential.

    Website Context:
    {website_context}

    Product Information:
    {product_info}

    Target Personas:
    {persona_info}

    Lead Data:
    {lead_data}

    Evaluate each lead and return a JSON response with this structure:
    {{
        "evaluated_leads": [
            {{
                "lead_id": string,
                "fit_score": number (0-1),
                "rationale": string,
                "matching_criteria": [string],
                "persona_match": string or null,
                "recommended_approach": string,
                "overall_analysis":[string]
            }}
        ]
    }}
    1. Return ONLY valid JSON without codeblocks, additional comments or anything else.
    2. If a field is not available, use null
    3. Do not include any other information or pleasantries or anything else outside the JSON

    Example (Structure only):
{{
  "evaluated_leads": [
    {{
      "lead_id": "6784a8440ec1a623615b2053",
      "fit_score": 0.85,
      "rationale": "Lead demonstrates strong alignment with product features and decision-making authority",
      "matching_criteria": [
        "Role matches target persona",
        "Expressed interest in similar solutions"
      ],
      "persona_match": "buyer",
      "recommended_approach": "Highlight ROI and integration capabilities in initial outreach",
      "overall_analysis": [
        "High potential for conversion",
        "Likely to influence purchase decision"
      ]
    }}
  ]
}}
    """

    LEAD_EVALUATION_PROMPT_V2 = """
You're a highly intelligent B2B Sales Development Representative tasked with evaluating leads that are the best fit for the Product you are selling.

You will be provided the following inputs delimited by triple quotes below:
1. Description of the Product you are selling.
2. Role titles of the Target Personas that need your Product.
3. Additional Signals (for example Keywords or events) that makes a Lead more relevant to your Product.
4. The Profiles of Leads you need to evaluate.

Your goal is to look for the Signals provided within each Leads's profile to evaluate how good of a match they are for selling your product to them.

Persona Types (choose one if possible):
- end_user: Uses the product on a day-to-day basis. Typically in more hands-on, operational roles.
- influencer: Has significant sway in purchase decisions, but may not directly hold budget.
             Could be team leads, department heads, or strong opinion leaders.
- buyer: Owns or significantly influences the budget, purchase authority, or procurement process.

Examples:
Example 1:
- Title: "Senior Data Analyst" → Usually end_user if the product is data/analytics-related.
Example 2:
- Title: "Head of Engineering" → Often influencer esp if the product is technical/engineering related.
Example 3:
- Title: "VP of Sales" → Likely buyer, since they typically control or heavily influence budgets for products used in sales organisations.

Important:
*. Role Titles of Target Personas below is the list of target personas you need to match each lead with.
*. Always assign one of end_user, influencer, buyer to the persona type if there's *any plausible match*.
*. Only assign null when there is NO conceivable match at all with any persona type.
*. Evaluate each lead independently, without referring to the other leads.
*. Assign a Fit Score from 0 to 100, where 100 indicates a perfect fit to the persona type, ICP and 0 indicates no alignment.
*. The more Signals you find in the Lead's profile that are relevant to your Product, the higher their score.
*. Consider their role titles in conjunction with the content including their background, about them, role descriptions, employment history and their profile provided. Often titles are abstract and the context around the title helps strengthen the conviction on the chosen persona type.
*. If the lead has started a new role recently or has recently been promoted, consider these as Signals as well.
*. Rationale should highlight and cite the specific Signals from the Lead's Profile that supports the score. If there are no Signals, say "No Signals found".
*. Write full sentences for bullet points in `matching_signals` and explain each signal with rationale from the lead's profile. Don't make up any reasons.

Evaluate each lead and return a JSON response with this structure:
{{
    "evaluated_leads": [
        {{
            "id": string,
            "fit_score": number (0-100),
            "rationale": string,
            "matching_signals": [string],
            "persona_match": string or null,
            "internal_analysis": string
        }}
    ]
}}
1. Return ONLY valid JSON without codeblocks, additional comments or anything else.
2. If a field is not available, use null.
3. Do not include any other information or pleasantries or anything else outside the JSON.

\"\"\"
Product Description:
{product_description}

Role Titles of Target Personas:
{persona_role_titles}

Additional Signals:
{additional_signals}

For each lead, you have:
1. Their profile information
2. Pre-evaluation insights showing:
   - Initial assessment score
   - Key signals identified
   - Career insights
   - Initial confidence level

Consider these insights but form your own evaluation. If you disagree with the pre-evaluation:
1. Explain why based on product fit in the `internal_analysis` field. You may use content from pre-evaluation in other fields however, DO NOT refer to "pre-evaluation" as a word/thing anywhere other than in `internal_analysis`.
2. Provide your reasoning based on the product context

If a lead had high pre-evaluation confidence and score but you score them lower:
- Explicitly explain the misalignment with the product in `internal_analysis` field
- Reference specific aspects of the product that don't match

Lead Profiles (with pre-evaluation insights):
{lead_profiles}

\"\"\"
"""


def _is_recent_career_change(lead: ApolloLead) -> bool:
    """
    Check if the lead has been recently promoted or changed roles.
    Returns False if there are any date parsing errors.
    """
    if not lead.employment_history:
        return False

    current_role = next(
        (emp for emp in lead.employment_history if emp.current),
        None
    )

    if not current_role or not current_role.start_date:
        return False

    try:
        start_date = datetime.strptime(current_role.start_date, "%Y-%m-%d")
        months_in_role = (datetime.now() - start_date).days / 30
        return months_in_role <= 6  # Consider promotions within last 6 months as recent
    except ValueError:
        # Handle invalid date format
        return False


def _determine_company_size(organization: Optional[Union[Dict[str, Any], object]]) -> str:
    """
    Determine company size category based on employee count and annual revenue.
    This function handles both dictionary inputs and objects with attribute access.
    """
    if not organization:
        return 'mid_market'

    # Check if organization is a dict; if not, use attribute access.
    if isinstance(organization, dict):
        employee_count = organization.get('estimated_num_employees') or 0
        annual_revenue = organization.get('annual_revenue') or 0
    else:
        employee_count = getattr(organization, 'estimated_num_employees', 0) or 0
        annual_revenue = getattr(organization, 'annual_revenue', 0) or 0

    if not employee_count or not annual_revenue:
        return "mid_market"

    if employee_count > 1000 or annual_revenue > 100000000:
        return 'enterprise'
    elif employee_count > 100 or annual_revenue > 10000000:
        return 'mid_market'
    else:
        return 'small'


class ApolloLeadsTask(AccountEnrichmentTask):
    """Task for identifying potential leads using Apollo API, ProxyCurl enrichment and AI analysis."""

    ENRICHMENT_TYPE = 'generate_leads'

    # Retry configurations
    APOLLO_RETRY_CONFIG = RetryConfig(
        max_attempts=3,
        base_delay=1.0,
        max_delay=5.0,
        retryable_exceptions=[
            RetryableError,
            asyncio.TimeoutError,
            ConnectionError
        ]
    )

    def __init__(self, callback_service):
        """Initialize the task with required services and configurations."""
        super().__init__(callback_service)
        self.callback_svc = callback_service
        self.config = ApolloConfig()
        self.metrics = ProcessingMetrics()
        self.bq_service = BigQueryService()
        self._initialize_credentials()
        self._configure_ai_service()
        self._initialize_services()
        self.prompts = PromptTemplates()
        self.jina_service = JinaService()

    def _initialize_credentials(self) -> None:
        """Initialize and validate required API credentials."""
        self.apollo_lead_search_api_key = os.getenv('APOLLO_LEAD_SEARCH_API_KEY')
        self.apollo_org_search_api_key = os.getenv('APOLLO_ORG_SEARCH_API_KEY')
        self.project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
        self.dataset = os.getenv('BIGQUERY_DATASET', 'userport_enrichment')

        if not self.apollo_lead_search_api_key:
            raise ValueError("APOLLO_LEAD_SEARCH_API_KEY environment variable is required")
        if not self.apollo_org_search_api_key:
            raise ValueError("APOLLO_ORG_SEARCH_API_KEY environment variable is required")

        # Initialize cache service
        self.cache_service = APICacheService(
            client=self.bq_service.client,
            project_id=self.project_id,
            dataset=self.dataset
        )

    def _configure_ai_service(self) -> None:
        """Configure the Gemini AI service."""
        self.model = AIServiceFactory().create_service("gemini")

    def _initialize_services(self) -> None:
        """Initialize required services."""
        self.proxycurl_service = ProxyCurlService(self.cache_service)

    @property
    def enrichment_type(self) -> str:
        return self.ENRICHMENT_TYPE

    @property
    def task_name(self) -> str:
        """Get the task identifier."""
        return "lead_identification_apollo"

    async def create_task_payload(self, **kwargs) -> Dict[str, Any]:
        """Create a standardized task payload."""
        required_fields = ['account_id', 'account_data', 'product_data']
        missing_fields = [field for field in required_fields if field not in kwargs]

        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

        return {
            "account_id": kwargs["account_id"],
            "account_data": kwargs["account_data"],
            "product_data": kwargs["product_data"],
            "tenant_id": kwargs.get("tenant_id"),
            "job_id": str(uuid.uuid4())
        }

    def _get_target_departments_and_functions(self, target_personas: Dict[str, Any]) -> tuple[list[str], list[str]]:
        """Extract target departments and functions from personas."""
        target_departments = []
        target_functions = []

        for persona_data in target_personas.values():
            if isinstance(persona_data, list):
                for persona in persona_data:
                    if isinstance(persona, dict):
                        if 'departments' in persona:
                            target_departments.extend(d.lower() for d in persona['departments'])
                        if 'functions' in persona:
                            target_functions.extend(f.lower() for f in persona['functions'])

        return target_departments, target_functions

    def _has_matching_terms(self, source_terms: List[str], target_terms: List[str]) -> bool:
        """
        Check if any source term contains or is contained within any target term.
        This allows for partial matches while handling underscores and common variations.
        """
        if not source_terms or not target_terms:
            return False

        source_terms = [term.lower().replace('_', ' ') for term in source_terms]
        target_terms = [term.lower().replace('_', ' ') for term in target_terms]

        for source in source_terms:
            for target in target_terms:
                # Check both directions of containment
                if source in target or target in source:
                    logger.debug(f"Term match found: {source} ⟷ {target}")
                    return True
        return False

    def _should_enrich_lead(
            self,
            evaluation: Dict[str, Any],
            apollo_lead: ApolloLead,
            product_data: Dict[str, Any]
    ) -> bool:
        """
        Enhanced logic for determining if a lead should be enriched.
        """
        # Use 'or 0' to ensure we don't get None values for numeric comparisons.
        score = evaluation.get('initial_score') or 0
        confidence = evaluation.get('confidence') or 0
        career_insights = evaluation.get('career_insights', {})

        # Get target personas from product data
        target_personas = product_data.get('persona_role_titles', {})
        target_departments, target_functions = self._get_target_departments_and_functions(target_personas)

        # 1. Base threshold from configuration based on seniority
        base_threshold = self.config.seniority_thresholds.get(
            apollo_lead.seniority,
            self.config.seniority_thresholds['default']
        )

        # 2. Company size adjustment
        company_size = _determine_company_size(apollo_lead.organization)
        size_multiplier = self.config.company_size_adjustments.get(company_size) or 1.0
        adjusted_threshold = base_threshold * size_multiplier

        # 3. Recent career changes
        if _is_recent_career_change(apollo_lead):
            adjusted_threshold *= self.config.recent_promotion_boost

        # 4. Department and function matching with boosting
        department_match = self._has_matching_terms(
            apollo_lead.departments,
            target_departments
        )
        function_match = self._has_matching_terms(
            apollo_lead.functions,
            target_functions
        )

        if department_match:
            adjusted_threshold *= self.config.department_match_boost
        if function_match:
            adjusted_threshold *= self.config.function_match_boost

        # 5. Industry experience validation
        relevant_experience = career_insights.get('years_of_relevant_experience') or 0
        industry_alignment = career_insights.get('industry_alignment') or 'low'

        if relevant_experience >= 5 and industry_alignment in ['high', 'medium']:
            adjusted_threshold *= 0.9  # 10% reduction for experienced professionals

        # 6. Decision making
        meets_thresholds = (
            score >= adjusted_threshold and
            confidence >= self.config.confidence_threshold
        )

        # Logging for transparency
        if meets_thresholds:
            logger.debug(
                f"Lead {apollo_lead.id} qualified for enrichment:\n"
                f"Base threshold: {base_threshold}\n"
                f"Adjusted threshold: {adjusted_threshold}\n"
                f"Score: {score}\n"
                f"Confidence: {confidence}\n"
                f"Adjustments applied: company_size={size_multiplier}, "
                f"department_match={department_match}, function_match={function_match}"
            )

        return meets_thresholds

    @with_retry(retry_config=AI_RETRY_CONFIG, operation_name="pre_evaluate_apollo_leads")
    async def pre_evaluate_apollo_leads(self, apollo_leads: List[ApolloLead], product_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Pre-evaluate Apollo leads to determine which ones warrant ProxyCurl enrichment."""
        try:
            if not apollo_leads:
                logger.warning("No Apollo leads provided for evaluation")
                return []

            base_prompt = f"""
            You are an experienced BDR/SDR tasked with quickly evaluating a list of potential leads based on limited information.
            Your goal is to identify leads that show strong potential and warrant deeper research/enrichment.

            Product Description:
            {product_data.get('description')}

            Target Personas:
            {json.dumps(product_data.get('persona_role_titles', {}), indent=2)}

            Evaluation Guidelines:
            1. Role Relevance:
               - How closely does their title match our target personas?
               - Is their seniority level appropriate for decision-making/influence?
               - Do their departments/functions align with our product's use case?

            2. Company Context:
               - Does their company profile suggest they might need our solution?
               - Is the company in our target market/industry?
               - Consider company size and maturity

            3. Confidence Level:
               - How certain are we about this evaluation given limited data?
               - What factors increase/decrease our confidence?

            Return a JSON response with this structure:
            {{
                "evaluated_leads": [
                    {{
                        "lead_id": string,
                        "initial_score": number (0-100),
                        "reason": string (specific reasons for the score),
                        "enrichment_recommended": boolean,
                        "confidence": number (0-100),
                        "key_signals": [string] (specific positive signals found),
                        "career_insights": {{
                            "relevant_past_roles": [string],
                            "years_of_relevant_experience": number,
                            "industry_alignment": string,
                            "function_alignment": string
                        }}
                    }}
                ]
            }}
            """

            # Configure concurrency
            semaphore = asyncio.Semaphore(self.config.ai_concurrent_requests)

            async def process_batch(batch: List[ApolloLead]) -> List[Dict[str, Any]]:
                async with semaphore:
                    try:
                        batch_data = [{
                            'id': lead.id,
                            'name': lead.name,
                            'headline': lead.headline,
                            'title': lead.title,
                            'seniority': lead.seniority,
                            'departments': lead.departments,
                            'subdepartments': lead.subdepartments,
                            'functions': lead.functions,
                            'organization': {
                                'name': lead.organization.name if lead.organization else None,
                                'founded_year': lead.organization.founded_year if lead.organization else None,
                                'website_url': lead.organization.website_url if lead.organization else None,
                                'primary_domain': lead.organization.primary_domain if lead.organization else None
                            } if lead.organization else None,
                            'employment_history': [{
                                'title': emp.title,
                                'organization_name': emp.organization_name,
                                'current': emp.current,
                                'description': emp.description,
                                'start_date': emp.start_date,
                                'end_date': emp.end_date
                            } for emp in lead.employment_history] if lead.employment_history else [],
                        } for lead in batch]

                        batch_prompt = f"{base_prompt}\n\nThe leads to evaluate:\n{json.dumps(batch_data, indent=2)}"
                        response = await self.model.generate_content(batch_prompt, is_json=True, operation_tag="pre_evaluate_apollo_leads")

                        if not response:
                            logger.error("Empty response from AI model")
                            self.metrics.ai_errors += 1
                            return []

                        if 'evaluated_leads' not in response:
                            logger.error(f"Invalid response structure: {response}")
                            self.metrics.ai_errors += 1
                            return []
                        return response['evaluated_leads']

                    except Exception as e:
                        logger.error(f"Error processing batch: {str(e)}")
                        self.metrics.ai_errors += 1
                        return []

            # Create batches and tasks
            batches = [apollo_leads[i:i + self.config.ai_batch_size]
                       for i in range(0, len(apollo_leads), self.config.ai_batch_size)]
            tasks = [process_batch(batch) for batch in batches]

            # Execute all batches concurrently and gather results
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Combine and filter results
            evaluated_leads = []
            for batch_result in results:
                if isinstance(batch_result, Exception):
                    logger.error(f"Batch processing failed: {str(batch_result)}")
                    self.metrics.ai_errors += 1
                else:
                    evaluated_leads.extend(batch_result)

            return evaluated_leads

        except Exception as e:
            logger.error(f"Error in initial lead evaluation: {str(e)}", exc_info=True)
            return []

    async def execute(self, payload: Dict[str, Any]) -> (Dict[str, Any], Dict[str, Any]):
        """Execute the lead identification task."""
        start_time = time.time()
        job_id = payload.get('job_id')
        account_id = payload.get('account_id')
        account_data = payload.get('account_data', {})
        product_data = payload.get('product_data', {})
        current_stage = 'initialization'

        name = account_data.get("name")
        if not name:
            raise ValueError(f"Account name is requried for lead identication for account ID: {account_id}")
        website = account_data.get('website')
        if not website:
            raise ValueError(f"Account website/domain is required for lead identification for account ID: {account_id}")
        domain = UrlUtils.get_domain(url=website)
        if not domain:
            raise ValueError(f"Domain is required for lead identification for account ID: {account_id}")
        account_data['domain'] = domain

        logger.info(f"Starting lead identification for job_id: {job_id}, account_id: {account_id}")

        try:
            # Send initial processing callback
            await self.callback_svc.send_callback(
                job_id=job_id,
                account_id=account_id,
                enrichment_type=self.ENRICHMENT_TYPE,
                source="apollo",
                status='processing',
                completion_percentage=10,
                processed_data={'stage': current_stage}
            )

            # Fetch Apollo Organization ID.
            current_stage = 'fetching_apollo_org_id'
            apollo_org_id: Optional[str] = await self._fetch_apollo_organization_id(name=name, domain=domain)
            if not apollo_org_id:
                logger.error(f"Failed to fetch Apollo Organization ID for domain: {domain}")

            # Fetch employees with concurrent processing
            current_stage = 'fetching_employees'
            apollo_leads: List[ApolloLead] = await self._fetch_employees_concurrent(domain=domain, apollo_org_id=apollo_org_id)
            self.metrics.total_leads_processed = len(apollo_leads)

            await self.callback_svc.send_callback(
                job_id=job_id,
                account_id=account_id,
                enrichment_type=self.ENRICHMENT_TYPE,
                source="apollo",
                status='processing',
                completion_percentage=30,
                processed_data={
                    'stage': current_stage,
                    'employees_found': len(apollo_leads)
                }
            )

            # Initial evaluation of Apollo leads
            current_stage = 'initial_evaluation'
            pre_evaluation_results = await self.pre_evaluate_apollo_leads(apollo_leads, product_data)

            # Filter leads for enrichment
            leads_for_enrichment = []
            skipped_leads = []
            apollo_leads_dict = {lead.id: lead for lead in apollo_leads}

            for eval_result in pre_evaluation_results:
                initial_score = eval_result.get("initial_score", 0)
                lead_id = eval_result.get("id") or eval_result.get("lead_id")

                # Skip if no valid lead_id or corresponding Apollo lead found.
                if not lead_id or lead_id not in apollo_leads_dict:
                    logger.warning(f"Skipping Lead {lead_id}, is not in Apollo Leads Dict: {apollo_leads_dict}")
                    continue

                apollo_lead = apollo_leads_dict[lead_id]

                # Skip leads with too low a score.
                if initial_score < ApolloConfig.min_fit_threshold:
                    skipped_leads.append(apollo_lead)
                    continue

                recommended = eval_result.get("enrichment_recommended", False)
                logger.debug(f"Lead {lead_id} is recommended for enrichment by Pre Evaluation with intitial score: {initial_score}")

                # Check if the lead is recommended by the LLM or passes the custom enrichment criteria.
                if recommended or self._should_enrich_lead(
                        evaluation=eval_result,
                        apollo_lead=apollo_lead,
                        product_data=product_data
                ):
                    leads_for_enrichment.append(apollo_lead)
                else:
                    skipped_leads.append(apollo_lead)

            logger.info(f"Selected {len(leads_for_enrichment)} out of {len(apollo_leads)} leads for enrichment")

            # Transform leads in batches
            current_stage = 'structuring_leads'
            enriched_leads: List[EnrichedLead] = []

            # Process selected leads
            if leads_for_enrichment:
                enriched_leads.extend(await self._process_leads_in_batches(
                    leads_for_enrichment,
                    self.config.batch_size,
                    self._transform_apollo_employee
                ))

                # Enrich promising leads with ProxyCurl
                if self.config.enrich_leads:
                    current_stage = 'enriching_leads'
                    try:
                        enriched_leads = await self.proxycurl_service.enrich_leads(enriched_leads)
                        self.metrics.enriched_leads = len(enriched_leads)
                    except Exception as e:
                        logger.error(f"Lead enrichment failed: {str(e)}", exc_info=True)
                        self.metrics.enrichment_errors += 1

            # Process skipped leads with basic transformation
            if skipped_leads:
                basic_leads = await self._process_leads_in_batches(
                    skipped_leads,
                    self.config.batch_size,
                    self._transform_apollo_employee
                )
                enriched_leads.extend(basic_leads)

            # Evaluate all leads
            current_stage = 'evaluating_leads'
            evaluated_leads = await self._evaluate_leads_v2(enriched_leads, product_data, pre_evaluations=pre_evaluation_results)

            # Store results with enhanced metadata
            current_stage = 'storing_results'
            self.metrics.processing_time = time.time() - start_time

            enriched_leads_dict_list: List[Dict[str, Any]] = [lead.model_dump() for lead in enriched_leads]
            evaluated_leads_dict_list: List[Dict[str, Any]] = [lead.model_dump() for lead in evaluated_leads]
            await self._store_results(
                job_id=job_id,
                account_id=account_id,
                structured_leads=enriched_leads_dict_list,  # Store enriched leads
                evaluated_leads=evaluated_leads_dict_list
            )

            score_distribution = self._calculate_score_distribution(evaluated_leads_dict_list)
            qualified_leads_dict_list = [l for l in evaluated_leads_dict_list if l['fit_score'] >= self.config.fit_score_threshold]

            result = {
                'job_id': job_id,
                'account_id': account_id,
                'enrichment_type': self.ENRICHMENT_TYPE,
                'source': "apollo",
                'status': 'completed',
                'completion_percentage': 100,
                'processed_data': {
                    'score_distribution': score_distribution,
                    'structured_leads': enriched_leads_dict_list,
                    'all_leads': evaluated_leads_dict_list,
                    'qualified_leads': qualified_leads_dict_list,
                    'metrics': asdict(self.metrics)
                }
            }

            summary = {
                "status": "completed",
                "job_id": job_id,
                "account_id": account_id,
                "total_leads_found": len(evaluated_leads_dict_list),
                "qualified_leads": len(qualified_leads_dict_list),
                "score_distribution": score_distribution,
                "metrics": asdict(self.metrics)
            }
            return result, summary

        except Exception as e:
            logger.error(f"Lead identification failed for job {job_id}: {str(e)}", exc_info=True)
            error_details = {
                'error_type': type(e).__name__,
                'message': str(e),
                'stage': current_stage,
                'metrics': asdict(self.metrics)
            }

            await self._store_error_state(job_id, account_id, error_details)
            await self.callback_svc.send_callback(
                job_id=job_id,
                account_id=account_id,
                enrichment_type=self.ENRICHMENT_TYPE,
                source="apollo",
                status='failed',
                error_details=error_details,
                processed_data={'stage': current_stage}
            )

            return None, {
                "status": "failed",
                "job_id": job_id,
                "account_id": account_id,
                "error": str(e),
                "stage": current_stage,
                "metrics": asdict(self.metrics)
            }

    @with_retry(retry_config=APOLLO_RETRY_CONFIG, operation_name="fetch_apollo_organization_id")
    async def _fetch_apollo_organization_id(self, name: str, domain: str) -> Optional[str]:
        """Returns Apollo Organization ID for given domain. If not found, returns None."""

        # Fetch LinkedIn URLs associated with the domain from BuiltWith.
        bw_service = BuiltWithService(cache_service=self.cache_service)
        builtwith_result = await bw_service.get_technology_profile(domain=domain)
        account_linkedin_urls: Optional[List[str]] = builtwith_result.get_account_linkedin_urls()
        if not account_linkedin_urls:
            logger.error(f"Apollo Organization ID: Failed to find Account LinkedIn URLs for name: {name} and domain: {domain}")
            return None
        else:
            logger.debug(f"Apollo Organization ID: Found LinkedIn URLs in BuiltWith response: {account_linkedin_urls}")

        try:
            # Use Account name to filter a list of organizations in Apollo.
            # We will assume that the organization is found in the first page of results for now.
            search_params = {
                'q_organization_name': name,
                'page': 1,
                'per_page': self.config.batch_size
            }
            headers = {
                'Content-Type': 'application/json',
                'x-api-key': self.apollo_org_search_api_key
            }
            response, status_code = await cached_request(
                cache_service=self.cache_service,
                url="https://api.apollo.io/api/v1/mixed_companies/search",
                method='POST',
                params=search_params,
                headers=headers,
                ttl_hours=self.config.cache_ttl_hours
            )

            if status_code == 429:
                raise RetryableError("Rate limit exceeded")

            if status_code != 200:
                raise ValueError(f"Got a non 200 response code: {status_code} when fetching Apollo org ID for name: {name}, domain: {domain} with response: {response}")

            apollo_org_response = SearchApolloOrganizationsResponse(**response)
            all_organizations = apollo_org_response.get_all_organizations()
            for org in all_organizations:
                for linkedin_url in account_linkedin_urls:
                    if UrlUtils.are_account_linkedin_urls_same(org.linkedin_url, linkedin_url):
                        # Found the desired organization, return ID.
                        logger.info(f"Found Apollo Org ID: {org} for name: {name} and domain: {domain}")
                        return org.id

            logger.error(f"Failed to find linkedin URL match: {account_linkedin_urls} among all the organizations in Apollo Org Search for name: {name} and domain: {domain}")
            return None

        except Exception as e:
            logger.error(f"Error fetching Apollo Org ID: {str(e)}")
            self.metrics.api_errors += 1
            return None

    @with_retry(retry_config=APOLLO_RETRY_CONFIG, operation_name="fetch_employees_concurrent")
    async def _fetch_employees_concurrent(self, domain: str, apollo_org_id: Optional[str]) -> List[ApolloLead]:
        """Fetch employees with concurrent processing."""
        all_employees: List[ApolloLead] = []
        semaphore = asyncio.Semaphore(self.config.concurrent_requests)

        async def fetch_page(page_num: int) -> Optional[SearchApolloLeadsResponse]:
            async with semaphore:
                try:
                    search_params = {
                        'page': page_num,
                        'per_page': self.config.batch_size
                    }
                    # If Apollo Org ID is present we will search using that
                    # else we will search using the domain.
                    if apollo_org_id:
                        search_params['organization_ids[]'] = apollo_org_id
                    else:
                        search_params['q_organization_domains'] = domain

                    headers = {
                        'Content-Type': 'application/json',
                        'x-api-key': self.apollo_lead_search_api_key
                    }
                    response, status_code = await cached_request(
                        cache_service=self.cache_service,
                        url="https://api.apollo.io/api/v1/mixed_people/search",
                        method='POST',
                        params=search_params,
                        headers=headers,
                        ttl_hours=self.config.cache_ttl_hours
                    )

                    if status_code == 200:
                        return SearchApolloLeadsResponse(**response)
                    elif status_code == 429:
                        raise RetryableError("Rate limit exceeded")
                    return []

                except Exception as e:
                    logger.error(f"Error fetching page {page_num}: {str(e)}")
                    self.metrics.api_errors += 1
                    return []

        # Fetch first page to get total count and pagination info
        first_page_result = await fetch_page(1)
        if not first_page_result:
            logger.error("Failed to fetch first page")
            return []
        if not first_page_result.get_leads():
            logger.error(f"Failed to fetch People in Apollo Search leads result: {first_page_result}")
            return []

        all_employees.extend(first_page_result.get_leads())

        # Get total count and calculate number of pages needed
        pagination = first_page_result.pagination
        total_count = min(
            pagination.total_entries if pagination.total_entries else 0,
            self.config.max_employees
        )

        if total_count <= self.config.batch_size:
            logger.info(f"Only {total_count} employees found, no additional pages needed")
            return all_employees

        # Calculate actual number of pages needed based on total count
        remaining_count = total_count - len(first_page_result.get_leads())
        pages_needed = (remaining_count + self.config.batch_size - 1) // self.config.batch_size

        logger.info(f"Fetching {remaining_count} remaining employees across {pages_needed} pages")

        # Fetch remaining pages concurrently
        tasks = []
        total_pages = pagination.total_pages if pagination.total_pages else 1
        for p in range(2, min(pages_needed + 2, total_pages + 1)):
            tasks.append(fetch_page(p))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, SearchApolloLeadsResponse) and result.get_leads():
                    all_employees.extend(result.get_leads())
                elif isinstance(result, Exception):
                    logger.error(f"Error in concurrent fetch: {str(result)}")
                    self.metrics.api_errors += 1

        return all_employees

    async def _process_leads_in_batches(
            self,
            leads: List[ApolloLead],
            batch_size: int,
            process_func: callable
    ) -> List[EnrichedLead]:
        """Process leads in concurrent batches."""
        results: List[EnrichedLead] = []
        for i in range(0, len(leads), batch_size):
            batch: List[ApolloLead] = leads[i:i + batch_size]
            tasks = [process_func(lead) for lead in batch]
            batch_results: List[Union[EnrichedLead, Exception]] = await asyncio.gather(*tasks, return_exceptions=True)

            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Batch processing error: {str(result)}")
                    self.metrics.failed_leads += 1
                elif isinstance(result, EnrichedLead):
                    results.append(result)

        return results

    async def _store_results(
            self,
            job_id: str,
            account_id: str,
            structured_leads: List[Dict[str, Any]],
            evaluated_leads: List[Dict[str, Any]]
    ) -> None:
        """Enhanced result storage with metadata and metrics."""
        try:
            # Add processing metadata
            metadata = {
                'processing_timestamp': datetime.utcnow().isoformat(),
                'total_leads_processed': len(structured_leads),
                'successful_evaluations': len(evaluated_leads),
                'processing_metrics': asdict(self.metrics),
                'config_used': asdict(self.config)
            }

            # Calculate quality metrics
            quality_metrics = {
                'complete_profile_rate': self._calculate_profile_completion_rate(structured_leads),
                'email_coverage_rate': self._calculate_email_coverage_rate(structured_leads),
                'seniority_distribution': self._calculate_seniority_distribution(structured_leads)
            }

            metadata['quality_metrics'] = quality_metrics

            await self.bq_service.insert_enrichment_raw_data(
                job_id=job_id,
                entity_id=account_id,
                source='apollo',
                raw_data={
                    'structured_leads': structured_leads,
                    'evaluated_leads': evaluated_leads,
                    'metadata': metadata
                },
                processed_data={
                    'qualified_leads': [
                        lead for lead in evaluated_leads
                        if lead.get('fit_score', 0) >= self.config.fit_score_threshold
                    ],
                    'quality_metrics': quality_metrics
                }
            )
        except Exception as e:
            logger.error(f"Error storing results: {str(e)}")
            self.metrics.api_errors += 1
            raise

    def _calculate_profile_completion_rate(self, leads: List[Dict[str, Any]]) -> float:
        """Calculate the rate of complete profiles."""
        required_fields = ['full_name', 'email', 'current_role.title', 'location.country']
        complete_profiles = 0

        for lead in leads:
            is_complete = True
            for field in required_fields:
                if '.' in field:
                    parent, child = field.split('.')
                    value = lead.get(parent, {}).get(child)
                else:
                    value = lead.get(field)

                if not value:
                    is_complete = False
                    break

            if is_complete:
                complete_profiles += 1

        return round(complete_profiles / len(leads), 4) if leads else 0.0

    def _calculate_email_coverage_rate(self, leads: List[Dict[str, Any]]) -> float:
        """Calculate the rate of leads with valid email addresses."""
        leads_with_email = sum(1 for lead in leads if lead.get('email'))
        return round(leads_with_email / len(leads), 4) if leads else 0.0

    def _calculate_seniority_distribution(self, leads: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate the distribution of seniority levels."""
        seniority_counts = {}
        total_leads = len(leads)

        for lead in leads:
            seniority = lead.get('current_role', {}).get('seniority', 'unknown')
            seniority_counts[seniority] = seniority_counts.get(seniority, 0) + 1

        return {
            level: round(count / total_leads, 4)
            for level, count in seniority_counts.items()
        } if total_leads else {}

    async def _transform_apollo_employee(self, apollo_employee: ApolloLead) -> Optional[EnrichedLead]:
        """Transform a single Apollo employee record to Enriched Lead."""
        try:
            if not apollo_employee.id:
                logger.warning(f"Missing lead ID in Apollo employee: {apollo_employee}, skipping record")
                self.metrics.failed_leads += 1
                return None

            enriched_employee = EnrichedLead(
                id=apollo_employee.id,
                linkedin_url=apollo_employee.linkedin_url,
                first_name=apollo_employee.first_name,
                last_name=apollo_employee.last_name,
                name=apollo_employee.name,
                headline=apollo_employee.headline,
                contact_info=EnrichedLead.ContactInfo(
                    email=apollo_employee.email,
                    email_status=apollo_employee.email_status,
                    extrapolated_email_confidence=apollo_employee.extrapolated_email_confidence
                ),
                location=EnrichedLead.Location(
                    city=apollo_employee.city,
                    state=apollo_employee.state,
                    country=apollo_employee.country
                ),
                photo_url=apollo_employee.photo_url,
                social_profiles=EnrichedLead.SocialProfiles(
                    linkedin_url=apollo_employee.linkedin_url,
                    twitter_url=apollo_employee.twitter_url,
                    facebook_url=apollo_employee.facebook_url,
                    github_url=apollo_employee.github_url
                ),
            )

            if apollo_employee.organization:
                enriched_employee.organization = EnrichedLead.Organization(
                    name=apollo_employee.organization.name,
                    website_url=apollo_employee.organization.website_url,
                    linkedin_url=apollo_employee.organization.linkedin_url,
                    founded_year=apollo_employee.organization.founded_year,
                    primary_domain=apollo_employee.organization.primary_domain,
                    logo_url=apollo_employee.organization.logo_url,
                    twitter_url=apollo_employee.organization.twitter_url,
                    facebook_url=apollo_employee.organization.logo_url,
                    alexa_ranking=apollo_employee.organization.alexa_ranking,
                    apollo_organization_id=apollo_employee.organization.id,
                    linkedin_uid=apollo_employee.organization.linkedin_uid
                )

            if apollo_employee.employment_history:
                enriched_employee.other_employments = []
                for apollo_employment in apollo_employee.employment_history:
                    if apollo_employment.current and (apollo_employee.organization != None) and (apollo_employee.organization.name == apollo_employment.organization_name):
                        # Current Employment as marked by Apollo.
                        # Should be set to True only for one of the employments.
                        enriched_employee.current_employment = EnrichedLead.CurrentEmployment(
                            title=apollo_employment.title,
                            organization_name=apollo_employment.organization_name,
                            description=apollo_employment.description,
                            start_date=apollo_employment.start_date,
                            end_date=apollo_employment.end_date,
                            seniority=apollo_employee.seniority,
                            departments=apollo_employee.departments,
                            subdepartments=apollo_employee.subdepartments,
                            functions=apollo_employee.functions,
                            apollo_organization_id=apollo_employment.organization_id
                        )
                    else:
                        # Add to past employment.
                        enriched_employee.other_employments.append(
                            EnrichedLead.Employment(
                                title=apollo_employment.title,
                                organization_name=apollo_employment.organization_name,
                                current=apollo_employment.current,
                                description=apollo_employment.description,
                                start_date=apollo_employment.start_date,
                                end_date=apollo_employment.end_date,
                                apollo_organization_id=apollo_employment.organization_id
                            )
                        )

            enriched_employee.social_profiles = EnrichedLead.SocialProfiles(
                linkedin_url=apollo_employee.linkedin_url,
                twitter_url=apollo_employee.twitter_url,
                facebook_url=apollo_employee.facebook_url,
                github_url=apollo_employee.github_url
            )

            enriched_employee.enrichment_info = EnrichedLead.EnrichmentInfo(
                last_enriched_at=datetime.strftime(datetime.now(timezone.utc), "%Y-%m-%d"),
                enrichment_sources=["apollo"],
                data_quality=EnrichedLead.EnrichmentInfo.Quality(
                    has_detailed_employment=(enriched_employee.current_employment != None and enriched_employee.other_employments != None and len(enriched_employee.other_employments) > 0)
                )
            )
            return enriched_employee

        except Exception as e:
            logger.error(f"Error transforming employee data: {apollo_employee} with error: {str(e)}")
            self.metrics.failed_leads += 1
            return None

    async def _evaluate_leads(self, enriched_leads: List[EnrichedLead], product_data: Dict[str, Any],
                              account_data) -> List[Dict[str, Any]]:
        """Evaluate leads in batches with enhanced error handling."""
        website_context_prompt = None
        if not enriched_leads:
            logger.warning("No enriched leads provided for evaluation")
            return []

        # Get website context first
        try:
            website = account_data.get('website',)
            if not website:
                logger.warning("Website URL not provided for context extraction")
                website_context_prompt = "<Website context unavailable>"
            else:
                website_context = await self.jina_service.read_url(url=website, headers={})
                website_context_prompt = await self.model.generate_content(
                    f"Summarize the website in 5-10 sentences:\n{website_context}",
                    is_json=False
                )
        except Exception as e:
            logger.error(f"Error getting website context: {str(e)}")
            website_context_prompt = "<Website context unavailable>"

        evaluated_leads = []
        start_time = time.time()
        for i in range(0, len(enriched_leads), self.config.ai_batch_size):
            try:
                batch_dict_list: List[Dict[str, Any]] = [b.model_dump() for b in enriched_leads[i:i + self.config.ai_batch_size]]
                evaluation_prompt = self.prompts.LEAD_EVALUATION_PROMPT.format(
                    website_context=website_context_prompt,
                    product_info=json.dumps(product_data, indent=2),
                    persona_info=json.dumps(product_data.get('persona_role_titles', {}), indent=2),
                    lead_data=json.dumps(batch_dict_list, indent=2)
                )

                response = await self.model.generate_content(
                    prompt=evaluation_prompt,
                    is_json=True,
                    operation_tag="lead_evaluation"
                )

                if not response:
                    logger.error(f"Empty response from AI for batch {i//self.config.ai_batch_size + 1}")
                    self.metrics.ai_errors += 1
                    continue

                # Validate and normalize each lead score
                if 'evaluated_leads' in response:
                    normalized_leads = []
                    for lead in response['evaluated_leads']:
                        try:
                            lead['fit_score'] = max(0.0, min(1.0, float(lead.get('fit_score', 0))))
                            normalized_leads.append(lead)
                        except (ValueError, TypeError) as e:
                            logger.error(f"Score normalization error: {str(e)}")
                            self.metrics.failed_leads += 1

                    evaluated_leads.extend(normalized_leads)
                    self.metrics.successful_leads += len(normalized_leads)
                else:
                    logger.error(f"Invalid response structure for batch {i//self.config.ai_batch_size + 1}")
                    self.metrics.ai_errors += 1

            except Exception as e:
                logger.error(f"Error processing batch {i//self.config.ai_batch_size + 1}: {str(e)}")
                self.metrics.ai_errors += 1
                continue

        self.metrics.processing_time = time.time() - start_time
        return evaluated_leads

    async def _evaluate_leads_v2(self, enriched_leads: List[EnrichedLead], product_data: Dict[str, Any],
                                 pre_evaluations: List[Dict]) -> List[EvaluatedLead]:
        """
        Evaluate leads in concurrent batches with enhanced error handling.
        Uses semaphore to limit concurrent AI requests while maximizing throughput.
        """
        if not enriched_leads:
            logger.warning("No enriched leads provided for evaluation")
            return []

        evaluated_leads: List[EvaluatedLead] = []
        start_time = time.time()

        # Convert pre_evaluations list to a dict for easier lookup
        pre_evaluations_dict = {
            eval_result.get('id') or eval_result.get('lead_id'): eval_result
            for eval_result in pre_evaluations
            if eval_result.get('id') or eval_result.get('lead_id')
        }

        # Configure concurrency
        semaphore = asyncio.Semaphore(self.config.ai_concurrent_requests)

        async def process_batch(batch: List[EnrichedLead]) -> List[EvaluatedLead]:
            """Process a single batch of leads with the AI model."""
            async with semaphore:
                try:
                    # Prepare lead profiles with pre-evaluation insights
                    lead_profiles = []
                    for lead in batch:
                        lead_data = lead.model_dump(include=lead.get_lead_evaluation_serialization_fields())
                        pre_eval = pre_evaluations_dict.get(lead.id)

                        if pre_eval:
                            lead_data['pre_evaluation_insights'] = {
                                'initial_score': pre_eval.get('initial_score'),
                                'key_signals': pre_eval.get('key_signals', []),
                                'career_insights': pre_eval.get('career_insights', {}),
                                'confidence': pre_eval.get('confidence')
                            }
                            # Add any time based signals for given lead.
                            time_based_signals: List[str] = self._get_time_based_signals(lead=lead)
                            if len(time_based_signals) > 0:
                                # Append to key signals.
                                lead_data['pre_evaluation_insights']['key_signals'].extend(time_based_signals)
                        else:
                            lead_data['pre_evaluation_insights'] = None

                        lead_profiles.append(lead_data)

                    evaluation_prompt = self.prompts.LEAD_EVALUATION_PROMPT_V2.format(
                        product_description=product_data.get("description", "Product description not available"),
                        persona_role_titles=json.dumps(product_data.get('persona_role_titles', {}), indent=2),
                        additional_signals=product_data.get('additional_lead_signals', ''),
                        lead_profiles=json.dumps(lead_profiles, indent=2)
                    )

                    response = await self.model.generate_content(
                        prompt=evaluation_prompt,
                        is_json=True,
                        operation_tag="lead_evaluation"
                    )

                    if not response or 'evaluated_leads' not in response:
                        logger.error(f"Invalid response from AI model for batch of {len(batch)} leads")
                        self.metrics.ai_errors += 1
                        return []

                    evaluated_leads_result = EvaluateLeadsResult(**response)
                    self.metrics.successful_leads += len(evaluated_leads_result.evaluated_leads)
                    return evaluated_leads_result.evaluated_leads

                except Exception as e:
                    logger.error(f"Error processing batch: {str(e)}", exc_info=True)
                    self.metrics.ai_errors += 1
                    return []

        # Create batches and tasks
        batches = [
            enriched_leads[i:i + self.config.ai_batch_size]
            for i in range(0, len(enriched_leads), self.config.ai_batch_size)
        ]

        logger.info(f"Processing {len(enriched_leads)} leads in {len(batches)} batches")
        tasks = [process_batch(batch) for batch in batches]

        # Execute all batches concurrently and gather results
        try:
            results: List[Union[List[EvaluatedLead], Exception]] = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results and handle any exceptions
            for batch_result in results:
                if isinstance(batch_result, Exception):
                    logger.error(f"Batch processing failed: {str(batch_result)}")
                    self.metrics.ai_errors += 1
                else:
                    evaluated_leads.extend(batch_result)

        except Exception as e:
            logger.error(f"Error in concurrent processing: {str(e)}", exc_info=True)
            self.metrics.ai_errors += 1

        self.metrics.processing_time = time.time() - start_time

        logger.info(
            f"Lead evaluation completed. "
            f"Processed {len(enriched_leads)} leads, "
            f"successfully evaluated {len(evaluated_leads)}, "
            f"in {self.metrics.processing_time:.2f} seconds"
        )
        return evaluated_leads

    def _get_time_based_signals(self, lead: EnrichedLead) -> List[str]:
        """Returns any time based signals for given lead or empty list if no signals found."""
        time_based_signals: List[str] = []

        if not lead.current_employment:
            logger.error(f"Current employment does not exist for lead with ID: {lead.id}, name: {lead.name} and LinkedIn URL: {lead.linkedin_url}")
            return time_based_signals

        # Check if current employment start is recent.
        current_start_date: Optional[datetime] = lead.current_employment.get_start_date_datetime()
        if not current_start_date:
            logger.warning(f"Start date is None for Enriched lead with ID: {lead.id}, name: {lead.name} with LinkedIn URL: {lead.linkedin_url}")
            return None

        d1 = datetime.now()
        d2 = current_start_date
        delta = relativedelta(d1, d2)
        if delta.years >= 1:
            # Too stale.
            return time_based_signals
        difference_in_months = delta.months
        if difference_in_months > 6:
            # Too stale.
            return time_based_signals

        # Fresh time signal, check if it is new job or promotion.
        current_org_name: Optional[str] = lead.current_employment.organization_name
        if not current_org_name:
            logger.error(f"Current organization name is None for lead with ID: {lead.id}, name: {lead.name} with LinkedIn URL: {lead.linkedin_url}")
            return time_based_signals

        last_org_name: Optional[str] = None
        if len(lead.other_employments) > 0:
            # Take the most recent other employment, it should already be in reverse chronological order.
            last_org_name = lead.other_employments[0].organization_name

        if current_org_name != last_org_name:
            # New role for the lead.
            logger.debug(f"New role {difference_in_months} months ago for lead with ID: {lead.id}, name: {lead.name} and LinkedIn URL: {lead.linkedin_url}")
            signal_message = "New Role:"
            if difference_in_months == 0:
                signal_message = f"{signal_message} Started this month"
            elif difference_in_months == 1:
                signal_message = f"{signal_message} Started 1 month ago"
            else:
                signal_message = f"{signal_message} Started {difference_in_months} months ago"
            return [signal_message]
        else:
            # Recent Promotion for the lead.
            logger.debug(f"Recent promotion {difference_in_months} months ago for lead with ID: {lead.id}, name: {lead.name} and LinkedIn URL: {lead.linkedin_url}")
            signal_message = "Recent Promotion:"
            if difference_in_months == 0:
                signal_message = f"{signal_message} this month"
            elif difference_in_months == 1:
                signal_message = f"{signal_message} 1 month ago"
            else:
                signal_message = f"{signal_message} {difference_in_months} months ago"
            return [signal_message]

    async def _store_error_state(self, job_id: str, entity_id: str, error_details: Dict[str, Any]) -> None:
        """Store error information with enhanced metadata in BigQuery."""
        try:
            if not job_id or not entity_id:
                logger.error("Missing required fields for error state storage")
                return

            # Add timestamp and processing metrics
            current_time = datetime.utcnow().isoformat()

            # Ensure error details are properly formatted
            formatted_error = {
                'error_type': error_details.get('error_type', 'unknown_error'),
                'message': error_details.get('message', 'Unknown error occurred'),
                'stage': error_details.get('stage', 'unknown'),
                'timestamp': current_time,
                'retryable': error_details.get('retryable', True),
                'metrics': asdict(self.metrics),
                'processing_metadata': {
                    'config': asdict(self.config),
                    'partial_completion': self.metrics.total_leads_processed > 0,
                    'success_rate': (
                        self.metrics.successful_leads / self.metrics.total_leads_processed
                        if self.metrics.total_leads_processed > 0 else 0
                    ),
                    'api_failure_rate': (
                        self.metrics.api_errors / max(1, self.metrics.total_leads_processed)
                    ),
                    'processing_duration': self.metrics.processing_time
                }
            }

            # Add stack trace if available
            if error_details.get('traceback'):
                formatted_error['traceback'] = error_details['traceback']

            logger.debug(f"Storing error state for job {job_id}, entity {entity_id}")

            await self.bq_service.insert_enrichment_raw_data(
                job_id=job_id,
                entity_id=entity_id,
                source='apollo',
                raw_data={},  # Empty since this is an error state
                processed_data={},  # Empty since this is an error state
                status='failed',
                error_details=formatted_error,
                attempt_number=error_details.get('attempt_number', 1),
                max_retries=error_details.get('max_retries', self.config.max_retries)
            )

            logger.info(f"Successfully stored error state for job {job_id}, entity {entity_id}")

        except Exception as e:
            logger.error(
                f"Failed to store error state for job {job_id}, entity {entity_id}: {str(e)}",
                exc_info=True
            )
            # Don't re-raise since this is already error handling code

    def _calculate_score_distribution(self, evaluated_leads: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate comprehensive score distribution with metrics."""
        if not evaluated_leads:
            return {
                'distribution': {
                    'excellent': 0,
                    'good': 0,
                    'moderate': 0,
                    'low': 0
                },
                'metrics': {
                    'average_score': 0.0,
                    'median_score': 0.0,
                    'qualified_rate': 0.0
                },
                'score_ranges': {
                    '80-100': 0,
                    '60-80': 0,
                    '40-60': 0,
                    '0-40': 0
                }
            }

        # Basic distribution counting
        distribution = {
            'excellent': 0,  # 80 - 100
            'good': 0,      # 60 - 80
            'moderate': 0,  # 40 - 60
            'low': 0        # 0 - 40
        }

        # Detailed score ranges for histogram
        score_ranges = {
            '80-100': 0,
            '60-80': 0,
            '40-60': 0,
            '0-40': 0
        }

        # Calculate score statistics
        scores = []
        for lead in evaluated_leads:
            score = lead.get('fit_score', 0)
            scores.append(score)

            # Update distribution categories
            if score >= 80:
                distribution['excellent'] += 1
                score_ranges['80-100'] += 1
            elif score >= 60:
                distribution['good'] += 1
                score_ranges['60-80'] += 1
            elif score >= 40:
                distribution['moderate'] += 1
                score_ranges['40-60'] += 1
            else:
                distribution['low'] += 1
                score_ranges['0-40'] += 1

        # Calculate statistical metrics
        total_leads = len(evaluated_leads)
        qualified_leads = sum(1 for lead in evaluated_leads
                              if lead.get('fit_score', 0) >= self.config.fit_score_threshold)

        scores.sort()
        median_index = total_leads // 2
        median_score = scores[median_index] if scores else 0
        average_score = sum(scores) / total_leads if scores else 0
        qualified_rate = qualified_leads / total_leads if total_leads > 0 else 0

        return {
            'distribution': distribution,
            'metrics': {
                'average_score': round(average_score, 4),
                'median_score': round(median_score, 4),
                'qualified_rate': round(qualified_rate, 4),
                'total_leads': total_leads,
                'qualified_leads': qualified_leads
            },
            'score_ranges': score_ranges,
            'statistics': {
                'min_score': round(min(scores), 4) if scores else 0,
                'max_score': round(max(scores), 4) if scores else 0,
                'score_variance': round(self._calculate_variance(scores), 4),
                'score_distribution_skew': self._calculate_distribution_skew(scores)
            }
        }

    def _calculate_variance(self, scores: List[float]) -> float:
        """Calculate variance of scores."""
        if not scores:
            return 0.0
        mean = sum(scores) / len(scores)
        squared_diff_sum = sum((x - mean) ** 2 for x in scores)
        return squared_diff_sum / len(scores)

    def _calculate_distribution_skew(self, scores: List[float]) -> str:
        """Calculate if distribution is skewed towards high or low scores."""
        if not scores:
            return "no_data"

        mean = sum(scores) / len(scores)
        median = sorted(scores)[len(scores) // 2]

        if abs(mean - median) < 0.1:  # Threshold for considering it normal
            return "normal"
        elif mean > median:
            return "right_skewed"  # More high scores
        else:
            return "left_skewed"  # More low scores
