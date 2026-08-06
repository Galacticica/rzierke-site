"""Tests for watch-order ordering, poster paths, and cycle detection.

The central promise of the sparse-position scheme is that inserting an entry
between two others never touches its neighbours, so most of these assert on what
did *not* change.
"""

from decimal import Decimal
from io import StringIO

import pytest
from django.core.exceptions import ValidationError

from connections.forms import WatchEntryAdminForm
from connections.models import (
    WatchEntry,
    WatchTrack,
    append_position,
    next_position_after,
    renormalize_track,
)
from connections.watch_order_service import would_create_cycle


@pytest.fixture
def mcu(db):
    return WatchTrack.objects.create(name="MCU", slug="mcu", lane_order=0)


@pytest.fixture
def xmen(db):
    return WatchTrack.objects.create(name="Fox X-Men", slug="fox-x-men", lane_order=1)


def make_entry(track, title, **kwargs):
    return WatchEntry.objects.create(
        track=track,
        title=title,
        slug=kwargs.pop("slug", title.lower().replace(" ", "-").replace(":", "")),
        **kwargs,
    )


class TestPositions:
    def test_first_entry_starts_at_the_gap(self, mcu):
        entry = make_entry(mcu, "Iron Man")
        assert entry.position == Decimal("10")

    def test_entries_append_in_creation_order(self, mcu):
        first = make_entry(mcu, "Iron Man")
        second = make_entry(mcu, "Hulk")
        third = make_entry(mcu, "Iron Man 2")
        assert [first.position, second.position, third.position] == [
            Decimal("10"),
            Decimal("20"),
            Decimal("30"),
        ]

    def test_append_position_is_per_track(self, mcu, xmen):
        make_entry(mcu, "Iron Man")
        make_entry(mcu, "Hulk")
        assert append_position(xmen) == Decimal("10")

    def test_insert_after_takes_the_midpoint(self, mcu):
        first = make_entry(mcu, "Iron Man")
        make_entry(mcu, "Iron Man 2")
        assert next_position_after(first) == Decimal("15")

    def test_insert_after_the_last_entry_appends(self, mcu):
        make_entry(mcu, "Iron Man")
        last = make_entry(mcu, "Hulk")
        assert next_position_after(last) == Decimal("30")

    def test_inserting_does_not_renumber_neighbours(self, mcu):
        first = make_entry(mcu, "Iron Man")
        second = make_entry(mcu, "Hulk")
        third = make_entry(mcu, "Iron Man 2")

        make_entry(mcu, "The Incredible Hulk", position=next_position_after(first))

        first.refresh_from_db()
        second.refresh_from_db()
        third.refresh_from_db()
        assert [first.position, second.position, third.position] == [
            Decimal("10"),
            Decimal("20"),
            Decimal("30"),
        ]

    def test_repeated_inserts_between_the_same_pair_keep_ordering(self, mcu):
        first = make_entry(mcu, "Iron Man")
        make_entry(mcu, "Hulk")

        for index in range(8):
            make_entry(mcu, f"Filler {index}", position=next_position_after(first))

        positions = list(
            WatchEntry.objects.filter(track=mcu).order_by("position", "pk").values_list("position", flat=True)
        )
        assert positions == sorted(positions)
        assert len(set(positions)) == len(positions), "positions must stay distinct"

    def test_exhausted_midpoints_ask_for_a_renormalize(self, mcu):
        first = make_entry(mcu, "Iron Man", position=Decimal("10"))
        make_entry(mcu, "Hulk", position=Decimal("10.000001"))

        with pytest.raises(ValidationError, match="Renormalize"):
            next_position_after(first)

    def test_renormalize_respreads_and_preserves_order(self, mcu):
        make_entry(mcu, "Iron Man", position=Decimal("10"))
        make_entry(mcu, "Hulk", position=Decimal("10.5"))
        make_entry(mcu, "Iron Man 2", position=Decimal("10.75"))

        titles_before = list(
            WatchEntry.objects.filter(track=mcu).order_by("position", "pk").values_list("title", flat=True)
        )
        assert renormalize_track(mcu) == 3

        rows = list(WatchEntry.objects.filter(track=mcu).order_by("position", "pk"))
        assert [row.position for row in rows] == [Decimal("10"), Decimal("20"), Decimal("30")]
        assert [row.title for row in rows] == titles_before

    def test_renormalize_only_touches_its_own_track(self, mcu, xmen):
        make_entry(mcu, "Iron Man", position=Decimal("10.5"))
        other = make_entry(xmen, "X-Men", position=Decimal("10.5"))

        renormalize_track(mcu)

        other.refresh_from_db()
        assert other.position == Decimal("10.5")


