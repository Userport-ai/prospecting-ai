import logging
from typing import Optional, Dict, Any, List, Tuple
from django.db import transaction
from django.utils import timezone

from app.models import Lead, Account, AccountEnrichmentStatus, EnrichmentType
from app.models.accounts import EnrichmentStatus
from app.models.enrichment.lead_enrichment_models import (
    EnrichmentCallbackData, EnrichmentData, CustomFields,
    ProcessedData, StructuredLead, EvaluationData, EngagementData, DataQuality, CurrentEmployment, ContactInfo
)

logger = logging.getLogger(__name__)


class StreamingCallbackHandlerV2:
    """Handler for processing paginated callbacks with Pydantic models."""

    @classmethod
    def handle_callback(cls, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Handle callback data by processing leads immediately."""
        try:
            logger.info(f"[handle_callback] Received callback for job_id={data.get("job_id", "<None>")}")

            if not data.get('pagination'):
                logger.info(
                    f"[handle_callback] No pagination for job_id={data.get("job_id", "<None>")}, account_id={data.get("account_id")} "
                    "returning data directly."
                )
                return data

            # Parse incoming data with Pydantic
            callback_data = EnrichmentCallbackData(**data)

            current_page = callback_data.pagination.page
            total_pages = callback_data.pagination.total_pages

            logger.info(
                f"[handle_callback] Processing pagination: "
                f"job_id={callback_data.job_id}, account_id={callback_data.account_id}, "
                f"current_page={current_page}, total_pages={total_pages}"
            )

            with transaction.atomic():
                # Get account
                account = Account.objects.select_for_update().get(id=callback_data.account_id)
                logger.debug(f"[handle_callback] Locked account id={callback_data.account_id} for update")

                # Process leads from this page
                cls._process_leads_batch(
                    account=account,
                    source=callback_data.source,
                    processed_data=callback_data.processed_data
                )

                if current_page < total_pages:
                    logger.debug(
                        f"[handle_callback] Intermediate page={current_page} < total_pages={total_pages}, "
                        f"job_id={callback_data.job_id}. No final update. Returning None."
                    )
                    return None

                logger.debug(
                    f"[handle_callback] Final page reached (page={current_page} of {total_pages}) "
                    f"for job_id={callback_data.job_id}. Updating account status."
                )
                cls._update_account_final_status(
                    account=account,
                    processed_data=callback_data.processed_data
                )
                logger.info(
                    f"[handle_callback] Completed final page for job_id={callback_data.job_id}. "
                    "Returning full data."
                )
                return data

        except Exception as e:
            logger.error(f"[handle_callback] Error processing callback: {str(e)}", exc_info=True)
            raise

    @classmethod
    def _build_lead_mapping(
            cls,
            all_leads: List[Dict[str, Any]],
            structured_leads: List[StructuredLead]
    ) -> Dict[str, Tuple[StructuredLead, EvaluationData]]:
        """Build a comprehensive mapping of lead data combining evaluation and structure."""
        lead_mapping = {}

        # First, process all_leads to get evaluation data
        evaluation_mapping = {}
        for lead in all_leads:
            lead_id = lead.get('id')
            if lead_id:
                evaluation = EvaluationData(
                    fit_score=lead.get('fit_score'),
                    matching_signals=lead.get('matching_signals', []),
                    overall_analysis=lead.get('overall_analysis', []),
                    persona_match=lead.get('persona_match'),
                    rationale=lead.get('rationale'),
                    recommended_approach=lead.get('recommended_approach'),
                    key_insights=lead.get('key_insights', [])
                )
                evaluation_mapping[lead_id] = evaluation
            else:
                logger.warning(f"Found lead in all_leads without ID: {lead}")

        # Then combine with structured lead data
        for structured_lead in structured_leads:
            if structured_lead.id:
                evaluation = evaluation_mapping.get(structured_lead.id)
                if not evaluation:
                    logger.warning(f"No evaluation data found for lead {structured_lead.id}")
                    evaluation = EvaluationData()  # Create empty evaluation with defaults
                lead_mapping[structured_lead.id] = (structured_lead, evaluation)
            else:
                logger.warning(f"Found structured lead without ID: {structured_lead}")

        return lead_mapping

    @classmethod
    def _process_leads_batch(
            cls,
            account: Account,
            source: str,
            processed_data: ProcessedData
    ) -> None:
        """Process a batch of leads for an account."""
        try:
            logger.debug(
                f"[_process_leads_batch] Starting lead batch processing: "
                f"{len(processed_data.all_leads)} leads in 'all_leads', "
                f"{len(processed_data.structured_leads)} leads in 'structured_leads'."
            )

            # Build comprehensive lead mapping using Pydantic models
            lead_mapping = cls._build_lead_mapping(
                processed_data.all_leads,
                processed_data.structured_leads
            )

            # Process each lead with complete data
            for lead_id, (structured_lead, evaluation) in lead_mapping.items():
                try:
                    if not structured_lead.linkedin_url:
                        logger.warning(f"Missing linkedin_url for lead {lead_id}")
                        continue

                    cls._create_or_update_lead(
                        account=account,
                        structured_lead=structured_lead,
                        evaluation=evaluation,
                        source=source
                    )
                except Exception as e:
                    logger.error(
                        f"[_process_leads_batch] Error processing lead {lead_id}: {str(e)}",
                        exc_info=True
                    )
                    raise

            logger.debug(
                f"[_process_leads_batch] Finished processing batch of "
                f"{len(lead_mapping)} leads."
            )

        except Exception as e:
            logger.error(f"[_process_leads_batch] Error processing lead batch: {str(e)}")
            raise

    @classmethod
    def _create_or_update_lead(
            cls,
            account: Account,
            structured_lead: StructuredLead,
            evaluation: EvaluationData,
            source: str
    ) -> None:
        """Create or update a single lead with validated data."""
        try:
            # Prepare enrichment data model
            enrichment_data = EnrichmentData(
                linkedin_url=structured_lead.linkedin_url,
                headline=structured_lead.headline,
                about=structured_lead.about,
                location=structured_lead.location,
                current_employment=structured_lead.current_employment,
                organization=structured_lead.organization,
                contact_info=structured_lead.contact_info,
                education=structured_lead.education,
                projects=structured_lead.projects,
                publications=structured_lead.publications,
                groups=structured_lead.groups,
                certifications=structured_lead.certifications,
                honor_awards=structured_lead.honor_awards,
                social_profiles=structured_lead.social_profiles,
                employment_history=structured_lead.other_employments,
                data_quality=structured_lead.data_quality,
                engagement_data=structured_lead.engagement_data,
                evaluation=evaluation,
                data_source=source,
                enriched_at=timezone.now().isoformat()
            )

            # Prepare custom fields
            custom_fields = CustomFields(
                evaluation=evaluation
            )

            # Extract name fields with defensive programming
            first_name = structured_lead.first_name
            last_name = structured_lead.last_name
            if not first_name and structured_lead.full_name:
                name_parts = structured_lead.full_name.split()
                first_name = name_parts[0] if name_parts else None
                last_name = name_parts[-1] if len(name_parts) > 1 else None

            # Get role title with defensive fallbacks
            role_title = None
            if structured_lead.current_employment and structured_lead.current_employment.title:
                role_title = structured_lead.current_employment.title
            elif structured_lead.headline:
                role_title = structured_lead.headline

            # Build defaults for create or update
            defaults = {
                'tenant': account.tenant,
                'first_name': first_name,
                'last_name': last_name,
                'role_title': role_title,
                'score': evaluation.fit_score,
                'enrichment_status': EnrichmentStatus.COMPLETED,
                'last_enriched_at': timezone.now(),
                'source': Lead.Source.ENRICHMENT,
                'suggestion_status': Lead.SuggestionStatus.SUGGESTED,
                'enrichment_data': enrichment_data.model_dump(exclude_none=True),
                'custom_fields': custom_fields.model_dump(exclude_none=True)
            }

            # Remove None values to use model defaults
            defaults = {k: v for k, v in defaults.items() if v is not None}

            # Create or update lead
            lead, created = Lead.objects.update_or_create(
                account=account,
                linkedin_url=structured_lead.linkedin_url,
                defaults=defaults
            )

            logger.info(
                f"[_create_or_update_lead] {'Created' if created else 'Updated'} "
                f"lead_id={lead.id}, linkedin_url={structured_lead.linkedin_url}, "
                f"score={lead.score}"
            )

            # Add explicit save for non-created leads
            if not created:
                lead.save()

        except Exception as e:
            logger.error(f"[_create_or_update_lead] Error creating/updating lead: {str(e)}")
            raise

    @classmethod
    def _update_account_final_status(
            cls,
            account: Account,
            processed_data: ProcessedData
    ) -> None:
        """Update account status after processing all leads."""
        try:
            all_leads_count = len(processed_data.all_leads)
            qualified_leads_count = len(processed_data.qualified_leads)

            # Update account enrichment sources
            account.enrichment_sources = account.enrichment_sources or {}
            account.enrichment_sources['lead_generation'] = {
                'last_run': timezone.now().isoformat(),
                'leads_found': all_leads_count,
                'qualified_leads': qualified_leads_count,
                'score_distribution': processed_data.score_distribution or {}
            }

            # Update enrichment status to completed
            AccountEnrichmentStatus.objects.filter(
                account=account,
                enrichment_type=EnrichmentType.GENERATE_LEADS
            ).update(
                status=EnrichmentStatus.COMPLETED,
                last_successful_run=timezone.now()
            )

            account.save()
            logger.info(
                f"[_update_account_final_status] Updated account {account.id} "
                f"enrichment status: {all_leads_count} total leads, "
                f"{qualified_leads_count} qualified leads. Status set to COMPLETED."
            )

        except Exception as e:
            logger.error(
                f"[_update_account_final_status] Error updating account status "
                f"for account_id={account.id}: {str(e)}"
            )
            raise