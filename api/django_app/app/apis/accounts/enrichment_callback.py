from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from app.apis.auth.auth_verify_cloud_run_decorator import verify_cloud_run_token
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
    """
    Callback endpoint for Cloud Run to update enrichment status and data
    """
    try:
        data = request.data
        job_id = data.get('job_id')
        account_id = data.get('account_id')
        status = data.get('status')
        raw_data = data.get('raw_data', {})
        processed_data = data.get('processed_data', {})

        if not all([job_id, account_id, status]):
            return Response({
                "error": "Missing required fields"
            }, status=400)

        with transaction.atomic():
            account = Account.objects.select_for_update().get(id=account_id)

            # Map status from BQ to Django model
            status_mapping = {
                'pending': EnrichmentStatus.PENDING,
                'processing': EnrichmentStatus.IN_PROGRESS,
                'completed': EnrichmentStatus.COMPLETED,
                'failed': EnrichmentStatus.FAILED
            }

            # Update account fields from processed data
            if processed_data:
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

                # If raw_data contains additional structured info
                if raw_data and isinstance(raw_data, dict):
                    company_info = raw_data.get('company_info', {})
                    account.company_type = company_info.get('company_type')
                    account.founded_year = company_info.get('founded_year')
                    account.customers = company_info.get('customers', [])
                    account.competitors = company_info.get('competitors', [])

            # Update enrichment metadata
            account.enrichment_status = status_mapping.get(status, EnrichmentStatus.FAILED)
            account.last_enriched_at = timezone.now()

            # Store enrichment sources and any error info
            if not account.enrichment_sources:
                account.enrichment_sources = {}
            account.enrichment_sources.update({
                data.get('source', 'unknown'): {
                    'status': status,
                    'timestamp': timezone.now().isoformat(),
                    'job_id': job_id,
                    'is_partial': data.get('is_partial', False),
                    'completion_percentage': data.get('completion_percentage', 0),
                    'error': data.get('error_details')
                }
            })

            account.save()

            logger.info(f"Updated account {account_id} enrichment status to {status}")

        return Response({
            "status": "success",
            "message": f"Updated account {account_id}",
            "current_status": account.enrichment_status
        })

    except Account.DoesNotExist:
        logger.error(f"Account {account_id} not found")
        return Response({
            "error": "Account not found"
        }, status=404)
    except Exception as e:
        logger.error(f"Error processing callback: {str(e)}")
        return Response({
            "error": str(e)
        }, status=500)