from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db import router
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from project_name.tenants.domains import DOMAIN_MAX_LENGTH
from project_name.tenants.domains import normalize_domain

PRIMARY_DOMAIN_CONSTRAINT = "tenants_storedomain_one_primary_per_store"
UNIQUE_MEMBERSHIP_CONSTRAINT = "tenants_storemembership_unique_store_user"


class StoreQuerySet(models.QuerySet):
    """Queryset whose delete marks rows instead of removing them."""

    def delete(self):
        now = timezone.now()
        count = self.filter(deleted_at__isnull=True).update(
            deleted_at=now,
            updated_at=now,
        )
        label = self.model._meta.label  # noqa: SLF001
        return count, {label: count}


class Store(models.Model):
    """Identity of one tenant store.

    ``status`` says whether the store is operating. ``deleted_at`` is a
    separate soft delete: the row, its domains, and its memberships stay
    in the database. Ordinary deletion only fills ``deleted_at``.
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
        if self.deleted_at is not None:
            return 0, {}
        self.soft_delete(using=using)
        label = self._meta.label
        return 1, {label: 1}

    def soft_delete(self, using=None) -> None:
        """Mark the store deleted without removing related rows."""
        if self.deleted_at is not None:
            return
        self.deleted_at = timezone.now()
        self.updated_at = self.deleted_at
        self.save(
            using=using,
            update_fields=["deleted_at", "updated_at"],
        )

    @property
    def is_publishable(self) -> bool:
        """Return whether a public page may show this store.

        Views that already hold a ``Store`` must check this before
        publishing it. The property does not hide rows from other queries.
        """
        return self.deleted_at is None and self.status == self.Status.ACTIVE


class StoreDomain(models.Model):
    """Hostname that resolves to one store."""

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
        with transaction.atomic():
            if self.is_primary and self.store_id is not None:
                previous = StoreDomain.objects.filter(
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

    def validate_constraints(self, exclude=None):
        # Saving a new primary clears the previous one. Validating the
        # partial unique constraint here would reject that replacement.
        # The database constraint still rejects two primaries written
        # without going through save().
        constraints = self.get_constraints()
        using = router.db_for_write(self.__class__, instance=self)
        errors = {}
        for model_class, model_constraints in constraints:
            for constraint in model_constraints:
                if constraint.name == PRIMARY_DOMAIN_CONSTRAINT:
                    continue
                try:
                    constraint.validate(
                        model_class,
                        self,
                        exclude=exclude,
                        using=using,
                    )
                except ValidationError as error:
                    if (
                        getattr(error, "code", None) == "unique"
                        and len(constraint.fields) == 1
                    ):
                        errors.setdefault(constraint.fields[0], []).append(error)
                    else:
                        errors = error.update_error_dict(errors)
        if errors:
            raise ValidationError(errors)


class StoreMembership(models.Model):
    """Link between an existing user and one store."""

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
