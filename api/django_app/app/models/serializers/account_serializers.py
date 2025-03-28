from rest_framework import serializers
from app.models import Account, AccountEnrichmentStatus
from app.utils.serialization_utils import get_custom_column_values


class AccountEnrichmentStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountEnrichmentStatus
        fields = [
            'enrichment_type',
            'status',
            'completion_percent',
        ]


class EnrichmentStatusSerializer(serializers.Serializer):
    total_enrichments = serializers.IntegerField()
    completed = serializers.IntegerField()
    failed = serializers.IntegerField()
    in_progress = serializers.IntegerField()
    pending = serializers.IntegerField()
    last_update = serializers.DateTimeField(allow_null=True)
    quality_score = serializers.FloatField(allow_null=True)
    avg_completion_percent = serializers.FloatField(allow_null=True)
    statuses = AccountEnrichmentStatusSerializer(many=True, allow_null=True)


class AccountDetailsSerializer(serializers.ModelSerializer):
    enrichment_status = EnrichmentStatusSerializer(source='get_enrichment_summary', read_only=True)
    custom_column_values = serializers.SerializerMethodField()

    class Meta:
        model = Account
        fields = [
            'id',
            'product',
            'name',
            'website',
            'linkedin_url',
            'industry',
            'location',
            'employee_count',
            'company_type',
            'founded_year',
            'customers',
            'competitors',
            'technologies',
            'funding_details',
            'enrichment_status',
            'enrichment_sources',
            'last_enriched_at',
            'custom_fields',
            'settings',
            'recent_events',
            'created_at',
            'updated_at',
            'custom_column_values'  
        ]
        read_only_fields = [
            'id',
            'enrichment_sources',
            'last_enriched_at',
            'created_at',
            'updated_at',
            'custom_column_values'  
        ]

    def get_custom_column_values(self, obj):
        """
        Return all custom column values for this account in an organized format.
        """
        return get_custom_column_values(obj)

class AccountBulkCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = [
            'name',
            'website',
            'linkedin_url',
            'industry',
            'location',
            'employee_count',
            'company_type',
            'founded_year',
            'technologies',
            'funding_details',
            'custom_fields'
        ]

    def validate(self, data):
        if not data.get('website'):
            raise serializers.ValidationError(
                "Website must be provided"
            )
        return data
