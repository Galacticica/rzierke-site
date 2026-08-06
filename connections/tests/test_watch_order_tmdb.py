"""Tests for TMDB metadata lookups.

The network is never touched: `connections.tmdb.requests.get` is monkeypatched
with a fake router, the same approach the ministry bible-api tests use.
"""

from unittest.mock import MagicMock

import pytest
from django.core.management import call_command
from io import StringIO

from connections import tmdb
from connections.models import WatchEntry, WatchTrack

MOVIE_SEARCH = {"results": [{"id": 1726, "title": "Iron Man"}]}
MOVIE_DETAIL = {"release_date": "2008-05-02", "runtime": 126}

TV_SEARCH = {"results": [{"id": 61889, "name": "Marvel's Daredevil"}]}
TV_DETAIL = {"first_air_date": "2015-04-10", "episode_run_time": [54], "number_of_episodes": 39}
TV_SEASON = {
    "air_date": "2015-04-10",
    "episodes": [{"runtime": 50}, {"runtime": 54}, {"runtime": 55}] * 4 + [{"runtime": 53}],
}


@pytest.fixture(autouse=True)
def tmdb_key(settings):
    settings.TMDB_API_KEY = "test-key"


@pytest.fixture
def fake_tmdb(monkeypatch):
    """Route TMDB paths to canned payloads and record the calls."""
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append((url, params or {}))
        response = MagicMock()
        response.raise_for_status.return_value = None

        if "/search/movie" in url:
            response.json.return_value = MOVIE_SEARCH
        elif "/search/tv" in url:
            response.json.return_value = TV_SEARCH
        elif "/season/" in url:
            response.json.return_value = TV_SEASON
        elif "/tv/" in url:
            response.json.return_value = TV_DETAIL
        elif "/movie/" in url:
            response.json.return_value = MOVIE_DETAIL
        else:
            response.json.return_value = {}
        return response

    monkeypatch.setattr("connections.tmdb.requests.get", fake_get)
    return calls


@pytest.fixture
def track(db):
    return WatchTrack.objects.create(name="MCU", slug="mcu")


class TestSeasonParsing:
    @pytest.mark.parametrize(
        "title,expected",
        [
            ("Daredevil Season 1", ("Daredevil", 1)),
            ("Loki - Season 2", ("Loki", 2)),
            ("Hawkeye: Season 1", ("Hawkeye", 1)),
            ("Agents of S.H.I.E.L.D. Season 7", ("Agents of S.H.I.E.L.D.", 7)),
            ("Iron Man", ("Iron Man", None)),
            ("Spider-Man 2", ("Spider-Man 2", None)),
        ],
    )
    def test_splits_a_season_suffix(self, title, expected):
        assert tmdb.split_season(title) == expected

    def test_a_film_with_a_number_is_not_a_season(self):
        """'Spider-Man 3' must not be read as season 3."""
        assert tmdb.split_season("Spider-Man 3") == ("Spider-Man 3", None)


