from http import HTTPStatus

import pytest
from django.contrib import admin
from django.contrib.auth.models import AnonymousUser
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured
from django.test import RequestFactory

from commerce.tenants.access import ROLE_PERMISSIONS
from commerce.tenants.access import StoreAction
from commerce.tenants.access import StoreArea
from commerce.tenants.access import store_admin_allows
from commerce.tenants.admin import StoreScopedAdmin
from commerce.tenants.admin import StoreScopedInlineMixin
from commerce.tenants.admin import store_admin_site
from commerce.tenants.models import Store
from commerce.tenants.models import StoreDomain
from commerce.tenants.models import StoreMembership
from commerce.tenants.tests.factories import StoreFactory
from commerce.tenants.tests.factories import StoreMembershipFactory
from commerce.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

PASSWORD = "merchant-pass-2026"  # noqa: S105


def _request(user, store):
    request = RequestFactory().get("/manage/")
    request.user = user
    request.store = store
    return request


def _member(store, role=StoreMembership.Role.ADMIN, **kwargs):
    return StoreMembershipFactory(store=store, role=role, **kwargs).user


@pytest.fixture
def item_admin(item_model):
    class ItemAdmin(StoreScopedAdmin):
        store_area = StoreArea.CATALOG

    return ItemAdmin(item_model, store_admin_site)


@pytest.fixture
def item_inline(item_model):
    class ItemInline(StoreScopedInlineMixin, admin.TabularInline):
        model = item_model
        store_area = StoreArea.CATALOG

    return ItemInline(item_model, store_admin_site)


def test_role_permissions_match_the_agreed_matrix():
    admin_role = ROLE_PERMISSIONS[StoreMembership.Role.ADMIN]
    collaborator = ROLE_PERMISSIONS[StoreMembership.Role.COLLABORATOR]

    assert StoreAction.DELETE in admin_role[StoreArea.CATALOG]
    assert StoreAction.DELETE not in collaborator[StoreArea.CATALOG]
    assert admin_role[StoreArea.PAYMENTS] == {StoreAction.VIEW}
    assert StoreArea.PAYMENTS not in collaborator
    assert StoreAction.ADD not in admin_role[StoreArea.ORDERS]


def test_store_admin_allows_follows_the_member_role():
    store = StoreFactory()
    collaborator = _member(store, StoreMembership.Role.COLLABORATOR)
    request = _request(collaborator, store)

    assert store_admin_allows(request, StoreArea.CATALOG, StoreAction.CHANGE)
    assert not store_admin_allows(request, StoreArea.CATALOG, StoreAction.DELETE)
    assert not store_admin_allows(request, StoreArea.PAYMENTS, StoreAction.VIEW)


def test_superuser_without_membership_may_only_view():
    store = StoreFactory()
    request = _request(UserFactory(is_superuser=True, is_staff=True), store)

    assert store_admin_allows(request, StoreArea.PAYMENTS, StoreAction.VIEW)
    assert not store_admin_allows(request, StoreArea.CATALOG, StoreAction.CHANGE)


def test_superuser_with_membership_uses_the_member_role():
    store = StoreFactory()
    superuser = UserFactory(is_superuser=True, is_staff=True)
    StoreMembershipFactory(
        store=store,
        user=superuser,
        role=StoreMembership.Role.COLLABORATOR,
    )
    request = _request(superuser, store)

    assert store_admin_allows(request, StoreArea.CATALOG, StoreAction.CHANGE)
    assert not store_admin_allows(request, StoreArea.PAYMENTS, StoreAction.VIEW)


@pytest.mark.parametrize(
    "case",
    ["staff", "inactive_membership", "other_store", "inactive_store", "no_store"],
)
def test_site_denies_users_without_access(case):
    store = StoreFactory()
    other = StoreFactory()
    user = UserFactory(is_staff=True)
    request_store = store
    if case == "inactive_membership":
        StoreMembershipFactory(store=store, user=user, is_active=False)
    elif case == "other_store":
        StoreMembershipFactory(store=other, user=user)
    elif case == "inactive_store":
        StoreMembershipFactory(store=store, user=user)
        store.status = Store.Status.INACTIVE
        store.save()
    elif case == "no_store":
        StoreMembershipFactory(store=store, user=user)
        request_store = None
    request = _request(user, request_store)

    assert store_admin_site.has_permission(request) is False
    assert not store_admin_allows(request, StoreArea.CATALOG, StoreAction.VIEW)


def test_site_admits_members_and_superusers_but_not_anonymous():
    store = StoreFactory()
    member = _member(store, StoreMembership.Role.COLLABORATOR)
    superuser = UserFactory(is_superuser=True, is_staff=True)

    assert store_admin_site.has_permission(_request(member, store)) is True
    assert store_admin_site.has_permission(_request(superuser, store)) is True
    assert store_admin_site.has_permission(_request(AnonymousUser(), store)) is False


