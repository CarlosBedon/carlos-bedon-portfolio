import sys
import types
from http import HTTPStatus

import pytest
from django.http import HttpResponse
from django.test.utils import override_settings
from django.urls import path
from django.urls import reverse

from commerce.tenants.models import Store
from commerce.tenants.tests.factories import StoreDomainFactory
from commerce.tenants.tests.factories import StoreFactory
from commerce.tenants.utils import get_current_store

pytestmark = pytest.mark.django_db

_PROBE_URLCONF = "commerce_tenant_probe_urls"


def test_registered_domain_resolves_the_store(tenant_client, store_with_domain):
    store, _domain = store_with_domain

    response = tenant_client.get(reverse("home"))

    assert response.status_code == HTTPStatus.OK
    assert response.context["current_store"] == store
    assert get_current_store() is None


def test_unknown_domain_is_a_404(client, settings):
    settings.ALLOWED_HOSTS = ["missing.example.com"]

    response = client.get("/", HTTP_HOST="missing.example.com")

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert get_current_store() is None


def test_inactive_store_is_a_404(client, settings):
    store = StoreFactory(status=Store.Status.INACTIVE)
    domain = StoreDomainFactory(
        store=store,
        domain="paused.example.com",
        is_primary=True,
    )
    settings.ALLOWED_HOSTS = [domain.domain]

    response = client.get("/", HTTP_HOST=domain.domain)

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_store_a_cannot_read_rows_from_store_b(item_model, client, settings):
    store_a = StoreFactory()
    store_b = StoreFactory()
    domain = StoreDomainFactory(store=store_a, is_primary=True)
    item_model.all_objects.create(name="from-a", store=store_a)
    item_model.all_objects.create(name="from-b", store=store_b)
    settings.ALLOWED_HOSTS = [domain.domain]
    seen = {}

    def probe(request):
        seen["store"] = request.store
        seen["names"] = set(item_model.objects.values_list("name", flat=True))
        return HttpResponse("ok")

    module = types.ModuleType(_PROBE_URLCONF)
    module.urlpatterns = [path("probe/", probe)]
    sys.modules[_PROBE_URLCONF] = module
    try:
        with override_settings(ROOT_URLCONF=_PROBE_URLCONF):
            response = client.get("/probe/", HTTP_HOST=domain.domain)
    finally:
        sys.modules.pop(_PROBE_URLCONF, None)

    assert response.status_code == HTTPStatus.OK
    assert seen["store"] == store_a
    assert seen["names"] == {"from-a"}
