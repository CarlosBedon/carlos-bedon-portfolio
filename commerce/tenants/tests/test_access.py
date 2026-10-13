import pytest
from django.contrib.auth.models import AnonymousUser

from commerce.tenants.access import get_store_for_member
from commerce.tenants.access import stores_for_member
from commerce.tenants.access import user_can_manage_store
from commerce.tenants.models import Store
from commerce.tenants.models import StoreMembership
from commerce.tenants.tests.factories import StoreFactory
from commerce.tenants.tests.factories import StoreMembershipFactory
from commerce.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


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


def test_anonymous_user_sees_no_stores():
    store = StoreFactory()
    anonymous = AnonymousUser()
    assert set(stores_for_member(anonymous)) == set()
    assert user_can_manage_store(anonymous, store) is False
    with pytest.raises(Store.DoesNotExist):
        get_store_for_member(anonymous, store.pk)
