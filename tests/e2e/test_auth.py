"""
File: test_auth.py
Description: Real-form signup/login/logout flows through the browser.
The rest of the suite uses the cookie-injection `login` fixture; this file
is the one place the actual auth forms are exercised.
"""

from playwright.sync_api import Page, expect


def test_signup_via_form(page: Page, live_server, db):
    page.goto(live_server.url + "/account/signup/")

    page.fill("#id_first_name", "Sign")
    page.fill("#id_last_name", "Upper")
    page.fill("#id_email", "signup-e2e@example.com")
    page.fill("#id_password", "sup3r-secret!")
    page.fill("#id_confirm_password", "sup3r-secret!")
    page.get_by_role("button", name="Sign Up").click()

    expect(page).to_have_url(live_server.url + "/")
    expect(page.get_by_role("link", name="Log Out")).to_be_visible()


def test_login_via_form_respects_next(page: Page, live_server, user):
    page.goto(live_server.url + "/account/login/?next=/ministry/")

    page.fill("#id_email", "e2e@example.com")
    page.fill("#id_password", "password123")
    page.get_by_role("button", name="Log In").click()

    expect(page).to_have_url(live_server.url + "/ministry/")
    expect(page.get_by_role("link", name="Log Out")).to_be_visible()


def test_login_wrong_password_shows_error(page: Page, live_server, user):
    page.goto(live_server.url + "/account/login/")

    page.fill("#id_email", "e2e@example.com")
    page.fill("#id_password", "not-the-password")
    page.get_by_role("button", name="Log In").click()

    expect(page.locator(".alert-error")).to_be_visible()
    assert "/account/login/" in page.url
    expect(page.get_by_role("link", name="Log In")).to_be_visible()


def test_logout_from_navbar(page: Page, live_server, user, login):
    login(user)
    page.goto(live_server.url + "/")
    expect(page.get_by_role("link", name="Log Out")).to_be_visible()

    page.get_by_role("link", name="Log Out").click()

    expect(page.get_by_role("link", name="Log In")).to_be_visible()
