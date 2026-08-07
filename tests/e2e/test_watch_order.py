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


def test_an_entry_can_drop_its_incoming_arrow(page: Page, live_server, long_lane):
    """Unticking "connects to previous" removes the arrow but keeps the slot."""
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)
    expect(page.locator(".watch-arrows path.watch-arrow")).to_have_count(8)
    before = grid_position(page, "film-5")

    long_lane[4].connects_to_previous = False
    long_lane[4].save()

    page.reload()
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)

    # One fewer arrow, but the tile has not moved.
    expect(page.locator(".watch-arrows path.watch-arrow")).to_have_count(7)
    assert grid_position(page, "film-5") == before


def test_a_lane_wraps_left_to_right_then_down(page: Page, live_server, long_lane):
    """Reads like a page of text: across the row, then back to the left below."""
    from connections.models import WatchOrderConfig

    WatchOrderConfig.objects.create(items_per_row=4)

    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)

    # 9 entries at 4 across -> rows of 4, 4, 1.
    assert grid_position(page, "film-1") == [1, 1]
    assert grid_position(page, "film-2") == [1, 2], "the second sits to the RIGHT of the first"
    assert grid_position(page, "film-4") == [1, 4]
    assert grid_position(page, "film-5") == [2, 1], "the fifth wraps back to the left, one row down"
    assert grid_position(page, "film-9") == [3, 1]


def test_wrapping_keeps_every_arrow(page: Page, live_server, long_lane):
    """A wrap arrow points upward, which the router used to silently skip."""
    from connections.models import WatchOrderConfig

    WatchOrderConfig.objects.create(items_per_row=4)

    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)

    # All 8 chain arrows survive: 6 sideways within rows, 2 wrapping down-left.
    expect(page.locator(".watch-arrows path.watch-arrow")).to_have_count(8)
    # Nothing points backwards up the page, so no stubs are needed.
    expect(page.locator(".watch-arrows path.watch-arrow[data-watch-wrap]")).to_have_count(0)


def test_no_wrapping_by_default(page: Page, live_server, long_lane):
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)

    assert grid_position(page, "film-9") == [9, 1]
    expect(page.locator(".watch-arrows path.watch-arrow[data-watch-wrap]")).to_have_count(0)


def test_branches_from_one_entry_sit_side_by_side(page: Page, live_server, fan_out):
    """Four seasons all following The Defenders fan out across one row."""
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)

    parent = grid_position(page, "defenders")
    branches = [grid_position(page, slug) for slug in ("dd-s3", "jj-s3", "lc-s2", "if-s2")]

    assert len({row for row, _ in branches}) == 1, f"all on one row: {branches}"
    assert branches[0][0] == parent[0] + 1, "one row below the parent"
    assert sorted(column for _, column in branches) == [1, 2, 3, 4], branches


def test_a_fan_out_reaches_every_branch(page: Page, live_server, fan_out):
    """The bug: a single long arrow through a stack, instead of one per branch."""
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)
    page.wait_for_timeout(400)

    arrived = incoming_arrow_targets(page)
    assert {"dd-s3", "jj-s3", "lc-s2", "if-s2", "punisher-s2"} <= arrived


def test_the_fan_out_rejoins_after_every_branch(page: Page, live_server, fan_out):
    """The next entry waits on all four, not just whichever came last."""
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)

    branch_rows = [grid_position(page, slug)[0] for slug in ("dd-s3", "jj-s3", "lc-s2", "if-s2")]
    assert grid_position(page, "punisher-s2")[0] == max(branch_rows) + 1


def test_a_single_entry_stays_centred_under_a_fan_out(page: Page, live_server, fan_out):
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)

    assert grid_position(page, "defenders")[1] == grid_position(page, "punisher-s2")[1]


def test_entries_converging_on_one_sit_side_by_side(page: Page, live_server, fan_in):
    """The reported bug: four unconnected shows stacked in one column."""
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)

    sources = [grid_position(page, slug) for slug in ("dd-s2", "jj-s1", "lc-s1", "if-s1")]

    assert len({row for row, _ in sources}) == 1, f"all abreast, not stacked: {sources}"
    assert len({column for _, column in sources}) == 4, f"four columns: {sources}"


def test_the_target_sits_below_all_of_them(page: Page, live_server, fan_in):
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)

    source_rows = [grid_position(page, slug)[0] for slug in ("dd-s2", "jj-s1", "lc-s1", "if-s1")]
    assert grid_position(page, "defenders")[0] > max(source_rows)


