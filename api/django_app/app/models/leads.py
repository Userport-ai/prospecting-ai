from django.db import models
from django.db.models import JSONField
from .common import BaseMixin
from .accounts import EnrichmentStatus


class Lead(BaseMixin):
    class SuggestionStatus(models.TextChoices):
        SUGGESTED = 'suggested', 'AI Suggested'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        MANUAL = 'manual', 'Manually Added'

    class Source(models.TextChoices):
        MANUAL = 'manual', 'Manually Added'
        ENRICHMENT = 'enrichment', 'Generated via Enrichment'
        IMPORT = 'import', 'Imported from File'

    account = models.ForeignKey('Account', on_delete=models.CASCADE)
    first_name = models.CharField(max_length=100, null=True, blank=True)
    last_name = models.CharField(max_length=100, null=True, blank=True)
    role_title = models.CharField(max_length=255, null=True, blank=True)
    linkedin_url = models.URLField(max_length=512, null=True, blank=True)
    email = models.EmailField(max_length=255, null=True, blank=True)
    phone = models.CharField(max_length=50, null=True, blank=True)
    enrichment_status = models.CharField(
        max_length=50,
        choices=EnrichmentStatus.choices,
        default=EnrichmentStatus.PENDING
    )
    custom_fields = JSONField(null=True, blank=True)
    score = models.FloatField(null=True, blank=True)
    last_enriched_at = models.DateTimeField(null=True, blank=True)

    # Source and suggestion tracking
    source = models.CharField(
        max_length=50,
        choices=Source.choices,
        default=Source.MANUAL
    )
    suggestion_status = models.CharField(
        max_length=50,
        choices=SuggestionStatus.choices,
        default=SuggestionStatus.MANUAL
    )
    enrichment_data = JSONField(
        null=True,
        blank=True,
        help_text='Stores enrichment specific data like fit score, persona match etc'
    )

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
            models.Index(fields=['source']),
            models.Index(fields=['suggestion_status']),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.account.name}"