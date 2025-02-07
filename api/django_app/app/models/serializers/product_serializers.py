from app.models import Product
from rest_framework import serializers


def validate_persona_role_titles(value):
    if not isinstance(value, dict):
        raise serializers.ValidationError("Persona role titles must be a JSON object")
    return value


class ProductDetailsSerializer(serializers.ModelSerializer):
    persona_role_titles = serializers.JSONField(required=True)

    class Meta:
        model = Product
        fields = [
            'id',
            'name',
            'description',
            'website',
            'icp_description',
            'persona_role_titles',
            'keywords',
            'playbook_description',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
