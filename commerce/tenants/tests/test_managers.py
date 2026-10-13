import pytest
from django.apps import apps
from django.db import connection
from django.db import models

from commerce.tenants.models import TenantAwareModel
from commerce.tenants.tests.factories import StoreFactory
from commerce.tenants.utils import reset_current_store
from commerce.tenants.utils import set_current_store

pytestmark = pytest.mark.django_db


@pytest.fixture(scope="session")
def item_model(django_db_setup, django_db_blocker):
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
    app_models = apps.all_models["tenants"]
    app_models.pop("item", None)
    apps.clear_cache()


def test_default_manager_is_empty_without_a_request_store(item_model):
    store = StoreFactory()
    item_model.all_objects.create(name="hidden", store=store)

    assert list(item_model.objects.all()) == []
    assert item_model.objects.global_objects().get().name == "hidden"
    assert item_model.all_objects.get().name == "hidden"


def test_default_manager_returns_only_the_request_store(item_model):
    current = StoreFactory()
    other = StoreFactory()
    item_model.all_objects.create(name="mine", store=current)
    item_model.all_objects.create(name="theirs", store=other)
    token = set_current_store(current)
    try:
        assert list(item_model.objects.values_list("name", flat=True)) == ["mine"]
    finally:
        reset_current_store(token)


def test_save_uses_the_request_store_when_none_was_set(item_model):
    store = StoreFactory()
    other = StoreFactory()
    token = set_current_store(store)
    try:
        created = item_model(name="auto")
        created.save()
        explicit = item_model(name="chosen", store=other)
        explicit.save()
    finally:
        reset_current_store(token)

    assert created.store_id == store.pk
    assert explicit.store_id == other.pk


def test_save_and_bulk_create_refuse_a_row_without_a_store(item_model):
    with pytest.raises(ValueError, match="active store"):
        item_model(name="orphan").save()
    with pytest.raises(ValueError, match="active store"):
        item_model.objects.bulk_create([item_model(name="bulk")])


def test_bulk_create_assigns_the_request_store(item_model):
    store = StoreFactory()
    token = set_current_store(store)
    try:
        item_model.objects.bulk_create([item_model(name="bulk")])
    finally:
        reset_current_store(token)

    assert item_model.all_objects.get(name="bulk").store_id == store.pk
