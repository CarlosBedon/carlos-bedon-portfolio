from django.core.exceptions import ValidationError

DOMAIN_MAX_LENGTH = 253

_INVALID_DOMAIN_MESSAGE = "Enter a valid domain name."


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


def _is_not_a_bare_host(candidate: str) -> bool:
    if "://" in candidate:
        return True
    if "/" in candidate:
        return True
    return ":" in candidate
