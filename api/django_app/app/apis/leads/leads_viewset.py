import logging

from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from app.apis.common.base import TenantScopedViewSet
from app.apis.leads.lead_generation_mixin import LeadGenerationMixin
from app.models import UserRole, Lead, Account, EnrichmentStatus, Product
from app.models.serializers.lead_serializers import (
    LeadDetailsSerializer,
    LeadBulkCreateSerializer
)
from app.models.enrichment.lead_linkedin_research import LinkedInResearchInputData
from app.permissions import HasRole
from app.services.worker_service import WorkerService

logger = logging.getLogger(__name__)


class LeadsViewSet(TenantScopedViewSet, LeadGenerationMixin):
    serializer_class = LeadDetailsSerializer
    queryset = Lead.objects.all()
    http_method_names = ['get', 'post', 'patch', 'delete']
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['id', 'account', 'email', 'phone', 'created_by', 'suggestion_status']
    ordering_fields = ['first_name', 'last_name', 'created_at', 'updated_at', 'score']
    ordering = ['-score']  # Default sorting

    def get_permissions(self):
        return [HasRole(allowed_roles=[UserRole.USER, UserRole.TENANT_ADMIN,
                                       UserRole.INTERNAL_ADMIN, UserRole.INTERNAL_CS])]

    @action(detail=False, methods=['post'])
    def generate(self, request):
        """
        Trigger lead generation for an account
        """
        account_id = request.data.get('account')
        if not account_id:
            return Response(
                {"error": "account_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            account = Account.objects.select_related('product').get(
                id=account_id,
                tenant=request.tenant
            )

            if not account.linkedin_url:
                return Response(
                    {"error": "Account must have a LinkedIn URL for lead generation"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            response = self._trigger_lead_generation(account)

            return Response({
                "message": "Lead generation started",
                "job_id": response.get('job_id'),
                "account_id": str(account.id)
            })

        except Account.DoesNotExist:
            return Response(
                {"error": "Account not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """
        Bulk create leads with enrichment
        """
        # Get account_id and leads data
        account_id = request.data.get('account')
        if not account_id:
            return Response(
                {"error": "account_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        leads_data = request.data.get('leads', [])
        if not leads_data:
            return Response(
                {"error": "No leads provided"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if len(leads_data) > 1000:
            return Response(
                {"error": "Maximum 1000 leads allowed per request"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate all leads
        serializer = LeadBulkCreateSerializer(data=leads_data, many=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Bulk create leads
        try:
            with transaction.atomic():
                leads = []
                for lead_data in leads_data:
                    lead = Lead(
                        tenant=request.tenant,
                        account_id=account_id,
                        created_by=request.user,
                        **lead_data
                    )
                    leads.append(lead)

                created_leads = Lead.objects.bulk_create(leads)

                # Trigger enrichment for created leads
                lead_ids = [lead.id for lead in created_leads]
                # TODO: Trigger enrichment job

                response_data = {
                    "message": "Leads created successfully",
                    "lead_count": len(created_leads),
                    "leads": LeadDetailsSerializer(created_leads, many=True).data
                }

                return Response(response_data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def enrich_linkedin_activity(self, request, pk=None):
        """
        Trigger LinkedIn research enrichment for a specific lead
        """
        try:
            # Get the lead with related account
            lead = Lead.objects.select_related('account').get(
                id=pk,
                tenant=request.tenant
            )

            if (not pk) or (not lead.linkedin_url):
                return Response(
                    {"error": "Lead must have both ID and LinkedIn URL for enrichment"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get HTML content from request payload
            posts_html = request.data.get('posts_html', '')
            comments_html = request.data.get('comments_html', '')
            reactions_html = request.data.get('reactions_html', '')

            # Get Lead, Account and Product data.
            account: Account = lead.account
            product: Product = account.product
            linkedin_research_input_data = LinkedInResearchInputData(
                lead_data=LinkedInResearchInputData.LeadData(
                    name=f"{lead.first_name} {lead.last_name}",
                    headline=lead.enrichment_data.get('headline'),
                    about=lead.enrichment_data.get('about'),
                    location=lead.enrichment_data.get('location'),
                    current_employment=lead.enrichment_data.get('current_employment'),
                    employment_history=lead.enrichment_data.get('employment_history'),
                    education=lead.enrichment_data.get('education'),
                    projects=lead.enrichment_data.get('projects'),
                    publications=lead.enrichment_data.get('publications'),
                    groups=lead.enrichment_data.get('groups'),
                    certifications=lead.enrichment_data.get('certifications'),
                    honor_awards=lead.enrichment_data.get('honor_awards'),
                ),
                account_data=LinkedInResearchInputData.AccountData(
                    name=account.name,
                    industry=account.industry,
                    location=account.location,
                    employee_count=account.employee_count,
                    company_type=account.company_type,
                    founded_year=account.founded_year,
                    technologies=account.technologies,
                    competitors=account.competitors,
                    customers=account.customers,
                    funding_details=account.funding_details
                ),
                product_data=LinkedInResearchInputData.ProductData(
                    name=product.name,
                    description=product.description,
                    persona_role_titles=product.persona_role_titles,
                    # TODO: This is hack, fix by adding a new column to table.
                    playbook_description=product.playbook_description.split("---")[1] if product.playbook_description else None
                )
            )

            # Prepare payload for worker service
            payload = {
                "account_id": str(lead.account.id),
                "lead_id": str(lead.id),
                "person_name": f"{lead.first_name or ''} {lead.last_name or ''}".strip(),
                "company_name": lead.account.name,
                "person_linkedin_url": lead.linkedin_url,
                "posts_html": posts_html,
                "comments_html": comments_html,
                "reactions_html": reactions_html,
                "research_request_type": "linkedin_only",
                "input_data": linkedin_research_input_data.model_dump(),
                "job_id": f"linkedin_research_{str(lead.id)}",
                "origin": "api",
                "user_id": str(request.user.id),
                "attempt_number": 1,
                "max_retries": 3
            }

            # Update lead status to indicate enrichment in progress
            lead.enrichment_status = EnrichmentStatus.IN_PROGRESS
            lead.save(update_fields=['enrichment_status'])

            # Trigger worker job
            worker_service = WorkerService()
            response = worker_service.trigger_lead_enrichment(payload)

            return Response({
                "message": "Lead LinkedIn research started",
                "job_id": response.get('job_id'),
                "lead_id": str(lead.id)
            })

        except Lead.DoesNotExist:
            return Response(
                {"error": "Lead not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            # Log the error for debugging
            logger.error(f"Failed to trigger lead LinkedIn research: {str(e)}")

            # Update lead status to failed if there's an error
            if 'lead' in locals():
                lead.enrichment_status = EnrichmentStatus.FAILED
                lead.save(update_fields=['enrichment_status'])

            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