def test_a_sibling_with_its_own_history_is_levelled_up(page: Page, live_server, fan_in):
    """Daredevil S2 follows a season 1, so it starts a row deeper than the rest.

    Without levelling, the four would stagger diagonally down the column and
    their arrows would cut through whatever sat between them.
    """
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)

    dd1_row = grid_position(page, "dd-s1")[0]
    assert grid_position(page, "dd-s2")[0] == dd1_row + 1
    assert grid_position(page, "jj-s1")[0] == dd1_row + 1, "levelled up to match its sibling"


def test_every_converging_arrow_is_drawn(page: Page, live_server, fan_in):
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)
    page.wait_for_timeout(400)

    arrived = incoming_arrow_targets(page)
    # Everything except the very first entry is pointed at by something.
    assert {"dd-s2", "jj-s1", "lc-s1", "if-s1", "defenders"} <= arrived


def incoming_arrow_targets(page: Page):
    """Slugs of tiles that an arrowhead actually lands on."""
    return set(page.evaluate("""() => {
        const el = document.querySelector('.watch-canvas');
        const canvas = el.getBoundingClientRect();
        const t = getComputedStyle(el).transform;
        const scale = t === 'none' ? 1 : parseFloat(t.split('(')[1].split(',')[0]);
        const heads = [...document.querySelectorAll('.watch-arrow[marker-end]')].map((path) => {
            const point = path.getPointAtLength(path.getTotalLength());
            return { x: point.x, y: point.y };
        });
        const hit = [];
        document.querySelectorAll('[data-watch-entry]').forEach((tile) => {
            if (tile.hidden) return;
            const rect = tile.getBoundingClientRect();
            const top = (rect.top - canvas.top) / scale;
            const left = (rect.left - canvas.left) / scale;
            const right = (rect.right - canvas.left) / scale;
            if (heads.some((h) => Math.abs(h.y - top) < 14 && h.x > left - 6 && h.x < right + 6)) {
                hit.push(tile.dataset.watchEntry);
            }
        });
        return hit;
    }"""))


def test_no_entry_is_left_without_an_incoming_arrow(page: Page, live_server, netflix_block):
    """Every tile bar the first must be pointed at by something.

    Siblings that name no predecessor of their own once ended up floating, with
    the fan-out reaching only the ones that did.
    """
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)
    page.wait_for_timeout(400)

    arrived = incoming_arrow_targets(page)
    everything = set(page.evaluate(
        "() => [...document.querySelectorAll('[data-watch-entry]')].map(t => t.dataset.watchEntry)"
    ))

    assert everything - arrived == {"dd-s1"}, f"orphaned: {sorted(everything - arrived - {'dd-s1'})}"


def test_a_fan_in_lands_as_one_arrow_not_four(page: Page, live_server, netflix_block):
    """Four separate elbows through one gutter is what made it unreadable.

    A bracket drops each source to a shared rail and enters the target once, so
    the giveaway is a single arrowhead on The Defenders rather than four.
    """
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)
    page.wait_for_timeout(400)

    heads = page.evaluate("""() => {
        const canvas = document.querySelector('.watch-canvas').getBoundingClientRect();
        const tile = document.querySelector('[data-watch-entry="defenders"]').getBoundingClientRect();
        const top = tile.top - canvas.top;
        const left = tile.left - canvas.left;
        const right = tile.right - canvas.left;
        return [...document.querySelectorAll('.watch-arrow[marker-end]')].filter((path) => {
            const point = path.getPointAtLength(path.getTotalLength());
            return Math.abs(point.y - top) < 14 && point.x > left - 6 && point.x < right + 6;
        }).length;
    }""")

    assert heads == 1, f"four sources should share one entry arrow, got {heads}"


def test_the_sources_of_a_fan_in_share_one_rail(page: Page, live_server, netflix_block):
    """Every source stub must stop at the same height - that is the rail."""
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)
    page.wait_for_timeout(400)

    ends = page.evaluate(r"""() => {
        const canvas = document.querySelector('.watch-canvas').getBoundingClientRect();
        const bottoms = ['jj-s1', 'dd-s2', 'lc-s1', 'if-s1'].map((slug) => {
            const r = document.querySelector(`[data-watch-entry="${slug}"]`).getBoundingClientRect();
            return { x: r.left + r.width / 2 - canvas.left, y: r.bottom - canvas.top };
        });
        const ys = [];
        document.querySelectorAll('.watch-arrow').forEach((path) => {
            const m = path.getAttribute('d').match(/^M ([\d.]+) ([\d.]+) L ([\d.]+) ([\d.]+)$/);
            if (!m) return;
            const [x1, y1, x2, y2] = [+m[1], +m[2], +m[3], +m[4]];
            // A vertical stub leaving one of the four sources.
            if (Math.abs(x1 - x2) < 0.5 && bottoms.some(b => Math.abs(b.x - x1) < 2 && Math.abs(b.y - y1) < 2)) {
                ys.push(Math.round(y2));
            }
        });
        return ys;
    }""")

    assert len(ends) == 4, f"expected a stub from each source, got {ends}"
    assert len(set(ends)) == 1, f"stubs must stop at one shared rail, got {ends}"


