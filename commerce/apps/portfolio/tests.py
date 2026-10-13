import pytest
from django.urls import resolve
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_home_url():
    assert reverse("home") == "/"
    assert resolve("/").view_name == "home"


def test_portfolio_home_url():
    assert reverse("portfolio:home") == "/portfolio/"
    assert resolve("/portfolio/").view_name == "portfolio:home"


def test_home_has_no_supabase_photo(client):
    response = client.get(reverse("home"))
    assert response.status_code == 200
    content = response.content.decode()
    assert "photo_url" not in content
    assert "supabase.co" not in content


def test_portfolio_home_still_works(client):
    response = client.get(reverse("portfolio:home"))
    assert response.status_code == 200
    assert b"Welcome" in response.content