class TestPosterPath:
    def test_bare_filename_is_prefixed(self, mcu):
        entry = make_entry(mcu, "Iron Man", poster_path="iron-man.jpg")
        assert entry.poster_path == "watch-order/iron-man.jpg"

    def test_already_prefixed_path_is_left_alone(self, mcu):
        entry = make_entry(mcu, "Iron Man", poster_path="watch-order/iron-man.webp")
        assert entry.poster_path == "watch-order/iron-man.webp"

    def test_blank_stays_blank(self, mcu):
        entry = make_entry(mcu, "Iron Man")
        assert entry.poster_path == ""


class TestTotalMinutes:
    def test_film_uses_its_runtime(self, mcu):
        assert make_entry(mcu, "Iron Man", runtime_minutes=126).total_minutes == 126

    def test_series_multiplies_by_episodes(self, mcu):
        entry = make_entry(mcu, "Agatha All Along", runtime_minutes=40, episode_count=9)
        assert entry.total_minutes == 360

    def test_missing_runtime_is_zero(self, mcu):
        assert make_entry(mcu, "Iron Man").total_minutes == 0


class TestCycleDetection:
    def test_cross_track_merge_is_fine(self, mcu, xmen):
        make_entry(xmen, "X-Men")
        deadpool = make_entry(xmen, "Deadpool & Wolverine")
        doomsday = make_entry(mcu, "Avengers: Doomsday")

        assert not would_create_cycle(doomsday, [deadpool.pk])

    def test_pointing_backwards_along_the_list_is_allowed(self, mcu):
        """The X-Men case: story order and list order legitimately disagree.

        First Class sits later in the list than Origins: Wolverine but comes
        first in the story. Treating list order as a rule would forbid saying so.
        """
        early = make_entry(mcu, "X-Men Origins: Wolverine")
        late = make_entry(mcu, "X-Men: First Class")

        assert not would_create_cycle(early, [late.pk])

    def test_two_entries_cannot_require_each_other(self, mcu, xmen):
        first = make_entry(mcu, "Avengers: Doomsday")
        second = make_entry(xmen, "Deadpool & Wolverine")
        second.prerequisites.add(first)

        assert would_create_cycle(first, [second.pk])

    def test_an_unsaved_entry_can_never_loop(self, mcu):
        """Nothing can reference an entry that does not exist yet.

        With list order out of the picture, a brand-new entry has no incoming
        edges at all, so whatever prerequisites it is given are always safe.
        """
        first = make_entry(mcu, "Iron Man")
        second = make_entry(mcu, "The Avengers")
        second.prerequisites.add(first)

        probe = WatchEntry(track=mcu, position=Decimal("5"))
        assert not would_create_cycle(probe, [first.pk, second.pk])

    def test_a_longer_loop_is_caught(self, mcu):
        first = make_entry(mcu, "A")
        second = make_entry(mcu, "B")
        third = make_entry(mcu, "C")
        second.prerequisites.add(first)
        third.prerequisites.add(second)

        # A after C closes A -> B -> C -> A.
        assert would_create_cycle(first, [third.pk])

    def test_removing_a_prerequisite_clears_the_cycle(self, mcu, xmen):
        first = make_entry(mcu, "Avengers: Doomsday")
        second = make_entry(xmen, "Deadpool & Wolverine")
        second.prerequisites.add(first)

        # Validating `second` with an empty set must not see its stored edge.
        assert not would_create_cycle(second, [])


