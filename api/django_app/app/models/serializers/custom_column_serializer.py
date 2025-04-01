from rest_framework import serializers
from app.models.custom_column import CustomColumn, LeadCustomColumnValue, AccountCustomColumnValue


class CustomColumnSerializer(serializers.ModelSerializer):
    """Serializer for CustomColumn model."""

    class Meta:
        model = CustomColumn
        fields = [
            'id', 'name', 'description', 'question', 'entity_type',
            'response_type', 'response_config', 'ai_config', 'context_type',
            'last_refresh', 'is_active',
            'created_at', 'updated_at', 'created_by'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']

    def validate_response_config(self, value):
        """Validate response_config based on response_type."""
        response_type = self.initial_data.get('response_type')

        if response_type == CustomColumn.ResponseType.STRING:
            if not isinstance(value.get('max_length', None), int):
                raise serializers.ValidationError("String response requires max_length as integer")

        elif response_type == CustomColumn.ResponseType.JSON_OBJECT:
            if 'schema' not in value:
                raise serializers.ValidationError("JSON object response requires schema")

        elif response_type == CustomColumn.ResponseType.BOOLEAN:
            # Optional but common fields for boolean
            for field in ['true_label', 'false_label']:
                if field in value and not isinstance(value[field], str):
                    raise serializers.ValidationError(f"{field} must be a string")

        elif response_type == CustomColumn.ResponseType.NUMBER:
            # Validate number min/max if provided
            if 'min' in value and 'max' in value:
                if value['min'] >= value['max']:
                    raise serializers.ValidationError("min must be less than max")

        elif response_type == CustomColumn.ResponseType.ENUM:
            if not value.get('allowed_values') or not isinstance(value['allowed_values'], list):
                raise serializers.ValidationError("Enum response requires allowed_values as a list")

            if len(value['allowed_values']) < 2:
                raise serializers.ValidationError("Enum must have at least two allowed values")

        return value

    def validate_ai_config(self, value):
        """Validate AI configuration."""
        if 'model' not in value:
            raise serializers.ValidationError("AI config must include model")

        # Validate temperature if provided
        if 'temperature' in value:
            temp = value['temperature']
            if not isinstance(temp, (int, float)) or temp < 0 or temp > 1:
                raise serializers.ValidationError("Temperature must be a number between 0 and 1")

        return value


class LeadCustomColumnValueSerializer(serializers.ModelSerializer):
    """Serializer for LeadCustomColumnValue model."""

    column_name = serializers.CharField(source='column.name', read_only=True)
    response_type = serializers.CharField(source='column.response_type', read_only=True)

    class Meta:
        model = LeadCustomColumnValue
        fields = [
            'id', 'column', 'column_name', 'lead', 'value_string',
            'value_json', 'value_boolean', 'value_number', 'raw_response',
            'confidence_score', 'generation_metadata', 'error_details',
            'status', 'generated_at', 'response_type'
        ]
        read_only_fields = [
            'id', 'generated_at', 'column_name', 'response_type'
        ]


class AccountCustomColumnValueSerializer(serializers.ModelSerializer):
    """Serializer for AccountCustomColumnValue model."""

    column_name = serializers.CharField(source='column.name', read_only=True)
    response_type = serializers.CharField(source='column.response_type', read_only=True)

    class Meta:
        model = AccountCustomColumnValue
        fields = [
            'id', 'column', 'column_name', 'account', 'value_string',
            'value_json', 'value_boolean', 'value_number', 'raw_response',
            'confidence_score', 'generation_metadata', 'error_details',
            'status', 'generated_at', 'response_type'
        ]
        read_only_fields = [
            'id', 'generated_at', 'column_name', 'response_type'
        ]