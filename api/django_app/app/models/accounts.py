# app/models/accounts.py
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import JSONField
from .common import BaseMixin
from .account_enrichment import EnrichmentStatus


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
    customers = ArrayField(
        models.CharField(max_length=250),
        null=True,
        blank=True
    )
    competitors = ArrayField(
        models.CharField(max_length=250),
        null=True,
        blank=True
    )

    technologies = JSONField(null=True, blank=True)
    full_technology_profile = JSONField(null=True, blank=True)
    funding_details = JSONField(null=True, blank=True)
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

    def get_enrichment_summary(self):
        """Get overall enrichment status summary from prefetched data"""
        statuses = list(self.enrichment_statuses.all())
        if not statuses:
            return {
                'total_enrichments': 0,
                'completed': 0,
                'failed': 0,
                'in_progress': 0,
                'pending': 0,
                'last_update': None,
                'quality_score': None,
                'avg_completion_percent': 0,
            }

        completed = sum(1 for s in statuses if s.status == EnrichmentStatus.COMPLETED)
        percent = sum([s.completion_percent for s in statuses if s.completion_percent is not None]) / len(statuses) if statuses else 0
        failed = sum(1 for s in statuses if s.status == EnrichmentStatus.FAILED)
        in_progress = sum(1 for s in statuses if s.status == EnrichmentStatus.IN_PROGRESS)
        pending = sum(1 for s in statuses if (not s.status) or (s.status == EnrichmentStatus.PENDING))

        last_update = max((s.last_attempted_run for s in statuses if s.last_attempted_run), default=None)

        quality_scores = [s.data_quality_score for s in statuses if s.data_quality_score is not None]
        avg_score = sum(quality_scores) / len(quality_scores) if quality_scores else None

        return {
            'total_enrichments': len(statuses),
            'completed': completed,
            'failed': failed,
            'in_progress': in_progress,
            'pending': pending,
            'last_update': last_update,
            'quality_score': avg_score,
            'avg_completion_percent': percent,
        }

    # In accounts.py
    def _cascade_soft_delete(self):
        # for now implemented this as postgres trigger, so this is not needed.
        pass

    def _cascade_restore(self, deletion_time=None):
        # for now implemented this as postgres trigger, so this is not needed.
        pass

    class Meta:
        db_table = 'accounts'
        indexes = [
            models.Index(fields=['tenant']),
            models.Index(fields=['name']),
            models.Index(fields=['website']),
            models.Index(fields=['created_by']),
        ]

    def __str__(self):
        return f"{self.name} ({self.tenant.name})"