class TestAdminForm:
    def _form_data(self, track, **overrides):
        data = {
            "title": "The Incredible Hulk",
            "slug": "the-incredible-hulk",
            "track": track.pk,
            "media_type": "Film",
            "is_published": "on",
        }
        data.update(overrides)
        return data

    def test_insert_after_sets_the_midpoint(self, mcu):
        first = make_entry(mcu, "Iron Man")
        make_entry(mcu, "Iron Man 2")

        form = WatchEntryAdminForm(data=self._form_data(mcu, insert_after=first.pk))
        assert form.is_valid(), form.errors
        entry = form.save()
        assert entry.position == Decimal("15")

    def test_blank_insert_after_appends(self, mcu):
        make_entry(mcu, "Iron Man")
        make_entry(mcu, "Iron Man 2")

        form = WatchEntryAdminForm(data=self._form_data(mcu))
        assert form.is_valid(), form.errors
        assert form.save().position == Decimal("30")

    def test_insert_after_an_entry_in_another_track_is_rejected(self, mcu, xmen):
        other = make_entry(xmen, "X-Men")

        form = WatchEntryAdminForm(data=self._form_data(mcu, insert_after=other.pk))
        assert not form.is_valid()
        assert "insert_after" in form.errors

    def test_appending_after_a_prerequisite_is_fine(self, mcu):
        make_entry(mcu, "Iron Man")
        late = make_entry(mcu, "Avengers: Doomsday")

        # The new entry appends past Doomsday, so requiring Doomsday is legal.
        form = WatchEntryAdminForm(data=self._form_data(mcu, prerequisites=[late.pk]))
        assert form.is_valid(), form.errors

    def test_cyclic_prerequisite_is_rejected(self, mcu):
        early = make_entry(mcu, "Iron Man")
        late = make_entry(mcu, "Avengers: Doomsday")
        late.prerequisites.add(early)

        # Doomsday already states it comes after Iron Man, so Iron Man cannot
        # also come after Doomsday.
        form = WatchEntryAdminForm(
            instance=early,
            data=self._form_data(mcu, title="Iron Man", slug="iron-man", prerequisites=[late.pk]),
        )
        assert not form.is_valid()
        assert "prerequisites" in form.errors

    def test_a_prerequisite_against_the_list_order_is_accepted(self, mcu):
        """Story order beats list order; only a real loop is refused."""
        early = make_entry(mcu, "X-Men Origins: Wolverine")
        late = make_entry(mcu, "X-Men: First Class")

        form = WatchEntryAdminForm(
            instance=early,
            data=self._form_data(
                mcu, title="X-Men Origins: Wolverine", slug="x-men-origins-wolverine",
                prerequisites=[late.pk],
            ),
        )
        assert form.is_valid(), form.errors

    def test_editing_keeps_position_when_insert_after_is_blank(self, mcu):
        make_entry(mcu, "Iron Man")
        entry = make_entry(mcu, "Hulk")

        form = WatchEntryAdminForm(
            instance=entry,
            data=self._form_data(mcu, title="Hulk", slug="hulk"),
        )
        assert form.is_valid(), form.errors
        assert form.save().position == Decimal("20")


class TestPosterLinking:
    """The link_watch_posters command against the real filename conventions."""

    @pytest.fixture
    def poster_dir(self, tmp_path, monkeypatch):
        directory = tmp_path / "watch-order"
        directory.mkdir()
        monkeypatch.setattr("connections.poster_matching.POSTER_DIR", directory)
        return directory

    def run(self, **options):
        from django.core.management import call_command

        output = StringIO()
        call_command("link_watch_posters", stdout=output, **options)
        return output.getvalue()

    def test_matches_title_and_year_to_a_filename(self, mcu, poster_dir):
        (poster_dir / "spider-man_no_way_home_2021.jpg").touch()
        entry = make_entry(mcu, "Spider-Man: No Way Home", release_year=2021)

        self.run(apply=True)

        entry.refresh_from_db()
        assert entry.poster_path == "watch-order/spider-man_no_way_home_2021.jpg"

    def test_matches_a_short_title(self, mcu, poster_dir):
        (poster_dir / "x2_2003.jpg").touch()
        entry = make_entry(mcu, "X2", release_year=2003)

        self.run(apply=True)

        entry.refresh_from_db()
        assert entry.poster_path == "watch-order/x2_2003.jpg"

    def test_falls_back_to_a_filename_without_a_year(self, mcu, poster_dir):
        (poster_dir / "the_amazing_spider-man.png").touch()
        entry = make_entry(mcu, "The Amazing Spider-Man", release_year=2012)

        self.run(apply=True)

        entry.refresh_from_db()
        assert entry.poster_path == "watch-order/the_amazing_spider-man.png"

    def test_dry_run_writes_nothing(self, mcu, poster_dir):
        (poster_dir / "iron_man_2008.jpeg").touch()
        entry = make_entry(mcu, "Iron Man", release_year=2008)

        output = self.run()

        entry.refresh_from_db()
        assert entry.poster_path == ""
        assert "Dry run" in output

    def test_ambiguous_matches_are_not_assigned(self, mcu, poster_dir):
        (poster_dir / "the_falcon_and_the_winter_soldier_2021.jpg").touch()
        (poster_dir / "the_falcon_and_the_winter_soldier_2021.png").touch()
        entry = make_entry(mcu, "The Falcon and the Winter Soldier", release_year=2021)

        output = self.run(apply=True)

        entry.refresh_from_db()
        assert entry.poster_path == ""
        assert "ambiguous" in output

    def test_reports_entries_with_no_file(self, mcu, poster_dir):
        make_entry(mcu, "Avengers: Doomsday", release_year=2026)

        output = self.run()

        assert "no poster file" in output
        assert "Avengers: Doomsday" in output

    def test_reports_unreferenced_files(self, mcu, poster_dir):
        (poster_dir / "elektra_2005.jpg").touch()

        output = self.run()

        assert "no entry references" in output
        assert "elektra_2005.jpg" in output

    def test_existing_poster_paths_are_left_alone(self, mcu, poster_dir):
        (poster_dir / "iron_man_2008.jpeg").touch()
        entry = make_entry(mcu, "Iron Man", release_year=2008, poster_path="custom.jpg")

        self.run(apply=True)

        entry.refresh_from_db()
        assert entry.poster_path == "watch-order/custom.jpg"


