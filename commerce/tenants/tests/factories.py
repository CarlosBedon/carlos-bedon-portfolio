from factory import Sequence
from factory import SubFactory
from factory.django import DjangoModelFactory

from commerce.tenants.models import Store
from commerce.tenants.models import StoreDomain
from commerce.tenants.models import StoreMembership
from commerce.users.tests.factories import UserFactory


class StoreFactory(DjangoModelFactory):
    """Active store. Pass ``status`` to build an inactive one."""

    name = Sequence(lambda n: f"Store {n}")
    slug = Sequence(lambda n: f"store-{n}")
    status = Store.Status.ACTIVE

    class Meta:
        model = Store


class StoreDomainFactory(DjangoModelFactory):
    """Unique hostname. ``StoreDomain.save()`` normalizes the value."""

    store = SubFactory(StoreFactory)
    domain = Sequence(lambda n: f"store-{n}.example.com")
    is_primary = False

    class Meta:
        model = StoreDomain


class StoreMembershipFactory(DjangoModelFactory):
    """Active membership. Pass ``role`` as admin or collaborator."""

    store = SubFactory(StoreFactory)
    user = SubFactory(UserFactory)
    role = StoreMembership.Role.COLLABORATOR
    is_active = True

    class Meta:
        model = StoreMembership