def test_anonymous_is_sent_to_the_store_login(tenant_client):
    response = tenant_client.get("/manage/")

    assert response.status_code == HTTPStatus.FOUND
    assert response["Location"].startswith("/manage/login/")


def test_member_without_staff_can_log_in_and_open_the_panel(
    tenant_client,
    store_with_domain,
):
    store, _domain = store_with_domain
    member = UserFactory(password=PASSWORD, is_staff=False)
    StoreMembershipFactory(store=store, user=member)

    response = tenant_client.post(
        "/manage/login/",
        {"username": member.username, "password": PASSWORD, "next": "/manage/"},
    )

    assert response.status_code == HTTPStatus.FOUND
    assert response["Location"] == "/manage/"
    assert tenant_client.get("/manage/").status_code == HTTPStatus.OK


def test_login_rejects_a_user_of_another_store(tenant_client):
    outsider = UserFactory(password=PASSWORD, is_staff=True)
    StoreMembershipFactory(store=StoreFactory(), user=outsider)

    response = tenant_client.post(
        "/manage/login/",
        {"username": outsider.username, "password": PASSWORD},
    )

    assert response.status_code == HTTPStatus.OK
    assert response.context["form"].errors
    assert "_auth_user_id" not in tenant_client.session


def test_view_on_site_shortcut_is_always_404(tenant_client, store_with_domain):
    store, domain = store_with_domain
    tenant_client.force_login(_member(store))
    content_type = ContentType.objects.get_for_model(StoreDomain)

    response = tenant_client.get(f"/manage/r/{content_type.pk}/{domain.pk}/")

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_scoped_admin_requires_a_tenant_model_and_an_area(item_model):
    class DomainAdmin(StoreScopedAdmin):
        store_area = StoreArea.CATALOG

    class AreaLessAdmin(StoreScopedAdmin):
        pass

    with pytest.raises(ImproperlyConfigured):
        DomainAdmin(StoreDomain, store_admin_site)
    with pytest.raises(ImproperlyConfigured):
        AreaLessAdmin(item_model, store_admin_site)


def test_scoped_admin_only_returns_rows_of_the_request_store(item_admin, item_model):
    store = StoreFactory()
    other = StoreFactory()
    own = item_model.all_objects.create(name="own", store=store)
    foreign = item_model.all_objects.create(name="foreign", store=other)
    request = _request(_member(store), store)

    assert list(item_admin.get_queryset(request)) == [own]
    assert item_admin.get_object(request, str(foreign.pk)) is None
    assert item_admin.has_change_permission(request, foreign) is False
    assert item_admin.has_change_permission(request, own) is True


def test_support_mode_is_read_only(item_admin, item_model):
    store = StoreFactory()
    own = item_model.all_objects.create(name="own", store=store)
    request = _request(UserFactory(is_superuser=True, is_staff=True), store)

    assert item_admin.has_view_permission(request, own) is True
    assert item_admin.has_add_permission(request) is False
    assert item_admin.has_change_permission(request, own) is False
    assert item_admin.has_delete_permission(request, own) is False


def test_save_model_forces_the_request_store(item_admin, item_model):
    store = StoreFactory()
    other = StoreFactory()
    request = _request(_member(store), store)
    obj = item_model(name="posted", store=other)

    item_admin.save_model(request, obj, form=None, change=False)

    assert item_model.all_objects.get(pk=obj.pk).store_id == store.pk


def test_store_field_never_reaches_the_form(item_admin):
    store = StoreFactory()
    request = _request(_member(store), store)

    form_class = item_admin.get_form(request)

    assert "store" in item_admin.get_exclude(request)
    assert "store" not in form_class.base_fields


def test_save_formset_sets_store_and_deletes_removed_rows(item_admin, item_model):
    store = StoreFactory()
    other = StoreFactory()
    removed = item_model.all_objects.create(name="removed", store=store)
    new = item_model(name="new", store=other)

    class Formset:
        deleted_objects = (removed,)
        m2m_saved = False

        def save(self, *, commit):
            assert commit is False
            return [new]

        def save_m2m(self):
            self.m2m_saved = True

    formset = Formset()
    item_admin.save_formset(
        _request(_member(store), store),
        form=None,
        formset=formset,
        change=True,
    )

    assert item_model.all_objects.get(pk=new.pk).store_id == store.pk
    assert not item_model.all_objects.filter(pk=removed.pk).exists()
    assert formset.m2m_saved is True


def test_inline_follows_the_parent_store(item_inline, item_model):
    store = StoreFactory()
    other = StoreFactory()
    own = item_model.all_objects.create(name="own", store=store)
    foreign = item_model.all_objects.create(name="foreign", store=other)
    request = _request(_member(store, StoreMembership.Role.COLLABORATOR), store)

    assert list(item_inline.get_queryset(request)) == [own]
    assert item_inline.has_change_permission(request, own) is True
    assert item_inline.has_change_permission(request, foreign) is False
    assert item_inline.has_delete_permission(request, own) is False
