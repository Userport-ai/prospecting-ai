import logging
import os
from datetime import datetime
from typing import Dict, Any, List, Optional

from models.lead_activities import LeadResearchReport, LinkedInActivity, ContentDetails
from services.bigquery_service import BigQueryService
from services.django_callback_service import CallbackService
from tasks.base import BaseTask
from tasks.enrichment_task import AccountEnrichmentTask
from utils.activity_parser import LinkedInActivityParser
from utils.lead_insights_gen import LeadInsights

logger = logging.getLogger(__name__)


class LeadLinkedInResearchTask(AccountEnrichmentTask):
    """Task for generating lead research report from LinkedIn activities."""

    ENRICHMENT_TYPE = "lead_linkedin_research"

    def __init__(self, callback_service):
        """Initialize task with required services."""
        super().__init__(callback_service)
        self.bq_service = BigQueryService()
        self._initialize_credentials()
        self.posts_html = None
        self.comments_html = None
        self.reactions_html = None

    def _initialize_credentials(self) -> None:
        """Initialize and validate required API credentials."""
        self.project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
        self.dataset = os.getenv('BIGQUERY_DATASET', 'userport_enrichment')

    @property
    def task_name(self) -> str:
        """Get the task identifier."""
        return "lead_linkedin_research"

    async def create_task_payload(self, **kwargs) -> Dict[str, Any]:
        """Create a standardized task payload."""
        required_fields = ['lead_id', 'account_id', 'company_name', 'person_linkedin_url', 'posts_html', 'comments_html', 'reactions_html']
        missing_fields = [field for field in required_fields if field not in kwargs]

        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

        return {
            "account_id": kwargs["account_id"],
            "company_name": kwargs["company_name"],
            'lead_id': kwargs["lead_id"],
            'person_name': kwargs["person_name"],
            "person_linkedin_url": kwargs["person_linkedin_url"],
            "posts_html": kwargs.get("posts_html"),
            "comments_html": kwargs.get("comments_html"),
            "reactions_html": kwargs.get("reactions_html"),
            "research_request_type": kwargs.get("research_request_type", "linkedin_only"),
            "input_data": kwargs.get("input_data"),
            "job_id": kwargs.get("job_id"),
            "origin": "extension",
            "user_id": kwargs.get("user_id"),
            "attempt_number": kwargs.get("attempt_number", 1),
            "max_retries": kwargs.get("max_retries", 3)
        }

    @property
    def enrichment_type(self) -> str:
        return self.ENRICHMENT_TYPE

    async def execute(self, payload: Dict[str, Any]) -> (Dict[str, Any], Dict[str, Any]):
        """Execute the lead research task."""
        job_id = payload.get('job_id')
        account_id = payload.get('account_id')
        lead_id = payload.get('lead_id')
        company_name = payload.get('company_name')
        person_linkedin_url = payload.get('person_linkedin_url')
        user_id = payload.get('user_id')
        input_data = payload.get("input_data")
        self.posts_html = payload.get('posts_html')
        self.comments_html = payload.get('comments_html')
        self.reactions_html = payload.get('reactions_html')
        current_stage = 'initialization'
        callback_service = await CallbackService.get_instance()

        logger.info(f"Starting lead research for job_id: {job_id}, account_id: {account_id}")

        try:
            # Initial processing callback
            await callback_service.send_callback(
                job_id=job_id,
                account_id=account_id,
                lead_id=lead_id,
                status='processing',
                enrichment_type='lead_linkedin_research',
                source="linkedin",
                completion_percentage=10,
                processed_data={'stage': current_stage}
            )

            # Parse LinkedIn activities
            current_stage = 'activity_parsing'
            activities = await self._parse_linkedin_activities(
                person_linkedin_url=person_linkedin_url,
                posts_html=payload.get('posts_html'),
                comments_html=payload.get('comments_html'),
                reactions_html=payload.get('reactions_html')
            )

            await callback_service.send_callback(
                job_id=job_id,
                account_id=account_id,
                lead_id=lead_id,
                status='processing',
                enrichment_type='lead_linkedin_research',
                source="linkedin",
                completion_percentage=30,
                processed_data={
                    'stage': current_stage,
                    'activities_found': len(activities)
                }
            )

            # Process content and generate insights
            current_stage = 'content_processing'
            content_details = await self._process_activities(
                activities=activities,
                person_name=payload.get('person_name'),
                company_name=payload.get('company_name'),
                company_description=payload.get('company_description', ''),
                person_role_title=payload.get('person_role_title', '')
            )

            await callback_service.send_callback(
                job_id=job_id,
                account_id=account_id,
                lead_id=lead_id,
                status='processing',
                enrichment_type='lead_linkedin_research',
                source="linkedin",
                completion_percentage=60,
                processed_data={
                    'stage': current_stage,
                    'content_processed': len(content_details)
                }
            )

            # Generate insights
            current_stage = 'insights_generation'
            insights = await self._generate_insights(
                lead_research_report_id=job_id,
                person_name=payload.get('person_name'),
                company_name=company_name,
                company_description="",
                person_role_title="",
                person_about_me="",
                content_details=content_details,
                input_data=input_data
            )

            # Store results
            current_stage = 'storing_results'
            await self._store_results(
                job_id=job_id,
                lead_id=lead_id,
                user_id=user_id,
                content_details=content_details,
                insights=insights
            )

            # Send success callback
            result = {
                'job_id': job_id,
                'account_id': account_id,
                'lead_id': lead_id,
                'status': 'completed',
                'enrichment_type': 'lead_linkedin_research',
                'source': "linkedin",
                'completion_percentage': 100,
                'processed_data': {
                    'content_details': [cd.model_dump() for cd in content_details],
                    'insights': insights.model_dump() if insights else None
                }
            }

            summary = {
                "status": "completed",
                "job_id": job_id,
                "account_id": account_id,
                "lead_id": lead_id,
                "activities_processed": len(activities),
                "content_generated": len(content_details)
            }
            return result, summary

        except Exception as e:
            logger.error(f"Lead research failed for job {job_id}: {str(e)}", exc_info=True)
            error_details = {
                'error_type': type(e).__name__,
                'message': str(e),
                'stage': current_stage,
                'retryable': True
            }

            # Store error state
            await self._store_error_state(job_id, lead_id, error_details)

            # Send failure callback
            await callback_service.send_callback(
                job_id=job_id,
                account_id=account_id,
                lead_id=lead_id,
                status='failed',
                enrichment_type='lead_linkedin_research',
                source="linkedin",
                error_details=error_details,
                processed_data={'stage': current_stage}
            )

            return None, {
                "status": "failed",
                "job_id": job_id,
                "account_id": account_id,
                "error": str(e),
                "stage": current_stage
            }

    async def _parse_linkedin_activities(
            self,
            person_linkedin_url: str,
            posts_html: Optional[str],
            comments_html: Optional[str],
            reactions_html: Optional[str]
    ) -> List[LinkedInActivity]:
        """Parse LinkedIn activities from HTML content."""
        activities = []

        if posts_html:
            activities.extend(LinkedInActivityParser.get_activities(
                person_linkedin_url=person_linkedin_url,
                page_html=posts_html,
                activity_type=LinkedInActivity.Type.POST
            ))

        if comments_html:
            activities.extend(LinkedInActivityParser.get_activities(
                person_linkedin_url=person_linkedin_url,
                page_html=comments_html,
                activity_type=LinkedInActivity.Type.COMMENT
            ))

        if reactions_html:
            activities.extend(LinkedInActivityParser.get_activities(
                person_linkedin_url=person_linkedin_url,
                page_html=reactions_html,
                activity_type=LinkedInActivity.Type.REACTION
            ))

        return activities

    async def _process_activities(
            self,
            activities: List[LinkedInActivity],
            person_name: str,
            company_name: str,
            company_description: str,
            person_role_title: str
    ) -> List[ContentDetails]:
        """Process LinkedIn activities into structured content."""
        content_details = []
        parser = LinkedInActivityParser(
            person_name=person_name,
            company_name=company_name,
            company_description=company_description,
            person_role_title=person_role_title
        )

        for activity in activities:
            try:
                content = await parser.parse_v2(activity=activity)
                if content:
                    content_details.append(content)
            except Exception as e:
                logger.error(f"Error processing activity: {str(e)}", exc_info=True)
                continue

        return content_details

    async def _generate_insights(
            self,
            lead_research_report_id: str,
            person_name: str,
            company_name: str,
            company_description: str,
            person_role_title: str,
            person_about_me: str,
            content_details: List[ContentDetails],
            input_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[LeadResearchReport.Insights]:
        """Generate insights from processed content."""
        try:
            insights_generator = LeadInsights(
                lead_research_report_id=lead_research_report_id,
                person_name=person_name,
                company_name=company_name,
                company_description=company_description,
                person_role_title=person_role_title,
                person_about_me=person_about_me,
                input_data=input_data
            )

            return await insights_generator.generate(all_content_details=content_details)
        except Exception as e:
            logger.error(f"Error generating insights: {str(e)}", exc_info=True)
            return None

    async def _store_results(
            self,
            job_id: str,
            lead_id: str,
            user_id: str,
            content_details: List[ContentDetails],
            insights: Optional[LeadResearchReport.Insights]
    ) -> None:
        """Store processing results in BigQuery."""
        try:
            await self.bq_service.insert_enrichment_raw_data(
                job_id=job_id,
                entity_id=lead_id,
                entity_type='lead',
                source='linkedin',
                raw_data={
                    'posts_html':     self.posts_html if self.posts_html else None,
                    'comments_html':  self.comments_html if self.comments_html else None,
                    'reactions_html': self.reactions_html if self.reactions_html else None,
                },
                processed_data={
                    'content_details': [cd.model_dump() for cd in content_details],
                    'insights': insights.model_dump() if insights else None,
                },
                status='completed'
            )
        except Exception as e:
            logger.error(f"Error storing results: {str(e)}", exc_info=True)
            raise

    async def _store_error_state(
            self,
            job_id: str,
            entity_id: str,
            error_details: Dict[str, Any]
    ) -> None:
        """Store error information in BigQuery."""
        try:
            formatted_error = {
                'error_type': error_details.get('error_type', 'unknown_error'),
                'message': error_details.get('message', 'Unknown error occurred'),
                'stage': error_details.get('stage', 'unknown'),
                'timestamp': datetime.utcnow().isoformat(),
                'retryable': error_details.get('retryable', True)
            }

            await self.bq_service.insert_enrichment_raw_data(
                job_id=job_id,
                entity_id=entity_id,
                entity_type='lead',
                source='linkedin',
                raw_data={},
                processed_data={},
                status='failed',
                error_details=formatted_error
            )

        except Exception as e:
            logger.error(
                f"Failed to store error state for job {job_id}: {str(e)}",
                exc_info=True
            )