class TestFetchMetadata:
    def test_a_film_gets_year_and_runtime(self, fake_tmdb):
        metadata = tmdb.fetch_metadata("Iron Man", media_type="Film")

        assert metadata["release_year"] == 2008
        assert metadata["runtime_minutes"] == 126
        assert metadata["episode_count"] is None
        assert metadata["tmdb_type"] == "movie"

    def test_a_season_gets_its_own_episode_count(self, fake_tmdb):
        metadata = tmdb.fetch_metadata("Daredevil Season 1", media_type="Series")

        assert metadata["tmdb_season"] == 1
        assert metadata["episode_count"] == 13
        assert metadata["tmdb_type"] == "tv"

    def test_a_season_runtime_is_per_episode(self, fake_tmdb):
        """total_minutes multiplies runtime by episodes, so this must not be a total."""
        metadata = tmdb.fetch_metadata("Daredevil Season 1", media_type="Series")

        assert metadata["runtime_minutes"] == 53  # mean of the season's episodes

    def test_a_whole_series_uses_the_show_totals(self, fake_tmdb):
        metadata = tmdb.fetch_metadata("Daredevil", media_type="Series")

        assert metadata["tmdb_season"] is None
        assert metadata["episode_count"] == 39
        assert metadata["release_year"] == 2015

    def test_a_season_title_is_treated_as_tv_whatever_the_media_type(self, fake_tmdb):
        metadata = tmdb.fetch_metadata("Daredevil Season 1", media_type="Film")
        assert metadata["tmdb_type"] == "tv"

    def test_a_stored_id_skips_the_search(self, fake_tmdb):
        tmdb.fetch_metadata("Whatever", media_type="Film", tmdb_id=1726, tmdb_type="movie")

        assert not any("/search/" in url for url, _ in fake_tmdb)

    def test_no_result_raises(self, monkeypatch):
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"results": []}
        monkeypatch.setattr("connections.tmdb.requests.get", lambda *a, **k: response)

        with pytest.raises(tmdb.TMDBError, match="Nothing on TMDB matched"):
            tmdb.fetch_metadata("Not A Real Film")

    def test_a_missing_key_raises_rather_than_calling_out(self, settings, monkeypatch):
        settings.TMDB_API_KEY = ""
        monkeypatch.setattr(
            "connections.tmdb.requests.get",
            lambda *a, **k: pytest.fail("must not hit the network without a key"),
        )

        with pytest.raises(tmdb.TMDBError, match="TMDB_API_KEY"):
            tmdb.fetch_metadata("Iron Man")

    def test_a_network_error_becomes_a_tmdb_error(self, monkeypatch):
        import requests

        def boom(*args, **kwargs):
            raise requests.ConnectionError("no route to host")

        monkeypatch.setattr("connections.tmdb.requests.get", boom)

        with pytest.raises(tmdb.TMDBError, match="TMDB request failed"):
            tmdb.fetch_metadata("Iron Man")


class TestApplyToEntry:
    def test_fills_blank_fields(self, track, fake_tmdb):
        entry = WatchEntry.objects.create(track=track, title="Iron Man", slug="iron-man")

        changed = tmdb.apply_to_entry(entry)

        entry.refresh_from_db()
        assert entry.release_year == 2008
        assert entry.runtime_minutes == 126
        assert "release_year" in changed

    def test_does_not_clobber_hand_entered_values(self, track, fake_tmdb):
        entry = WatchEntry.objects.create(
            track=track, title="Iron Man", slug="iron-man", release_year=1999, runtime_minutes=99
        )

        tmdb.apply_to_entry(entry)

        entry.refresh_from_db()
        assert entry.release_year == 1999
        assert entry.runtime_minutes == 99

    def test_overwrite_replaces_them(self, track, fake_tmdb):
        entry = WatchEntry.objects.create(
            track=track, title="Iron Man", slug="iron-man", release_year=1999, runtime_minutes=99
        )

        tmdb.apply_to_entry(entry, overwrite=True)

        entry.refresh_from_db()
        assert entry.release_year == 2008
        assert entry.runtime_minutes == 126

    def test_records_the_tmdb_identity_for_later_corrections(self, track, fake_tmdb):
        entry = WatchEntry.objects.create(track=track, title="Daredevil Season 1", slug="dd-s1")

        tmdb.apply_to_entry(entry)

        entry.refresh_from_db()
        assert (entry.tmdb_id, entry.tmdb_type, entry.tmdb_season) == (61889, "tv", 1)

    def test_a_season_entry_totals_correctly(self, track, fake_tmdb):
        entry = WatchEntry.objects.create(
            track=track, title="Daredevil Season 1", slug="dd-s1", media_type="Series"
        )

        tmdb.apply_to_entry(entry)

        entry.refresh_from_db()
        assert entry.episode_count == 13
        assert entry.total_minutes == 13 * 53

    def test_save_false_leaves_the_database_alone(self, track, fake_tmdb):
        entry = WatchEntry.objects.create(track=track, title="Iron Man", slug="iron-man")

        tmdb.apply_to_entry(entry, save=False)

        assert entry.release_year == 2008
        assert WatchEntry.objects.get(pk=entry.pk).release_year is None


