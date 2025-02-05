import logging
from typing import Optional, Dict, Any

from django.db import transaction
from django.utils import timezone

from app.models import Lead, Account, AccountEnrichmentStatus, EnrichmentType
from app.models.accounts import EnrichmentStatus

logger = logging.getLogger(__name__)


class StreamingCallbackHandler:
    """Handler for processing paginated callbacks."""

    @classmethod
    def handle_callback(cls, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Handle callback data by processing leads immediately."""
        try:
            job_id = data.get('job_id')
            logger.info(f"[handle_callback] Received callback for job_id={job_id}")

            pagination = data.get('pagination')
            logger.debug(f"[handle_callback] Raw pagination data={pagination}")

            if not pagination:
                # Non-paginated callback - return data as is
                logger.info(f"[handle_callback] No pagination for job_id={job_id}, returning data directly.")
                return data

            account_id = data.get('account_id')
            current_page = pagination.get('page', 1)
            total_pages = pagination.get('total_pages', 1)

            logger.info(
                f"[handle_callback] Processing pagination: "
                f"job_id={job_id}, account_id={account_id}, "
                f"current_page={current_page}, total_pages={total_pages}"
            )

            with transaction.atomic():
                # Get account
                account = Account.objects.select_for_update().get(id=account_id)
                logger.debug(f"[handle_callback] Locked account id={account_id} for update")

                # Process leads from this page
                cls._process_leads_batch(
                    account=account,
                    source=data.get('source', 'proxycurl'),
                    processed_data=data.get('processed_data', {})
                )

                if current_page < total_pages:
                    logger.debug(
                        f"[handle_callback] Intermediate page={current_page} < total_pages={total_pages}, "
                        f"job_id={job_id}. No final update. Returning None."
                    )
                    return None

                # If we're on the final page, update account status and return
                logger.debug(
                    f"[handle_callback] Final page reached (page={current_page} of {total_pages}) for job_id={job_id}. "
                    f"Updating account status."
                )
                cls._update_account_final_status(
                    account=account,
                    processed_data=data.get('processed_data', {})
                )
                logger.info(
                    f"[handle_callback] Completed final page for job_id={job_id}. Returning full data."
                )
                return data

        except Exception as e:
            logger.error(f"[handle_callback] Error processing callback for job_id={data.get('job_id')}: {str(e)}")
            raise

    @classmethod
    def _process_leads_batch(
            cls,
            account: Account,
            source: str,
            processed_data: Dict[str, Any]
    ) -> None:
        """Process a batch of leads for an account."""
        try:
            all_leads = processed_data.get('all_leads', [])
            structured_leads = processed_data.get('structured_leads', [])
            logger.debug(
                f"[_process_leads_batch] Starting lead batch processing: "
                f"{len(all_leads)} leads in 'all_leads', "
                f"{len(structured_leads)} leads in 'structured_leads'."
            )

            # Create a mapping of lead_id to data from different sections
            lead_data_mapping = {}

            # Process all_leads section
            for lead in all_leads:
                lead_id = lead.get('id')
                if lead_id:
                    lead_data_mapping[lead_id] = {
                        'evaluation': {
                            'fit_score': lead.get('fit_score'),
                            'matching_signals': lead.get('matching_signals', []),
                            'overall_analysis': lead.get('overall_analysis', []),
                            'persona_match': lead.get('persona_match'),
                            'rationale': lead.get('rationale'),
                            'recommended_approach': lead.get('recommended_approach'),
                            'key_insights': lead.get('key_insights', [])
                        }
                    }
                else:
                    logger.debug(
                        f"[_process_leads_batch] Found a lead in 'all_leads' without a lead_id: {lead}"
                    )

            # Process structured_leads section
            for lead in structured_leads:
                lead_id = lead.get('id')
                if lead_id:
                    if lead_id in lead_data_mapping:
                        lead_data = lead_data_mapping[lead_id]
                        lead_data.update({
                            # Basic info
                            'first_name': lead.get('first_name'),
                            'last_name': lead.get('last_name'),
                            'full_name': lead.get('full_name'),
                            'headline': lead.get('headline'),
                            'about': lead.get('about'),
                            'linkedin_url': lead.get('linkedin_url'),

                            # Contact information
                            'contact_info': {
                                'email': lead.get('contact_info', {}).get('email'),
                                'email_status': lead.get('contact_info', {}).get('email_status'),
                                'phone_numbers': lead.get('contact_info', {}).get('phone_numbers', []),
                            },

                            # Role and company info
                            'current_employment': {
                                'title': lead.get('current_employment', {}).get('title'),
                                'organization_name': lead.get('current_employment', {}).get('organization_name'),
                                'description': lead.get('current_employment', {}).get('description'),
                                'start_date': lead.get('current_employment', {}).get('start_date'),
                                'location': lead.get('current_employment', {}).get('location'),
                                'department': lead.get('current_employment', {}).get('department'),
                                'seniority': lead.get('current_employment', {}).get('seniority'),
                                'functions': lead.get('current_employment', {}).get('functions', []),
                                'subdepartments': lead.get('current_employment', {}).get('subdepartments', [])
                            },
                            'organization': lead.get('organization'),

                            # Location
                            'location': {
                                'city': lead.get('location', {}).get('city'),
                                'state': lead.get('location', {}).get('state'),
                                'country': lead.get('location', {}).get('country'),
                            },

                            'education': lead.get('education'),
                            'projects': lead.get('projects'),
                            'publications': lead.get('publications'),
                            'groups': lead.get('groups'),
                            'certifications': lead.get('certifications'),
                            'honor_awards': lead.get('honor_awards'),

                            # Professional history
                            'social_profiles': lead.get('social_profiles'),
                            'other_employments': lead.get('other_employments'),

                            # Data quality
                            'data_quality': {
                                'existence_level': lead.get('data_quality', {}).get('existence_level'),
                                'email_domain_catchall': lead.get('data_quality', {}).get('email_domain_catchall', False),
                                'profile_photo_url': lead.get('data_quality', {}).get('profile_photo_url'),
                                'last_updated': lead.get('data_quality', {}).get('last_updated')
                            },

                            # Engagement data
                            'engagement_data': {
                                'intent_strength': lead.get('engagement_data', {}).get('intent_strength'),
                                'show_intent': lead.get('engagement_data', {}).get('show_intent', False),
                                'last_activity_date': lead.get('engagement_data', {}).get('last_activity_date')
                            }
                        })
                    else:
                        logger.debug(
                            f"[_process_leads_batch] Found a lead in 'structured_leads' without a matching 'all_leads' entry. "
                            f"lead_id={lead_id}"
                        )
                else:
                    logger.debug(
                        f"[_process_leads_batch] Found a lead in 'structured_leads' without a lead_id: {lead}"
                    )

            logger.debug(
                f"[_process_leads_batch] Constructed lead_data_mapping with {len(lead_data_mapping)} entries."
            )

            # Process each lead
            for lead_id, lead_data in lead_data_mapping.items():
                logger.debug(f"[_process_leads_batch] Processing lead_id={lead_id} with data={lead_data}")
                try:
                    cls._create_or_update_lead(
                        account=account,
                        lead_data=lead_data,
                        source=source
                    )
                except Exception as e:
                    logger.error(f"[_process_leads_batch] Error processing lead {lead_id}: {str(e)}")
                    raise

            logger.debug(f"[_process_leads_batch] Finished processing batch of {len(lead_data_mapping)} leads.")

        except Exception as e:
            logger.error(f"[_process_leads_batch] Error processing lead batch: {str(e)}")
            raise

    @classmethod
    def _create_or_update_lead(
            cls,
            account: Account,
            lead_data: Dict[str, Any],
            source: str
    ) -> None:
        """Create or update a single lead with validated data."""
        try:
            # Prepare enrichment data
            enrichment_data = {
                # Base profile info
                'linkedin_url': lead_data.get('linkedin_url'),
                'headline': lead_data.get('headline'),
                'about': lead_data.get('about'),
                'location': lead_data.get('location'),
                'current_employment': lead_data.get('current_employment'),
                'organization': lead_data.get('organization'),

                # Contact info
                'contact_info': lead_data.get('contact_info'),

                'education': lead_data.get('education'),
                'projects': lead_data.get('projects'),
                'publications': lead_data.get('publications'),
                'groups': lead_data.get('groups'),
                'certifications': lead_data.get('certifications'),
                'honor_awards': lead_data.get('honor_awards'),

                # Professional details
                'social_profiles': lead_data.get('social_profiles'),
                'employment_history': lead_data.get('other_employments'),

                # Data quality
                'data_quality': lead_data.get('data_quality'),

                # Engagement info
                'engagement_data': lead_data.get('engagement_data'),

                # Evaluation data
                'evaluation': lead_data.get('evaluation'),

                # Source and timing
                'data_source': source,
                'enriched_at': timezone.now().isoformat()
            }

            # Prepare custom fields
            custom_fields = {
                'evaluation': lead_data.get('evaluation', {}),
            }

            # Extract name fields
            first_name = lead_data.get('first_name')
            last_name = lead_data.get('last_name')
            if not first_name and lead_data.get('full_name'):
                name_parts = lead_data.get('full_name', '').split()
                first_name = name_parts[0] if name_parts else None
                last_name = name_parts[-1] if len(name_parts) > 1 else None

            # Get role title
            role_title = (
                lead_data.get('current_employment', {}).get('title') or
                lead_data.get('headline')
            )

            # Build defaults for create or update
            defaults = {
                'tenant': account.tenant,
                'first_name': first_name,
                'last_name': last_name,
                'role_title': role_title,
                'score': lead_data.get('evaluation', {}).get('fit_score', 0.0),
                'enrichment_status': EnrichmentStatus.COMPLETED,
                'last_enriched_at': timezone.now(),
                'source': Lead.Source.ENRICHMENT,
                'suggestion_status': Lead.SuggestionStatus.SUGGESTED,
                'enrichment_data': enrichment_data,
                'custom_fields': custom_fields
            }

            # Remove None values to use model defaults
            defaults = {k: v for k, v in defaults.items() if v is not None}

            # Create or update lead
            lead, created = Lead.objects.update_or_create(
                account=account,
                linkedin_url=lead_data.get('linkedin_url'),
                defaults=defaults
            )

            logger.info(
                f"[_create_or_update_lead] {'Created' if created else 'Updated'} lead_id={lead.id}, "
                f"linkedin_url={lead_data.get('linkedin_url')}, score={lead.score}"
            )

            # Even if not created, we might do additional actions here
            if not created:
                lead.save()

        except Exception as e:
            logger.error(f"[_create_or_update_lead] Error creating/updating lead: {str(e)}")
            raise

    @classmethod
    def _update_account_final_status(
            cls,
            account: Account,
            processed_data: Dict[str, Any]
    ) -> None:
        """Update account status after processing all leads."""
        try:
            all_leads_count = len(processed_data.get('all_leads', []))
            qualified_leads_count = len(processed_data.get('qualified_leads', []))

            # Update account enrichment sources
            account.enrichment_sources = account.enrichment_sources or {}
            account.enrichment_sources['lead_generation'] = {
                'last_run': timezone.now().isoformat(),
                'leads_found': all_leads_count,
                'qualified_leads': qualified_leads_count,
                'score_distribution': processed_data.get('score_distribution', {})
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
                f"[_update_account_final_status] Error updating account status for account_id={account.id}: {str(e)}"
            )
            raise
