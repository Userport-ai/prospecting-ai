# app/migrations/xxxx_add_cascade_soft_delete_restore_trigger.py
from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('app', '0015_add_cascade_soft_delete_trigger'),
    ]

    operations = [
        migrations.RunSQL(
            """
            CREATE OR REPLACE FUNCTION cascade_account_soft_delete_restore()
            RETURNS TRIGGER AS $$
            BEGIN
                -- Case 1: Account is being soft deleted (deleted_at changed from NULL to non-NULL)
                IF NEW.deleted_at IS NOT NULL AND OLD.deleted_at IS NULL THEN
                    -- Cascade soft delete to leads
                    UPDATE leads
                    SET deleted_at = NEW.deleted_at
                    WHERE account_id = NEW.id AND deleted_at IS NULL;
                
                -- Case 2: Account is being restored (deleted_at changed from non-NULL to NULL)
                ELSIF NEW.deleted_at IS NULL AND OLD.deleted_at IS NOT NULL THEN
                    -- Restore leads that were deleted at the same time as the account
                    UPDATE leads
                    SET deleted_at = NULL
                    WHERE account_id = NEW.id AND deleted_at = OLD.deleted_at;
                END IF;
                
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

            -- Create the trigger
            CREATE TRIGGER cascade_account_soft_delete_restore_trigger
            AFTER UPDATE ON accounts
            FOR EACH ROW
            EXECUTE FUNCTION cascade_account_soft_delete_restore();
            """,

            # Rollback SQL
            """
            DROP TRIGGER IF EXISTS cascade_account_soft_delete_restore_trigger ON accounts;
            DROP FUNCTION IF EXISTS cascade_account_soft_delete_restore();
            """
        )
    ]