import pytest
from django.apps import apps
from django.db import connection
from django.db import models

from commerce.tenants.models import TenantAwareModel


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
