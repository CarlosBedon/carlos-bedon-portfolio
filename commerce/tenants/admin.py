from django.contrib import admin
from django.core.exceptions import ImproperlyConfigured
from django.db.models import QuerySet
from django.http import Http404
from django.urls import path
from django.utils.translation import gettext_lazy as _

from commerce.tenants.access import StoreAction
from commerce.tenants.access import StoreArea
from commerce.tenants.access import can_enter_store_admin
from commerce.tenants.access import store_admin_allows
from commerce.tenants.forms import StoreAdminAuthenticationForm
from commerce.tenants.models import Store
from commerce.tenants.models import StoreDomain
from commerce.tenants.models import StoreMembership
from commerce.tenants.models import TenantAwareModel


class StoreAdminSite(admin.AdminSite):
    """Merchant panel for the store resolved from the request host.

    It is mounted at ``/manage/``, outside ``ADMIN_URL``, so the tenant
    middleware sets ``request.store``. Entry needs an active membership in
    that store; a superuser without one may only read (support mode).
    ``is_staff`` plays no part, and the platform admin stays a separate
    site.
    """

    site_header = _("Store administration")
    site_title = _("Store administration")
    index_title = _("Store administration")
    login_form = StoreAdminAuthenticationForm

    def has_permission(self, request):
        return can_enter_store_admin(request.user, getattr(request, "store", None))

    def get_urls(self):
        urls = [
            pattern
            for pattern in super().get_urls()
            if getattr(pattern, "name", None) != "view_on_site"
        ]
        # Django's view looks objects up with the base manager, across
        # stores. The name stays so that a reverse() still resolves.
        disabled = path(
            "r/<path:content_type_id>/<path:object_id>/",
            self.view_on_site_disabled,
            name="view_on_site",
        )
        return [disabled, *urls]

    def view_on_site_disabled(self, request, *args, **kwargs):
        raise Http404


store_admin_site = StoreAdminSite(name="store_admin")


class _StoreScopedOptions:
    """Rules shared by merchant-panel model admins and inlines.

    Rows come from ``all_objects`` filtered by ``request.store``, so the
    result does not depend on the request ``ContextVar``. The ``store``
    field never reaches a form, and foreign keys to tenant models only
    offer rows of the same store.
    """

    store_area: StoreArea | None = None

    def _check_store_scope(self):
        if not issubclass(self.model, TenantAwareModel):
            message = f"{self.model.__name__} must inherit TenantAwareModel."
            raise ImproperlyConfigured(message)
        if self.store_area is None:
            message = f"{type(self).__name__} must set store_area."
            raise ImproperlyConfigured(message)

    def _store_queryset(self, request):
        store = getattr(request, "store", None)
        if store is None:
            return self.model.all_objects.none()
        queryset = self.model.all_objects.filter(store=store)
        ordering = self.get_ordering(request)
        if ordering:
            queryset = queryset.order_by(*ordering)
        return queryset

    def _allows(self, request, action, obj=None):
        store = getattr(request, "store", None)
        if obj is not None and (
            store is None or getattr(obj, "store_id", None) != store.pk
        ):
            return False
        return store_admin_allows(request, self.store_area, action)

    def get_exclude(self, request, obj=None):
        exclude = list(super().get_exclude(request, obj) or ())
        if "store" not in exclude:
            exclude.append("store")
        return exclude

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if "queryset" not in kwargs:
            queryset = _related_store_queryset(db_field, request)
            if queryset is not None:
                kwargs["queryset"] = queryset
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if "queryset" not in kwargs:
            queryset = _related_store_queryset(db_field, request)
            if queryset is not None:
                kwargs["queryset"] = queryset
        return super().formfield_for_manytomany(db_field, request, **kwargs)


def _related_store_queryset(db_field, request):
    related_model = db_field.remote_field.model
    if not issubclass(related_model, TenantAwareModel):
        return None
    store = getattr(request, "store", None)
    if store is None:
        return related_model.all_objects.none()
    return related_model.all_objects.filter(store=store)


