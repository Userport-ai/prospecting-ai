import base64
import json
import logging
from typing import Optional

from django.db import models, transaction
from django.db.models import F, Case, When, FloatField, Value, Q
from django.db.models.expressions import RawSQL
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
    persona_match = filters.CharFilter(method='filter_persona_match')

    # Define known persona types for consistency
    PERSONA_BUYER = 'buyer'
    PERSONA_INFLUENCER = 'influencer'
    PERSONA_END_USER = 'end_user'
    PERSONA_UNKNOWN = 'unknown'

    # List of all known persona types for easy reference
    KNOWN_PERSONA_TYPES = [PERSONA_BUYER, PERSONA_INFLUENCER, PERSONA_END_USER]

    @classmethod
    def apply_persona_match_filter(cls, queryset, value: Optional[str] = None):
        """
        Apply persona_match filtering with support for comma-separated values.
        Handle 'unknown' persona type in accordance with SQL:
        ((custom_fields->'evaluation'->>'persona_match' IS NULL) OR (custom_fields->'evaluation'->>'persona_match' NOT IN ('buyer', 'influencer', 'end_user')))

        Args:
            queryset: The base queryset to filter
            value: String with persona match value(s), can be comma-separated

        Returns:
            QuerySet: Filtered queryset
        """
        if not value:
            return queryset

        # Split by comma and strip whitespace for all values
        personas = [p.strip() for p in value.split(',') if p.strip()]

        if not personas:
            return queryset

        # Handle special case for 'unknown' persona
        if cls.PERSONA_UNKNOWN in personas:
            # Remove 'unknown' from the list since we'll handle it differently
            other_personas = [p for p in personas if p != cls.PERSONA_UNKNOWN]

            # Create a combined filter
            if other_personas:
                # If there are other personas, we need to combine the 'unknown' logic with them
                return queryset.filter(
                    # Either match one of the specified personas
                    Q(enrichment_data__evaluation__persona_match__in=other_personas) |
                    # Or match the criteria for 'unknown' - updated to match the SQL query
                    (Q(enrichment_data__evaluation__persona_match__isnull=True) |
                     ~Q(enrichment_data__evaluation__persona_match__in=cls.KNOWN_PERSONA_TYPES))
                )
            else:
                # If 'unknown' is the only persona in the filter
                return queryset.filter(
                    Q(enrichment_data__evaluation__persona_match__isnull=True) |
                    ~Q(enrichment_data__evaluation__persona_match__in=cls.KNOWN_PERSONA_TYPES)
                )
        else:
            # If 'unknown' is not in the list, just use a simple filter
            return queryset.filter(enrichment_data__evaluation__persona_match__in=personas)

    def filter_persona_match(self, queryset, name, value):
        """
        Filter by persona_match in enrichment_data->evaluation->persona_match
        Supports comma-separated values for OR filtering (e.g. 'buyer,influencer')
        Also supports special handling for 'unknown' persona type.
        """
        return self.apply_persona_match_filter(queryset, value)

    class Meta:
        model = Lead
        fields = ['id', 'account', 'email', 'phone', 'created_by', 'suggestion_status', 'account_created_by', 'persona_match']