def test_the_side_branch_still_reaches_its_own_target(page: Page, live_server, netflix_block):
    """Daredevil S2 feeds both the fan-in and The Punisher; both must survive."""
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)
    page.wait_for_timeout(400)

    assert "punisher-s1" in incoming_arrow_targets(page)


def test_story_order_beats_list_order(page: Page, live_server, xmen_franchise):
    """First Class is listed after Origins but must be drawn above it."""
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)

    assert grid_position(page, "first-class")[0] < grid_position(page, "origins")[0]


def test_the_two_branches_converge_on_days_of_future_past(page: Page, live_server, xmen_franchise):
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)

    dofp_row = grid_position(page, "dofp")[0]
    assert dofp_row > grid_position(page, "last-stand")[0]
    assert dofp_row > grid_position(page, "origins")[0]


def test_the_trilogy_keeps_its_own_order(page: Page, live_server, xmen_franchise):
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)

    assert (
        grid_position(page, "x-men")[0]
        < grid_position(page, "x2")[0]
        < grid_position(page, "last-stand")[0]
    )


def test_nothing_points_backwards_up_the_page(page: Page, live_server, xmen_franchise):
    """A cycle used to leave the layout guessing, with arrows running upward."""
    console = []
    page.on("console", lambda msg: console.append(msg.text))

    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)
    page.wait_for_timeout(400)

    expect(page.locator(".watch-arrows path.watch-arrow[data-watch-wrap]")).to_have_count(0)
    assert not [line for line in console if "cycle" in line.lower()], console


def test_every_x_men_film_is_reachable(page: Page, live_server, xmen_franchise):
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)
    page.wait_for_timeout(400)

    arrived = incoming_arrow_targets(page)
    assert {"x2", "last-stand", "origins", "dofp"} <= arrived


def test_sequential_siblings_are_not_forced_level(page: Page, live_server, xmen_franchise):
    """The Last Stand and Origins both feed DOFP, but one leads to the other.

    Levelling them is impossible, and trying left each pass shoving them further
    apart until the chart had a chasm down the middle.
    """
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)

    rows = [
        grid_position(page, slug)[0]
        for slug in ("x-men", "x2", "last-stand", "first-class", "origins", "dofp")
    ]
    assert rows == sorted(rows), rows
    assert max(rows) <= 6, f"rows ran away: {rows}"


def test_entries_split_by_another_are_read_as_sequential(page: Page, live_server, scattered_fan_in):
    """A fan is a run of neighbours; something in between means "in order".

    Entries sharing a relative from opposite ends of a list are sequential, not
    parallel - which is exactly how X-Men: First Class relates to The Last Stand.
    """
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)
    page.wait_for_timeout(400)

    rows = [grid_position(page, s)[0] for s in ("jj-s1", "dd-s2", "filler", "lc-s1", "if-s1")]
    assert rows == sorted(rows) and len(set(rows)) == len(rows), rows


def test_no_duplicate_arrows_when_a_group_is_split(page: Page, live_server, scattered_fan_in):
    """Re-wiring a group produced doubled edges on top of each other."""
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)
    page.wait_for_timeout(400)

    paths = page.evaluate(
        "() => [...document.querySelectorAll('.watch-arrow')].map(p => p.getAttribute('d'))"
    )
    assert len(paths) == len(set(paths)), "identical arrows drawn twice"


def test_a_stated_predecessor_is_not_dragged_down_by_the_list(page: Page, live_server, real_shape):
    """Punisher S2 states only Punisher S1, so it belongs level with the fan.

    Adding the list-order frontier on top pushed it a row below everything that
    happened to precede it, knocking it out of line.
    """
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)

    fan = [grid_position(page, slug)[0] for slug in ("jj2", "lc2", "if2", "dd3")]
    assert len(set(fan)) == 1, fan
    assert grid_position(page, "pn2")[0] == fan[0], "Punisher S2 fell out of line"


