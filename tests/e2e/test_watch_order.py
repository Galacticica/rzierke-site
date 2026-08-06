"""
File: test_watch_order.py
Description: Watch-order chart: the client-side layout places tiles into lanes,
arrows are drawn between them, converging lanes push the merge target below both,
track filtering re-lays-out, and watched state survives a reload.
Uses the `watch_order` fixture (MCU and X-Men lanes merging into Doomsday).
"""

from playwright.sync_api import Page, expect

WATCH_URL = "/mcu-relationships/watch-order/"


def grid_position(page: Page, slug):
    """The tile's computed grid placement, as (row, column)."""
    return page.evaluate(
        """(slug) => {
            const tile = document.querySelector(`[data-watch-entry="${slug}"]`);
            const style = getComputedStyle(tile);
            return [parseInt(style.gridRowStart, 10), parseInt(style.gridColumnStart, 10)];
        }""",
        slug,
    )


def test_chart_renders_without_js_errors(page: Page, live_server, watch_order):
    console_errors = []
    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
    page.on("pageerror", lambda exc: console_errors.append(str(exc)))

    page.goto(live_server.url + WATCH_URL)

    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)
    expect(page.locator("[data-watch-entry]")).to_have_count(6)
    assert not console_errors, f"JS console errors on {WATCH_URL}: {console_errors}"


def test_lanes_get_their_own_columns(page: Page, live_server, watch_order):
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)

    assert grid_position(page, "iron-man")[1] == 1
    assert grid_position(page, "x-men")[1] == 2


def test_entries_stack_down_their_own_track(page: Page, live_server, watch_order):
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)

    assert grid_position(page, "iron-man")[0] < grid_position(page, "the-avengers")[0]


def test_merge_target_drops_below_both_lanes(page: Page, live_server, watch_order):
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)

    doomsday_row = grid_position(page, "doomsday")[0]
    assert doomsday_row > grid_position(page, "the-avengers")[0]
    assert doomsday_row > grid_position(page, "deadpool-wolverine")[0]


def test_arrows_are_drawn_between_tiles(page: Page, live_server, watch_order):
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)

    # 4 track edges (2 MCU + 2 X-Men) plus the one cross-lane merge.
    expect(page.locator(".watch-arrows path.watch-arrow")).to_have_count(5)


def test_hiding_a_track_relayouts_and_drops_its_arrows(page: Page, live_server, watch_order):
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)

    before = grid_position(page, "doomsday")[0]
    page.locator('[data-watch-track="fox-x-men"]').click()

    expect(page.locator('[data-watch-entry="x-men"]')).to_be_hidden()
    # Only the two MCU track edges survive; the merge arrow has no source now.
    expect(page.locator(".watch-arrows path.watch-arrow")).to_have_count(2)
    # Doomsday no longer waits on the X-Men lane, so it moves up.
    assert grid_position(page, "doomsday")[0] < before


def test_detail_card_opens_with_entry_details(page: Page, live_server, watch_order):
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)

    page.locator('[data-watch-entry="iron-man"] [data-watch-open]').click()

    popup = page.locator("[data-watch-popup]")
    expect(popup).to_be_visible()
    expect(popup.locator("[data-watch-popup-title]")).to_have_text("Iron Man")
    expect(popup.locator("[data-watch-popup-meta]")).to_contain_text("2008")


def test_entries_without_a_poster_render_as_text_cards(page: Page, live_server, watch_order):
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)

    placeholder = page.locator('[data-watch-entry="iron-man"] .watch-tile__placeholder')
    expect(placeholder).to_be_visible()
    expect(placeholder).to_contain_text("Iron Man")


def test_anonymous_watched_state_persists_in_the_browser(page: Page, live_server, watch_order):
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)

    page.locator('[data-watch-entry="iron-man"] [data-watch-toggle]').click()
    expect(page.locator('[data-watch-entry="iron-man"]')).to_have_class("watch-tile is-watched")
    expect(page.locator("[data-watch-progress-count]")).to_have_text("1 / 6 watched")

    page.reload()
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)
    expect(page.locator('[data-watch-entry="iron-man"]')).to_have_class("watch-tile is-watched")


def test_signed_in_watched_state_persists_to_the_account(
    page: Page, live_server, watch_order, user, login
):
    login(user)
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)

    page.locator('[data-watch-entry="the-avengers"] [data-watch-toggle]').click()
    expect(page.locator("[data-watch-progress-count]")).to_have_text("1 / 6 watched")

    from connections.models import WatchProgress

    # Give the POST a moment to land, then confirm it is really in the database.
    expect(page.locator('[data-watch-entry="the-avengers"]')).to_have_class("watch-tile is-watched")
    page.wait_for_timeout(500)
    assert WatchProgress.objects.filter(user=user, entry__slug="the-avengers").exists()


def test_progress_reports_remaining_hours(page: Page, live_server, watch_order):
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)

    # 126 + 143 + 150 + 104 + 134 + 128 = 785 minutes -> 13 hours.
    expect(page.locator("[data-watch-progress-remaining]")).to_have_text("13 hrs left")


def select_collection(page: Page, slug):
    page.locator("[data-watch-collection]").select_option(slug)


