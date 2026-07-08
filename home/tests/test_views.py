"""
File: test_views.py
Description: Unit tests for the home app's static pages.
"""

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_homepage_renders(client):
    url = reverse("homepage")
    assert url == "/"
    response = client.get(url)
    assert response.status_code == 200
    assert "home/homepage.html" in [t.name for t in response.templates]


def test_about_renders(client):
    url = reverse("about")
    assert url == "/about/"
    response = client.get(url)
    assert response.status_code == 200
    assert "home/about.html" in [t.name for t in response.templates]
