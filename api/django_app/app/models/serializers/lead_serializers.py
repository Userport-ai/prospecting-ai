from rest_framework import serializers

from app.models import Lead
from app.utils.serialization_utils import get_custom_column_values


class LeadDetailsSerializer(serializers.ModelSerializer):
    # Add a nested serializer for minimal account details
    account_details = serializers.SerializerMethodField()
    custom_column_values = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = [
            'id',
            'account_details',
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
            'suggestion_status',
            'updated_at',
            'custom_column_values'
        ]
        read_only_fields = [
            'id',
            'account_details',
            'enrichment_status',
            'score',
            'last_enriched_at',
            'created_at',
            'updated_at',
            'custom_column_values'
        ]
        depth = 1

    def get_account_details(self, obj):
        """
        Return minimal account details for nested display
        """
        return {
            'id': obj.account.id,
            'name': obj.account.name,
            'website': obj.account.website,
            'industry': obj.account.industry,
            'recent_events': obj.account.recent_events,
            'custom_column_values': self.get_custom_column_values(obj.account),
        }

    def get_custom_column_values(self, obj):
        """
        Return all custom column values for this lead in an organized format.
        """
        return get_custom_column_values(obj)


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
