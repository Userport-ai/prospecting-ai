from django.db import models

from app.models.common import BaseMixin


class EnrichmentType(models.TextChoices):
    COMPANY_INFO = 'company_info', 'Company Information'
    GENERATE_LEADS = 'generate_leads', 'Potential Leads for a particular Account'
    LEAD_LINKEDIN_RESEARCH = 'lead_linkedin_research', 'Lead Information from LinkedIn and other sources'

class EnrichmentStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    IN_PROGRESS = 'in_progress', 'In Progress'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'

class AccountEnrichmentStatus(BaseMixin):
    account = models.ForeignKey('Account', on_delete=models.CASCADE, related_name='enrichment_statuses')
    enrichment_type = models.CharField(max_length=50, choices=EnrichmentType.choices)
    status = models.CharField(
        max_length=50,
        choices=EnrichmentStatus.choices,
        default=EnrichmentStatus.PENDING
    )
    last_successful_run = models.DateTimeField(null=True)
    last_attempted_run = models.DateTimeField(null=True)
    next_scheduled_run = models.DateTimeField(null=True)
    failure_count = models.IntegerField(default=0)
    data_quality_score = models.FloatField(null=True)
    source = models.CharField(max_length=50)
    error_details = models.JSONField(null=True)
    metadata = models.JSONField(default=dict)

    class Meta:
        unique_together = ('account', 'enrichment_type')
        indexes = [
            models.Index(fields=['account', 'enrichment_type']),
            models.Index(fields=['status']),
            models.Index(fields=['last_attempted_run']),
        ]
