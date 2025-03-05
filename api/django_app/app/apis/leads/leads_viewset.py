import logging
from django.db import transaction
from django.db import models
from django.db.models import F, Case, When, FloatField, Value, ExpressionWrapper, Q
from django.db.models.functions import Cast, Least
from django.db.models.expressions import RawSQL
from django_filters import rest_framework as filters
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


# Custom filter class for Lead model
class LeadFilter(filters.FilterSet):
    account_created_by = filters.UUIDFilter(field_name='account__created_by', lookup_expr='exact')

    class Meta:
        model = Lead
        fields = ['id', 'account', 'email', 'phone', 'created_by', 'suggestion_status', 'account_created_by']


class LeadsViewSet(TenantScopedViewSet, LeadGenerationMixin):
    serializer_class = LeadDetailsSerializer
    queryset = Lead.objects.all()
    http_method_names = ['get', 'post', 'patch', 'delete']
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = LeadFilter
    ordering_fields = ['first_name', 'last_name', 'created_at', 'updated_at', 'score']

    def get_permissions(self):
        return [HasRole(allowed_roles=[UserRole.USER, UserRole.TENANT_ADMIN,
                                       UserRole.INTERNAL_ADMIN, UserRole.INTERNAL_CS])]

    def _annotate_persona_match(self, queryset):
        """
        Helper method to annotate the queryset with persona_match from JSON field.

        Args:
            queryset: The base queryset to annotate

        Returns:
            QuerySet: The annotated queryset with persona_match field
        """
        return queryset.annotate(
            persona_match=Cast(
                RawSQL(
                    "enrichment_data->'evaluation'->>'persona_match'",
                    []
                ),
                models.CharField()
            )
        )

    def _annotate_with_adjusted_scores(self, queryset, multipliers):
        """
        Helper method to annotate the queryset with adjusted scores based on persona.

        Args:
            queryset: The base queryset to annotate
            multipliers: Dictionary of multipliers for each persona type

        Returns:
            QuerySet: The annotated queryset with adjusted scores
        """
        return queryset.annotate(
            # Calculate the score with multipliers in one step
            multiplied_score=Case(
                When(persona_match=Value('buyer'),
                     then=F('score') * Value(multipliers.get('buyer', 1.2))),
                When(persona_match=Value('influencer'),
                     then=F('score') * Value(multipliers.get('influencer', 1.0))),
                When(persona_match=Value('end_user'),
                     then=F('score') * Value(multipliers.get('end_user', 0.8))),
                default=F('score'),
                output_field=FloatField(),
            ),
            # Cap the score at 100 using the Least function
            adjusted_score=Least(F('multiplied_score'), Value(100.0), output_field=FloatField())
        )

    def get_queryset(self):
        """
        Enhanced queryset with persona-based score adjustments.

        This method applies different weights to leads based on their persona type
        stored in enrichment_data.evaluation.persona_match:
        - Buyers get a higher weight (1.2x)
        - Influencers maintain their score (1.0x)
        - End Users get a lower weight (0.8x)

        This balances the results to favor buyers and influencers over end users
        while maintaining the original scoring within each persona category.
        """
        queryset = super().get_queryset().select_related('account')

        # Check if created_at is in query params and map to account__created_by
        if 'created_at' in self.request.query_params:
            created_by_value = self.request.query_params.get('created_at')
            queryset = queryset.filter(account__created_by=created_by_value)

        # Get balance parameters from query params with defaults - false by default
        balance_personas = self.request.query_params.get('balance_personas', 'false').lower() == 'true'

        # Apply persona-based score adjustment if requested
        if balance_personas:
            # Define multipliers
            multipliers = {
                'buyer': float(self.request.query_params.get('buyer_multiplier', '1.05')),
                'influencer': float(self.request.query_params.get('influencer_multiplier', '1.0')),
                'end_user': float(self.request.query_params.get('end_user_multiplier', '0.85'))
            }

            # First annotate with persona_match
            queryset = self._annotate_persona_match(queryset)

            # Then annotate with adjusted scores based on persona
            queryset = self._annotate_with_adjusted_scores(queryset, multipliers)

            # Order by adjusted score, then by original score for ties
            return queryset.order_by(F('adjusted_score').desc(nulls_last=True), F('score').desc(nulls_last=True))
        else:
            # Use the original score ordering
            return queryset.order_by(F('score').desc(nulls_last=True))

    @action(detail=False, methods=['get'])
    def balanced(self, request):
        """
        Return leads with balanced persona distribution using quotas.

        This endpoint returns a balanced mix of leads with configurable quotas:
        - min_buyers: Minimum number of buyers to include (default: 5)
        - min_influencers: Minimum number of influencers to include (default: 5)
        - max_end_users: Maximum number of end users to include (default: 5)
        - total: Total number of leads to return (default: 15)

        The results will contain at least the specified minimums of buyers and influencers,
        and at most the specified maximum of end users, up to the total count.
        Any remaining slots will be filled with the highest-scoring leads regardless of persona.
        """
        # Get parameters with defaults
        account_id = request.query_params.get('account')
        min_buyers = int(request.query_params.get('min_buyers', '5'))
        min_influencers = int(request.query_params.get('min_influencers', '5'))
        max_end_users = int(request.query_params.get('max_end_users', '5'))
        total_limit = int(request.query_params.get('total', '15'))

        # Validate parameters
        if min_buyers + min_influencers + max_end_users > total_limit:
            return Response(
                {"error": "Sum of quota parameters exceeds total limit"},
                status=status.HTTP_400_BAD_REQUEST
            )

        base_queryset = super().get_queryset().select_related('account').order_by('-score')
        if account_id:
            base_queryset = base_queryset.filter(account_id=account_id)

        # Annotate with persona_match for filtering
        persona_queryset = self._annotate_persona_match(base_queryset)

        # Filter by persona type
        buyer_queryset = persona_queryset.filter(
            persona_match='buyer'
        ).order_by('-score')[:min_buyers]

        influencer_queryset = persona_queryset.filter(
            persona_match='influencer'
        ).order_by('-score')[:min_influencers]

        end_user_queryset = persona_queryset.filter(
            persona_match='end_user'
        ).order_by('-score')[:max_end_users]

        # Apply quotas
        buyers = list(buyer_queryset)
        influencers = list(influencer_queryset)
        end_users = list(end_user_queryset)

        # Calculate remaining slots
        selected_ids = [lead.id for lead in buyers + influencers + end_users]
        remaining_slots = total_limit - len(selected_ids)

        # Fill remaining slots with highest-scoring leads not yet selected
        remaining_leads = []
        if remaining_slots > 0:
            remaining_leads = list(
                base_queryset.exclude(id__in=selected_ids).order_by('-score')[:remaining_slots]
            )

        # Combine all selected leads
        combined_leads = buyers + influencers + end_users + remaining_leads

        # Sort by score for final ordering
        combined_leads.sort(key=lambda x: x.score or 0, reverse=True)

        # Serialize and return
        serializer = self.get_serializer(combined_leads, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def quota_distribution(self, request):
        """
        Returns leads with a specified distribution across persona types.

        This endpoint allows specifying percentages for each persona type:
        - buyer_percent: Percentage of results to be buyers (default: 40)
        - influencer_percent: Percentage of results to be influencers (default: 40)
        - end_user_percent: Percentage of results to be end users (default: 20)
        - total: Total number of leads to return (default: 15)

        The results will contain approximately the specified distribution of persona types,
        with the highest-scoring leads selected from each category.
        """
        # Get parameters with defaults
        account_id = request.query_params.get('account')
        buyer_percent = float(request.query_params.get('buyer_percent', '40'))
        influencer_percent = float(request.query_params.get('influencer_percent', '40'))
        end_user_percent = float(request.query_params.get('end_user_percent', '20'))
        total_limit = int(request.query_params.get('total', '15'))

        # Validate percentages sum to 100
        total_percent = buyer_percent + influencer_percent + end_user_percent
        if not (99.0 <= total_percent <= 101.0):  # Allow small rounding errors
            return Response(
                {"error": "Percentages must sum to approximately 100"},
                status=status.HTTP_400_BAD_REQUEST
            )

        base_queryset = super().get_queryset().select_related('account').order_by('-score')
        if account_id:
            base_queryset = base_queryset.filter(account_id=account_id)

        # Calculate number of leads for each persona type
        buyer_count = int(round(total_limit * buyer_percent / 100.0))
        influencer_count = int(round(total_limit * influencer_percent / 100.0))
        end_user_count = total_limit - buyer_count - influencer_count  # Ensure total adds up exactly

        # Annotate with persona_match for filtering
        persona_queryset = self._annotate_persona_match(base_queryset)

        # Filter by persona type
        buyers = list(persona_queryset.filter(
            persona_match='buyer'
        ).order_by('-score')[:buyer_count])

        influencers = list(persona_queryset.filter(
            persona_match='influencer'
        ).order_by('-score')[:influencer_count])

        end_users = list(persona_queryset.filter(
            persona_match='end_user'
        ).order_by('-score')[:end_user_count])

        # If we don't have enough of a certain type, fill with the highest-scoring remaining leads
        selected_ids = [lead.id for lead in buyers + influencers + end_users]
        remaining_slots = total_limit - len(selected_ids)

        remaining_leads = []
        if remaining_slots > 0:
            remaining_leads = list(
                base_queryset.exclude(id__in=selected_ids).order_by('-score')[:remaining_slots]
            )

        # Combine all selected leads
        combined_leads = buyers + influencers + end_users + remaining_leads

        # Sort by score for final ordering
        combined_leads.sort(key=lambda x: x.score or 0, reverse=True)

        # Serialize and return
        serializer = self.get_serializer(combined_leads, many=True)
        return Response(serializer.data)

    # Keep existing methods below
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
        lead = None
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
            enrichment_data = lead.enrichment_data or {}

            linkedin_research_input_data = LinkedInResearchInputData(
                lead_data=LinkedInResearchInputData.LeadData(
                    name=f"{lead.first_name} {lead.last_name}",
                    headline=enrichment_data.get('headline'),
                    about=enrichment_data.get('about'),
                    location=enrichment_data.get('location'),
                    current_employment=enrichment_data.get('current_employment'),
                    employment_history=enrichment_data.get('employment_history'),
                    education=enrichment_data.get('education'),
                    projects=enrichment_data.get('projects'),
                    publications=enrichment_data.get('publications'),
                    groups=enrichment_data.get('groups'),
                    certifications=enrichment_data.get('certifications'),
                    honor_awards=enrichment_data.get('honor_awards'),
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
                    playbook_description=product.playbook_description
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
            if lead is not None and 'lead' in locals():
                lead.enrichment_status = EnrichmentStatus.FAILED
                lead.save(update_fields=['enrichment_status'])

            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )