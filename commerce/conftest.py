from typing import TYPE_CHECKING

import pytest

from commerce.tenants.tests.factories import StoreDomainFactory
from commerce.tenants.tests.factories import StoreFactory
from commerce.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from commerce.users.models import User


@pytest.fixture(autouse=True)
def _media_storage(settings, tmpdir) -> None:
    settings.MEDIA_ROOT = tmpdir.strpath


@pytest.fixture
def user(db) -> User:
    return UserFactory.create()


@pytest.fixture
def testserver_store(db):
    """Active store for the host Django's test client sends by default."""
    store = StoreFactory()
    StoreDomainFactory(store=store, domain="testserver", is_primary=True)
    return store


@pytest.fixture(autouse=True)
def _register_testserver_store(request):
    if "client" in request.fixturenames or "admin_client" in request.fixturenames:
        request.getfixturevalue("testserver_store")


@pytest.fixture
def store_with_domain(db):
    """Return an active store and the primary domain that points at it."""
    store = StoreFactory()
    domain = StoreDomainFactory(
        store=store,
        domain=f"{store.slug}.example.com",
        is_primary=True,
    )
    return store, domain


@pytest.fixture
def tenant_client(client, settings, store_with_domain):
    """Client that sends the store's primary host on every request.

    ``ALLOWED_HOSTS`` includes that host so Django reaches
    ``TenantResolutionMiddleware`` instead of rejecting the host first.
    """
    _store, domain = store_with_domain
    settings.ALLOWED_HOSTS = [domain.domain, "testserver"]
    client.defaults["HTTP_HOST"] = domain.domain
    return client
