from django.db import models
from django.db.models import JSONField

from .common import BaseMixin


class Settings(BaseMixin):
    """
    User/tenant modifiable settings for storing preferences, UI state, etc.
    Inherits tenant from BaseMixin since settings always need a tenant.
    """
    key = models.CharField(max_length=255)
    value = JSONField()
    user = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='settings'
    )
    tenant = models.ForeignKey(
        'Tenant',
        on_delete=models.CASCADE,
        related_name='tenant_settings'
    )

    class Meta:
        db_table = 'settings'
        indexes = [
            models.Index(fields=['tenant']),
            models.Index(fields=['key']),
            models.Index(fields=['tenant', 'user']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'user', 'key'],
                name='unique_setting_per_scope'
            )
        ]

    def __str__(self):
        scope_str = f"{self.tenant.name}"
        if self.user:
            scope_str += f" - {self.user.email}"
        return f"{scope_str}: {self.key}"