def test_a_fan_in_member_keeps_its_place_in_the_list(page: Page, live_server, real_shape):
    """The Last Stand feeds Days of Future Past but still follows X2.

    Being grouped with First Class stripped its incoming edge, so it floated to
    row 0 and headed a column of its own.
    """
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)

    assert grid_position(page, "ls")[0] == grid_position(page, "x2")[0] + 1


def test_only_the_lane_heads_are_unreached(page: Page, live_server, real_shape):
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)
    page.wait_for_timeout(400)

    arrived = incoming_arrow_targets(page)
    everything = set(page.evaluate(
        "() => [...document.querySelectorAll('[data-watch-entry]')].map(t => t.dataset.watchEntry)"
    ))
    assert everything - arrived == {"fc", "dd1"}, sorted(everything - arrived)


def drag(page: Page, from_x, from_y, to_x, to_y, steps=12):
    page.mouse.move(from_x, from_y)
    page.mouse.down()
    page.mouse.move(to_x, to_y, steps=steps)
    page.mouse.up()


def test_dragging_pans_the_chart_sideways(page: Page, live_server, netflix_block):
    page.set_viewport_size({"width": 500, "height": 700})
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)
    page.wait_for_timeout(300)

    scroller = page.locator(".watch-scroll")
    before = scroller.evaluate("el => el.scrollLeft")

    box = scroller.bounding_box()
    drag(page, box["x"] + box["width"] - 20, box["y"] + 40, box["x"] + 40, box["y"] + 40)

    assert scroller.evaluate("el => el.scrollLeft") > before


def test_dragging_up_scrolls_the_page(page: Page, live_server, netflix_block):
    page.set_viewport_size({"width": 900, "height": 500})
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)
    page.wait_for_timeout(300)

    box = page.locator(".watch-scroll").bounding_box()
    start_y = box["y"] + box["height"] - 20
    drag(page, box["x"] + 30, start_y, box["x"] + 30, box["y"] + 20)

    assert page.evaluate("() => window.scrollY") > 0


def test_a_drag_does_not_open_the_tile_it_ends_on(page: Page, live_server, netflix_block):
    """Panning must not double as clicking whatever is under the cursor."""
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)
    page.wait_for_timeout(300)

    tile = page.locator('[data-watch-entry="defenders"] [data-watch-open]').bounding_box()
    drag(page, tile["x"] + 20, tile["y"] + 20, tile["x"] + 90, tile["y"] + 20)

    expect(page.locator("[data-watch-popup]")).to_be_hidden()


def test_a_plain_click_still_opens_the_tile(page: Page, live_server, netflix_block):
    """The drag threshold must not swallow ordinary clicks."""
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)
    page.wait_for_timeout(300)

    page.locator('[data-watch-entry="defenders"] [data-watch-open]').click()

    expect(page.locator("[data-watch-popup]")).to_be_visible()
    expect(page.locator("[data-watch-popup-title]")).to_have_text("The Defenders")


def test_the_cursor_shows_the_chart_is_draggable(page: Page, live_server, netflix_block):
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)

    cursor = page.locator(".watch-scroll").evaluate("el => getComputedStyle(el).cursor")
    assert cursor == "grab"


def test_panning_stops_at_the_right_hand_edge(page: Page, live_server, netflix_block):
    page.set_viewport_size({"width": 500, "height": 700})
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)
    page.wait_for_timeout(300)

    scroller = page.locator(".watch-scroll")
    box = scroller.bounding_box()

    # Drag far past the end, several times over.
    for _ in range(3):
        drag(page, box["x"] + box["width"] - 10, box["y"] + 40, box["x"] - 400, box["y"] + 40)

    limit = scroller.evaluate("el => el.scrollWidth - el.clientWidth")
    assert scroller.evaluate("el => el.scrollLeft") <= limit + 1


def test_panning_stops_at_the_left_hand_edge(page: Page, live_server, netflix_block):
    page.set_viewport_size({"width": 500, "height": 700})
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)
    page.wait_for_timeout(300)

    scroller = page.locator(".watch-scroll")
    box = scroller.bounding_box()
    for _ in range(3):
        drag(page, box["x"] + 10, box["y"] + 40, box["x"] + box["width"] + 400, box["y"] + 40)

    assert scroller.evaluate("el => el.scrollLeft") >= 0


