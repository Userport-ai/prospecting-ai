# app/models/config.py
import uuid

from django.db import models
from django.db.models import JSONField
from django.core.exceptions import ValidationError
from .common import AuditMixin, SoftDeleteMixin


class ConfigScope(models.TextChoices):
    GLOBAL = 'global', 'Global'
    TENANT = 'tenant', 'Tenant Specific'
    USER = 'user', 'User Specific'


class Config(AuditMixin, SoftDeleteMixin):
    """
    System-managed configuration that controls feature flags, limits, etc.
    Read-only for clients.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=255)
    value = JSONField()
    scope = models.CharField(
        max_length=20,
        choices=ConfigScope.choices,
        default=ConfigScope.GLOBAL
    )
    description = models.TextField(null=True, blank=True)
    # Make tenant optional since global configs don't need it
    tenant = models.ForeignKey(
        'Tenant',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='configs'
    )
    user = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='configs'
    )

    class Meta:
        db_table = 'configs'
        indexes = [
            models.Index(fields=['key']),
            models.Index(fields=['scope']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['scope', 'tenant', 'user', 'key'],
                name='unique_config_per_scope'
            )
        ]

    def clean(self):
        """
        Validate that tenant and user fields align with the scope
        """
        if self.scope == ConfigScope.GLOBAL and (self.tenant or self.user):
            raise ValidationError('Global configs cannot have tenant or user')

        if self.scope == ConfigScope.TENANT and not self.tenant:
            raise ValidationError('Tenant scope configs must have a tenant')

        if self.scope == ConfigScope.USER and not (self.tenant and self.user):
            raise ValidationError('User scope configs must have both tenant and user')

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        scope_str = f"[{self.scope}]"
        if self.tenant:
            scope_str += f" {self.tenant.name}"
        if self.user:
            scope_str += f" {self.user.email}"
        return f"{scope_str} {self.key}"