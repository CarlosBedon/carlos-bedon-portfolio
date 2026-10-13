from factory import Sequence
from factory import SubFactory
from factory.django import DjangoModelFactory

from commerce.tenants.models import Store
from commerce.tenants.models import StoreDomain
from commerce.tenants.models import StoreMembership
from commerce.users.tests.factories import UserFactory


class StoreFactory(DjangoModelFactory):
    name = Sequence(lambda n: f"Store {n}")
    slug = Sequence(lambda n: f"store-{n}")

    class Meta:
        model = Store


class StoreDomainFactory(DjangoModelFactory):
    store = SubFactory(StoreFactory)
    domain = Sequence(lambda n: f"store-{n}.example.com")

    class Meta:
        model = StoreDomain


class StoreMembershipFactory(DjangoModelFactory):
    store = SubFactory(StoreFactory)
    user = SubFactory(UserFactory)

    class Meta:
        model = StoreMembership