def test_the_chart_cannot_be_dragged_off_the_bottom(page: Page, live_server, netflix_block):
    """Dragging up used to scroll the page past the chart entirely."""
    page.set_viewport_size({"width": 900, "height": 500})
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)
    page.wait_for_timeout(300)

    box = page.locator(".watch-scroll").bounding_box()
    for _ in range(6):
        drag(page, box["x"] + 30, box["y"] + box["height"] - 10, box["x"] + 30, box["y"] - 400)

    still_showing = page.evaluate("""() => {
        const r = document.getElementById('watch-order-chart').getBoundingClientRect();
        return r.bottom > 0 && r.top < window.innerHeight;
    }""")
    assert still_showing, "the chart was dragged out of view"


def test_the_chart_cannot_be_dragged_off_the_top(page: Page, live_server, netflix_block):
    page.set_viewport_size({"width": 900, "height": 500})
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)
    page.wait_for_timeout(300)

    box = page.locator(".watch-scroll").bounding_box()
    for _ in range(6):
        drag(page, box["x"] + 30, box["y"] + 20, box["x"] + 30, box["y"] + 460)

    assert page.evaluate("() => window.scrollY") >= 0
    still_showing = page.evaluate("""() => {
        const r = document.getElementById('watch-order-chart').getBoundingClientRect();
        return r.bottom > 0 && r.top < window.innerHeight;
    }""")
    assert still_showing, "the chart was dragged out of view"


def test_a_long_reach_routes_around_the_tiles(page: Page, live_server, long_reach):
    """First Class -> Days of Future Past must not cut through six posters."""
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)
    page.wait_for_timeout(400)

    crossings = page.evaluate("""() => {
        const canvas = document.querySelector('.watch-canvas').getBoundingClientRect();
        const boxes = [...document.querySelectorAll('[data-watch-entry]')].map(t => {
            const r = t.getBoundingClientRect();
            return {slug: t.dataset.watchEntry,
                    l: r.left - canvas.left, r: r.right - canvas.left,
                    t: r.top - canvas.top, b: r.bottom - canvas.top};
        });
        const hits = [];
        document.querySelectorAll('.watch-arrow').forEach(path => {
            const total = path.getTotalLength();
            for (let d = 0; d <= total; d += 4) {
                const p = path.getPointAtLength(d);
                boxes.forEach(b => {
                    // Well inside a tile, not just grazing its border.
                    if (p.x > b.l + 4 && p.x < b.r - 4 && p.y > b.t + 4 && p.y < b.b - 4) {
                        hits.push(b.slug);
                    }
                });
            }
        });
        return [...new Set(hits)];
    }""")

    assert crossings == [], f"arrows pass through: {crossings}"


def test_the_long_reach_still_lands_on_its_target(page: Page, live_server, long_reach):
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)
    page.wait_for_timeout(400)

    assert "dofp" in incoming_arrow_targets(page)


def test_the_column_still_reads_in_order(page: Page, live_server, long_reach):
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)

    rows = [grid_position(page, s)[0]
            for s in ("fc", "ow", "xm", "x2", "ls", "tw", "dofp", "apoc")]
    assert rows == sorted(rows) and len(set(rows)) == len(rows), rows


def test_cross_lane_links_are_drawn_differently(page: Page, live_server, watch_order):
    """A jump between lanes is a sync point, not part of either lane's flow.

    Drawn like the flow, a link spanning several columns reads as the running
    order having bolted off across the page.
    """
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)
    page.wait_for_timeout(400)

    dashed = page.locator(".watch-arrow[stroke-dasharray]")
    solid = page.locator(".watch-arrow:not([stroke-dasharray])")

    # Deadpool & Wolverine -> Doomsday crosses lanes; the rest run down a lane.
    expect(dashed).to_have_count(1)
    assert solid.count() >= 3


def test_a_cross_lane_link_is_not_a_wrap(page: Page, live_server, watch_order):
    """Both are dashed, but only a wrap carries the marker the tests key on."""
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)

    expect(page.locator(".watch-arrow[data-watch-wrap]")).to_have_count(0)


def arrows_outside_the_canvas(page: Page):
    """Arrow bounding boxes that stick out past the chart's own area."""
    return page.evaluate("""() => {
        const canvas = document.querySelector('.watch-canvas');
        const width = canvas.scrollWidth;
        const height = canvas.scrollHeight;
        const out = [];
        document.querySelectorAll('.watch-arrow').forEach((path) => {
            const box = path.getBBox();
            if (box.x < -2 || box.y < -2 ||
                box.x + box.width > width + 2 || box.y + box.height > height + 2) {
                out.push(path.getAttribute('d').slice(0, 60));
            }
        });
        return out;
    }""")