class LeadsViewSet(TenantScopedViewSet, LeadGenerationMixin):
    serializer_class = LeadDetailsSerializer
    queryset = Lead.objects.all()
    http_method_names = ['get', 'post', 'patch', 'delete']
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = LeadFilter
    ordering_fields = ['first_name', 'last_name', 'created_at', 'updated_at', 'score']

    # Define known persona types for consistency
    PERSONA_BUYER = 'buyer'
    PERSONA_INFLUENCER = 'influencer'
    PERSONA_END_USER = 'end_user'
    PERSONA_UNKNOWN = 'unknown'

    # List of all known persona types for easy reference
    KNOWN_PERSONA_TYPES = [PERSONA_BUYER, PERSONA_INFLUENCER, PERSONA_END_USER]

    PERSONA_PRIORITY = [PERSONA_BUYER, PERSONA_INFLUENCER, PERSONA_END_USER, PERSONA_UNKNOWN]

    def get_permissions(self):
        return [HasRole(allowed_roles=[UserRole.USER, UserRole.TENANT_ADMIN,
                                       UserRole.INTERNAL_ADMIN, UserRole.INTERNAL_CS])]

    def _annotate_persona_match(self, queryset):
        """
        Helper method to annotate the queryset with persona_match from JSON field.
        Properly handles NULL values by using COALESCE.

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
                Value(self.PERSONA_UNKNOWN)  # Default value when persona_match is NULL
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
                When(persona_match=Value(self.PERSONA_BUYER),
                     then=models.functions.Coalesce('score', Value(0.0)) * Value(multipliers.get(self.PERSONA_BUYER, 1.2))),
                When(persona_match=Value(self.PERSONA_INFLUENCER),
                     then=models.functions.Coalesce('score', Value(0.0)) * Value(multipliers.get(self.PERSONA_INFLUENCER, 1.0))),
                When(persona_match=Value(self.PERSONA_END_USER),
                     then=models.functions.Coalesce('score', Value(0.0)) * Value(multipliers.get(self.PERSONA_END_USER, 0.8))),
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
                self.PERSONA_BUYER: float(self.request.query_params.get('buyer_multiplier', '1.05')),
                self.PERSONA_INFLUENCER: float(self.request.query_params.get('influencer_multiplier', '1.0')),
                self.PERSONA_END_USER: float(self.request.query_params.get('end_user_multiplier', '0.85'))
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
        # Always use total_count from counts if available, following Django REST Framework standards
        total_count = counts.get("total_count") if counts and "total_count" in counts else (
            # If no total_count in counts, default to the length of results for backward compatibility
            len(results)
        )

        response_data = {
            "count": total_count,
            "next_cursor": next_cursor_str,
            "prev_cursor": previous_cursor_str,
            "next": next_url,
            "previous": previous_url,
            "results": serialized_data
        }

        # Include additional counts data if provided
        if counts:
            response_data["meta"] = {"counts": counts}

        return Response(response_data)

    def _normalize_distribution_percentages(self, buyer_percent, influencer_percent, end_user_percent):
        """
        Normalize the distribution percentages to ensure they sum exactly to 100%.

        Args:
            buyer_percent: Percentage for buyers
            influencer_percent: Percentage for influencers
            end_user_percent: Percentage for end users

        Returns:
            tuple: Normalized (buyer_percent, influencer_percent, end_user_percent)
        """
        total = buyer_percent + influencer_percent + end_user_percent

        # If total is already 100, return as is
        if abs(total - 100.0) < 0.001:
            return buyer_percent, influencer_percent, end_user_percent

        # Otherwise normalize to exactly 100%
        factor = 100.0 / total
        return (
            buyer_percent * factor,
            influencer_percent * factor,
            end_user_percent * factor
        )

    def _fetch_leads_by_persona(self, queryset, persona, target_count, offset, existing_ids=None):
        """
        Helper method to fetch leads by persona type with pagination

        Args:
            queryset: Base queryset to filter from
            persona: Persona type to filter for
            target_count: Number of leads to fetch
            offset: Pagination offset
            existing_ids: Set of IDs to exclude from results

        Returns:
            tuple: (leads, new_offset, has_more)
        """
        if target_count <= 0:
            return [], offset, False

        if existing_ids is None:
            existing_ids = set()

        # For unknown personas, use the SQL equivalent of:
        # ((custom_fields->'evaluation'->>'persona_match' IS NULL) OR (custom_fields->'evaluation'->>'persona_match' NOT IN ('buyer', 'influencer', 'end_user')))
        if persona == self.PERSONA_UNKNOWN:
            persona_queryset = queryset.filter(
                Q(persona_match__isnull=True) | ~Q(persona_match__in=self.KNOWN_PERSONA_TYPES)
            )
        else:
            persona_queryset = queryset.filter(persona_match=persona)

        # Order by score
        persona_queryset = persona_queryset.order_by('-score')

        # Exclude existing IDs
        if existing_ids:
            persona_queryset = persona_queryset.exclude(id__in=existing_ids)

        # Fetch one extra to check if there are more
        leads_with_extra = list(persona_queryset[offset:offset + target_count + 1])

        has_more = False
        if len(leads_with_extra) > target_count:
            has_more = True
            # Remove the extra item
            leads = leads_with_extra[:target_count]
        else:
            leads = leads_with_extra

        return leads, offset + len(leads), has_more

    @action(detail=False, methods=['get'])
    def quota_distribution(self, request):
        """
        Returns leads with a specified distribution across persona types using cursor-based pagination.
        If a persona type doesn't have enough leads to meet its quota, remaining slots are filled
        in priority order: buyers first, then influencers, then end users.

        Parameters:
        - buyer_percent: Percentage of results to be buyers (default: 40)
        - influencer_percent: Percentage of results to be influencers (default: 40)
        - end_user_percent: Percentage of results to be end users (default: 20)
        - limit: Number of leads to return per page (default: 15)
        - cursor: Pagination cursor (optional)
        - persona_match: Filter by persona match, comma-separated values supported (e.g. 'buyer,influencer')
        """
        # Parse parameters
        account_id = request.query_params.get('account')
        buyer_percent = float(request.query_params.get('buyer_percent', '40'))
        influencer_percent = float(request.query_params.get('influencer_percent', '40'))
        end_user_percent = float(request.query_params.get('end_user_percent', '20'))
        limit = int(request.query_params.get('limit', '15'))

        # Normalize percentages to exactly 100%
        buyer_percent, influencer_percent, end_user_percent = self._normalize_distribution_percentages(
            buyer_percent, influencer_percent, end_user_percent
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
                "buyer_offset": 0,
                "influencer_offset": 0,
                "end_user_offset": 0,
                "unknown_offset": 0,
                "buyer_count": 0,
                "influencer_count": 0,
                "end_user_count": 0,
                "unknown_count": 0,
                "total_count": 0
            }

        # Calculate target counts for this page
        buyer_target = int(round(limit * buyer_percent / 100.0))
        influencer_target = int(round(limit * influencer_percent / 100.0))
        end_user_target = limit - buyer_target - influencer_target

        # Use a transaction to ensure consistency across queries
        with transaction.atomic():
            # Prepare base queryset
            base_queryset = super().get_queryset().select_related('account')
            if account_id:
                base_queryset = base_queryset.filter(account_id=account_id)

            # Add suggestion_status filter if provided
            suggestion_status = request.query_params.get('suggestion_status')
            if suggestion_status:
                base_queryset = base_queryset.filter(suggestion_status=suggestion_status)

            # Add persona_match filter if provided (for direct filtering)
            persona_match_filter = request.query_params.get('persona_match')
            if persona_match_filter:
                base_queryset = LeadFilter.apply_persona_match_filter(base_queryset, persona_match_filter)

            # Annotate with persona_match
            base_queryset = self._annotate_persona_match(base_queryset)

            # Get total counts for each persona type (for proper pagination info) - cache these for reuse
            persona_counts = {}
            for persona in [self.PERSONA_BUYER, self.PERSONA_INFLUENCER, self.PERSONA_END_USER]:
                persona_counts[f"total_{persona}s_count"] = base_queryset.filter(persona_match=persona).count()

            # Count unknown personas - updated to match the SQL query
            # ((custom_fields->'evaluation'->>'persona_match' IS NULL) OR (custom_fields->'evaluation'->>'persona_match' NOT IN ('buyer', 'influencer', 'end_user')))
            persona_counts["total_unknown_count"] = base_queryset.filter(
                Q(persona_match__isnull=True) | ~Q(persona_match__in=self.KNOWN_PERSONA_TYPES)
            ).count()

            # Total count of all leads
            persona_counts["total_count"] = base_queryset.count()

            # Track results, existing IDs, and pagination state
            results = []
            existing_ids = set()
            next_cursor = cursor.copy()
            has_more = False
            remaining_slots = limit

            # Use our helper method to fetch leads for each persona type based on the target percentages
            # 1. Start with buyers
            buyer_leads, next_buyer_offset, buyer_has_more = self._fetch_leads_by_persona(
                base_queryset,
                self.PERSONA_BUYER,
                buyer_target,
                cursor.get("buyer_offset", 0)
            )

            if buyer_leads:
                results.extend(buyer_leads)
                next_cursor["buyer_count"] += len(buyer_leads)
                next_cursor["buyer_offset"] = next_buyer_offset
                remaining_slots -= len(buyer_leads)
                existing_ids.update({lead.id for lead in buyer_leads})
                if buyer_has_more:
                    has_more = True

            # 2. Get influencers
            influencer_leads, next_influencer_offset, influencer_has_more = self._fetch_leads_by_persona(
                base_queryset,
                self.PERSONA_INFLUENCER,
                influencer_target,
                cursor.get("influencer_offset", 0)
            )

            if influencer_leads:
                results.extend(influencer_leads)
                next_cursor["influencer_count"] += len(influencer_leads)
                next_cursor["influencer_offset"] = next_influencer_offset
                remaining_slots -= len(influencer_leads)
                existing_ids.update({lead.id for lead in influencer_leads})
                if influencer_has_more:
                    has_more = True

            # 3. Get end users
            end_user_leads, next_end_user_offset, end_user_has_more = self._fetch_leads_by_persona(
                base_queryset,
                self.PERSONA_END_USER,
                end_user_target,
                cursor.get("end_user_offset", 0)
            )

            if end_user_leads:
                results.extend(end_user_leads)
                next_cursor["end_user_count"] += len(end_user_leads)
                next_cursor["end_user_offset"] = next_end_user_offset
                remaining_slots -= len(end_user_leads)
                existing_ids.update({lead.id for lead in end_user_leads})
                if end_user_has_more:
                    has_more = True

            # Fill remaining slots by priority
            if remaining_slots > 0:
                # Efficient batch fetching of additional leads in priority order
                # instead of making separate queries for each persona type
                for persona in self.PERSONA_PRIORITY:
                    if remaining_slots <= 0:
                        break

                    if persona == self.PERSONA_BUYER:
                        offset_key = "buyer_offset"
                        count_key = "buyer_count"
                    elif persona == self.PERSONA_INFLUENCER:
                        offset_key = "influencer_offset"
                        count_key = "influencer_count"
                    elif persona == self.PERSONA_END_USER:
                        offset_key = "end_user_offset"
                        count_key = "end_user_count"
                    else:  # PERSONA_UNKNOWN
                        offset_key = "unknown_offset"
                        count_key = "unknown_count"

                    additional_leads, next_offset, additional_has_more = self._fetch_leads_by_persona(
                        base_queryset,
                        persona,
                        remaining_slots,
                        cursor.get(offset_key, 0),
                        existing_ids
                    )

                    if additional_leads:
                        print(f"additional_leads: {len(additional_leads)}")
                        results.extend(additional_leads)
                        print(f"results: {len(additional_leads)}")
                        next_cursor[count_key] += len(additional_leads)
                        next_cursor[offset_key] = next_offset + (next_cursor.get(offset_key, 0) - cursor.get(offset_key, 0))
                        remaining_slots -= len(additional_leads)
                        existing_ids.update({lead.id for lead in additional_leads})

                        if additional_has_more:
                            has_more = True


            # Update running count in cursor for pagination consistency
            next_cursor["total_count"] = cursor["total_count"] + len(results)

            # Sort results by score for consistent ordering - do this in memory since we have a limited set
            results.sort(key=lambda x: x.score if x.score is not None else 0, reverse=True)

            # Encode the next cursor
            next_cursor_str = base64.b64encode(json.dumps(next_cursor).encode('utf-8')).decode('utf-8')

            # Add debug information about persona distribution
            persona_distribution = {}
            for lead in results:
                persona = getattr(lead, 'persona_match', self.PERSONA_UNKNOWN)
                if persona is None or persona == '':
                    persona = self.PERSONA_UNKNOWN
                persona_distribution[persona] = persona_distribution.get(persona, 0) + 1

            # Create counts dictionary for response - include actual total counts from database
            counts = {
                "buyer_count": next_cursor["buyer_count"],
                "influencer_count": next_cursor["influencer_count"],
                "end_user_count": next_cursor["end_user_count"],
                "unknown_count": next_cursor.get("unknown_count", 0),
                "seen_count": next_cursor["total_count"],  # this is how many we've seen so far
                "total_count": persona_counts["total_count"],  # this is the total count across all pages
                "total_buyers_count": persona_counts["total_buyers_count"],
                "total_influencers_count": persona_counts["total_influencers_count"],
                "total_end_users_count": persona_counts["total_end_users_count"],
                "total_unknown_count": persona_counts.get("total_unknown_count", 0),
                "distribution": {
                    "buyer_percent": buyer_percent,
                    "influencer_percent": influencer_percent,
                    "end_user_percent": end_user_percent
                },
                "current_page_info": {
                    "requested_limit": limit,
                    "actual_returned": len(results),
                    "unfilled_slots": remaining_slots,
                    "personas_distribution": persona_distribution
                }
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