import pytest
from django.contrib import admin
from django.contrib.admin.sites import AdminSite

import project_name.tenants.admin as tenants_admin
from project_name.tenants.admin import StoreAdmin
from project_name.tenants.admin import StoreDeletedFilter
from project_name.tenants.admin import StoreDomainInline
from project_name.tenants.admin import StoreMembershipInline
from project_name.tenants.models import Store
from project_name.tenants.models import StoreDomain
from project_name.tenants.models import StoreMembership
from project_name.tenants.tests.factories import StoreDomainFactory
from project_name.tenants.tests.factories import StoreFactory
from project_name.tenants.tests.factories import StoreMembershipFactory


def test_store_models_are_registered():
    assert admin.site.is_registered(Store)
    assert admin.site.is_registered(StoreDomain)
    assert admin.site.is_registered(StoreMembership)


def test_store_admin_inlines_cover_domains_and_memberships():
    assert [inline.model for inline in StoreAdmin.inlines] == [
        StoreDomain,
        StoreMembership,
    ]
    assert StoreDomainInline in StoreAdmin.inlines
    assert StoreMembershipInline in StoreAdmin.inlines


def test_admin_module_does_not_normalize_domains():
    assert not hasattr(tenants_admin, "normalize_domain")


def test_deleted_filter_offers_yes_and_no():
    deleted_filter = StoreDeletedFilter(
        request=None,
        params={},
        model=Store,
        model_admin=None,
    )
    assert [choice[0] for choice in deleted_filter.lookups(None, None)] == [
        "yes",
        "no",
    ]


def test_delete_confirmation_keeps_related_rows():
    model_admin = StoreAdmin(Store, AdminSite())
    deleted_objects, _model_count, perms_needed, protected = (
        model_admin.get_deleted_objects(
            [Store(name="Alpha", slug="alpha")],
            request=None,
        )
    )
    assert perms_needed == set()
    assert protected == []
    assert deleted_objects


@pytest.mark.django_db
def test_admin_delete_model_soft_deletes_and_keeps_related_rows():
    store = StoreFactory()
    domain = StoreDomainFactory(store=store, domain="admin-one.example.com")
    membership = StoreMembershipFactory(store=store)
    StoreAdmin.delete_model(None, request=None, obj=store)
    store.refresh_from_db()
    assert store.deleted_at is not None
    assert StoreDomain.objects.filter(pk=domain.pk).exists()
    assert StoreMembership.objects.filter(pk=membership.pk).exists()


@pytest.mark.django_db
def test_admin_delete_queryset_soft_deletes_and_keeps_domains():
    store = StoreFactory()
    domain = StoreDomainFactory(store=store, domain="admin-many.example.com")
    StoreAdmin.delete_queryset(
        None,
        request=None,
        queryset=Store.objects.filter(pk=store.pk),
    )
    store.refresh_from_db()
    assert store.deleted_at is not None
    assert StoreDomain.objects.filter(pk=domain.pk).exists()
