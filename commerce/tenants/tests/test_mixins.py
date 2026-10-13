from http import HTTPStatus

import pytest
from django.contrib.auth.models import AnonymousUser
from django.http import Http404
from django.http import HttpResponse
from django.test import RequestFactory
from django.urls import reverse
from django.views import View

from commerce.tenants.mixins import TenantRequiredMixin
from commerce.tenants.models import Store
from commerce.tenants.models import StoreMembership
from commerce.tenants.tests.factories import StoreFactory
from commerce.tenants.tests.factories import StoreMembershipFactory
from commerce.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


class OpenView(TenantRequiredMixin, View):
    def get(self, request):
        return HttpResponse("ok")


class AdminView(TenantRequiredMixin, View):
    required_role = StoreMembership.Role.ADMIN

    def get(self, request):
        return HttpResponse("ok")


def _get(view, user, store):
    request = RequestFactory().get("/private/")
    request.user = user
    request.store = store
    return view.as_view()(request)


def test_missing_store_is_a_404_even_for_a_superuser():
    user = UserFactory(is_superuser=True, is_staff=True)

    with pytest.raises(Http404):
        _get(OpenView, user, None)


def test_inactive_or_deleted_store_is_a_404_for_an_admin_member():
    user = UserFactory()
    inactive = StoreFactory(status=Store.Status.INACTIVE)
    deleted = StoreFactory()
    StoreMembershipFactory(
        store=inactive,
        user=user,
        role=StoreMembership.Role.ADMIN,
    )
    StoreMembershipFactory(
        store=deleted,
        user=user,
        role=StoreMembership.Role.ADMIN,
    )
    deleted.soft_delete()

    with pytest.raises(Http404):
        _get(OpenView, user, inactive)
    with pytest.raises(Http404):
        _get(AdminView, user, Store.objects.get(pk=deleted.pk))


def test_anonymous_user_is_sent_to_the_login_page():
    store = StoreFactory()

    response = _get(OpenView, AnonymousUser(), store)

    assert response.status_code == HTTPStatus.FOUND
    assert response.url.startswith(reverse("account_login"))


def test_member_without_the_required_role_is_a_404():
    user = UserFactory()
    store = StoreFactory()
    StoreMembershipFactory(
        store=store,
        user=user,
        role=StoreMembership.Role.COLLABORATOR,
    )

    assert _get(OpenView, user, store).status_code == HTTPStatus.OK
    with pytest.raises(Http404):
        _get(AdminView, user, store)


def test_admin_member_can_open_a_role_restricted_view():
    user = UserFactory()
    store = StoreFactory()
    StoreMembershipFactory(
        store=store,
        user=user,
        role=StoreMembership.Role.ADMIN,
    )

    assert _get(AdminView, user, store).status_code == HTTPStatus.OK


def test_inactive_membership_and_another_store_are_a_404():
    user = UserFactory()
    store = StoreFactory()
    other = StoreFactory()
    StoreMembershipFactory(store=store, user=user, is_active=False)
    StoreMembershipFactory(
        store=other,
        user=user,
        role=StoreMembership.Role.ADMIN,
    )

    with pytest.raises(Http404):
        _get(OpenView, user, store)


def test_superuser_without_membership_can_open_the_view():
    user = UserFactory(is_superuser=True, is_staff=True)
    store = StoreFactory()

    assert _get(AdminView, user, store).status_code == HTTPStatus.OK


def test_staff_without_membership_is_a_404():
    user = UserFactory(is_staff=True)
    store = StoreFactory()

    with pytest.raises(Http404):
        _get(OpenView, user, store)