def test_no_arrow_escapes_the_chart(page: Page, live_server, long_reach):
    """A detour out of the outermost column has no gutter to use on that side.

    It was drawn past the edge of the chart regardless, so the line appeared to
    run off into nothing.
    """
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)
    page.wait_for_timeout(400)

    assert arrows_outside_the_canvas(page) == []


def test_no_arrow_escapes_with_several_lanes(page: Page, live_server, netflix_block):
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)
    page.wait_for_timeout(400)

    assert arrows_outside_the_canvas(page) == []


def test_no_arrow_escapes_across_lanes(page: Page, live_server, watch_order):
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)
    page.wait_for_timeout(400)

    assert arrows_outside_the_canvas(page) == []


def zoom_level(page: Page):
    return page.evaluate("""() => {
        const t = getComputedStyle(document.querySelector('.watch-canvas')).transform;
        if (t === 'none') return 1;
        return parseFloat(t.split('(')[1].split(',')[0]);
    }""")


def test_zoom_in_and_out(page: Page, live_server, netflix_block):
    page.set_viewport_size({"width": 700, "height": 800})
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)
    page.wait_for_timeout(400)

    start = zoom_level(page)
    page.locator('[data-watch-zoom="in"]').click()
    page.wait_for_timeout(200)
    assert zoom_level(page) > start

    page.locator('[data-watch-zoom="out"]').click()
    page.locator('[data-watch-zoom="out"]').click()
    page.wait_for_timeout(200)
    assert zoom_level(page) < start


def test_cannot_zoom_out_past_the_content(page: Page, live_server, netflix_block):
    """The floor is the scale where the chart just fills the width.

    Below it you would be zooming out into empty space either side.
    """
    page.set_viewport_size({"width": 700, "height": 800})
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)
    page.wait_for_timeout(400)

    for _ in range(20):
        page.locator('[data-watch-zoom="out"]').click()
    page.wait_for_timeout(300)

    fit = page.evaluate("""() => {
        const s = document.querySelector('.watch-scroll');
        return Math.min(1, s.clientWidth / document.querySelector('.watch-canvas').offsetWidth);
    }""")
    assert zoom_level(page) >= fit - 0.01, f"zoomed below the fit scale: {zoom_level(page)} < {fit}"


def test_fit_shows_the_whole_width(page: Page, live_server, netflix_block):
    page.set_viewport_size({"width": 700, "height": 800})
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)
    page.wait_for_timeout(400)

    page.locator('[data-watch-zoom="fit"]').click()
    page.wait_for_timeout(300)

    overflow = page.evaluate("""() => {
        const s = document.querySelector('.watch-scroll');
        return s.scrollWidth - s.clientWidth;
    }""")
    assert overflow <= 2, f"still {overflow}px of hidden chart after Fit"


def test_zoom_is_capped_on_the_way_in(page: Page, live_server, netflix_block):
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)
    page.wait_for_timeout(400)

    for _ in range(20):
        page.locator('[data-watch-zoom="in"]').click()
    page.wait_for_timeout(300)

    assert zoom_level(page) <= 2.01


def test_arrows_stay_attached_when_zoomed(page: Page, live_server, netflix_block):
    """Rects come back scaled; measuring without dividing them back down would
    scatter every arrow away from its tile."""
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)
    page.wait_for_timeout(400)

    page.locator('[data-watch-zoom="in"]').click()
    page.locator('[data-watch-zoom="in"]').click()
    page.wait_for_timeout(500)

    assert arrows_outside_the_canvas(page) == []
    assert "defenders" in incoming_arrow_targets(page)


def test_the_zoom_level_is_shown(page: Page, live_server, netflix_block):
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)
    page.wait_for_timeout(400)

    expect(page.locator("[data-watch-zoom-level]")).to_have_text("100%")


