import logging
from typing import Dict, Any, Optional, Tuple

from django.db import transaction, models
from django.utils import timezone
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from app.apis.auth.auth_verify_cloud_run_decorator import verify_cloud_run_token
from app.apis.custom_column.custom_column_callback_handler import CustomColumnCallbackHandler
from app.apis.leads.lead_enrichment_handler import LeadEnrichmentHandler
from app.apis.leads.streaming_leads_callback_handler_v2 import StreamingCallbackHandlerV2
from app.models import Lead
from app.models.account_enrichment import AccountEnrichmentStatus, EnrichmentType, EnrichmentStatus
from app.models.accounts import Account
from app.models.custom_column import CustomColumn
from app.services.column_generation_orchestrator import ColumnGenerationOrchestrator

logger = logging.getLogger(__name__)


def get_current_enrichment_status(account_id: str, enrichment_type: str) -> Optional[AccountEnrichmentStatus]:
    """
    Get current enrichment status with select_for_update to handle concurrency
    """
    try:
        return AccountEnrichmentStatus.objects.select_for_update().get(
            account_id=account_id,
            enrichment_type=enrichment_type,
        )
    except AccountEnrichmentStatus.DoesNotExist:
        return None


def should_process_callback(current_status: Optional[AccountEnrichmentStatus], new_status: str,
                            pagination_data: Optional[Dict] = None) -> Tuple[bool, Optional[str]]:
    """
    Determine if the callback should be processed based on current status and pagination
    Returns: (should_process: bool, skip_reason: Optional[str])
    """
    if not current_status:
        return True, None

    # Handle pagination for lead generation
    if pagination_data:
        current_metadata = current_status.metadata or {}
        processed_pages = current_metadata.get('processed_pages', [])
        current_page = pagination_data.get('page')

        if current_page in processed_pages:
            return False, f"Page {current_page} already processed"

        return True, None

    # Don't reprocess completed non-paginated enrichments
    if current_status.status == EnrichmentStatus.COMPLETED:
        return False, "Enrichment already completed"

    # Always process if current status is pending or in_progress
    if current_status.status in [EnrichmentStatus.PENDING, EnrichmentStatus.IN_PROGRESS]:
        return True, None

    # If current status is failed, only process new completed status
    if current_status.status == EnrichmentStatus.FAILED:
        if new_status == EnrichmentStatus.COMPLETED:
            return True, None
        else:
            return False, "Cannot update failed status except to completed"

    return True, None

async def _trigger_custom_column_generation_after_enrichment(account, account_id):
    """Trigger custom column generation after account enrichment is complete."""
    logger.info(f"Triggering custom column generation for account {account_id} after enrichment")
    try:
        # Start orchestrated generation for all account-type columns
        orchestration_result = await ColumnGenerationOrchestrator.start_orchestrated_generation(
            tenant_id=str(account.tenant_id),
            entity_ids=[account_id],
            entity_type=CustomColumn.EntityType.ACCOUNT.value(),
            batch_size=10
        )

        logger.info(f"Custom column orchestration started: {orchestration_result}")
        return orchestration_result
    except Exception as e:
        logger.error(f"Failed to trigger custom column generation after enrichment: {str(e)}", exc_info=True)
        # Don't raise - we don't want to fail the callback if column generation fails
        return {"error": str(e), "status": "failed"}


