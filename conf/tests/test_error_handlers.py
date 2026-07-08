"""
File: test_error_handlers.py
Description: Unit tests for the project's custom error handlers
(conf.views.custom_page_not_found / custom_server_error). settings_test runs
with DEBUG=False, so the handler404 wired in conf/urls.py is actually used.
"""

import pytest
from django.test import RequestFactory

from conf.views import custom_server_error

pytestmark = pytest.mark.django_db


def test_unknown_url_uses_custom_404_template(client):
    response = client.get("/this-url-definitely-does-not-exist/")
    assert response.status_code == 404
    assert "404.html" in [t.name for t in response.templates]


def test_custom_server_error_returns_500():
    # Triggering a real 500 through the test client would raise the original
    # exception instead of exercising the handler, so call it directly.
    request = RequestFactory().get("/")
    response = custom_server_error(request)
    assert response.status_code == 500