def test_two_detours_do_not_share_a_line(page: Page, live_server, two_detours):
    """Both reaches leave the same column, so they must be spaced apart.

    Drawn on the same line they merge into one stroke that appears to go
    nowhere - which is what makes a chart with two long reaches unreadable.
    """
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)
    page.wait_for_timeout(400)

    # The longest straight vertical run of each arrow: its detour gutter.
    legs = page.evaluate("""() => {
        const found = [];
        document.querySelectorAll('.watch-arrow').forEach((path) => {
            const total = path.getTotalLength();
            if (total < 150) return;
            let best = null;
            let run = null;
            for (let d = 0; d <= total; d += 3) {
                const p = path.getPointAtLength(d);
                if (run && Math.abs(p.x - run.x) < 1) {
                    run.to = p.y;
                    continue;
                }
                if (run && (!best || Math.abs(run.to - run.from) > Math.abs(best.to - best.from))) {
                    best = run;
                }
                run = { x: p.x, from: p.y, to: p.y };
            }
            if (run && (!best || Math.abs(run.to - run.from) > Math.abs(best.to - best.from))) {
                best = run;
            }
            if (best && Math.abs(best.to - best.from) > 150) {
                found.push(best);
            }
        });
        return found;
    }""")

    assert len(legs) >= 2, f"expected two long detours, got {legs}"

    for index, first in enumerate(legs):
        for second in legs[index + 1:]:
            overlapping = first["from"] < second["to"] and second["from"] < first["to"]
            if overlapping:
                assert abs(first["x"] - second["x"]) >= 5, (
                    f"two detours drawn on the same line at x={first['x']:.0f}"
                )


def test_starting_a_drag_does_not_jump_the_page(page: Page, live_server, netflix_block):
    """The first move must continue from where you are, not snap into range.

    Zooming changes the chart's height, so the pan limits can already exclude
    the current scroll position - and clamping to them jumps the view.
    """
    page.set_viewport_size({"width": 900, "height": 500})
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)
    page.wait_for_timeout(400)

    page.locator('[data-watch-zoom="out"]').click()
    page.locator('[data-watch-zoom="out"]').click()
    page.wait_for_timeout(300)

    # Sit above the chart, where the clamp used to snap from.
    page.evaluate("() => window.scrollTo(0, 0)")
    page.wait_for_timeout(200)
    before = page.evaluate("() => window.scrollY")

    box = page.locator(".watch-scroll").bounding_box()
    page.mouse.move(box["x"] + 40, box["y"] + 40)
    page.mouse.down()
    page.mouse.move(box["x"] + 40, box["y"] + 28, steps=4)
    page.mouse.up()

    after = page.evaluate("() => window.scrollY")
    assert abs(after - before) < 60, f"the page jumped from {before} to {after}"


def test_a_drag_still_stops_at_the_chart_edge_after_zooming(page: Page, live_server, netflix_block):
    """Widening the range must not disable the clamp altogether."""
    page.set_viewport_size({"width": 900, "height": 500})
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)
    page.wait_for_timeout(400)

    page.locator('[data-watch-zoom="out"]').click()
    page.wait_for_timeout(300)

    box = page.locator(".watch-scroll").bounding_box()
    for _ in range(6):
        drag(page, box["x"] + 30, box["y"] + box["height"] - 10, box["x"] + 30, box["y"] - 400)

    still_showing = page.evaluate("""() => {
        const r = document.getElementById('watch-order-chart').getBoundingClientRect();
        return r.bottom > 0 && r.top < window.innerHeight;
    }""")
    assert still_showing, "the chart was dragged out of view"


def wheel_over_chart(page: Page, delta):
    """Wheel over a point that is inside the chart *and* inside the viewport.

    The chart is routinely taller than the window, so its centre is often off
    screen and a wheel aimed there lands on nothing.
    """
    box = page.locator(".watch-scroll").bounding_box()
    size = page.viewport_size
    x = min(max(box["x"] + box["width"] / 2, 5), size["width"] - 5)
    y = min(max(box["y"] + 40, 5), size["height"] - 5)
    page.mouse.move(x, y)
    page.mouse.wheel(0, delta)
    page.wait_for_timeout(250)


def test_the_wheel_zooms_over_the_chart(page: Page, live_server, netflix_block):
    page.set_viewport_size({"width": 700, "height": 800})
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)
    page.wait_for_timeout(400)

    start = zoom_level(page)
    wheel_over_chart(page, -120)
    assert zoom_level(page) > start

    wheel_over_chart(page, 120)
    wheel_over_chart(page, 120)
    assert zoom_level(page) < start


def test_the_wheel_cannot_zoom_below_the_fit(page: Page, live_server, netflix_block):
    page.set_viewport_size({"width": 700, "height": 800})
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)
    page.wait_for_timeout(400)

    for _ in range(25):
        wheel_over_chart(page, 120)

    fit = page.evaluate("""() => {
        const s = document.querySelector('.watch-scroll');
        return Math.min(1, s.clientWidth / document.querySelector('.watch-canvas').offsetWidth);
    }""")
    assert zoom_level(page) >= fit - 0.01


