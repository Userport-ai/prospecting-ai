# Generated by Django 5.1.4 on 2025-03-24 16:12

import django.contrib.postgres.fields
import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0018_account_recent_events'),
    ]

    operations = [
        migrations.AlterField(
            model_name='accountenrichmentstatus',
            name='enrichment_type',
            field=models.CharField(choices=[('custom_column', 'Ask AI'), ('company_info', 'Company Information'), ('generate_leads', 'Potential Leads for a particular Account'), ('lead_linkedin_research', 'Lead Information from LinkedIn and other sources')], max_length=50),
        ),
        migrations.CreateModel(
            name='CustomColumn',
            fields=[
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('entity_type', models.CharField(choices=[('lead', 'Lead'), ('account', 'Account')], max_length=50)),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, null=True)),
                ('question', models.TextField()),
                ('response_type', models.CharField(choices=[('string', 'String'), ('json_object', 'JSON Object'), ('boolean', 'Boolean'), ('number', 'Number'), ('enum', 'Enumeration')], max_length=50)),
                ('response_config', models.JSONField(default=dict)),
                ('ai_config', models.JSONField()),
                ('context_type', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=50), default=list, size=None)),
                ('last_refresh', models.DateTimeField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created', to=settings.AUTH_USER_MODEL)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='custom_columns', to='app.product')),
                ('tenant', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='app.tenant')),
            ],
        ),
        migrations.CreateModel(
            name='AccountCustomColumnValue',
            fields=[
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('value_string', models.TextField(blank=True, null=True)),
                ('value_json', models.JSONField(blank=True, null=True)),
                ('value_boolean', models.BooleanField(blank=True, null=True)),
                ('value_number', models.DecimalField(blank=True, decimal_places=6, max_digits=19, null=True)),
                ('raw_response', models.TextField(blank=True, null=True)),
                ('confidence_score', models.FloatField(blank=True, null=True)),
                ('generation_metadata', models.JSONField(blank=True, null=True)),
                ('error_details', models.JSONField(blank=True, null=True)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('processing', 'Processing'), ('completed', 'Completed'), ('error', 'Error')], default='pending', max_length=50)),
                ('generated_at', models.DateTimeField(auto_now_add=True)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='custom_column_values', to='app.account')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created', to=settings.AUTH_USER_MODEL)),
                ('tenant', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='app.tenant')),
                ('column', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.customcolumn')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='LeadCustomColumnValue',
            fields=[
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('value_string', models.TextField(blank=True, null=True)),
                ('value_json', models.JSONField(blank=True, null=True)),
                ('value_boolean', models.BooleanField(blank=True, null=True)),
                ('value_number', models.DecimalField(blank=True, decimal_places=6, max_digits=19, null=True)),
                ('raw_response', models.TextField(blank=True, null=True)),
                ('confidence_score', models.FloatField(blank=True, null=True)),
                ('generation_metadata', models.JSONField(blank=True, null=True)),
                ('error_details', models.JSONField(blank=True, null=True)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('processing', 'Processing'), ('completed', 'Completed'), ('error', 'Error')], default='pending', max_length=50)),
                ('generated_at', models.DateTimeField(auto_now_add=True)),
                ('column', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.customcolumn')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created', to=settings.AUTH_USER_MODEL)),
                ('lead', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='custom_column_values', to='app.lead')),
                ('tenant', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='app.tenant')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddIndex(
            model_name='customcolumn',
            index=models.Index(fields=['tenant', 'product'], name='app_customc_tenant__da5eb1_idx'),
        ),
        migrations.AddIndex(
            model_name='customcolumn',
            index=models.Index(fields=['entity_type'], name='app_customc_entity__0d7819_idx'),
        ),
        migrations.AddIndex(
            model_name='customcolumn',
            index=models.Index(fields=['is_active'], name='app_customc_is_acti_ee54f6_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='customcolumn',
            unique_together={('tenant', 'product', 'name')},
        ),
        migrations.AddIndex(
            model_name='accountcustomcolumnvalue',
            index=models.Index(fields=['status'], name='app_account_status_4f1cf0_idx'),
        ),
        migrations.AddIndex(
            model_name='accountcustomcolumnvalue',
            index=models.Index(fields=['generated_at'], name='app_account_generat_8a427d_idx'),
        ),
        migrations.AddIndex(
            model_name='accountcustomcolumnvalue',
            index=models.Index(fields=['account'], name='app_account_account_093b01_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='accountcustomcolumnvalue',
            unique_together={('column', 'account')},
        ),
        migrations.AddIndex(
            model_name='leadcustomcolumnvalue',
            index=models.Index(fields=['status'], name='app_leadcus_status_7c674e_idx'),
        ),
        migrations.AddIndex(
            model_name='leadcustomcolumnvalue',
            index=models.Index(fields=['generated_at'], name='app_leadcus_generat_6f7f52_idx'),
        ),
        migrations.AddIndex(
            model_name='leadcustomcolumnvalue',
            index=models.Index(fields=['lead'], name='app_leadcus_lead_id_f1ca9d_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='leadcustomcolumnvalue',
            unique_together={('column', 'lead')},
        ),
    ]