class TestCommand:
    def run(self, **options):
        output = StringIO()
        call_command("fetch_watch_metadata", stdout=output, **options)
        return output.getvalue()

    def test_backfills_entries(self, track, fake_tmdb):
        entry = WatchEntry.objects.create(track=track, title="Iron Man", slug="iron-man")

        output = self.run()

        entry.refresh_from_db()
        assert entry.release_year == 2008
        assert "1 updated" in output

    def test_dry_run_saves_nothing(self, track, fake_tmdb):
        entry = WatchEntry.objects.create(track=track, title="Iron Man", slug="iron-man")

        output = self.run(dry_run=True)

        entry.refresh_from_db()
        assert entry.release_year is None
        assert "Dry run" in output

    def test_a_failed_lookup_does_not_stop_the_rest(self, track, monkeypatch):
        WatchEntry.objects.create(track=track, title="Bad", slug="bad")
        good = WatchEntry.objects.create(track=track, title="Iron Man", slug="iron-man")

        def fake_get(url, params=None, timeout=None):
            response = MagicMock()
            response.raise_for_status.return_value = None
            if "/search/" in url and params.get("query") == "Bad":
                response.json.return_value = {"results": []}
            elif "/search/" in url:
                response.json.return_value = MOVIE_SEARCH
            else:
                response.json.return_value = MOVIE_DETAIL
            return response

        monkeypatch.setattr("connections.tmdb.requests.get", fake_get)

        output = self.run()

        good.refresh_from_db()
        assert good.release_year == 2008
        assert "1 updated" in output and "1 failed" in output

    def test_without_a_key_it_refuses_instead_of_silently_doing_nothing(self, track, settings):
        from django.core.management.base import CommandError

        settings.TMDB_API_KEY = ""
        with pytest.raises(CommandError, match="TMDB_API_KEY"):
            self.run()


