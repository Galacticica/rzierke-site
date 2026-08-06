"""
File: test_watch_order_admin.py
Description: The watch entry admin form: the Movie picker (which powers the
character-graph link) is never filled in automatically, but opening it searches
for whatever is in Title so the matching film is already at the top.
"""

import pytest
from playwright.sync_api import Page, expect

ADD_URL = "/admin/connections/watchentry/add/"


@pytest.fixture
def movies(db):
    from connections.models import Movie

    return {
        "cap": Movie.objects.create(title="Captain America: The First Avenger", release_date="2011-07-22"),
        "iron": Movie.objects.create(title="Iron Man", release_date="2008-05-02"),
        "dd": Movie.objects.create(title="Daredevil", release_date="2015-04-10"),
    }


@pytest.fixture
def admin_page(page: Page, live_server, login, superuser, watch_order, movies):
    login(superuser)
    page.goto(live_server.url + ADD_URL)
    expect(page.locator("#id_title")).to_be_visible(timeout=20000)
    return page


def open_movie_picker(page: Page):
    page.locator(".field-movie .select2-selection, #select2-id_movie-container").first.click()
    return page.locator(".select2-container--open .select2-search__field")


def test_the_picker_searches_for_the_title(admin_page: Page):
    admin_page.locator("#id_title").fill("Captain America: The First Avenger")

    search = open_movie_picker(admin_page)

    expect(search).to_have_value("Captain America: The First Avenger")
    expect(admin_page.locator(".select2-results__option")).to_contain_text("Captain America")


def test_a_season_suffix_is_stripped_before_searching(admin_page: Page):
    """The film is "Daredevil"; the tile is "Daredevil Season 1 Ep 1-7"."""
    admin_page.locator("#id_title").fill("Daredevil Season 1 Ep 1-7")

    search = open_movie_picker(admin_page)

    expect(search).to_have_value("Daredevil")


def test_an_empty_title_leaves_the_search_alone(admin_page: Page):
    search = open_movie_picker(admin_page)

    expect(search).to_have_value("")


def test_the_movie_is_not_filled_in_on_save(admin_page: Page, live_server):
    """The graph link stays deliberate - saving must never guess a film."""
    from connections.models import WatchEntry

    # "Daredevil" exists as a Movie but not yet as a watch entry.
    admin_page.locator("#id_title").fill("Daredevil")
    admin_page.locator("#id_track").select_option(label="MCU")
    admin_page.locator('[name="_save"]').first.click()

    # Saving redirects back to the changelist.
    admin_page.wait_for_url("**/admin/connections/watchentry/", timeout=20000)

    entry = WatchEntry.objects.get(title="Daredevil")
    assert entry.movie_id is None, "an exactly-matching Movie exists, but it must not be guessed"