class TestPosterAutofill:
    """The admin form fills poster_path from the committed files on save."""

    @pytest.fixture
    def poster_dir(self, tmp_path, monkeypatch):
        directory = tmp_path / "watch-order"
        directory.mkdir()
        monkeypatch.setattr("connections.poster_matching.POSTER_DIR", directory)
        return directory

    def _form_data(self, track, title, slug, **overrides):
        data = {
            "title": title,
            "slug": slug,
            "track": track.pk,
            "media_type": "Film",
            "is_published": "on",
        }
        data.update(overrides)
        return data

    def test_saving_finds_the_poster_without_typing_a_path(self, mcu, poster_dir):
        (poster_dir / "spider-man_no_way_home_2021.jpg").touch()

        form = WatchEntryAdminForm(
            data=self._form_data(mcu, "Spider-Man: No Way Home", "no-way-home", release_year=2021)
        )
        assert form.is_valid(), form.errors
        assert form.save().poster_path == "watch-order/spider-man_no_way_home_2021.jpg"

    def test_an_apostrophe_in_the_title_still_matches(self, mcu, poster_dir):
        # "Marvel's" -> marvels_, not "marvel s".
        (poster_dir / "marvels_daredevil_2015.png").touch()

        form = WatchEntryAdminForm(
            data=self._form_data(mcu, "Marvel's Daredevil", "daredevil", release_year=2015)
        )
        assert form.is_valid(), form.errors
        assert form.save().poster_path == "watch-order/marvels_daredevil_2015.png"

    def test_a_hand_picked_path_is_never_overwritten(self, mcu, poster_dir):
        (poster_dir / "iron_man_2008.jpeg").touch()

        form = WatchEntryAdminForm(
            data=self._form_data(
                mcu, "Iron Man", "iron-man", release_year=2008, poster_path="watch-order/custom.png"
            )
        )
        assert form.is_valid(), form.errors
        assert form.save().poster_path == "watch-order/custom.png"

    def test_no_matching_file_leaves_it_blank(self, mcu, poster_dir):
        form = WatchEntryAdminForm(
            data=self._form_data(mcu, "Avengers: Doomsday", "doomsday", release_year=2026)
        )
        assert form.is_valid(), form.errors
        assert form.save().poster_path == ""

    def test_an_ambiguous_title_is_left_for_a_human(self, mcu, poster_dir):
        (poster_dir / "the_falcon_and_the_winter_soldier_2021.jpg").touch()
        (poster_dir / "the_falcon_and_the_winter_soldier_2021.png").touch()

        form = WatchEntryAdminForm(
            data=self._form_data(
                mcu, "The Falcon and the Winter Soldier", "falcon-winter-soldier", release_year=2021
            )
        )
        assert form.is_valid(), form.errors
        assert form.save().poster_path == ""


