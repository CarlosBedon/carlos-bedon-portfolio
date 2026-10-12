from django.contrib import admin
from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _

from project_name.tenants.models import Store
from project_name.tenants.models import StoreDomain
from project_name.tenants.models import StoreMembership


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
