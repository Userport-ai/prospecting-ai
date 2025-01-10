from typing import Dict, Any

from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from app.apis.auth.auth_verify_cloud_run_decorator import verify_cloud_run_token
from app.models.account_enrichment import AccountEnrichmentStatus, EnrichmentType
from app.models.accounts import Account, EnrichmentStatus
from django.db import transaction
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

@authentication_classes([])  # Disable default auth
@permission_classes([AllowAny])
@api_view(['POST'])
@verify_cloud_run_token
def enrichment_callback(request):
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

        # Update fields from processed_data
        account.name = processed_data.get('company_name') or account.name
        account.employee_count = processed_data.get('employee_count')
        account.industry = processed_data.get('industry', [None])[0]  # Take first industry if list
        account.location = processed_data.get('location')
        account.website = processed_data.get('website')
        account.linkedin_url = processed_data.get('linkedin_url')

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
        return

    logger.warning(f"Unsupported enrichment type: {enrichment_type}")