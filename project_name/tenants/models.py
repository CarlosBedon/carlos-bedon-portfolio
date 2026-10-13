from django.conf import settings
from django.db import models
from django.db import router
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from project_name.tenants.utils import DOMAIN_MAX_LENGTH
from project_name.tenants.utils import normalize_domain

PRIMARY_DOMAIN_CONSTRAINT = "tenants_storedomain_one_primary_per_store"
UNIQUE_MEMBERSHIP_CONSTRAINT = "tenants_storemembership_unique_store_user"


class StoreQuerySet(models.QuerySet):
    """Queryset whose ``delete()`` sets ``deleted_at``.

    The return value follows Django: ``(count, {model_label: count})``,
    or ``(0, {})`` when no row changes. Loaded instances are left as they
    are; callers refresh them. The same guards as ``QuerySet.delete()``
    reject slices, ``distinct(*fields)``, ``values()``, and combined
    queries. Plain ``distinct()`` is allowed. Default model ordering is
    cleared so that query can select primary keys only.

    Calling ``django.db.models.QuerySet.delete()`` on this queryset
    bypasses this method. Django's collector then removes the store with
    SQL, and the store foreign keys cascade to domains and memberships.
    """

    def delete(self):
        self._not_support_combined_queries("delete")
        if self.query.is_sliced:
            message = "Cannot use 'limit' or 'offset' with delete()."
            raise TypeError(message)
        if self.query.distinct_fields:
            message = "Cannot call delete() after .distinct(*fields)."
            raise TypeError(message)
        if self._fields is not None:
            message = "Cannot call delete() after .values() or .values_list()"
            raise TypeError(message)

        now = timezone.now()
        candidates = self.filter(deleted_at__isnull=True)
        # order_by() keeps Meta.ordering. A DISTINCT pk query then fails
        # because those columns are not in the select list.
        candidates.query.clear_ordering(force=True)
        primary_keys = candidates.values("pk")
        count = (
            self.model.objects.using(self.db)
            .filter(pk__in=primary_keys)
            .update(deleted_at=now, updated_at=now)
        )
        self._result_cache = None
        if not count:
            return 0, {}
        label = self.model._meta.label  # noqa: SLF001
        return count, {label: count}


class Store(models.Model):
    """Identity of one tenant store.

    ``status`` says whether the store is operating. ``deleted_at`` is a
    soft delete. ``delete()`` and ``QuerySet.delete()`` only fill that
    timestamp, so domains and memberships stay.

    A physical delete of the store happens only when the row is removed
    with SQL. The foreign keys use ``CASCADE``, so that removal also
    deletes its domains and memberships. Deleting a user removes that
    user's memberships. Deleting one domain or one membership removes
    only that row.
    """

    class Status(models.TextChoices):
        ACTIVE = "active", _("Active")
        INACTIVE = "inactive", _("Inactive")

    name = models.CharField(_("internal name"), max_length=255)
    slug = models.SlugField(_("slug"), max_length=80, unique=True)
    status = models.CharField(
        _("status"),
        max_length=32,
        choices=Status,
        default=Status.ACTIVE,
    )
    deleted_at = models.DateTimeField(
        _("deleted at"),
        null=True,
        blank=True,
        db_index=True,
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    objects = StoreQuerySet.as_manager()

    class Meta:
        verbose_name = _("store")
        verbose_name_plural = _("stores")
        ordering = ("name", "slug")

    def __str__(self) -> str:
        return f"{self.name} ({self.slug})"

    def delete(self, using=None, keep_parents=False):  # noqa: FBT002
        if not self._is_pk_set():
            message = (
                f"{self._meta.object_name} object can't be deleted because its "
                f"{self._meta.pk.attname} attribute is set to None."
            )
            raise ValueError(message)
        using = using or router.db_for_write(self.__class__, instance=self)
        deleted = self.__class__.objects.using(using).filter(pk=self.pk).delete()
        self.refresh_from_db(using=using, fields=["deleted_at", "updated_at"])
        return deleted

    def soft_delete(self, using=None) -> None:
        """Mark the store deleted without removing related rows."""
        self.delete(using=using)

    @property
    def is_publishable(self) -> bool:
        """Return whether the store is active and not soft-deleted.

        This predicate does nothing by itself. A view or API that already
        has a ``Store`` must read it, or call the helpers in
        ``project_name.tenants.access``. The default manager still
        returns soft-deleted stores.
        """
        return self.deleted_at is None and self.status == self.Status.ACTIVE


class StoreDomain(models.Model):
    """Hostname assigned to one store.

    The store foreign key cascades only when the store row is removed
    with SQL. Soft-deleting the store leaves this row in place.
    """

    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="domains",
        verbose_name=_("store"),
    )
    domain = models.CharField(
        _("domain"),
        max_length=DOMAIN_MAX_LENGTH,
        unique=True,
    )
    is_primary = models.BooleanField(_("primary"), default=False)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("store domain")
        verbose_name_plural = _("store domains")
        ordering = ("domain",)
        constraints = [
            models.UniqueConstraint(
                fields=["store"],
                condition=models.Q(is_primary=True),
                name=PRIMARY_DOMAIN_CONSTRAINT,
            ),
        ]

    def __str__(self) -> str:
        return self.domain

    def save(self, *args, **kwargs):
        self.domain = normalize_domain(self.domain)
        using = kwargs.get("using") or router.db_for_write(
            self.__class__,
            instance=self,
        )
        kwargs["using"] = using
        with transaction.atomic(using=using):
            if self.is_primary and self.store_id is not None:
                previous = StoreDomain.objects.using(using).filter(
                    store_id=self.store_id,
                    is_primary=True,
                )
                if self.pk is not None:
                    previous = previous.exclude(pk=self.pk)
                previous.update(is_primary=False)
            super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        self.domain = normalize_domain(self.domain)


class StoreMembership(models.Model):
    """Link between an existing user and one store.

    Soft-deleting the store leaves this row in place. Deleting the user,
    or deleting this row directly, removes it with SQL.
    """

    class Role(models.TextChoices):
        ADMIN = "admin", _("Administrator")
        COLLABORATOR = "collaborator", _("Collaborator")

    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="memberships",
        verbose_name=_("store"),
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="store_memberships",
        verbose_name=_("user"),
    )
    role = models.CharField(
        _("role"),
        max_length=32,
        choices=Role,
        default=Role.COLLABORATOR,
    )
    is_active = models.BooleanField(_("active"), default=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("store membership")
        verbose_name_plural = _("store memberships")
        constraints = [
            models.UniqueConstraint(
                fields=["store", "user"],
                name=UNIQUE_MEMBERSHIP_CONSTRAINT,
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} @ {self.store}"
