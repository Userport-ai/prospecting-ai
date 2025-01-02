# serializers/settings_serializers.py
from rest_framework import serializers
from app.models import Settings, User


class SettingsSerializer(serializers.ModelSerializer):
    created_by_email = serializers.SerializerMethodField(read_only=True)
    user_email = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Settings
        fields = [
            'id',
            'key',
            'value',
            'user',
            'user_email',
            'created_by',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id',
            'user',
            'user_email',
            'created_by',
            'created_at',
            'updated_at'
        ]

    def get_user_email(self, obj):
        return obj.user.email if obj.user else None

    def validate(self, data):
        """
        Validate the settings data
        """
        # If user is provided, ensure they belong to the same tenant
        user = data.get('user')
        request = self.context.get('request')

        if user and user.tenant != request.tenant:
            raise serializers.ValidationError({
                "user": "User must belong to the same tenant"
            })

        return data