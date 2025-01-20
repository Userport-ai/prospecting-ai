import logging
from typing import Dict, Any

from django.db import transaction
from django.utils import timezone

from app.models import Lead, EnrichmentStatus
from app.models.enrichment.lead_linkedin_research import (
    LinkedInActivity,
    LinkedInEnrichmentData,
    EnrichmentMetadata,
    PersonalityInsights
)

logger = logging.getLogger(__name__)

class LeadEnrichmentHandler:
    """Handler for processing individual lead enrichment data from LinkedIn"""

    @staticmethod
    def handle_lead_enrichment(lead_id: str, account_id: str, processed_data: Dict[str, Any]) -> None:
        """
        Handle enrichment for a specific lead
        """
        if not processed_data:
            logger.warning(f"No processed data provided for lead {lead_id}")
            return

        logger.info(f"Processing LinkedIn enrichment for lead {lead_id}")
        try:
            with transaction.atomic():
                lead = Lead.objects.select_for_update().get(
                    id=lead_id,
                    account_id=account_id
                )

                content_details = processed_data.get('content_details', [])
                if not content_details:
                    logger.warning("No content details found in processed data")
                    return

                # Create enrichment data using Pydantic models
                activities = [
                    LinkedInActivity(
                        type=activity.get('linkedin_activity_type'),
                        date=activity.get('publish_date'),
                        url=activity.get('url'),
                        category=activity.get('category'),
                        category_reason=activity.get('category_reason'),
                        detailed_summary=activity.get('detailed_summary'),
                        concise_summary=activity.get('concise_summary'),
                        one_line_summary=activity.get('one_line_summary'),
                        author=activity.get('author'),
                        author_type=activity.get('author_type'),
                        focus_on_company=activity.get('focus_on_company'),
                        focus_on_company_reason=activity.get('focus_on_company_reason'),
                        reactions=activity.get('num_linkedin_reactions'),
                        comments=activity.get('num_linkedin_comments'),
                        reposts=activity.get('num_linkedin_reposts'),
                        product_associations=activity.get('product_associations'),
                        hashtags=activity.get('hashtags'),
                        main_colleague=activity.get('main_colleague'),
                        main_colleague_reason=activity.get('main_colleague_reason'),
                        processing_status=activity.get('processing_status')
                    )
                    for activity in content_details
                ]

                enrichment_data = LinkedInEnrichmentData(
                    metadata=EnrichmentMetadata(
                        num_company_related_activities=processed_data.get('insights', {}).get('num_company_related_activities')
                    ),
                    activities=activities,
                    insights=processed_data.get('insights')
                ).dict(exclude_none=True)

                # Create personality insights
                insights = processed_data.get('insights', {})
                personality_insights = PersonalityInsights(
                    traits=insights.get('personality_traits'),
                    recommended_approach=insights.get('recommended_approach'),
                    areas_of_interest=insights.get('areas_of_interest'),
                    engaged_colleagues=insights.get('engaged_colleagues'),
                    engaged_products=insights.get('engaged_products')
                ).dict(exclude_none=True)

                # Update or merge enrichment_data
                if lead.enrichment_data:
                    current_data = lead.enrichment_data.copy()
                    current_data.update(enrichment_data)
                    lead.enrichment_data = current_data
                else:
                    lead.enrichment_data = enrichment_data

                # Update or merge custom_fields
                custom_fields = {'personality_insights': personality_insights}
                if lead.custom_fields:
                    current_custom = lead.custom_fields.copy()
                    current_custom.update(custom_fields)
                    lead.custom_fields = current_custom
                else:
                    lead.custom_fields = custom_fields

                # Update status
                lead.enrichment_status = EnrichmentStatus.COMPLETED
                lead.last_enriched_at = timezone.now()

                lead.save()
                logger.info(f"Successfully updated lead {lead_id} with LinkedIn enrichment data")

        except Lead.DoesNotExist:
            logger.error(f"Lead {lead_id} not found for account {account_id}")
            raise
        except Exception as e:
            logger.error(f"Error updating lead {lead_id}: {str(e)}")
            raise