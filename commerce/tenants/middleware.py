from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import Http404
from django.http.request import split_domain_port

from commerce.tenants.models import Store
from commerce.tenants.models import StoreDomain
from commerce.tenants.utils import normalize_domain
from commerce.tenants.utils import reset_current_store
from commerce.tenants.utils import set_current_store


class TenantResolutionMiddleware:
    """Resolve ``request.store`` from the request host.

    A host matches a ``StoreDomain`` whose store is ``active`` and not
    soft-deleted. Any other host gets a bare 404. The Django admin is
    exempt so a platform operator can create the first domain.

    The store is also stored in a ``ContextVar`` for the duration of the
    request and removed afterwards, including when the view raises.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if _is_admin_request(request):
            request.store = None
            return self.get_response(request)

        store = _store_for_request(request)
        request.store = store
        token = set_current_store(store)
        try:
            return self.get_response(request)
        finally:
            reset_current_store(token)


def _is_admin_request(request) -> bool:
    prefix = "/" + settings.ADMIN_URL.strip("/")
    path = request.path
    return path == prefix or path.startswith(prefix + "/")


def _store_for_request(request) -> Store:
    domain, _port = split_domain_port(request.get_host())
    if not domain:
        raise Http404
    try:
        normalized = normalize_domain(domain)
    except ValidationError as exc:
        raise Http404 from exc
    try:
        match = StoreDomain.objects.select_related("store").get(
            domain=normalized,
            store__status=Store.Status.ACTIVE,
            store__deleted_at__isnull=True,
        )
    except StoreDomain.DoesNotExist as exc:
        raise Http404 from exc
    return match.store