def update_enrichment_status(
        account: Account,
        enrichment_type: str,
        status: str,
        data: Dict[str, Any],
        pagination_data: Optional[Dict] = None
) -> AccountEnrichmentStatus:
    """
    Atomic update of enrichment status including metadata
    """
    with transaction.atomic():
        # Get or create with lock - lock held for entire transaction
        enrichment_status = AccountEnrichmentStatus.objects.select_for_update().get_or_create(
            account=account,
            enrichment_type=enrichment_type,
            defaults={
                'status': status,
                'metadata': {},
                'source': data.get('source', 'unknown'),
            }
        )[0]

        # All operations now happen while holding the lock
        metadata = enrichment_status.metadata or {}
        new_metadata = data.get('metadata', {})
        merged_metadata = {**metadata, **new_metadata}

        # Update pagination tracking if needed
        if pagination_data:
            processed_pages = metadata.get('processed_pages', [])
            current_page = pagination_data.get('page')
            if current_page is not None and current_page not in processed_pages:
                processed_pages.append(current_page)
                merged_metadata.update({
                    'processed_pages': processed_pages,
                    'total_pages': pagination_data.get('total_pages'),
                    'last_processed_page': current_page
                })

        # Build update fields dict
        update_fields = {
            'status': status,
            'last_attempted_run': timezone.now(),
            'last_successful_run': timezone.now() if status == EnrichmentStatus.COMPLETED else None,
            'source': data.get('source', 'unknown'),
            'completion_percent': data.get('completion_percentage', 0),
            'error_details': data.get('error_details'),
            'metadata': merged_metadata,
            'data_quality_score': data.get('quality_score'),
        }

        # Use F() expression for atomic increment
        if status == EnrichmentStatus.FAILED:
            update_fields['failure_count'] = models.F('failure_count') + 1

        # Perform atomic update
        AccountEnrichmentStatus.objects.filter(
            pk=enrichment_status.pk
        ).update(**update_fields)

        # Refresh from db to get updated state
        enrichment_status.refresh_from_db()

        return enrichment_status


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
@verify_cloud_run_token
def enrichment_callback(request):
    logger.info(f"Enrichment callback request for {request.data.get('enrichment_type', 'Unknown')} account_id: {request.data.get('account_id')}")

    try:
        data = request.data
        account_id = data.get('account_id')
        lead_id = data.get('lead_id')
        status = data.get('status')
        enrichment_type = data.get('enrichment_type')
        processed_data = data.get('processed_data', {})
        pagination_data = data.get('pagination')

        if not all([account_id, status, enrichment_type]):
            return Response({
                "error": "Missing required fields"
            }, status=400)

        if enrichment_type == EnrichmentType.CUSTOM_COLUMN:
            # Custom column callback handling is simpler and doesn't use AccountEnrichmentStatus
            result = CustomColumnCallbackHandler.handle_callback(data)
            if result:
                return Response({"status": "success"})
            else:
                return Response({"error": "Failed to process custom column callback"}, status=500)
        else:
            with transaction.atomic():
                account = Account.objects.select_for_update().get(id=account_id)

                # Check current enrichment status
                current_status = get_current_enrichment_status(account_id, enrichment_type)
                should_process, skip_reason = should_process_callback(
                    current_status,
                    status,
                    pagination_data if enrichment_type == EnrichmentType.GENERATE_LEADS else None
                )

                if not should_process:
                    logger.info(f"Skipping callback for account {account_id}, type {enrichment_type}: {skip_reason}")
                    return Response({
                        "status": "skipped",
                        "reason": skip_reason,
                    })

                # For paginated requests, status should be in_progress until final page
                if pagination_data:
                    current_page = pagination_data.get('page', 1)
                    total_pages = pagination_data.get('total_pages', 1)
                    if current_page < total_pages:
                        status = EnrichmentStatus.IN_PROGRESS

                # Update enrichment status atomically
                enrichment_status = update_enrichment_status(
                    account=account,
                    enrichment_type=enrichment_type,
                    status=status,
                    data=data,
                    pagination_data=pagination_data
                )

                # Process based on enrichment type
                if enrichment_type == EnrichmentType.GENERATE_LEADS:
                    # Process through streaming handler
                    result = StreamingCallbackHandlerV2.handle_callback(data)
                    if result is None and pagination_data:
                        current_page = pagination_data.get('page', 1)
                        total_pages = pagination_data.get('total_pages', 1)
                        if current_page < total_pages:
                            # Intermediate page - acknowledge receipt
                            return Response({
                                "status": "processing",
                                "page": pagination_data.get('page'),
                                "total_pages": pagination_data.get('total_pages')
                            })
                else:
                    if status == EnrichmentStatus.COMPLETED and processed_data:
                        if enrichment_type == EnrichmentType.LEAD_LINKEDIN_RESEARCH:
                            if not lead_id:
                                raise ValueError("Lead ID required for lead enrichment")
                            LeadEnrichmentHandler.handle_lead_enrichment(
                                lead_id=lead_id,
                                account_id=account_id,
                                processed_data=processed_data
                            )
                        else:
                            # Use existing account enrichment function for other types
                            _update_account_from_enrichment(account, enrichment_type, processed_data)
                            # After enrichment is complete, trigger custom column generation
                            # We use asyncio.create_task to run this non-blocking
                            _trigger_custom_column_generation_after_enrichment(account, account_id)

        return Response({
            "status": "success",
        })

    except Account.DoesNotExist:
        logger.error(f"Account.DoesNotExist: {account_id}", exc_info=True)
        return Response({"error": "Account not found"}, status=404)
    except Lead.DoesNotExist:
        logger.error(f"Lead.DoesNotExist:{lead_id}. Account ID: {account_id}", exc_info=True)
        return Response({"error": "Lead not found"}, status=404)
    except Exception as e:
        logger.error(f"Error processing callback: Account ID: {account_id}. Error: {str(e)}", exc_info=True)
        return Response({"error": str(e)}, status=500)


