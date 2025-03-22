# app/models/products.py
from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.db.models import JSONField, UniqueConstraint, Q
from .common import BaseMixin


class Product(BaseMixin):
    name = models.CharField(max_length=255)
    description = models.TextField()
    icp_description = models.TextField(null=True, blank=True)
    website=models.URLField(null=True)
    persona_role_titles = JSONField()
    keywords = ArrayField(
        models.CharField(max_length=100),
        null=True,
        blank=True
    )
    settings = JSONField(null=True, blank=True)
    created_by = models.ForeignKey(
        'app.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_products'
    )
    playbook_description = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'products'
        indexes = [
            models.Index(fields=['tenant']),
            models.Index(fields=['name']),
            models.Index(fields=['created_by']),
        ]

        constraints = [
            UniqueConstraint(
                fields=['tenant', 'name'],
                condition=Q(deleted_at__isnull=True),
                name='unique_active_product_name_per_tenant'
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.tenant.name})"
