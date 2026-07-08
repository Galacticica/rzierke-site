"""
File: test_ministry_verses.py
Description: Verses-by-theme browser: category cards render from the bundled
JSON, and clicking a theme HTMX-loads a (faked) verse card. bible-api.com is
stubbed by the autouse `fake_bible_api` fixture, so every card shows John 3:16.
"""

from playwright.sync_api import Page, expect

FAKED_TEXT = "For God so loved the world that he gave his only Son."


def test_verses_page_shows_categories_and_first_category_themes(page: Page, live_server, db):
    page.goto(live_server.url + "/ministry/verses/")

    expect(page.get_by_role("heading", name="Verses by Theme")).to_be_visible()
    # Category names come from ministry/data/bible_verses.json.
    expect(page.locator("body")).to_contain_text("Relationship with God")
    # The first category is expanded by default, so its theme buttons are visible.
    first_category = page.locator(".collapse").first
    expect(first_category.get_by_role("button", name="Love", exact=True)).to_be_visible()
    expect(first_category.get_by_role("button", name="Grace", exact=True)).to_be_visible()


def test_clicking_theme_loads_verse_card(page: Page, live_server, db):
    page.goto(live_server.url + "/ministry/verses/")

    page.locator(".collapse").first.get_by_role("button", name="Love", exact=True).click()

    card = page.locator('#verse-display [data-testid="verse-card"]')
    expect(card).to_be_visible()
    expect(card).to_contain_text("John 3:16")
    expect(card).to_contain_text(FAKED_TEXT)
    expect(card).to_contain_text("WEB")


def test_reroll_button_fetches_another_verse(page: Page, live_server, db):
    page.goto(live_server.url + "/ministry/verses/")
    page.locator(".collapse").first.get_by_role("button", name="Love", exact=True).click()

    card = page.locator('#verse-display [data-testid="verse-card"]')
    expect(card).to_be_visible()

    # The faked API returns identical content, so prove the swap happened by
    # waiting for the verse-random request the re-roll button fires.
    with page.expect_response(lambda r: "/random/" in r.url and r.status == 200):
        card.get_by_role("button", name="Another verse on Love").click()

    expect(card).to_be_visible()
    expect(card).to_contain_text("John 3:16")
    expect(card).to_contain_text(FAKED_TEXT)
