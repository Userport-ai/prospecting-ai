from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError

from app.models import Product, Account, Lead
from app.models.common import BaseMixin


class CustomColumn(BaseMixin):
    """Custom column model for AI-generated insights."""

    class EntityType(models.TextChoices):
        LEAD = 'lead', 'Lead'
        ACCOUNT = 'account', 'Account'

    class ResponseType(models.TextChoices):
        STRING = 'string', 'String'
        JSON_OBJECT = 'json_object', 'JSON Object'
        BOOLEAN = 'boolean', 'Boolean'
        NUMBER = 'number', 'Number'
        ENUM = 'enum', 'Enumeration'

    # Required fields
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='custom_columns')
    entity_type = models.CharField(max_length=50, choices=EntityType.choices)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    question = models.TextField()
    response_type = models.CharField(max_length=50, choices=ResponseType.choices)

    # Configuration fields
    response_config = models.JSONField(default=dict)
    ai_config = models.JSONField()
    context_type = ArrayField(models.CharField(max_length=50), default=list)

    last_refresh = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [['tenant', 'product', 'name']]
        indexes = [
            models.Index(fields=['tenant', 'product']),
            models.Index(fields=['entity_type']),
            models.Index(fields=['is_active']),
        ]
        db_table = 'custom_columns'  # Custom table name without app_ prefix

    def clean(self):
        super().clean()
        # Validate response_config based on response_type
        if self.response_type == self.ResponseType.STRING:
            required_keys = {'max_length'}
            if not all(key in self.response_config for key in required_keys):
                raise ValidationError({'response_config': f'Missing required keys: {required_keys}'})

        elif self.response_type == self.ResponseType.JSON_OBJECT:
            if 'schema' not in self.response_config:
                raise ValidationError({'response_config': 'Missing required key: schema'})

        elif self.response_type == self.ResponseType.ENUM:
            if 'allowed_values' not in self.response_config or not isinstance(self.response_config.get('allowed_values'), list):
                raise ValidationError({'response_config': 'Missing or invalid allowed_values array'})

        # Validate AI config
        required_ai_keys = {'model'}
        if not all(key in self.ai_config for key in required_ai_keys):
            raise ValidationError({'ai_config': f'Missing required keys: {required_ai_keys}'})


class BaseCustomColumnValue(BaseMixin):
    """Base model for custom column values."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PROCESSING = 'processing', 'Processing'
        COMPLETED = 'completed', 'Completed'
        ERROR = 'error', 'Error'

    column = models.ForeignKey(CustomColumn, on_delete=models.CASCADE)
    value_string = models.TextField(null=True, blank=True)
    value_json = models.JSONField(null=True, blank=True)
    value_boolean = models.BooleanField(null=True, blank=True)
    value_number = models.DecimalField(max_digits=19, decimal_places=6, null=True, blank=True)
    raw_response = models.TextField(null=True, blank=True)
    confidence_score = models.FloatField(null=True, blank=True)
    generation_metadata = models.JSONField(null=True, blank=True)
    error_details = models.JSONField(null=True, blank=True)
    status = models.CharField(max_length=50, choices=Status.choices, default=Status.PENDING)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['generated_at']),
        ]

    def clean(self):
        super().clean()
        # Ensure only one value type is set
        value_fields = ['value_string', 'value_json', 'value_boolean', 'value_number']
        non_null_values = sum(1 for field in value_fields if getattr(self, field) is not None)

        if non_null_values > 1:
            raise ValidationError("Only one value type should be set")

        # Validate value against column's response_type
        if self.status == self.Status.COMPLETED and non_null_values == 0:
            raise ValidationError("Completed status requires a value")


class LeadCustomColumnValue(BaseCustomColumnValue):
    """Custom column values for leads."""
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='custom_column_values')

    class Meta(BaseCustomColumnValue.Meta):
        unique_together = [['column', 'lead']]
        indexes = BaseCustomColumnValue.Meta.indexes + [
            models.Index(fields=['lead']),
        ]
        db_table = 'lead_custom_column_values'  # Custom table name without app_ prefix


class AccountCustomColumnValue(BaseCustomColumnValue):
    """Custom column values for accounts."""
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='custom_column_values')

    class Meta(BaseCustomColumnValue.Meta):
        unique_together = [['column', 'account']]
        indexes = BaseCustomColumnValue.Meta.indexes + [
            models.Index(fields=['account']),
        ]
        db_table = 'account_custom_column_values'  # Custom table name without app_ prefix