class StoreScopedAdmin(_StoreScopedOptions, admin.ModelAdmin):
    """Base ``ModelAdmin`` for a ``TenantAwareModel`` in ``store_admin_site``.

    Subclasses set ``store_area``. Permissions come from
    ``ROLE_PERMISSIONS``, not from Django model permissions. An object of
    another store is never returned, so its change, delete, and history
    URLs answer like a missing object.
    """

    view_on_site = False

    def __init__(self, model, admin_site):
        super().__init__(model, admin_site)
        self._check_store_scope()

    def get_queryset(self, request):
        return self._store_queryset(request)

    def has_module_permission(self, request):
        return self._allows(request, StoreAction.VIEW)

    def has_view_permission(self, request, obj=None):
        return self._allows(request, StoreAction.VIEW, obj)

    def has_add_permission(self, request):
        return self._allows(request, StoreAction.ADD)

    def has_change_permission(self, request, obj=None):
        return self._allows(request, StoreAction.CHANGE, obj)

    def has_delete_permission(self, request, obj=None):
        return self._allows(request, StoreAction.DELETE, obj)

    def save_model(self, request, obj, form, change):
        obj.store = request.store
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for deleted in formset.deleted_objects:
            deleted.delete()
        for instance in instances:
            if isinstance(instance, TenantAwareModel):
                instance.store = request.store
            instance.save()
        formset.save_m2m()


class StoreScopedInlineMixin(_StoreScopedOptions):
    """Store rules for an inline of a ``StoreScopedAdmin``.

    Use it before ``admin.TabularInline`` or ``admin.StackedInline``.
    ``obj`` in the permission methods is the parent object.
    """

    def __init__(self, parent_model, admin_site):
        super().__init__(parent_model, admin_site)
        self._check_store_scope()

    def get_queryset(self, request):
        queryset = self._store_queryset(request)
        if not self.has_view_or_change_permission(request):
            queryset = queryset.none()
        return queryset

    def has_view_permission(self, request, obj=None):
        return self._allows(request, StoreAction.VIEW, obj)

    def has_add_permission(self, request, obj):
        return self._allows(request, StoreAction.ADD, obj)

    def has_change_permission(self, request, obj=None):
        return self._allows(request, StoreAction.CHANGE, obj)

    def has_delete_permission(self, request, obj=None):
        return self._allows(request, StoreAction.DELETE, obj)


class StoreDeletedFilter(admin.SimpleListFilter):
    title = _("deleted")
    parameter_name = "deleted"

    def lookups(self, request, model_admin):
        return (
            ("yes", _("Yes")),
            ("no", _("No")),
        )

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(deleted_at__isnull=False)
        if self.value() == "no":
            return queryset.filter(deleted_at__isnull=True)
        return queryset


class StoreDomainInline(admin.TabularInline):
    model = StoreDomain
    extra = 0
    fields = ("domain", "is_primary")


class StoreMembershipInline(admin.TabularInline):
    model = StoreMembership
    extra = 0
    autocomplete_fields = ("user",)
    fields = ("user", "role", "is_active")


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "status", "deleted_at", "created_at")
    list_filter = (StoreDeletedFilter, "status")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at", "deleted_at")
    inlines = (StoreDomainInline, StoreMembershipInline)

    def delete_model(self, request, obj):
        obj.soft_delete()

    def delete_queryset(self, request, queryset):
        queryset.delete()

    def get_deleted_objects(self, objs, request):
        count = objs.count() if isinstance(objs, QuerySet) else len(objs)
        message = _(
            "The selected stores will be marked as deleted. "
            "Their domains and memberships will be kept.",
        )
        verbose_name_plural = self.model._meta.verbose_name_plural  # noqa: SLF001
        return [message], {verbose_name_plural: count}, set(), []


@admin.register(StoreDomain)
class StoreDomainAdmin(admin.ModelAdmin):
    list_display = ("domain", "store", "is_primary", "created_at")
    list_filter = ("is_primary", "store")
    search_fields = ("domain", "store__name", "store__slug")
    autocomplete_fields = ("store",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(StoreMembership)
class StoreMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "store", "role", "is_active", "created_at")
    list_filter = ("role", "is_active", "store")
    search_fields = ("user__username", "user__name", "store__name", "store__slug")
    autocomplete_fields = ("store", "user")
    readonly_fields = ("created_at", "updated_at")
