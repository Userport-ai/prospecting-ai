from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError

from app.models import Account, Lead
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
        # Add conditional unique constraint that only applies to non-deleted rows
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'entity_type', 'name'],
                condition=models.Q(deleted_at__isnull=True),
                name='unique_active_custom_column'
            )
        ]
        indexes = [
            models.Index(fields=['tenant']),
            models.Index(fields=['entity_type']),
            models.Index(fields=['is_active']),
        ]
        db_table = 'custom_columns'

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
    rationale = models.TextField(null=True, blank=True) # store AI's reasoning
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
        db_table = 'lead_custom_column_values'


class AccountCustomColumnValue(BaseCustomColumnValue):
    """Custom column values for accounts."""
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='custom_column_values')

    class Meta(BaseCustomColumnValue.Meta):
        unique_together = [['column', 'account']]
        indexes = BaseCustomColumnValue.Meta.indexes + [
            models.Index(fields=['account']),
        ]
        db_table = 'account_custom_column_values'


class CustomColumnDependency(BaseMixin):
    """Model for tracking dependencies between custom columns."""
    
    dependent_column = models.ForeignKey(
        CustomColumn, 
        on_delete=models.CASCADE, 
        related_name='dependencies'
    )
    required_column = models.ForeignKey(
        CustomColumn, 
        on_delete=models.CASCADE, 
        related_name='dependents'
    )
    
    class Meta:
        unique_together = [['dependent_column', 'required_column']]
        db_table = 'custom_column_dependencies'
        
    def clean(self):
        super().clean()
        # Prevent self-dependencies
        if self.dependent_column == self.required_column:
            raise ValidationError("A column cannot depend on itself")
            
        # Ensure entity types match
        if self.dependent_column.entity_type != self.required_column.entity_type:
            raise ValidationError(
                "Dependencies can only be created between columns of the same entity type"
            )
            
        # Check for cycles in the dependency graph
        from app.services.dependency_graph_service import DependencyGraphService
        import logging
        
        logger = logging.getLogger(__name__)
        
        if self.pk is None:  # Only check for new dependencies
            dependent_id = str(self.dependent_column.id)
            required_id = str(self.required_column.id)
            
            logger.debug(f"Checking cycle in model validation: {dependent_id} -> {required_id}")
            
            # Check for direct cycle first
            if self.dependent_column.id == self.required_column.id:
                logger.error(f"Self-reference detected: {dependent_id}")
                raise ValidationError("A column cannot depend on itself")
                
            # Check for existing cycle in reverse direction
            reverse_dependency_exists = CustomColumnDependency.objects.filter(
                dependent_column=self.required_column,
                required_column=self.dependent_column
            ).exists()
            
            if reverse_dependency_exists:
                logger.error(f"Direct cycle detected: {required_id} -> {dependent_id} already exists")
                raise ValidationError("This dependency would create a circular reference")
                
            # Check for indirect cycles
            if DependencyGraphService.would_create_cycle(dependent_id, required_id):
                logger.error(f"Indirect cycle detected between {dependent_id} and {required_id}")
                raise ValidationError("This dependency would create a circular reference")