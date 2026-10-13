"""Pure helpers and the store bound to the current request.

Authorization does not belong here. Who can see or manage a store lives
in ``commerce.tenants.access``.
"""

from contextvars import ContextVar
from contextvars import Token
from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError

if TYPE_CHECKING:
    from commerce.tenants.models import Store

DOMAIN_MAX_LENGTH = 253

_INVALID_DOMAIN_MESSAGE = "Enter a valid domain name."
_current_store: ContextVar[Store | None] = ContextVar("current_store", default=None)


def normalize_domain(value: str) -> str:
    """Return a host, or raise ValidationError.

    Strips outer spaces, lowercases, and removes one trailing dot.
    Rejects a full URL, a path, or a port. Internationalized names stay
    as Unicode; punycode is intentionally not applied.
    """
    if not isinstance(value, str):
        raise ValidationError(_INVALID_DOMAIN_MESSAGE, code="invalid")
    candidate = value.strip().lower()
    if candidate.endswith("."):
        candidate = candidate[:-1]
    if not candidate or _is_not_a_bare_host(candidate):
        raise ValidationError(_INVALID_DOMAIN_MESSAGE, code="invalid")
    return candidate


def get_current_store() -> Store | None:
    """Return the store resolved for this request, if the middleware set one."""
    return _current_store.get()


def set_current_store(store: Store) -> Token[Store | None]:
    """Bind ``store`` to the current request context and return its reset token."""
    return _current_store.set(store)


def reset_current_store(token: Token[Store | None]) -> None:
    """Restore the context that was active before ``set_current_store``."""
    _current_store.reset(token)


def _is_not_a_bare_host(candidate: str) -> bool:
    if "://" in candidate:
        return True
    if "/" in candidate:
        return True
    return ":" in candidate