class TestAdminAutoFetch:
    """Creating an entry in the admin looks up its metadata; failure never blocks the save."""

    def _post(self, client, track, **overrides):
        data = {
            "title": "Iron Man",
            "slug": "iron-man",
            "track": track.pk,
            "media_type": "Film",
            "is_published": "on",
            "_save": "Save",
        }
        data.update(overrides)
        return client.post("/admin/connections/watchentry/add/", data, follow=True)

    def test_creating_an_entry_fills_metadata(self, client, superuser, track, fake_tmdb):
        client.force_login(superuser)

        self._post(client, track)

        entry = WatchEntry.objects.get(slug="iron-man")
        assert entry.release_year == 2008
        assert entry.runtime_minutes == 126

    def test_a_season_entry_fills_its_episode_count(self, client, superuser, track, fake_tmdb):
        client.force_login(superuser)

        self._post(client, track, title="Daredevil Season 1", slug="dd-s1", media_type="Series")

        entry = WatchEntry.objects.get(slug="dd-s1")
        assert entry.episode_count == 13
        assert entry.tmdb_season == 1

    def test_a_tmdb_failure_still_saves_the_entry(self, client, superuser, track, monkeypatch):
        """The whole point of fetching after the save: TMDB must never block adding a film."""
        import requests

        def boom(*args, **kwargs):
            raise requests.ConnectionError("down")

        monkeypatch.setattr("connections.tmdb.requests.get", boom)
        client.force_login(superuser)

        response = self._post(client, track)

        assert WatchEntry.objects.filter(slug="iron-man").exists()
        assert b"TMDB lookup failed" in response.content

    def test_no_key_means_no_lookup_and_no_error(self, client, superuser, track, settings, monkeypatch):
        settings.TMDB_API_KEY = ""
        monkeypatch.setattr(
            "connections.tmdb.requests.get",
            lambda *a, **k: pytest.fail("must not hit the network without a key"),
        )
        client.force_login(superuser)

        self._post(client, track)

        assert WatchEntry.objects.filter(slug="iron-man").exists()

    def test_a_missing_key_says_so_instead_of_skipping_silently(
        self, client, superuser, track, settings
    ):
        """Silence here reads as "the feature is broken" - it has to explain itself."""
        settings.TMDB_API_KEY = ""
        client.force_login(superuser)

        response = self._post(client, track)

        assert b"add TMDB_API_KEY" in response.content

    def test_no_nagging_when_everything_was_typed_in(self, client, superuser, track, settings):
        settings.TMDB_API_KEY = ""
        client.force_login(superuser)

        response = self._post(client, track, release_year=2008, runtime_minutes=126)

        assert b"TMDB_API_KEY" not in response.content

    def test_a_title_tmdb_cannot_find_says_so(self, client, superuser, track, monkeypatch):
        response_stub = MagicMock()
        response_stub.raise_for_status.return_value = None
        response_stub.json.return_value = {"results": []}
        monkeypatch.setattr("connections.tmdb.requests.get", lambda *a, **k: response_stub)
        client.force_login(superuser)

        response = self._post(client, track, title="Not A Real Film", slug="nope")

        assert WatchEntry.objects.filter(slug="nope").exists()
        assert b"TMDB lookup failed" in response.content

    def test_editing_an_existing_entry_does_not_refetch(self, client, superuser, track, fake_tmdb):
        """Only creation triggers a lookup, so ordinary edits stay offline."""
        client.force_login(superuser)
        self._post(client, track)
        fake_tmdb.clear()

        entry = WatchEntry.objects.get(slug="iron-man")
        client.post(
            f"/admin/connections/watchentry/{entry.pk}/change/",
            {
                "title": "Iron Man", "slug": "iron-man", "track": track.pk,
                "media_type": "Film", "is_published": "on",
                "release_year": 2008, "runtime_minutes": 126, "_save": "Save",
            },
            follow=True,
        )

        assert fake_tmdb == []


class TestCorrectingAWrongMatch:
    """Fixing tmdb_id then re-fetching must actually replace the bad values."""

    @pytest.fixture
    def wrongly_matched(self, track, fake_tmdb):
        """An entry carrying values from a bad match."""
        return WatchEntry.objects.create(
            track=track, title="Iron Man", slug="iron-man",
            release_year=1951, runtime_minutes=42, tmdb_id=999, tmdb_type="movie",
        )

    def _run_action(self, client, entry, action):
        return client.post(
            "/admin/connections/watchentry/",
            {"action": action, "_selected_action": [str(entry.pk)]},
            follow=True,
        )

    def test_the_plain_action_cannot_fix_it(self, client, superuser, wrongly_matched, fake_tmdb):
        client.force_login(superuser)

        self._run_action(client, wrongly_matched, "fetch_tmdb_metadata")

        wrongly_matched.refresh_from_db()
        assert wrongly_matched.release_year == 1951, "blank-only fill must leave it alone"

    def test_the_replace_action_fixes_it(self, client, superuser, wrongly_matched, fake_tmdb):
        client.force_login(superuser)
        wrongly_matched.tmdb_id = 1726  # the id corrected by hand
        wrongly_matched.save()

        self._run_action(client, wrongly_matched, "refetch_tmdb_metadata")

        wrongly_matched.refresh_from_db()
        assert wrongly_matched.release_year == 2008
        assert wrongly_matched.runtime_minutes == 126

    def test_a_corrected_id_is_used_instead_of_searching(self, client, superuser, wrongly_matched, fake_tmdb):
        client.force_login(superuser)
        wrongly_matched.tmdb_id = 1726
        wrongly_matched.save()
        fake_tmdb.clear()

        self._run_action(client, wrongly_matched, "refetch_tmdb_metadata")

        assert not any("/search/" in url for url, _ in fake_tmdb)
        assert any("/movie/1726" in url for url, _ in fake_tmdb)

    def test_the_plain_action_points_at_the_replace_one(self, client, superuser, wrongly_matched, fake_tmdb):
        client.force_login(superuser)

        response = self._run_action(client, wrongly_matched, "fetch_tmdb_metadata")

        assert b"Re-fetch from TMDB" in response.content


