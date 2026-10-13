from django.db import models

from commerce.tenants.utils import get_current_store


def assign_active_store(instance) -> bool:
    """Set ``instance.store`` from the request when it was left empty.

    An explicit store is kept. With no explicit store and no request
    store, saving would write an unscoped row, so this raises instead.
    """
    if instance.store_id is not None:
        return False
    store = get_current_store()
    if store is None:
        message = "A tenant record needs the active store."
        raise ValueError(message)
    instance.store = store
    return True


class TenantQuerySet(models.QuerySet):
    """Queryset that can limit rows to the store of the current request."""

    def for_active_store(self):
        """Filter to the request store, or return no rows when it is absent."""
        store = get_current_store()
        if store is None:
            return self.none()
        return self.filter(store=store)

    def bulk_create(self, objs, **kwargs):
        for obj in objs:
            assign_active_store(obj)
        return super().bulk_create(objs, **kwargs)


class TenantManager(models.Manager):
    """Default manager for a tenant-owned model.

    ``get_queryset()`` is already limited to the request store. Platform
    code that must see every store uses ``global_objects()`` or the
    model's ``all_objects`` manager.
    """

    def get_queryset(self):
        return TenantQuerySet(self.model, using=self._db).for_active_store()

    def global_objects(self):
        """Return every row, including rows from other stores."""
        return super().get_queryset()
