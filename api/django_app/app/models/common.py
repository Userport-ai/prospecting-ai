# app/models/common.py
import uuid
from django.db import models
from django.db.models import QuerySet
from django.utils import timezone


class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).alive()

    def all_with_deleted(self):
        return SoftDeleteQuerySet(self.model, using=self._db)


class SoftDeleteMixin(models.Model):
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def delete(self, hard=False, cascade=True):
        if hard:
            return super().delete()

        self.deleted_at = timezone.now()
        self.save()

        # Handle cascade soft delete
        if cascade:
            self._cascade_soft_delete()

    def _cascade_soft_delete(self):
        """
        Performs a cascade soft delete on related objects.
        This method should be overridden by models that need custom cascade behavior.
        """
        pass

    def restore(self, cascade=True):
        # Only restore if currently deleted
        if self.deleted_at is None:
            return

        # Store the deletion timestamp for restoring cascaded records
        deletion_time = self.deleted_at
        self.deleted_at = None
        self.save()

        # Handle cascade restore
        if cascade:
            self._cascade_restore(deletion_time)

    def _cascade_restore(self, deletion_time=None):
        """
        Performs a cascade restore on related objects.
        This method should be overridden by models that need custom restore behavior.
        """
        pass


class AuditMixin(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='%(class)s_created'
    )

    class Meta:
        abstract = True


class TenantScopeMixin(models.Model):
    tenant = models.ForeignKey('Tenant', on_delete=models.CASCADE, null=True)

    class Meta:
        abstract = True


class BaseMixin(TenantScopeMixin, AuditMixin, SoftDeleteMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class SoftDeleteQuerySet(QuerySet):
    def delete(self, cascade=True):
        deletion_time = timezone.now()

        if cascade:
            # Apply cascade delete to each object individually
            for obj in self:
                obj.delete(hard=False, cascade=True)
            return len(self)
        else:
            # Simple bulk update without cascade
            return self.update(deleted_at=deletion_time)

    def hard_delete(self):
        return super().delete()

    def alive(self):
        return self.filter(deleted_at__isnull=True)

    def dead(self):
        return self.filter(deleted_at__isnull=False)