def test_the_wheel_scrolls_the_page_once_zoom_bottoms_out(page: Page, live_server, netflix_block):
    """Swallowing the wheel at the limit would leave the page unscrollable."""
    page.set_viewport_size({"width": 700, "height": 500})
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)
    page.wait_for_timeout(400)

    page.locator('[data-watch-zoom="fit"]').click()
    page.wait_for_timeout(300)
    before = page.evaluate("() => window.scrollY")

    wheel_over_chart(page, 200)
    wheel_over_chart(page, 200)

    assert page.evaluate("() => window.scrollY") > before, "the wheel stopped scrolling the page"


def test_the_wheel_scrolls_the_page_once_zoom_tops_out(page: Page, live_server, netflix_block):
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)
    page.wait_for_timeout(400)

    for _ in range(12):
        wheel_over_chart(page, -120)
    assert zoom_level(page) >= 1.99

    page.evaluate("() => window.scrollTo(0, 200)")
    page.wait_for_timeout(150)
    before = page.evaluate("() => window.scrollY")
    wheel_over_chart(page, -200)

    assert page.evaluate("() => window.scrollY") != before or before == 0


def test_zooming_keeps_the_point_under_the_cursor(page: Page, live_server, netflix_block):
    """Zoom should grow around the cursor, not fling the chart across the view."""
    page.set_viewport_size({"width": 700, "height": 800})
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)
    page.wait_for_timeout(400)

    tile = page.locator('[data-watch-entry="jj-s1"]')
    tile.scroll_into_view_if_needed()
    page.wait_for_timeout(200)
    before = tile.bounding_box()

    page.mouse.move(before["x"] + before["width"] / 2, before["y"] + before["height"] / 2)
    page.mouse.wheel(0, -120)
    page.wait_for_timeout(400)

    after = tile.bounding_box()
    moved = abs(
        (after["x"] + after["width"] / 2) - (before["x"] + before["width"] / 2)
    )
    assert moved < 40, f"the tile under the cursor slid {moved:.0f}px"


def test_hiding_a_track_updates_the_counter(page: Page, live_server, watch_order):
    """The totals describe the chart on screen, chips included."""
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)
    expect(page.locator("[data-watch-progress-count]")).to_have_text("0 / 6 watched")

    page.locator('[data-watch-track="fox-x-men"]').click()

    # The three X-Men entries drop out of the count.
    expect(page.locator("[data-watch-progress-count]")).to_have_text("0 / 3 watched")


def test_hiding_a_track_updates_the_hours_left(page: Page, live_server, watch_order):
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)
    expect(page.locator("[data-watch-progress-remaining]")).to_have_text("13 hrs left")

    page.locator('[data-watch-track="fox-x-men"]').click()

    # 126 + 143 + 150 = 419 minutes -> 7 hours.
    expect(page.locator("[data-watch-progress-remaining]")).to_have_text("7 hrs left")


def test_showing_a_track_again_restores_the_counter(page: Page, live_server, watch_order):
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)

    chip = page.locator('[data-watch-track="fox-x-men"]')
    chip.click()
    expect(page.locator("[data-watch-progress-count]")).to_have_text("0 / 3 watched")

    chip.click()
    expect(page.locator("[data-watch-progress-count]")).to_have_text("0 / 6 watched")


def test_watching_something_in_a_hidden_track_is_not_counted(page: Page, live_server, watch_order):
    """A tick still stands; it just is not part of the visible total."""
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)

    page.locator('[data-watch-entry="x-men"] [data-watch-toggle]').click()
    expect(page.locator("[data-watch-progress-count]")).to_have_text("1 / 6 watched")

    page.locator('[data-watch-track="fox-x-men"]').click()
    expect(page.locator("[data-watch-progress-count]")).to_have_text("0 / 3 watched")

    page.locator('[data-watch-track="fox-x-men"]').click()
    expect(page.locator("[data-watch-progress-count]")).to_have_text("1 / 6 watched")


def test_chips_and_a_collection_narrow_together(page: Page, live_server, watch_order):
    page.goto(live_server.url + WATCH_URL)
    expect(page.locator(".watch-grid[data-laid-out]")).to_be_visible(timeout=20000)

    select_collection(page, "doomsday-prep")
    expect(page.locator("[data-watch-progress-count]")).to_have_text("0 / 2 watched")

    # Both Doomsday Prep entries are in the MCU lane, so hiding it empties the count.
    page.locator('[data-watch-track="mcu"]').click()
    expect(page.locator("[data-watch-progress-count]")).to_have_text("0 / 0 watched")
