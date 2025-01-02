from rest_framework import serializers
from app.models import Lead


class LeadDetailsSerializer(serializers.ModelSerializer):
    # Add a nested serializer for minimal account details
    account_details = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = [
            'id',
            'account',
            'account_details',  # Read-only nested account information
            'first_name',
            'last_name',
            'role_title',
            'linkedin_url',
            'email',
            'phone',
            'enrichment_status',
            'custom_fields',
            'score',
            'last_enriched_at',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id',
            'account_details',
            'enrichment_status',
            'score',
            'last_enriched_at',
            'created_at',
            'updated_at'
        ]
        depth=1

    def get_account_details(self, obj):
        """
        Return minimal account details for nested display
        """
        return {
            'id': obj.account.id,
            'name': obj.account.name,
            'industry': obj.account.industry,
        }

    def validate_custom_fields(self, value):
        if value is not None and not isinstance(value, dict):
            raise serializers.ValidationError("Custom fields must be a JSON object")
        return value

    def validate(self, data):
        """
        Ensure at least one identifier (linkedin_url or email) is provided
        """
        if not data.get('linkedin_url') and not data.get('email'):
            raise serializers.ValidationError(
                "Either linkedin_url or email must be provided"
            )
        return data


# For bulk operations, we might want a simplified serializer
class LeadBulkCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = [
            'first_name',
            'last_name',
            'role_title',
            'linkedin_url',
            'email',
            'phone',
            'custom_fields'
        ]

    def validate(self, data):
        if not data.get('linkedin_url') and not data.get('email'):
            raise serializers.ValidationError(
                "Either linkedin_url or email must be provided"
            )
        return data