def test_collection_filters_the_chart(page: Page, live_server, watch_order):
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)

    select_collection(page, "doomsday-prep")

    expect(page.locator('[data-watch-entry="iron-man"]')).to_be_visible()
    expect(page.locator('[data-watch-entry="the-avengers"]')).to_be_hidden()
    expect(page.locator('[data-watch-entry="x-men"]')).to_be_hidden()


def test_a_hole_in_a_lane_is_bridged_not_stacked(page: Page, live_server, watch_order):
    """The Avengers is skipped by the collection, so Iron Man must chain past it.

    Doomsday's prerequisite (Deadpool) is outside the collection and therefore
    dropped, so the rebuilt lane chain is the only thing separating these two.
    Taking the chain from the server instead would break at the hole and leave
    both on row 1, overlapping in the same column.
    """
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)

    select_collection(page, "doomsday-prep")

    iron_man = grid_position(page, "iron-man")
    doomsday = grid_position(page, "doomsday")
    assert iron_man[1] == doomsday[1], "both are still in the MCU lane"
    assert doomsday[0] > iron_man[0], f"stacked on the same row: {iron_man} vs {doomsday}"


def test_collection_progress_counts_only_its_members(page: Page, live_server, watch_order):
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)
    expect(page.locator("[data-watch-progress-count]")).to_have_text("0 / 6 watched")

    select_collection(page, "doomsday-prep")
    expect(page.locator("[data-watch-progress-count]")).to_have_text("0 / 2 watched")


def test_an_entry_can_sit_in_a_collection_and_still_show_in_everything(
    page: Page, live_server, watch_order
):
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)

    select_collection(page, "doomsday-prep")
    expect(page.locator('[data-watch-entry="the-avengers"]')).to_be_hidden()

    select_collection(page, "")
    expect(page.locator('[data-watch-entry="the-avengers"]')).to_be_visible()
    expect(page.locator("[data-watch-progress-count]")).to_have_text("0 / 6 watched")


def test_the_graph_link_opens_filtered_to_that_film(page: Page, live_server, watch_order):
    """The link must land on the film's cast, not the whole graph.

    Iron Man's Movie has two characters; a third is deliberately outside it, so a
    graph that ignored the filter would show three nodes.
    """
    from connections.models import Character, Movie, Relationship

    stark = Character.objects.create(name="Tony Stark")
    rhodes = Character.objects.create(name="James Rhodes")
    unrelated = Character.objects.create(name="Stephen Strange")
    Relationship.objects.create(
        character1=stark, character2=rhodes, relationship_type="Ally", directional=False
    )
    Relationship.objects.create(
        character1=stark, character2=unrelated, relationship_type="Ally", directional=False
    )

    movie = Movie.objects.create(title="Iron Man", release_date="2008-05-02")
    movie.characters.add(stark, rhodes)

    entry = watch_order["iron_man"]
    entry.movie = movie
    entry.save()

    requested = []
    page.on("request", lambda request: requested.append(request.url))

    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)

    page.locator('[data-watch-entry="iron-man"] [data-watch-open]').click()
    link = page.locator("[data-watch-popup-graph]")
    expect(link).to_be_visible()

    link.click()
    expect(page.locator("#mcu-graph canvas").first).to_be_visible(timeout=20000)

    # The deep link ticked the filter before the first fetch, so the graph asked
    # for this movie's subgraph rather than the whole thing.
    assert page.locator(f'input[data-graph-filter="movie"][value="{movie.id}"]').is_checked()
    filter_calls = [url for url in requested if "/api/graph/filter/" in url]
    assert filter_calls, "the graph never called the filter endpoint"
    assert all(f"movie={movie.id}" in url for url in filter_calls), filter_calls

    # And the user can see why the graph is narrowed.
    expect(page.locator("#graph-summary")).to_contain_text("Iron Man")

    response = page.request.get(live_server.url + f"/api/graph/filter/?movie={movie.id}")
    labels = {node["data"].get("label") for node in response.json()["nodes"]}
    assert labels == {"Tony Stark", "James Rhodes"}, "Stephen Strange is not in this film"


def test_no_graph_link_when_the_entry_has_no_movie(page: Page, live_server, watch_order):
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)

    page.locator('[data-watch-entry="the-avengers"] [data-watch-open]').click()

    expect(page.locator("[data-watch-popup]")).to_be_visible()
    expect(page.locator("[data-watch-popup-graph]")).to_be_hidden()


def test_continued_tracks_render_as_one_column(page: Page, live_server, continued_sagas):
    """Infinity Saga and Multiverse Saga stack in a single column, chained straight
    through, with no prerequisite and therefore no stray second arrow."""
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)

    gotg = grid_position(page, "gotg-2")
    groot = grid_position(page, "i-am-groot")
    wakanda = grid_position(page, "eyes-of-wakanda")
    xmen = grid_position(page, "x-men")

    # Same column, running straight down across the saga handover.
    assert gotg[1] == groot[1] == wakanda[1], f"{gotg} {groot} {wakanda}"
    assert gotg[0] < groot[0] < wakanda[0]
    # The unrelated studio lane stays parallel.
    assert xmen[1] != gotg[1]


def test_the_handover_draws_a_single_arrow(page: Page, live_server, continued_sagas):
    """The reported bug: I Am Groot picking up an extra line alongside its chain."""
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)

    # 4 chain edges total (3 down the merged column, 0 in X-Men which has one entry).
    expect(page.locator(".watch-arrows path.watch-arrow")).to_have_count(3)
