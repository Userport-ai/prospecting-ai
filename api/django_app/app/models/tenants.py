# app/models/tenants.py
import uuid

from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.db.models import JSONField

from .common import AuditMixin, SoftDeleteMixin


class TenantStatus(models.TextChoices):
    ACTIVE = 'active', 'Active'
    INACTIVE = 'inactive', 'Inactive'
    SUSPENDED = 'suspended', 'Suspended'


class Tenant(AuditMixin, SoftDeleteMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    website = models.URLField(max_length=255, unique=True)
    status = models.CharField(
        max_length=20,
        choices=TenantStatus.choices,
        default=TenantStatus.ACTIVE
    )
    settings = JSONField(null=True, blank=True)

    class Meta:
        db_table = 'tenants'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['website']),
            GinIndex(fields=['settings'])
        ]

    def __str__(self):
        return f"{self.name} ({self.website})"

    def save(self, *args, **kwargs):
        # TODO(Sowrabh): Validate JSON schema etc.
        super().save(*args, **kwargs)