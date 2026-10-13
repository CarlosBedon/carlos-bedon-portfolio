import pytest
from django.core.exceptions import ValidationError

from project_name.tenants.utils import normalize_domain


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Tienda.COM.", "tienda.com"),
        ("  tienda.com  ", "tienda.com"),
        ("tienda.com.", "tienda.com"),
        ("WWW.Tienda.COM.", "www.tienda.com"),
        ("  CAFÉ.COM. ", "café.com"),
    ],
)
def test_normalize_domain(raw, expected):
    assert normalize_domain(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        ".",
        "https://tienda.com",
        "tienda.com/path",
        "tienda.com:8000",
    ],
)
def test_normalize_domain_rejects_invalid_values(raw):
    with pytest.raises(ValidationError):
        normalize_domain(raw)
