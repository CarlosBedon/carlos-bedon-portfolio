import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory

from commerce.tenants.access import ROLE_PERMISSIONS
from commerce.tenants.access import StoreAction
from commerce.tenants.access import StoreArea
from commerce.tenants.access import active_membership
from commerce.tenants.access import can_enter_merchant
from commerce.tenants.access import get_store_for_member
from commerce.tenants.access import merchant_allows
from commerce.tenants.access import stores_for_member
from commerce.tenants.access import user_can_manage_store
from commerce.tenants.models import Store
from commerce.tenants.models import StoreMembership
from commerce.tenants.tests.factories import StoreFactory
from commerce.tenants.tests.factories import StoreMembershipFactory
from commerce.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def _request(user, store):
    request = RequestFactory().get("/")
    request.user = user
    request.store = store
    return request


def test_active_admin_can_see_and_manage_the_store():
    user = UserFactory()
    store = StoreFactory()
    StoreMembershipFactory(
        store=store,
        user=user,
        role=StoreMembership.Role.ADMIN,
    )
    assert set(stores_for_member(user)) == {store}
    assert get_store_for_member(user, store.pk) == store
    assert user_can_manage_store(user, store) is True


def test_collaborator_can_see_the_store_and_cannot_manage_it():
    user = UserFactory()
    store = StoreFactory()
    StoreMembershipFactory(
        store=store,
        user=user,
        role=StoreMembership.Role.COLLABORATOR,
    )
    assert set(stores_for_member(user)) == {store}
    assert user_can_manage_store(user, store) is False


def test_inactive_membership_hides_the_store():
    user = UserFactory()
    store = StoreFactory()
    StoreMembershipFactory(store=store, user=user, is_active=False)
    assert set(stores_for_member(user)) == set()
    assert user_can_manage_store(user, store) is False
    with pytest.raises(Store.DoesNotExist):
        get_store_for_member(user, store.pk)


def test_inactive_store_stays_visible_and_cannot_be_managed_or_published():
    user = UserFactory()
    store = StoreFactory(status=Store.Status.INACTIVE)
    StoreMembershipFactory(
        store=store,
        user=user,
        role=StoreMembership.Role.ADMIN,
    )
    assert set(stores_for_member(user)) == {store}
    assert user_can_manage_store(user, store) is False
    assert store.is_publishable is False


def test_deleted_store_cannot_be_managed_or_published():
    user = UserFactory()
    store = StoreFactory()
    StoreMembershipFactory(
        store=store,
        user=user,
        role=StoreMembership.Role.ADMIN,
    )
    store.soft_delete()
    loaded = Store.objects.get(pk=store.pk)
    assert loaded.deleted_at is not None
    assert set(stores_for_member(user)) == set()
    assert user_can_manage_store(user, loaded) is False
    assert loaded.is_publishable is False
    with pytest.raises(Store.DoesNotExist):
        get_store_for_member(user, loaded.pk)


def test_member_of_one_store_cannot_open_another_store_by_id():
    user = UserFactory()
    own_store = StoreFactory(slug="own-store")
    other_store = StoreFactory(slug="other-store")
    StoreMembershipFactory(
        store=own_store,
        user=user,
        role=StoreMembership.Role.ADMIN,
    )
    loaded = Store.objects.get(pk=other_store.pk)
    assert set(stores_for_member(user)) == {own_store}
    assert user_can_manage_store(user, loaded) is False
    with pytest.raises(Store.DoesNotExist):
        get_store_for_member(user, other_store.pk)


def test_superuser_without_membership_has_no_member_access():
    user = UserFactory(is_superuser=True, is_staff=True)
    store = StoreFactory()
    assert set(stores_for_member(user)) == set()
    assert user_can_manage_store(user, store) is False
    with pytest.raises(Store.DoesNotExist):
        get_store_for_member(user, store.pk)


def test_staff_without_membership_has_no_member_access():
    user = UserFactory(is_staff=True)
    store = StoreFactory()
    assert user_can_manage_store(user, store) is False
    with pytest.raises(Store.DoesNotExist):
        get_store_for_member(user, store.pk)


def test_superuser_with_admin_membership_can_manage_that_store():
    user = UserFactory(is_superuser=True, is_staff=True)
    store = StoreFactory()
    StoreMembershipFactory(
        store=store,
        user=user,
        role=StoreMembership.Role.ADMIN,
    )
    assert user_can_manage_store(user, store) is True


def test_active_membership_matches_the_role_and_ignores_superuser():
    member = UserFactory()
    store = StoreFactory()
    membership = StoreMembershipFactory(
        store=store,
        user=member,
        role=StoreMembership.Role.COLLABORATOR,
    )
    superuser = UserFactory(is_superuser=True, is_staff=True)

    assert active_membership(member, store) == membership
    assert active_membership(member, store, role=StoreMembership.Role.ADMIN) is None
    assert active_membership(superuser, store) is None


def test_anonymous_user_sees_no_stores():
    store = StoreFactory()
    anonymous = AnonymousUser()
    assert set(stores_for_member(anonymous)) == set()
    assert user_can_manage_store(anonymous, store) is False
    with pytest.raises(Store.DoesNotExist):
        get_store_for_member(anonymous, store.pk)


def test_role_permissions_match_the_agreed_matrix():
    admin_role = ROLE_PERMISSIONS[StoreMembership.Role.ADMIN]
    collaborator = ROLE_PERMISSIONS[StoreMembership.Role.COLLABORATOR]

    assert StoreAction.DELETE in admin_role[StoreArea.CATALOG]
    assert StoreAction.DELETE not in collaborator[StoreArea.CATALOG]
    assert admin_role[StoreArea.PAYMENTS] == {StoreAction.VIEW}
    assert StoreArea.PAYMENTS not in collaborator
    assert StoreAction.ADD not in admin_role[StoreArea.ORDERS]


def test_merchant_allows_follows_the_member_role():
    store = StoreFactory()
    collaborator = StoreMembershipFactory(
        store=store,
        role=StoreMembership.Role.COLLABORATOR,
    ).user
    request = _request(collaborator, store)

    assert merchant_allows(request, StoreArea.CATALOG, StoreAction.CHANGE)
    assert not merchant_allows(request, StoreArea.CATALOG, StoreAction.DELETE)
    assert not merchant_allows(request, StoreArea.PAYMENTS, StoreAction.VIEW)


def test_superuser_without_membership_may_only_view_in_merchant():
    store = StoreFactory()
    request = _request(UserFactory(is_superuser=True, is_staff=True), store)

    assert can_enter_merchant(request.user, store)
    assert merchant_allows(request, StoreArea.PAYMENTS, StoreAction.VIEW)
    assert not merchant_allows(request, StoreArea.CATALOG, StoreAction.CHANGE)


def test_superuser_with_membership_uses_the_member_role_in_merchant():
    store = StoreFactory()
    superuser = UserFactory(is_superuser=True, is_staff=True)
    StoreMembershipFactory(
        store=store,
        user=superuser,
        role=StoreMembership.Role.COLLABORATOR,
    )
    request = _request(superuser, store)

    assert merchant_allows(request, StoreArea.CATALOG, StoreAction.CHANGE)
    assert not merchant_allows(request, StoreArea.PAYMENTS, StoreAction.VIEW)


@pytest.mark.parametrize(
    "case",
    ["staff", "inactive_membership", "other_store", "inactive_store", "no_store"],
)
def test_merchant_denies_users_without_access(case):
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

    assert can_enter_merchant(user, request_store) is False
    assert not merchant_allows(request, StoreArea.CATALOG, StoreAction.VIEW)
