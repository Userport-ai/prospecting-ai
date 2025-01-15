from typing import Dict, Any

from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from app.apis.auth.auth_verify_cloud_run_decorator import verify_cloud_run_token
from app.models import Lead
from app.models.account_enrichment import AccountEnrichmentStatus, EnrichmentType
from app.models.accounts import Account, EnrichmentStatus
from django.db import transaction
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

@api_view(['POST'])
@authentication_classes([])  # Disable default auth
@permission_classes([AllowAny])
@verify_cloud_run_token
def enrichment_callback(request):
    logger.info(f"Enrichment callback request for {request.data.get('enrichment_type', 'Unknown')} Full data: {request.data}")
    try:
        data = request.data
        account_id = data.get('account_id')
        status = data.get('status')
        enrichment_type = data.get('enrichment_type')
        processed_data = data.get('processed_data', {})

        if not all([account_id, status, enrichment_type]):
            return Response({
                "error": "Missing required fields"
            }, status=400)

        with transaction.atomic():
            account = Account.objects.select_for_update().get(id=account_id)

            enrichment_status, _ = AccountEnrichmentStatus.objects.update_or_create(
                account=account,
                enrichment_type=enrichment_type,
                defaults={
                    'status': status,
                    'last_attempted_run': timezone.now(),
                    'last_successful_run': timezone.now() if status == EnrichmentStatus.COMPLETED else None,
                    'source': data.get('source', 'unknown'),
                    'error_details': data.get('error_details'),
                    'metadata': data.get('metadata', {}),
                    'data_quality_score': data.get('quality_score')
                }
            )

            if status == EnrichmentStatus.FAILED:
                enrichment_status.failure_count += 1
                enrichment_status.save()

            # Update account fields if enrichment was successful
            if status == EnrichmentStatus.COMPLETED and processed_data:
                _update_account_from_enrichment(account, enrichment_type, processed_data)
                account.save()

        return Response({
            "status": "success",
            "enrichment_summary": account.get_enrichment_summary()
        })

    except Account.DoesNotExist:
        return Response({"error": "Account not found"}, status=404)
    except Exception as e:
        logger.error(f"Error processing callback: {str(e)}")
        return Response({"error": str(e)}, status=500)


def _update_account_from_enrichment(account: Account, enrichment_type: str, processed_data: Dict[str, Any]) -> None:
    if enrichment_type == EnrichmentType.GENERATE_LEADS:
        if not processed_data:
            return
        logger.info(f"Updating account {account.id} with suggested leads. "
                    f"No. of qualified leads: {len(processed_data.get('qualified_leads', []))}")

        leads_data = processed_data.get('qualified_leads', [])

        with transaction.atomic():
            for lead_data in leads_data:
                # Move profile-specific fields to enrichment_data
                enrichment_data = {
                    # Evaluation data
                    'fit_score': lead_data.get('fit_score', 0.0),
                    'persona_match': lead_data.get('persona_match'),
                    'matching_criteria': lead_data.get('matching_criteria', []),
                    'recommended_approach': lead_data.get('recommended_approach'),
                    'analysis': lead_data.get('overall_analysis', []),

                    # Profile metadata
                    'profile_url': lead_data.get('profile_url'),
                    'public_identifier': lead_data.get('public_identifier'),
                    'profile_pic_url': lead_data.get('profile_pic_url'),
                    'headline': lead_data.get('headline'),  # Moved from direct field
                    'location': lead_data.get('location'),  # Moved from direct field

                    # Professional details
                    'occupation': lead_data.get('occupation'),
                    'summary': lead_data.get('summary'),
                    'follower_count': lead_data.get('follower_count', 0),
                    'connection_count': lead_data.get('connection_count', 0),

                    # Current role details
                    'current_role': lead_data.get('current_role', {}),

                    # Skills and experience
                    'skills': lead_data.get('skills', []),
                    'experience_history': lead_data.get('experience_history', []),
                    'education': lead_data.get('education', []),
                    'languages': lead_data.get('languages', []),
                    'languages_and_proficiencies': lead_data.get('languages_and_proficiencies', []),

                    # Additional content
                    'articles': lead_data.get('articles', []),
                    'activities': lead_data.get('activities', []),
                    'volunteer_work': lead_data.get('volunteer_work', []),

                    # Location details
                    'country': lead_data.get('country'),
                    'country_full_name': lead_data.get('country_full_name'),
                    'city': lead_data.get('city'),
                    'state': lead_data.get('state'),

                    # Source tracking
                    'data_source': lead_data.get('data_source', 'proxycurl'),

                    # Timestamp
                    'enriched_at': timezone.now().isoformat()
                }

                # Collect all fields that aren't part of the standard model
                custom_fields = {}
                for key, value in lead_data.items():
                    if key not in [
                        'first_name', 'last_name', 'email', 'phone', 'linkedin_url',
                        'fit_score', 'current_role', 'headline'  # Already handled
                    ] and key not in enrichment_data:  # Don't duplicate enrichment data
                        custom_fields[key] = value

                # If there's raw data, add it to custom fields
                if 'raw_data' in lead_data:
                    custom_fields['raw_data'] = lead_data['raw_data']

                defaults = {
                    'tenant': account.tenant,
                    'first_name': lead_data.get('first_name'),
                    'last_name': lead_data.get('last_name'),
                    'role_title': lead_data.get('current_role', {}).get('title') or lead_data.get('headline'),
                    'email': lead_data.get('email'),
                    'phone': lead_data.get('phone'),
                    'score': lead_data.get('fit_score', 0.0),
                    'enrichment_status': EnrichmentStatus.COMPLETED,
                    'last_enriched_at': timezone.now(),
                    'source': Lead.Source.ENRICHMENT,
                    'suggestion_status': Lead.SuggestionStatus.SUGGESTED,
                    'enrichment_data': enrichment_data,
                    'custom_fields': custom_fields
                }

                # Remove None values
                defaults = {k: v for k, v in defaults.items() if v is not None}

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
            'leads_found': len(leads_data)
        }
        account.save()