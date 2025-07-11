# Generated by Django 5.1.4 on 2025-01-10 05:26

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0008_alter_product_website'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='account',
            name='enrichment_status',
        ),
        migrations.CreateModel(
            name='AccountEnrichmentStatus',
            fields=[
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('enrichment_type', models.CharField(choices=[('company_info', 'Company Information'), ('potential_leads', 'Potential Leads for this Account and Product')], max_length=50)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('in_progress', 'In Progress'), ('completed', 'Completed'), ('failed', 'Failed')], default='pending', max_length=50)),
                ('last_successful_run', models.DateTimeField(null=True)),
                ('last_attempted_run', models.DateTimeField(null=True)),
                ('next_scheduled_run', models.DateTimeField(null=True)),
                ('failure_count', models.IntegerField(default=0)),
                ('data_quality_score', models.FloatField(null=True)),
                ('source', models.CharField(max_length=50)),
                ('error_details', models.JSONField(null=True)),
                ('metadata', models.JSONField(default=dict)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enrichment_statuses', to='app.account')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created', to=settings.AUTH_USER_MODEL)),
                ('tenant', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='app.tenant')),
            ],
            options={
                'indexes': [models.Index(fields=['account', 'enrichment_type'], name='app_account_account_615bca_idx'), models.Index(fields=['status'], name='app_account_status_022c3e_idx'), models.Index(fields=['last_attempted_run'], name='app_account_last_at_08892a_idx')],
                'unique_together': {('account', 'enrichment_type')},
            },
        ),
    ]
