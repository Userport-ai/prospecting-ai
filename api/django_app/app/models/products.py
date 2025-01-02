# app/models/products.py
from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.db.models import JSONField
from .common import BaseMixin


class Product(BaseMixin):
    name = models.CharField(max_length=255)
    description = models.TextField()
    icp_description = models.TextField(null=True, blank=True)
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

    class Meta:
        db_table = 'products'
        indexes = [
            models.Index(fields=['tenant']),
            models.Index(fields=['name']),
            models.Index(fields=['created_by']),
        ]
        unique_together = [['tenant', 'name']]

    def __str__(self):
        return f"{self.name} ({self.tenant.name})"