class TestEpisodeRanges:
    """An entry covering part of a season counts and times only those episodes."""

    @pytest.fixture
    def numbered_season(self, monkeypatch):
        """A 13-episode season where each episode's runtime is 40 + its number."""
        season = {
            "air_date": "2013-09-24",
            "episodes": [
                {"episode_number": number, "runtime": 40 + number, "air_date": f"2013-09-{number:02d}"}
                for number in range(1, 14)
            ],
        }

        def fake_get(url, params=None, timeout=None):
            response = MagicMock()
            response.raise_for_status.return_value = None
            if "/search/" in url:
                response.json.return_value = TV_SEARCH
            elif "/season/" in url:
                response.json.return_value = season
            else:
                response.json.return_value = TV_DETAIL
            return response

        monkeypatch.setattr("connections.tmdb.requests.get", fake_get)

    def test_counts_only_the_episodes_in_range(self, numbered_season):
        metadata = tmdb.fetch_metadata("Agents of Shield Season 1 Ep 1-7", media_type="Series")

        assert metadata["episode_count"] == 7

    def test_runtime_is_the_mean_of_just_those_episodes(self, numbered_season):
        metadata = tmdb.fetch_metadata("Agents of Shield Season 1 Ep 1-7", media_type="Series")

        # Episodes 1-7 run 41..47, mean 44 - not the whole season's 47.
        assert metadata["runtime_minutes"] == 44

    def test_a_later_range_differs_from_an_earlier_one(self, numbered_season):
        first = tmdb.fetch_metadata("Agents of Shield Season 1 Ep 1-7", media_type="Series")
        second = tmdb.fetch_metadata("Agents of Shield Season 1 Ep 8-13", media_type="Series")

        assert second["episode_count"] == 6
        assert second["runtime_minutes"] != first["runtime_minutes"]

    def test_a_single_episode(self, numbered_season):
        metadata = tmdb.fetch_metadata("Agents of Shield Season 1 Ep 4", media_type="Series")

        assert metadata["episode_count"] == 1
        assert metadata["runtime_minutes"] == 44

    def test_no_range_covers_the_whole_season(self, numbered_season):
        metadata = tmdb.fetch_metadata("Agents of Shield Season 1", media_type="Series")

        assert metadata["episode_count"] == 13

    def test_the_stored_season_is_recorded(self, numbered_season):
        metadata = tmdb.fetch_metadata("Agents of Shield Season 1 Ep 1-7", media_type="Series")

        assert metadata["tmdb_season"] == 1
        assert metadata["tmdb_type"] == "tv"

    def test_total_minutes_reflects_only_the_range(self, track, numbered_season):
        entry = WatchEntry.objects.create(
            track=track, title="Agents of Shield Season 1 Ep 1-7",
            slug="aos-s1-e1-7", media_type="Series",
        )

        tmdb.apply_to_entry(entry)

        entry.refresh_from_db()
        assert entry.total_minutes == 7 * 44

    def test_a_season_named_in_the_title_beats_a_stale_stored_one(self, numbered_season, track):
        """Retitling to another season must not keep looking up the old one."""
        entry = WatchEntry.objects.create(
            track=track, title="Agents of Shield Season 1", slug="aos", media_type="Series",
            tmdb_season=4,
        )

        metadata = tmdb.fetch_metadata(
            entry.title, media_type="Series", tmdb_id=entry.tmdb_id, season=entry.tmdb_season
        )

        assert metadata["tmdb_season"] == 1
