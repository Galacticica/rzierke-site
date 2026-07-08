"""
File: test_smoke.py
Description: Page-load smoke tests: every public page renders without JS
console errors, and the custom 404 page is served.
"""

import pytest
from playwright.sync_api import Page, expect

PUBLIC_PAGES = [
    "/",
    "/about/",
    "/ministry/",
    "/ministry/devotions/",
    "/ministry/playlists/",
    "/rzpercussion/",
    "/development-portfolio/",
]


@pytest.mark.parametrize("path", PUBLIC_PAGES)
def test_public_page_loads_without_js_errors(page: Page, live_server, db, path):
    console_errors = []
    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
    page.on("pageerror", lambda exc: console_errors.append(str(exc)))

    response = page.goto(live_server.url + path)

    assert response is not None and response.status == 200, f"{path} returned {response and response.status}"
    # Asset 404s (e.g. a missing favicon) surface as console errors too — any
    # error here means a broken build/manifest or a JS exception.
    assert not console_errors, f"JS console errors on {path}: {console_errors}"


def test_devotions_order_toggle_htmx(page: Page, live_server, db):
    from ministry.models import Devotion

    Devotion.objects.create(title="Older Devotion", content="First", date="2026-01-01")
    Devotion.objects.create(title="Newer Devotion", content="Second", date="2026-06-01")

    page.goto(live_server.url + "/ministry/devotions/")
    body = page.locator("body")
    expect(body).to_contain_text("Newer Devotion")

    newer_pos = page.content().find("Newer Devotion")
    older_pos = page.content().find("Older Devotion")
    assert newer_pos < older_pos, "newest should be listed first by default"

    oldest_toggle = page.get_by_text("Oldest", exact=False).first
    if oldest_toggle.count():
        oldest_toggle.click()
        expect(body).to_contain_text("Older Devotion")


def test_custom_404_page(page: Page, live_server, db):
    response = page.goto(live_server.url + "/definitely-not-a-page/")

    assert response is not None and response.status == 404
    expect(page.locator("body")).to_contain_text("404")
