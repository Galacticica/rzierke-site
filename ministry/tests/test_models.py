"""
File: test_models.py
Description: Unit tests for the ministry models: Song slug generation,
SongQuerySet.search, Devotion date ordering, and PlaylistQuerySet.search.
"""

import datetime

import pytest

from ministry.models import Artist, Devotion, Playlist, Song

pytestmark = pytest.mark.django_db


class TestSongSlug:
    def test_slug_generated_from_title(self):
        song = Song.objects.create(title="Amazing Grace")
        assert song.slug == "amazing-grace"

    def test_collision_appends_numeric_suffix(self):
        first = Song.objects.create(title="Amazing Grace")
        second = Song.objects.create(title="Amazing Grace")
        third = Song.objects.create(title="Amazing Grace")

        assert first.slug == "amazing-grace"
        assert second.slug == "amazing-grace-2"
        assert third.slug == "amazing-grace-3"

    def test_slug_not_regenerated_when_title_changes(self):
        song = Song.objects.create(title="Amazing Grace")
        song.title = "A Totally Different Title"
        song.save()
        song.refresh_from_db()
        assert song.slug == "amazing-grace"

    def test_symbol_only_title_falls_back_to_song(self):
        song = Song.objects.create(title="!!!")
        assert song.slug == "song"

    def test_long_title_truncated_with_suffix_fits_max_length(self):
        long_title = "a" * 200
        first = Song.objects.create(title=long_title)
        second = Song.objects.create(title=long_title)

        assert first.slug == "a" * 200
        assert second.slug == "a" * 200 + "-2"
        assert len(second.slug) <= 220


class TestSongSearch:
    def test_matches_title_icontains(self):
        Song.objects.create(title="Amazing Grace")
        Song.objects.create(title="How Great Thou Art")

        results = Song.objects.search("amazing")
        assert list(results.values_list("title", flat=True)) == ["Amazing Grace"]

    def test_matches_artist_name(self):
        song = Song.objects.create(title="Oceans")
        song.artist.add(Artist.objects.create(name="Hillsong United"))
        Song.objects.create(title="Other Song")

        results = Song.objects.search("hillsong")
        assert list(results) == [song]

    def test_matches_lsb_number(self):
        song = Song.objects.create(title="Amazing Grace", lsb_number="744")
        Song.objects.create(title="Other Song")

        results = Song.objects.search("744")
        assert list(results) == [song]

    def test_matches_ccli_number(self):
        song = Song.objects.create(title="Oceans", ccli_number="6428767")
        Song.objects.create(title="Other Song")

        results = Song.objects.search("6428767")
        assert list(results) == [song]

    def test_blank_query_returns_all(self):
        Song.objects.create(title="One")
        Song.objects.create(title="Two")

        assert Song.objects.search("").count() == 2
        assert Song.objects.search("   ").count() == 2

    def test_none_query_returns_all(self):
        Song.objects.create(title="One")
        assert Song.objects.search(None).count() == 1

    def test_two_matching_artists_yield_song_once(self):
        song = Song.objects.create(title="Duet")
        song.artist.add(
            Artist.objects.create(name="Smith Band"),
            Artist.objects.create(name="Smith Trio"),
        )

        results = Song.objects.search("smith")
        assert list(results) == [song]


class TestDevotionOrdering:
    def test_order_by_date_newest_and_oldest(self):
        old = Devotion.objects.create(
            title="Old", content="c", date=datetime.date(2026, 1, 1)
        )
        new = Devotion.objects.create(
            title="New", content="c", date=datetime.date(2026, 6, 1)
        )

        assert list(Devotion.objects.order_by_date(newest_first=True)) == [new, old]
        assert list(Devotion.objects.order_by_date(newest_first=False)) == [old, new]


class TestPlaylistSearch:
    def test_matches_name(self):
        lent = Playlist.objects.create(
            name="Lent 2026", description="Songs for Lent", spotify_playlist_id="abc1"
        )
        Playlist.objects.create(
            name="Advent", description="Christmas prep", spotify_playlist_id="abc2"
        )

        assert list(Playlist.objects.search("lent 2026")) == [lent]

    def test_matches_description(self):
        Playlist.objects.create(
            name="Lent 2026", description="Songs for Lent", spotify_playlist_id="abc1"
        )
        advent = Playlist.objects.create(
            name="Advent", description="Christmas prep", spotify_playlist_id="abc2"
        )

        assert list(Playlist.objects.search("christmas")) == [advent]

    def test_blank_query_returns_all(self):
        Playlist.objects.create(name="A", description="d", spotify_playlist_id="a1")
        Playlist.objects.create(name="B", description="d", spotify_playlist_id="b1")

        assert Playlist.objects.search("").count() == 2
        assert Playlist.objects.search(None).count() == 2
