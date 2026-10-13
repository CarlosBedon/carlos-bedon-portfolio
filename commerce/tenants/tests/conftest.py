import pytest
from django.apps import apps
from django.db import connection
from django.db import models

from commerce.tenants.models import TenantAwareModel
from commerce.tenants.tests.factories import StoreDomainFactory
from commerce.tenants.tests.factories import StoreFactory


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


@pytest.fixture(scope="session")
def item_model(django_db_setup, django_db_blocker):
    """Concrete ``TenantAwareModel`` used only to prove query isolation."""

    class Item(TenantAwareModel):
        name = models.CharField(max_length=20)

        class Meta:
            app_label = "tenants"
            db_table = "tenants_test_item"

    with django_db_blocker.unblock(), connection.schema_editor() as schema_editor:
        schema_editor.create_model(Item)
    yield Item
    with django_db_blocker.unblock(), connection.schema_editor() as schema_editor:
        schema_editor.delete_model(Item)
    apps.all_models["tenants"].pop("item", None)
    apps.clear_cache()
