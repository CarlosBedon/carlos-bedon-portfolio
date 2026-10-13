from types import SimpleNamespace

from django.template import engines
from django.test import RequestFactory

from commerce.tenants.context_processors import current_store


def test_request_without_a_store_exposes_none():
    request = RequestFactory().get("/admin/")

    assert current_store(request) == {"current_store": None}


def test_templates_receive_the_store_attached_to_the_request():
    request = RequestFactory().get("/")
    request.store = SimpleNamespace(name="Norte")
    template = engines["django"].from_string("{{ current_store.name }}")

    assert template.render({}, request) == "Norte"
