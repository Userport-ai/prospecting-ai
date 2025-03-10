import base64
import json
import logging

from django.db import models
from django.db import transaction
from django.db.models import F, Case, When, FloatField, Value
from django.db.models.expressions import RawSQL
from django.db.models.functions import Cast
from django.db.models.functions import Cast, Least
from django_filters import rest_framework as filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from app.apis.common.base import TenantScopedViewSet
from app.apis.leads.lead_generation_mixin import LeadGenerationMixin
from app.models import UserRole, Lead, Account, EnrichmentStatus, Product
from app.models.enrichment.lead_linkedin_research import LinkedInResearchInputData
from app.models.serializers.lead_serializers import (
    LeadDetailsSerializer,
    LeadBulkCreateSerializer
)
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
        Modified to handle NULL scores properly.

        Args:
            queryset: The base queryset to annotate
            multipliers: Dictionary of multipliers for each persona type

        Returns:
            QuerySet: The annotated queryset with adjusted scores
        """
        return queryset.annotate(
            # Calculate the score with multipliers in one step, using Coalesce to handle NULLs
            multiplied_score=Case(
                When(persona_match=Value('buyer'),
                     then=models.functions.Coalesce('score', Value(0.0)) * Value(multipliers.get('buyer', 1.2))),
                When(persona_match=Value('influencer'),
                     then=models.functions.Coalesce('score', Value(0.0)) * Value(multipliers.get('influencer', 1.0))),
                When(persona_match=Value('end_user'),
                     then=models.functions.Coalesce('score', Value(0.0)) * Value(multipliers.get('end_user', 0.8))),
                default=models.functions.Coalesce('score', Value(0.0)),
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
        - Buyers get a higher weight (1.05x)
        - Influencers maintain their score (1.0x)
        - End Users get a lower weight (0.85x)

        This balances the results to favor buyers and influencers over end users
        while maintaining the original scoring within each persona category.
        """
        queryset = super().get_queryset().select_related('account')

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
            
            # order by adjusted_score before returning the results
            return queryset.order_by(F('adjusted_score').desc(nulls_last=True))


        else:
            # Use the original score ordering
            return queryset.order_by(F('score').desc(nulls_last=True))

    def _format_pagination_response(self, results, serializer, request, next_cursor_str=None, previous_cursor_str=None, counts=None, has_more=False):
        """
        Helper method to format the pagination response in standard Django format

        Args:
            results: The queryset results to be serialized
            serializer: The serializer to use
            request: The request object for building URLs
            next_cursor_str: Base64 encoded cursor for next page
            previous_cursor_str: Base64 encoded cursor for previous page
            counts: Additional count information to include
            has_more: Boolean indicating if there are more results

        Returns:
            Response: Formatted response with standard pagination structure
        """
        # Serialize results
        serialized_data = serializer(results, many=True).data

        # Construct next and previous URLs
        base_url = request.build_absolute_uri().split('?')[0]
        # Ensure HTTPS instead of HTTP
        if base_url.startswith('http://'):
            base_url = base_url.replace('http://', 'https://', 1)

        query_params = request.query_params.copy()

        # Create next URL if we have more results
        next_url = None
        if next_cursor_str and has_more:
            import urllib.parse
            query_params['cursor'] = next_cursor_str
            next_url = f"{base_url}?{'&'.join([f'{k}={urllib.parse.quote(str(v))}' for k, v in query_params.items()])}"

        # Create previous URL if we have a previous cursor
        previous_url = None
        if previous_cursor_str:
            import urllib.parse
            query_params['cursor'] = previous_cursor_str
            previous_url = f"{base_url}?{'&'.join([f'{k}={urllib.parse.quote(str(v))}' for k, v in query_params.items()])}"

        # Format the response in standard Django pagination format
        response_data = {
            "count": counts.get("total_count", len(results)) if counts else len(results),
            "next": next_url,
            "previous": previous_url,
            "results": serialized_data
        }

        # Include additional counts data if provided
        if counts:
            response_data["meta"] = {"counts": counts}

        return Response(response_data)

    @action(detail=False, methods=['get'])
    def balanced(self, request):
        """
        Return leads with balanced persona distribution using quotas with cursor-based pagination.

        Parameters:
        - min_buyers: Minimum number of buyers to include (default: 5)
        - min_influencers: Minimum number of influencers to include (default: 5)
        - max_end_users: Maximum number of end users to include (default: 5)
        - limit: Number of leads to return per page (default: 15)
        - cursor: Pagination cursor (optional)
        """
        # Parse parameters
        account_id = request.query_params.get('account')
        min_buyers = int(request.query_params.get('min_buyers', '5'))
        min_influencers = int(request.query_params.get('min_influencers', '5'))
        max_end_users = int(request.query_params.get('max_end_users', '5'))
        limit = int(request.query_params.get('limit', '15'))

        # Validate parameters
        if min_buyers + min_influencers + max_end_users > limit:
            return Response(
                {"error": "Sum of quota parameters exceeds total limit"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Define default cursor values
        default_cursor = {
            "buyer_page": 0,
            "influencer_page": 0,
            "end_user_page": 0,
            "remaining_page": 0,
            "buyer_count": 0,
            "influencer_count": 0,
            "end_user_count": 0,
            "total_count": 0
        }

        # Parse cursor if provided
        cursor_str = request.query_params.get('cursor')
        cursor = default_cursor.copy()  # Start with defaults

        if cursor_str:
            try:
                parsed_cursor = json.loads(base64.b64decode(cursor_str).decode('utf-8'))
                # Update default cursor with any valid keys from parsed cursor
                for key in default_cursor:
                    if key in parsed_cursor:
                        cursor[key] = parsed_cursor[key]

                # Log any unexpected keys for debugging
                unexpected_keys = set(parsed_cursor.keys()) - set(default_cursor.keys())
                if unexpected_keys:
                    logger.warning(f"Cursor contained unexpected keys: {unexpected_keys}")
            except Exception as e:
                logger.warning(f"Failed to parse cursor: {str(e)}")
                # We'll continue with the default cursor rather than failing the request

        # Prepare base queryset with all filters except persona
        base_queryset = super().get_queryset().select_related('account')
        if account_id:
            base_queryset = base_queryset.filter(account_id=account_id)

        # Add suggestion_status filter if provided
        suggestion_status = request.query_params.get('suggestion_status')
        if suggestion_status:
            base_queryset = base_queryset.filter(suggestion_status=suggestion_status)

        # Annotate with persona_match
        base_queryset = self._annotate_persona_match(base_queryset)

        # Apply pagination and fetch leads for each persona
        results = []
        next_cursor = cursor.copy()
        has_more = False

        # Fetch buyers if quota not met
        buyer_to_fetch = min(min_buyers - cursor["buyer_count"], limit - len(results))
        if buyer_to_fetch > 0:
            buyer_queryset = base_queryset.filter(persona_match='buyer').order_by('-score')
            buyer_offset = cursor["buyer_page"] * buyer_to_fetch
            buyers = list(buyer_queryset[buyer_offset:buyer_offset + buyer_to_fetch])

            if buyers:
                results.extend(buyers)
                next_cursor["buyer_count"] += len(buyers)

                # Update page number if we got a full page
                if len(buyers) == buyer_to_fetch:
                    next_cursor["buyer_page"] += 1
                    has_more = True

        # Fetch influencers if quota not met
        influencer_to_fetch = min(min_influencers - cursor["influencer_count"], limit - len(results))
        if influencer_to_fetch > 0:
            influencer_queryset = base_queryset.filter(persona_match='influencer').order_by('-score')
            influencer_offset = cursor["influencer_page"] * influencer_to_fetch
            influencers = list(influencer_queryset[influencer_offset:influencer_offset + influencer_to_fetch])

            if influencers:
                results.extend(influencers)
                next_cursor["influencer_count"] += len(influencers)

                # Update page number if we got a full page
                if len(influencers) == influencer_to_fetch:
                    next_cursor["influencer_page"] += 1
                    has_more = True

        # Fetch end_users if quota not met
        end_user_to_fetch = min(max_end_users - cursor["end_user_count"], limit - len(results))
        if end_user_to_fetch > 0:
            end_user_queryset = base_queryset.filter(persona_match='end_user').order_by('-score')
            end_user_offset = cursor["end_user_page"] * end_user_to_fetch
            end_users = list(end_user_queryset[end_user_offset:end_user_offset + end_user_to_fetch])

            if end_users:
                results.extend(end_users)
                next_cursor["end_user_count"] += len(end_users)

                # Update page number if we got a full page
                if len(end_users) == end_user_to_fetch:
                    next_cursor["end_user_page"] += 1
                    has_more = True

        # Calculate how many more leads we need to return
        remaining_slots = min(limit - len(results), limit)

        # Fetch remaining leads if needed (highest score regardless of persona)
        if remaining_slots > 0:
            # We need to exclude leads already returned in this page and all previous pages
            # For each persona category, construct a queryset of all leads already fetched
            buyer_queryset = base_queryset.filter(persona_match='buyer').order_by('-score')
            buyer_total_fetched = cursor["buyer_page"] * min_buyers + (0 if cursor["buyer_page"] == next_cursor["buyer_page"] else buyer_to_fetch)
            already_fetched_buyers = set(lead.id for lead in buyer_queryset[:buyer_total_fetched])

            influencer_queryset = base_queryset.filter(persona_match='influencer').order_by('-score')
            influencer_total_fetched = cursor["influencer_page"] * min_influencers + (0 if cursor["influencer_page"] == next_cursor["influencer_page"] else influencer_to_fetch)
            already_fetched_influencers = set(lead.id for lead in influencer_queryset[:influencer_total_fetched])

            end_user_queryset = base_queryset.filter(persona_match='end_user').order_by('-score')
            end_user_total_fetched = cursor["end_user_page"] * max_end_users + (0 if cursor["end_user_page"] == next_cursor["end_user_page"] else end_user_to_fetch)
            already_fetched_end_users = set(lead.id for lead in end_user_queryset[:end_user_total_fetched])

            # Exclude already fetched IDs
            excluded_ids = already_fetched_buyers.union(already_fetched_influencers).union(already_fetched_end_users)

            # Also exclude leads already fetched in the current page
            current_page_ids = {lead.id for lead in results}
            excluded_ids = excluded_ids.union(current_page_ids)

            # Get remaining leads - handle empty excluded_ids case
            remaining_queryset = base_queryset.order_by('-score')
            if excluded_ids:
                remaining_queryset = remaining_queryset.exclude(id__in=excluded_ids)

            # Use safe offset access
            remaining_page = cursor.get("remaining_page", 0)
            remaining_offset = remaining_page * remaining_slots

            # Log pagination details for debugging
            logger.debug(f"Remaining leads pagination: offset={remaining_offset}, slots={remaining_slots}")

            # Fetch the leads
            remaining_leads = list(remaining_queryset[remaining_offset:remaining_offset + remaining_slots])

            if remaining_leads:
                results.extend(remaining_leads)

                # Check if we got a full page of remaining leads
                if len(remaining_leads) == remaining_slots:
                    next_cursor["remaining_page"] = remaining_page + 1
                    has_more = True

        # Update total count
        next_cursor["total_count"] = cursor["total_count"] + len(results)

        # Sort results by score - handle potential attribute errors safely
        def safe_sort_key(lead):
            try:
                return lead.score if hasattr(lead, 'score') and lead.score is not None else 0
            except Exception as e:
                logger.debug(f"Error getting score for lead: {str(e)}")
                return 0

        results.sort(key=safe_sort_key, reverse=True)

        # Encode the next cursor
        next_cursor_str = base64.b64encode(json.dumps(next_cursor).encode('utf-8')).decode('utf-8')

        # Add debug information about persona distribution
        persona_distribution = {}
        for lead in results:
            persona = getattr(lead, 'persona_match', 'unknown')
            persona_distribution[persona] = persona_distribution.get(persona, 0) + 1

        # Create counts dictionary for response
        counts = {
            "buyer_count": next_cursor["buyer_count"],
            "influencer_count": next_cursor["influencer_count"],
            "end_user_count": next_cursor["end_user_count"],
            "total_count": next_cursor["total_count"],
            "personas_in_current_page": persona_distribution
        }

        # Get previous cursor for previous URL
        previous_cursor_str = None
        if cursor["total_count"] > 0:  # If we've seen any results before this page
            prev_cursor = cursor.copy()
            previous_cursor_str = base64.b64encode(json.dumps(prev_cursor).encode('utf-8')).decode('utf-8')

        # Use the helper method to format the response
        return self._format_pagination_response(
            results=results,
            serializer=self.get_serializer,
            request=request,
            next_cursor_str=next_cursor_str if has_more else None,
            previous_cursor_str=previous_cursor_str,
            counts=counts,
            has_more=has_more
        )

    @action(detail=False, methods=['get'])
    def quota_distribution(self, request):
        """
        Returns leads with a specified distribution across persona types using cursor-based pagination.

        Parameters:
        - buyer_percent: Percentage of results to be buyers (default: 40)
        - influencer_percent: Percentage of results to be influencers (default: 40)
        - end_user_percent: Percentage of results to be end users (default: 20)
        - limit: Number of leads to return per page (default: 15)
        - cursor: Pagination cursor (optional)
        """
        # Parse parameters
        account_id = request.query_params.get('account')
        buyer_percent = float(request.query_params.get('buyer_percent', '40'))
        influencer_percent = float(request.query_params.get('influencer_percent', '40'))
        end_user_percent = float(request.query_params.get('end_user_percent', '20'))
        limit = int(request.query_params.get('limit', '15'))

        # Validate percentages sum to 100
        total_percent = buyer_percent + influencer_percent + end_user_percent
        if not (99.0 <= total_percent <= 101.0):  # Allow small rounding errors
            return Response(
                {"error": "Percentages must sum to approximately 100"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Parse cursor if provided
        cursor_str = request.query_params.get('cursor')
        cursor = None
        if cursor_str:
            try:
                cursor = json.loads(base64.b64decode(cursor_str).decode('utf-8'))
            except Exception as e:
                logger.warning(f"Failed to parse cursor: {str(e)}")
                # We'll continue with the default cursor rather than failing the request

        # Initialize cursor state if not provided
        if not cursor:
            cursor = {
                "buyer_page": 0,
                "influencer_page": 0,
                "end_user_page": 0,
                "buyer_count": 0,
                "influencer_count": 0,
                "end_user_count": 0,
                "total_count": 0,
            }

        # Calculate target counts for this page
        buyer_target = int(round(limit * buyer_percent / 100.0))
        influencer_target = int(round(limit * influencer_percent / 100.0))
        end_user_target = limit - buyer_target - influencer_target

        # Prepare base queryset
        base_queryset = super().get_queryset().select_related('account')
        if account_id:
            base_queryset = base_queryset.filter(account_id=account_id)

        # Add suggestion_status filter if provided
        suggestion_status = request.query_params.get('suggestion_status')
        if suggestion_status:
            base_queryset = base_queryset.filter(suggestion_status=suggestion_status)

        # Annotate with persona_match
        base_queryset = self._annotate_persona_match(base_queryset)

        # Apply pagination and fetch leads for each persona
        results = []
        next_cursor = cursor.copy()
        has_more = False

        # Fetch buyers
        if buyer_target > 0:
            buyer_queryset = base_queryset.filter(persona_match='buyer').order_by('-score')
            buyer_offset = cursor["buyer_page"] * buyer_target
            buyers = list(buyer_queryset[buyer_offset:buyer_offset + buyer_target])

            if buyers:
                results.extend(buyers)
                next_cursor["buyer_count"] += len(buyers)

                # Update page if we got a full page
                if len(buyers) == buyer_target:
                    next_cursor["buyer_page"] += 1
                    has_more = True

        # Fetch influencers
        if influencer_target > 0:
            influencer_queryset = base_queryset.filter(persona_match='influencer').order_by('-score')
            influencer_offset = cursor["influencer_page"] * influencer_target
            influencers = list(influencer_queryset[influencer_offset:influencer_offset + influencer_target])

            if influencers:
                results.extend(influencers)
                next_cursor["influencer_count"] += len(influencers)

                # Update page if we got a full page
                if len(influencers) == influencer_target:
                    next_cursor["influencer_page"] += 1
                    has_more = True

        # Fetch end users
        if end_user_target > 0:
            end_user_queryset = base_queryset.filter(persona_match='end_user').order_by('-score')
            end_user_offset = cursor["end_user_page"] * end_user_target
            end_users = list(end_user_queryset[end_user_offset:end_user_offset + end_user_target])

            if end_users:
                results.extend(end_users)
                next_cursor["end_user_count"] += len(end_users)

                # Update page if we got a full page
                if len(end_users) == end_user_target:
                    next_cursor["end_user_page"] += 1
                    has_more = True

        # Update total count
        next_cursor["total_count"] = cursor["total_count"] + len(results)

        # Sort results by score
        results.sort(key=lambda x: x.score if x.score is not None else 0, reverse=True)

        # Encode the next cursor
        next_cursor_str = base64.b64encode(json.dumps(next_cursor).encode('utf-8')).decode('utf-8')

        # Add debug information about persona distribution
        persona_distribution = {}
        for lead in results:
            persona = getattr(lead, 'persona_match', 'unknown')
            persona_distribution[persona] = persona_distribution.get(persona, 0) + 1

        # Create counts dictionary for response
        counts = {
            "buyer_count": next_cursor["buyer_count"],
            "influencer_count": next_cursor["influencer_count"],
            "end_user_count": next_cursor["end_user_count"],
            "total_count": next_cursor["total_count"],
            "distribution": {
                "buyer_percent": buyer_percent,
                "influencer_percent": influencer_percent,
                "end_user_percent": end_user_percent
            },
            "personas_in_current_page": persona_distribution
        }

        # Get previous cursor for previous URL
        previous_cursor_str = None
        if cursor["total_count"] > 0:  # If we've seen any results before this page
            prev_cursor = cursor.copy()
            previous_cursor_str = base64.b64encode(json.dumps(prev_cursor).encode('utf-8')).decode('utf-8')

        # Use the helper method to format the response
        return self._format_pagination_response(
            results=results,
            serializer=self.get_serializer,
            request=request,
            next_cursor_str=next_cursor_str if has_more else None,
            previous_cursor_str=previous_cursor_str,
            counts=counts,
            has_more=has_more
        )

    def _annotate_persona_match(self, queryset):
        """
        Helper method to annotate the queryset with persona_match from JSON field.
        Includes a COALESCE to handle NULL values.

        Args:
            queryset: The base queryset to annotate

        Returns:
            QuerySet: The annotated queryset with persona_match field
        """
        return queryset.annotate(
            persona_match=models.functions.Coalesce(
                Cast(
                    RawSQL(
                        "enrichment_data->'evaluation'->>'persona_match'",
                        []
                    ),
                    models.CharField()
                ),
                Value('unknown')  # Default value when persona_match is NULL
            )
        )
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