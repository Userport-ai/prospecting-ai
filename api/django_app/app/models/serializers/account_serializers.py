from rest_framework import serializers
from app.models import Account


class EnrichmentStatusSerializer(serializers.Serializer):
    total_enrichments = serializers.IntegerField()
    completed = serializers.IntegerField()
    failed = serializers.IntegerField()
    in_progress = serializers.IntegerField()
    pending = serializers.IntegerField()
    last_update = serializers.DateTimeField(allow_null=True)
    quality_score = serializers.FloatField(allow_null=True)
    avg_completion_percent = serializers.FloatField(allow_null=True)


class AccountDetailsSerializer(serializers.ModelSerializer):
    enrichment_status = EnrichmentStatusSerializer(source='get_enrichment_summary', read_only=True)

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
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id',
            'enrichment_sources',
            'last_enriched_at',
            'created_at',
            'updated_at'
        ]

    def validate_technologies(self, value):
        if value is not None and not isinstance(value, dict):
            raise serializers.ValidationError("Technologies must be a JSON object")
        return value

    def validate_funding_details(self, value):
        if value is not None and not isinstance(value, dict):
            raise serializers.ValidationError("Funding details must be a JSON object")
        return value

    def validate_custom_fields(self, value):
        if value is not None and not isinstance(value, dict):
            raise serializers.ValidationError("Custom fields must be a JSON object")
        return value


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
