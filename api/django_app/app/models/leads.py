from django.db import models
from django.db.models import JSONField
from .common import BaseMixin
from .accounts import EnrichmentStatus


class Lead(BaseMixin):
    account = models.ForeignKey('Account', on_delete=models.CASCADE)
    first_name = models.CharField(max_length=100, null=True, blank=True)
    last_name = models.CharField(max_length=100, null=True, blank=True)
    role_title = models.CharField(max_length=255, null=True, blank=True)
    linkedin_url = models.URLField(max_length=512, null=True, blank=True)
    email = models.EmailField(max_length=255, null=True, blank=True)
    phone = models.CharField(max_length=50, null=True, blank=True)

    created_by = models.ForeignKey(
        'app.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_leads'
    )
    enrichment_status = models.CharField(
        max_length=50,
        choices=EnrichmentStatus.choices,
        default=EnrichmentStatus.PENDING
    )
    custom_fields = JSONField(null=True, blank=True)
    score = models.FloatField(null=True, blank=True)
    last_enriched_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'leads'
        indexes = [
            models.Index(fields=['tenant']),
            models.Index(fields=['email']),
            models.Index(fields=['linkedin_url']),
            models.Index(fields=['role_title']),
            models.Index(fields=['enrichment_status']),
            models.Index(fields=['account']),
            models.Index(fields=['created_by']),
            models.Index(fields=['score']),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.account.name}"