from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('app', '0001_initial'),  # Make sure this matches your previous migration
    ]

    operations = [
        migrations.AlterField(
            model_name='accountenrichmentstatus',
            name='enrichment_type',
            field=models.CharField(
                choices=[
                    ('company_info', 'Company Information'),
                    ('generate_leads', 'Potential Leads for a particular Account'),
                    ('lead_linkedin_research', 'Lead Information from LinkedIn and other sources'),
                    ('technology_info', 'Technology Stack Information')
                ],
                max_length=50
            ),
        ),
    ]