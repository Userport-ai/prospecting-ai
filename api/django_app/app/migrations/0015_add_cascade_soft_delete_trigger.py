# app/migrations/xxxx_add_cascade_soft_delete_trigger.py
from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('app', '0014_remove_lead_leads_score_7739f8_idx_and_more'),
    ]

    operations = [
        migrations.RunSQL(
            """
            CREATE OR REPLACE FUNCTION cascade_soft_delete_account_leads()
            RETURNS TRIGGER AS $$
            BEGIN
                -- Only execute for relevant updates (when deleted_at changes from NULL to non-NULL)
                IF NEW.deleted_at IS NOT NULL AND (OLD.deleted_at IS NULL OR OLD.deleted_at != NEW.deleted_at) THEN
                    -- Use a more efficient query with indexed columns
                    UPDATE leads
                    SET deleted_at = NEW.deleted_at
                    WHERE account_id = NEW.id 
                      AND deleted_at IS NULL;
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

            CREATE TRIGGER cascade_soft_delete_account_leads_trigger
            AFTER UPDATE ON accounts
            FOR EACH ROW
            EXECUTE FUNCTION cascade_soft_delete_account_leads();
            """,

            # Rollback SQL
            """
            DROP TRIGGER IF EXISTS cascade_soft_delete_account_leads_trigger ON accounts;
            DROP FUNCTION IF EXISTS cascade_soft_delete_account_leads();
            """
        )
    ]