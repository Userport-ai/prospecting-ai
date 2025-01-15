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
    """
     Updates account fields based on enrichment data
     Args:
         account: Account instance to update
         enrichment_type: Type of enrichment
         processed_data: Dictionary containing processed enrichment data and raw_data
     """
    if enrichment_type == EnrichmentType.COMPANY_INFO:
        if not processed_data:
            return
        logger.info(f"Updating account {account.id} with company info")
        # Update fields from processed_data
        account.name = account.name or processed_data.get('company_name')
        account.employee_count = processed_data.get('employee_count')
        account.industry = processed_data.get('industry', [None])[0]  # Take first industry if list
        account.location = processed_data.get('location')
        account.website = account.website or processed_data.get('website')
        account.linkedin_url = account.linkedin_url or processed_data.get('linkedin_url')
        # Handle array/JSON fields
        if 'technologies' in processed_data:
            account.technologies = processed_data['technologies']
        if 'funding_details' in processed_data:
            account.funding_details = processed_data['funding_details']
        # Handle company info from raw_data
        raw_data = processed_data.get('raw_data', {})
        if isinstance(raw_data, dict):
            company_info = raw_data.get('company_info', {})
            account.company_type = company_info.get('company_type')
            account.founded_year = company_info.get('founded_year')
            account.customers = company_info.get('customers', [])
            account.competitors = company_info.get('competitors', [])
        account.save()
        return
    elif enrichment_type == EnrichmentType.GENERATE_LEADS:
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

                # First, extract all possible data for Lead model fields
                current_role = lead_data.get('current_role', {})
                role_title = (
                        current_role.get('title') or
                        lead_data.get('role_title') or
                        lead_data.get('headline') or
                        lead_data.get('occupation')
                )

                # Get name fields, trying multiple sources
                first_name = (
                        lead_data.get('first_name') or
                        (lead_data.get('full_name', '').split()[0] if lead_data.get('full_name') else None)
                )
                last_name = (
                        lead_data.get('last_name') or
                        (lead_data.get('full_name', '').split()[-1] if lead_data.get('full_name') and len(lead_data.get('full_name', '').split()) > 1 else None)
                )

                # Extract phone with fallbacks
                phone = (
                        lead_data.get('phone') or
                        lead_data.get('mobile') or
                        current_role.get('phone') or
                        None
                )

                # Collect all fields that aren't part of the standard model
                custom_fields = {}
                model_fields = {
                    'first_name', 'last_name', 'email', 'phone', 'linkedin_url',
                    'fit_score', 'current_role', 'headline', 'role_title', 'score',
                    'enrichment_status', 'source', 'suggestion_status'
                }

                for key, value in lead_data.items():
                    if key not in model_fields and key not in enrichment_data:
                        custom_fields[key] = value

                # If there's raw data, add it to custom fields
                if 'raw_data' in lead_data:
                    custom_fields['raw_data'] = lead_data['raw_data']

                # Create the defaults dictionary with all available data
                defaults = {
                    'tenant': account.tenant,
                    'first_name': first_name,
                    'last_name': last_name,
                    'role_title': role_title,
                    'email': lead_data.get('email'),
                    'phone': phone,
                    'linkedin_url': lead_data.get('linkedin_url'),
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
    else:
        logger.warning(f"Unsupported enrichment type: {enrichment_type}")
        account.save()