class TestPosterTokenMatching:
    """Titles that don't spell the filename exactly still find their poster."""

    @pytest.fixture
    def poster_dir(self, tmp_path, monkeypatch):
        directory = tmp_path / "watch-order"
        directory.mkdir()
        monkeypatch.setattr("connections.poster_matching.POSTER_DIR", directory)
        for name in [
            "marvels_daredevil_2015.png",
            "marvels_daredevil_2015_-_season_1.png",
            "marvels_daredevil_2015_-_season_2.png",
            "daredevil_2003.png",
            "iron_man_2008.jpeg",
            "iron_man_2_2010.jpeg",
        ]:
            (directory / name).touch()
        return directory

    def match(self, title, year=None):
        from connections.poster_matching import find_poster

        return find_poster(title, year)

    def test_a_season_title_without_the_studio_prefix_matches(self, poster_dir):
        assert self.match("Daredevil Season 1", 2015) == "watch-order/marvels_daredevil_2015_-_season_1.png"

    def test_seasons_stay_distinct(self, poster_dir):
        assert self.match("Daredevil Season 2", 2015) == "watch-order/marvels_daredevil_2015_-_season_2.png"

    def test_the_bare_series_title_prefers_the_series_poster(self, poster_dir):
        # Every season file also contains "daredevil"; the one with the least
        # left over after the title must win.
        assert self.match("Daredevil", 2015) == "watch-order/marvels_daredevil_2015.png"

    def test_the_year_separates_the_film_from_the_series(self, poster_dir):
        assert self.match("Daredevil", 2003) == "watch-order/daredevil_2003.png"

    def test_a_title_is_not_swallowed_by_its_sequel(self, poster_dir):
        assert self.match("Iron Man", 2008) == "watch-order/iron_man_2008.jpeg"
        assert self.match("Iron Man 2", 2010) == "watch-order/iron_man_2_2010.jpeg"

    def test_an_unrelated_title_still_finds_nothing(self, poster_dir):
        assert self.match("Avengers: Doomsday", 2026) is None

    def test_a_genuine_tie_is_left_alone(self, poster_dir):
        (poster_dir / "echo_2024.png").touch()
        (poster_dir / "echo_2024.jpg").touch()
        assert self.match("Echo", 2024) is None


class TestAdminPagesLoad:
    """The admin pages must actually render.

    Regression guard: `format_html()` with no arguments raises in Django 6, which
    took down the entry changelist for every entry whose poster file existed.
    """

    @pytest.fixture
    def entries(self, mcu, tmp_path, monkeypatch):
        directory = tmp_path / "watch-order"
        directory.mkdir()
        (directory / "iron_man_2008.jpeg").touch()
        monkeypatch.setattr("connections.poster_matching.POSTER_DIR", directory)
        return [
            make_entry(mcu, "Iron Man", poster_path="watch-order/iron_man_2008.jpeg"),
            make_entry(mcu, "Hulk", poster_path="watch-order/not_committed_yet.png"),
            make_entry(mcu, "Thor"),
        ]

    @pytest.mark.parametrize(
        "url",
        [
            "/admin/connections/watchentry/",
            "/admin/connections/watchtrack/",
            "/admin/connections/watchcollection/",
            "/admin/connections/watchprogress/",
        ],
    )
    def test_changelists_render(self, client, superuser, entries, url):
        client.force_login(superuser)
        assert client.get(url).status_code == 200

    def test_the_add_form_renders(self, client, superuser, entries):
        client.force_login(superuser)
        assert client.get("/admin/connections/watchentry/add/").status_code == 200

    def test_the_change_form_renders_every_poster_state(self, client, superuser, entries):
        client.force_login(superuser)
        for entry in entries:
            response = client.get(f"/admin/connections/watchentry/{entry.pk}/change/")
            assert response.status_code == 200, entry.title


