# app/models/accounts.py
from django.db import models
from django.db.models import JSONField
from .common import BaseMixin


class EnrichmentStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    IN_PROGRESS = 'in_progress', 'In Progress'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'


class Account(BaseMixin):
    product = models.ForeignKey('Product', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    website = models.URLField(max_length=512, null=True, blank=True)
    linkedin_url = models.URLField(max_length=512, null=True, blank=True)
    industry = models.CharField(max_length=255, null=True, blank=True)
    location = models.CharField(max_length=255, null=True, blank=True)
    employee_count = models.IntegerField(null=True, blank=True)
    company_type = models.CharField(max_length=100, null=True, blank=True)
    founded_year = models.IntegerField(null=True, blank=True)

    technologies = JSONField(null=True, blank=True)
    funding_details = JSONField(null=True, blank=True)
    enrichment_status = models.CharField(
        max_length=50,
        choices=EnrichmentStatus.choices,
        default=EnrichmentStatus.PENDING
    )
    enrichment_sources = JSONField(null=True, blank=True)
    last_enriched_at = models.DateTimeField(null=True, blank=True)
    custom_fields = JSONField(null=True, blank=True)
    settings = JSONField(null=True, blank=True)

    created_by = models.ForeignKey(
        'app.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_accounts'
    )

    class Meta:
        db_table = 'accounts'
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['website']),
        ]

    def __str__(self):
        return f"{self.name} ({self.tenant.name})"