import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db import transaction

from project_name.tenants.models import PRIMARY_DOMAIN_CONSTRAINT
from project_name.tenants.models import UNIQUE_MEMBERSHIP_CONSTRAINT
from project_name.tenants.models import Store
from project_name.tenants.models import StoreDomain
from project_name.tenants.models import StoreMembership
from project_name.tenants.tests.factories import StoreDomainFactory
from project_name.tenants.tests.factories import StoreFactory
from project_name.tenants.tests.factories import StoreMembershipFactory
from project_name.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def test_slug_is_unique():
    StoreFactory(slug="alpha")
    with transaction.atomic(), pytest.raises(IntegrityError):
        StoreFactory(slug="alpha")


def test_domain_is_normalized_on_save():
    store = StoreFactory()
    domain = StoreDomain.objects.create(store=store, domain="  CAFÉ.COM. ")
    assert domain.domain == "café.com"


def test_invalid_domain_is_rejected_on_save():
    store = StoreFactory()
    with pytest.raises(ValidationError):
        StoreDomain.objects.create(store=store, domain="https://tienda.com")
    assert store.domains.count() == 0


def test_normalized_domain_is_globally_unique():
    store = StoreFactory()
    other = StoreFactory()
    StoreDomainFactory(store=store, domain="tienda.com")
    with transaction.atomic(), pytest.raises(IntegrityError):
        StoreDomain.objects.create(store=other, domain="TIENDA.com.")


def test_saving_a_primary_domain_clears_the_previous_one():
    store = StoreFactory()
    first = StoreDomainFactory(
        store=store,
        domain="first.example.com",
        is_primary=True,
    )
    second = StoreDomainFactory(
        store=store,
        domain="second.example.com",
        is_primary=True,
    )
    first.refresh_from_db()
    assert second.is_primary is True
    assert first.is_primary is False


def test_two_primary_domains_cannot_bypass_save():
    store = StoreFactory()
    with transaction.atomic(), pytest.raises(IntegrityError):
        StoreDomain.objects.bulk_create(
            [
                StoreDomain(
                    store=store,
                    domain="first.example.com",
                    is_primary=True,
                ),
                StoreDomain(
                    store=store,
                    domain="second.example.com",
                    is_primary=True,
                ),
            ],
        )


def test_primary_domain_constraint_is_partial():
    constraints = StoreDomain._meta.constraints  # noqa: SLF001
    constraint = next(
        item for item in constraints if item.name == PRIMARY_DOMAIN_CONSTRAINT
    )
    assert constraint.condition is not None


def test_membership_pair_is_unique():
    store = StoreFactory()
    user = UserFactory()
    StoreMembershipFactory(store=store, user=user)
    with transaction.atomic(), pytest.raises(IntegrityError):
        StoreMembershipFactory(store=store, user=user)


def test_membership_constraint_covers_store_and_user():
    constraints = StoreMembership._meta.constraints  # noqa: SLF001
    constraint = next(
        item for item in constraints if item.name == UNIQUE_MEMBERSHIP_CONSTRAINT
    )
    assert constraint.fields == ("store", "user")


def test_same_user_can_belong_to_two_stores():
    user = UserFactory()
    first = StoreMembershipFactory(user=user, role=StoreMembership.Role.ADMIN)
    second = StoreMembershipFactory(user=user, role=StoreMembership.Role.COLLABORATOR)
    assert first.store_id != second.store_id


def test_inactive_status_is_not_a_soft_delete():
    store = StoreFactory(status=Store.Status.INACTIVE)
    assert store.deleted_at is None
    assert store.is_publishable is False


def test_soft_delete_keeps_domains_and_memberships():
    store = StoreFactory()
    domain = StoreDomainFactory(store=store, domain="kept.example.com")
    membership = StoreMembershipFactory(store=store)
    store.soft_delete()
    store.refresh_from_db()
    assert store.deleted_at is not None
    assert store.status == Store.Status.ACTIVE
    assert store.is_publishable is False
    assert Store.objects.filter(pk=store.pk).exists()
    assert StoreDomain.objects.filter(pk=domain.pk).exists()
    assert StoreMembership.objects.filter(pk=membership.pk).exists()


def test_instance_delete_is_logical():
    store = StoreFactory()
    domain = StoreDomainFactory(store=store, domain="instance.example.com")
    store.delete()
    store.refresh_from_db()
    assert store.deleted_at is not None
    assert StoreDomain.objects.filter(pk=domain.pk).exists()


def test_queryset_delete_is_logical():
    store = StoreFactory()
    domain = StoreDomainFactory(store=store, domain="queryset.example.com")
    Store.objects.filter(pk=store.pk).delete()
    store.refresh_from_db()
    assert store.deleted_at is not None
    assert StoreDomain.objects.filter(pk=domain.pk).exists()
