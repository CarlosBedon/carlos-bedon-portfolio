from http import HTTPStatus

import pytest
from django.http import Http404
from django.http import HttpResponse
from django.test import RequestFactory

from commerce.tenants.middleware import TenantResolutionMiddleware
from commerce.tenants.models import Store
from commerce.tenants.tests.factories import StoreDomainFactory
from commerce.tenants.tests.factories import StoreFactory
from commerce.tenants.utils import get_current_store

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _allow_test_hosts(settings):
    settings.ALLOWED_HOSTS = ["*"]


def _call(request):
    seen = {}

    def get_response(incoming):
        seen["store"] = get_current_store()
        seen["request_store"] = incoming.store
        return HttpResponse("ok")

    response = TenantResolutionMiddleware(get_response)(request)
    return response, seen


def test_host_with_port_resolves_the_active_store():
    store = StoreFactory()
    StoreDomainFactory(store=store, domain="shop.example.com")
    request = RequestFactory().get("/", HTTP_HOST="Shop.Example.com:8000")

    response, seen = _call(request)

    assert response.status_code == HTTPStatus.OK
    assert seen["request_store"] == store
    assert seen["store"] == store
    assert get_current_store() is None


def test_unknown_host_is_a_bare_404_and_clears_context():
    request = RequestFactory().get("/", HTTP_HOST="missing.example.com")

    with pytest.raises(Http404):
        _call(request)

    assert get_current_store() is None


def test_inactive_store_is_a_404():
    store = StoreFactory(status=Store.Status.INACTIVE)
    StoreDomainFactory(store=store, domain="paused.example.com")
    request = RequestFactory().get("/", HTTP_HOST="paused.example.com")

    with pytest.raises(Http404):
        _call(request)


def test_deleted_store_is_a_404():
    store = StoreFactory()
    StoreDomainFactory(store=store, domain="gone.example.com")
    store.soft_delete()
    request = RequestFactory().get("/", HTTP_HOST="gone.example.com")

    with pytest.raises(Http404):
        _call(request)


def test_admin_is_reachable_without_a_store_domain():
    request = RequestFactory().get("/admin/", HTTP_HOST="localhost")

    response, seen = _call(request)

    assert response.status_code == HTTPStatus.OK
    assert seen["request_store"] is None
    assert seen["store"] is None