def _update_account_from_enrichment(account: Account, enrichment_type: str, processed_data: Dict[str, Any]) -> None:
    """
     Updates account fields based on enrichment data
     Args:
         account: Account instance to update
         enrichment_type: Type of enrichment
         processed_data: Dictionary containing processed enrichment data
     """
    if enrichment_type == EnrichmentType.COMPANY_INFO:
        if not processed_data:
            return
        logger.info(f"Updating account {account.id} with company info")
        # Update fields from processed_data
        update_fields = {
            'name': processed_data.get('company_name'),
            'employee_count': processed_data.get('employee_count'),
            'industry': processed_data.get('industry'),
            'location': processed_data.get('location'),
            'website': processed_data.get('website'),
            'linkedin_url': processed_data.get('linkedin_url'),
            'technologies': processed_data.get('technologies'),
            'full_technology_profile': processed_data.get('tech_profile'),
            'funding_details': processed_data.get('funding_details'),
            'company_type': processed_data.get('company_type'),
            'founded_year': processed_data.get('founded_year'),
            'customers': processed_data.get('customers', []),
            'competitors': processed_data.get('competitors', []),
            'recent_events': processed_data.get('recent_events', [])
        }
        # Filter out None values
        update_fields = {k: v for k, v in update_fields.items() if v is not None}
        Account.objects.filter(pk=account.pk).update(**update_fields)
        account.refresh_from_db()
        return
    elif enrichment_type == EnrichmentType.GENERATE_LEADS:
        if not processed_data:
            return
        logger.info(f"Updating account {account.id} with suggested leads. "
                    f"No. of qualified leads: {len(processed_data.get('qualified_leads', []))}")

        qualified_leads = processed_data.get('qualified_leads', [])
        structured_leads = processed_data.get('structured_leads', [])
        all_leads = processed_data.get('all_leads', [])

        # Create a mapping of lead_id to data from different sections
        lead_data_mapping = {}

        # Process all_leads section
        for lead in all_leads:
            lead_id = lead.get('lead_id')
            if lead_id:
                lead_data_mapping[lead_id] = {
                    'fit_score': lead.get('fit_score'),
                    'matching_signals': lead.get('matching_signals', []),
                    'overall_analysis': lead.get('overall_analysis', []),
                    'persona_match': lead.get('persona_match'),
                    'rationale': lead.get('rationale'),
                    'recommended_approach': lead.get('recommended_approach')
                }

        # Process structured_leads section
        for lead in structured_leads:
            lead_id = lead.get('lead_id')
            if lead_id and lead_id in lead_data_mapping:
                lead_data = lead_data_mapping[lead_id]
                # Update with career history
                career_history = lead.get('career_history', {})
                lead_data.update({
                    'companies_count': career_history.get('companies_count'),
                    'industry_exposure': career_history.get('industry_exposure', []),
                    'total_years_experience': career_history.get('total_years_experience'),
                    'previous_roles': career_history.get('previous_roles', [])
                })
                # Update with other structured fields
                lead_data.update({
                    'current_role': lead.get('current_role', {}),
                    'education': lead.get('education', []),
                    'first_name': lead.get('first_name'),
                    'last_name': lead.get('last_name'),
                    'full_name': lead.get('full_name'),
                    'headline': lead.get('headline'),
                    'linkedin_url': lead.get('linkedin_url'),
                    'location': lead.get('location', {}),
                    'occupation': lead.get('occupation'),
                    'public_identifier': lead.get('public_identifier'),
                    'summary': lead.get('summary'),
                    'recommendations': lead.get('recommendations', []),
                    'online_presence': lead.get('online_presence', {}),
                    'professional_info': lead.get('professional_info', {})
                })

        # Convert merged data into leads_data format
        with transaction.atomic():
            for lead_id, lead_data in lead_data_mapping.items():
                # Move profile-specific fields to enrichment_data
                current_role = lead_data.get('current_role', {})
                online_presence = lead_data.get('online_presence', {})
                professional_info = lead_data.get('professional_info', {})
                location_data = lead_data.get('location', {})

                enrichment_data = {
                    # Profile metadata
                    'profile_url': lead_data.get('linkedin_url'),
                    'public_identifier': lead_data.get('public_identifier'),
                    'profile_pic_url': online_presence.get('profile_pic_url'),
                    'headline': lead_data.get('headline'),
                    'location': location_data,

                    # Professional details
                    'occupation': lead_data.get('occupation'),
                    'summary': lead_data.get('summary'),
                    'follower_count': online_presence.get('follower_count', 0),
                    'connection_count': online_presence.get('connection_count', 0),

                    # Career and experience
                    'companies_count': lead_data.get('companies_count'),
                    'industry_exposure': lead_data.get('industry_exposure', []),
                    'total_years_experience': lead_data.get('total_years_experience'),
                    'previous_roles': lead_data.get('previous_roles', []),

                    # Current role details
                    'current_role': current_role,

                    # Skills and education
                    'skills': professional_info.get('skills', []),
                    'certifications': professional_info.get('certifications', []),
                    'education': lead_data.get('education', []),
                    'languages': professional_info.get('languages', []),

                    # Additional content
                    'recommendations': lead_data.get('recommendations', []),

                    # Location details
                    'country': location_data.get('country'),
                    'country_full_name': location_data.get('country_full_name'),
                    'city': location_data.get('city'),
                    'state': location_data.get('state'),

                    # Source tracking
                    'data_source': processed_data.get('source', 'proxycurl'),

                    # Timestamp
                    'enriched_at': timezone.now().isoformat()
                }

                # Extract name fields
                first_name = lead_data.get('first_name')
                last_name = lead_data.get('last_name')
                if not first_name and lead_data.get('full_name'):
                    name_parts = lead_data.get('full_name', '').split()
                    first_name = name_parts[0] if name_parts else None
                    last_name = name_parts[-1] if len(name_parts) > 1 else None

                # Get role title from various sources
                role_title = (
                    current_role.get('title') or
                    lead_data.get('occupation') or
                    lead_data.get('headline')
                )

                custom_fields = {
                    # Evaluation data
                    'evaluation': {
                        'fit_score': lead_data.get('fit_score', 0.0),
                        'persona_match': lead_data.get('persona_match'),
                        'matching_signals': lead_data.get('matching_signals', []),
                        'recommended_approach': lead_data.get('recommended_approach'),
                        'analysis': lead_data.get('overall_analysis', []),
                        'rationale': lead_data.get('rationale'),
                    },
                }

                # Create the defaults dictionary with all available data
                defaults = {
                    'tenant': account.tenant,
                    'first_name': first_name,
                    'last_name': last_name,
                    'role_title': role_title,
                    'linkedin_url': lead_data.get('linkedin_url'),
                    'score': lead_data.get('fit_score', 0.0),
                    'enrichment_status': EnrichmentStatus.COMPLETED,
                    'last_enriched_at': timezone.now(),
                    'source': Lead.Source.ENRICHMENT,
                    'suggestion_status': Lead.SuggestionStatus.SUGGESTED,
                    'enrichment_data': enrichment_data,
                    'custom_fields': custom_fields,
                }

                # Remove None values
                defaults = {k: v for k, v in defaults.items() if v is not None}

                # Create or update lead
                lead, created = Lead.objects.get_or_create(
                    account=account,
                    linkedin_url=lead_data.get('linkedin_url'),
                    defaults=defaults
                )

                if not created:
                    # Update existing lead
                    for field, value in defaults.items():
                        setattr(lead, field, value)
                    lead.save()

            # Update account enrichment status
            account.enrichment_sources = account.enrichment_sources or {}
            account.enrichment_sources['lead_generation'] = {
                'last_run': timezone.now().isoformat(),
                'leads_found': len(lead_data_mapping),
                'score_distribution': processed_data.get('score_distribution', {})
            }
            account.save()
