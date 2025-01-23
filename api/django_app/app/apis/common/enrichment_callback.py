import logging
from typing import Dict, Any

from django.db import transaction
from django.utils import timezone
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from app.apis.auth.auth_verify_cloud_run_decorator import verify_cloud_run_token
from app.apis.leads.lead_enrichment_handler import LeadEnrichmentHandler
from app.apis.leads.streaming_leads_callback_handler import StreamingCallbackHandler
from app.models import Lead
from app.models.account_enrichment import AccountEnrichmentStatus, EnrichmentType
from app.models.accounts import Account, EnrichmentStatus

logger = logging.getLogger(__name__)


@api_view(['POST'])
@authentication_classes([])  # Disable default auth
@permission_classes([AllowAny])
# TODO**** @verify_cloud_run_token
def enrichment_callback(request):
    logger.info(f"Enrichment callback request for {request.data.get('enrichment_type', 'Unknown')}")

    try:
        data = request.data
        account_id = data.get('account_id')
        lead_id = data.get('lead_id')
        status = data.get('status')
        enrichment_type = data.get('enrichment_type')
        processed_data = data.get('processed_data', {})

        if not all([account_id, status, enrichment_type]):
            return Response({
                "error": "Missing required fields"
            }, status=400)

        with transaction.atomic():
            account = Account.objects.select_for_update().get(id=account_id)

            # Update enrichment status
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

            # Process based on enrichment type
            if status == EnrichmentStatus.COMPLETED and processed_data:
                if enrichment_type == EnrichmentType.LEAD_LINKEDIN_RESEARCH:
                    if not lead_id:
                        raise ValueError("Lead ID required for lead enrichment")
                    LeadEnrichmentHandler.handle_lead_enrichment(
                        lead_id=lead_id,
                        account_id=account_id,
                        processed_data=processed_data
                    )
                elif enrichment_type == EnrichmentType.GENERATE_LEADS and data.get('pagination'):
                    # Process through streaming handler
                    result = StreamingCallbackHandler.handle_callback(data)
                    if result is None:
                        # Intermediate page - acknowledge receipt
                        return Response({"status": "processing"})
                else:
                    # Use existing account enrichment function for other types
                    _update_account_from_enrichment(account, enrichment_type, processed_data)

        return Response({
            "status": "success",
            "enrichment_summary": account.get_enrichment_summary()
        })

    except Account.DoesNotExist:
        return Response({"error": "Account not found"}, status=404)
    except Lead.DoesNotExist:
        return Response({"error": "Lead not found"}, status=404)
    except Exception as e:
        logger.error(f"Error processing callback: {str(e)}", exc_info=True)
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
        account.name = processed_data.get('company_name')
        account.employee_count = processed_data.get('employee_count')
        account.industry = processed_data.get('industry')
        account.location = processed_data.get('location')
        account.website = processed_data.get('website')
        account.linkedin_url = processed_data.get('linkedin_url')
        # Handle array/JSON fields
        if 'technologies' in processed_data:
            account.technologies = processed_data['technologies']
        if 'funding_details' in processed_data:
            account.funding_details = processed_data['funding_details']
        account.company_type = processed_data.get('company_type')
        account.founded_year = processed_data.get('founded_year')
        account.customers = processed_data.get('customers', [])
        account.competitors = processed_data.get('competitors', [])
        account.save()
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
                    'matching_criteria': lead.get('matching_criteria', []),
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
                        'matching_criteria': lead_data.get('matching_criteria', []),
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