class TestManualPosition:
    """Position must be editable by hand; the helpers are a convenience, not a cage."""

    def _form_data(self, track, **overrides):
        data = {
            "title": "The Incredible Hulk",
            "slug": "the-incredible-hulk",
            "track": track.pk,
            "media_type": "Film",
            "is_published": "on",
        }
        data.update(overrides)
        return data

    def test_the_field_is_editable(self, mcu):
        form = WatchEntryAdminForm()
        assert not form.fields["position"].disabled

    def test_a_typed_position_is_used(self, mcu):
        make_entry(mcu, "Iron Man")

        form = WatchEntryAdminForm(data=self._form_data(mcu, position="17.5"))
        assert form.is_valid(), form.errors
        assert form.save().position == Decimal("17.5")

    def test_a_typed_position_can_be_changed_on_an_existing_entry(self, mcu):
        make_entry(mcu, "Iron Man")
        entry = make_entry(mcu, "Hulk")

        form = WatchEntryAdminForm(
            instance=entry,
            data=self._form_data(mcu, title="Hulk", slug="hulk", position="5"),
        )
        assert form.is_valid(), form.errors
        assert form.save().position == Decimal("5")

    def test_insert_after_still_wins_when_both_are_given(self, mcu):
        first = make_entry(mcu, "Iron Man")
        make_entry(mcu, "Iron Man 2")

        form = WatchEntryAdminForm(
            data=self._form_data(mcu, position="999", insert_after=first.pk)
        )
        assert form.is_valid(), form.errors
        assert form.save().position == Decimal("15")

    def test_blank_position_still_appends(self, mcu):
        make_entry(mcu, "Iron Man")
        make_entry(mcu, "Hulk")

        form = WatchEntryAdminForm(data=self._form_data(mcu))
        assert form.is_valid(), form.errors
        assert form.save().position == Decimal("30")

    def test_editing_without_touching_position_keeps_it(self, mcu):
        make_entry(mcu, "Iron Man")
        entry = make_entry(mcu, "Hulk")

        form = WatchEntryAdminForm(
            instance=entry, data=self._form_data(mcu, title="Hulk", slug="hulk")
        )
        assert form.is_valid(), form.errors
        assert form.save().position == Decimal("20")


class TestPosterAcronymsAndRanges:
    """Poster matching across spelled-out acronyms and partial-season entries."""

    @pytest.fixture
    def poster_dir(self, tmp_path, monkeypatch):
        directory = tmp_path / "watch-order"
        directory.mkdir()
        monkeypatch.setattr("connections.poster_matching.POSTER_DIR", directory)
        for name in [
            "marvels_agents_of_s.h.i.e.l.d._2013.png",
            "marvels_agents_of_s.h.i.e.l.d._2013_-_season_1.png",
            "marvels_agents_of_s.h.i.e.l.d._2013_-_season_2.png",
            "iron_man_2008.jpeg",
        ]:
            (directory / name).touch()
        return directory

    def match(self, title, year=None):
        from connections.poster_matching import find_poster

        return find_poster(title, year)

    def test_a_spelled_out_acronym_matches_the_plain_spelling(self, poster_dir):
        assert self.match("Agents of Shield Season 1") == (
            "watch-order/marvels_agents_of_s.h.i.e.l.d._2013_-_season_1.png"
        )

    def test_the_dotted_spelling_still_matches(self, poster_dir):
        assert self.match("Agents of S.H.I.E.L.D. Season 1") == (
            "watch-order/marvels_agents_of_s.h.i.e.l.d._2013_-_season_1.png"
        )

    def test_an_episode_range_gets_the_season_poster(self, poster_dir):
        assert self.match("Agents of Shield Season 1 Ep 1-7") == (
            "watch-order/marvels_agents_of_s.h.i.e.l.d._2013_-_season_1.png"
        )

    def test_two_ranges_in_one_season_share_a_poster(self, poster_dir):
        assert self.match("Agents of Shield Season 1 Ep 1-7") == self.match(
            "Agents of Shield Season 1 Ep 8-13"
        )

    def test_seasons_stay_distinct_under_a_range(self, poster_dir):
        assert self.match("Agents of Shield Season 2 Ep 1-5") == (
            "watch-order/marvels_agents_of_s.h.i.e.l.d._2013_-_season_2.png"
        )

    def test_indexing_a_file_twice_does_not_make_it_ambiguous(self, poster_dir):
        """The acronym file is indexed under both spellings; that is one match."""
        assert self.match("Agents of Shield") is not None

    def test_films_are_unaffected(self, poster_dir):
        assert self.match("Iron Man", 2008) == "watch-order/iron_man_2008.jpeg"
