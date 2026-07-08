"""
File: test_filters.py
Description: Unit tests for ministry.filters.SongFilter: the free-text q
filter, the lsb_only checkbox, and the artist/tag multi-select filters.
"""

import pytest

from ministry.filters import SongFilter
from ministry.models import Artist, Song, Tag

pytestmark = pytest.mark.django_db


def filtered(data):
    return SongFilter(data, queryset=Song.objects.all()).qs


class TestQFilter:
    def test_q_delegates_to_search(self):
        Song.objects.create(title="Amazing Grace")
        Song.objects.create(title="How Great Thou Art")

        results = filtered({"q": "amazing"})
        assert list(results.values_list("title", flat=True)) == ["Amazing Grace"]

    def test_q_matches_artist_name(self):
        song = Song.objects.create(title="Oceans")
        song.artist.add(Artist.objects.create(name="Hillsong United"))
        Song.objects.create(title="Other")

        assert list(filtered({"q": "hillsong"})) == [song]

    def test_empty_data_returns_all(self):
        Song.objects.create(title="One")
        Song.objects.create(title="Two")

        assert filtered({}).count() == 2


class TestLsbOnlyFilter:
    def test_lsb_only_excludes_null_and_empty_lsb(self):
        with_lsb = Song.objects.create(title="Hymn", lsb_number="744")
        Song.objects.create(title="No LSB", lsb_number=None)
        Song.objects.create(title="Empty LSB", lsb_number="")

        results = filtered({"lsb_only": "true"})
        assert list(results) == [with_lsb]

    def test_lsb_only_unchecked_returns_all(self):
        Song.objects.create(title="Hymn", lsb_number="744")
        Song.objects.create(title="No LSB", lsb_number=None)

        assert filtered({}).count() == 2


class TestArtistFilter:
    def test_single_artist_filters_songs(self):
        artist = Artist.objects.create(name="Hillsong")
        other = Artist.objects.create(name="Elevation")
        song = Song.objects.create(title="Oceans")
        song.artist.add(artist)
        other_song = Song.objects.create(title="Graves")
        other_song.artist.add(other)

        results = filtered({"artist": [str(artist.pk)]})
        assert list(results) == [song]

    def test_multiple_artists_are_or_combined(self):
        a1 = Artist.objects.create(name="Hillsong")
        a2 = Artist.objects.create(name="Elevation")
        s1 = Song.objects.create(title="Oceans")
        s1.artist.add(a1)
        s2 = Song.objects.create(title="Graves")
        s2.artist.add(a2)
        Song.objects.create(title="Unrelated")

        results = filtered({"artist": [str(a1.pk), str(a2.pk)]})
        assert set(results) == {s1, s2}

    def test_song_with_both_selected_artists_appears_once(self):
        a1 = Artist.objects.create(name="Hillsong")
        a2 = Artist.objects.create(name="Elevation")
        song = Song.objects.create(title="Collab")
        song.artist.add(a1, a2)

        results = filtered({"artist": [str(a1.pk), str(a2.pk)]})
        assert list(results) == [song]


class TestTagFilter:
    def test_tag_filters_songs(self):
        tag = Tag.objects.create(name="Christmas")
        song = Song.objects.create(title="Silent Night")
        song.tag.add(tag)
        Song.objects.create(title="Untagged")

        results = filtered({"tag": [str(tag.pk)]})
        assert list(results) == [song]

    def test_multiple_tags_are_or_combined(self):
        t1 = Tag.objects.create(name="Christmas")
        t2 = Tag.objects.create(name="Easter")
        s1 = Song.objects.create(title="Silent Night")
        s1.tag.add(t1)
        s2 = Song.objects.create(title="In Christ Alone")
        s2.tag.add(t2)
        Song.objects.create(title="Neither")

        results = filtered({"tag": [str(t1.pk), str(t2.pk)]})
        assert set(results) == {s1, s2}


class TestCombinedFilters:
    def test_q_and_lsb_only_combine(self):
        keep = Song.objects.create(title="Amazing Grace", lsb_number="744")
        Song.objects.create(title="Amazing Love")  # matches q, no LSB
        Song.objects.create(title="Other Hymn", lsb_number="801")  # LSB, no q match

        results = filtered({"q": "amazing", "lsb_only": "true"})
        assert list(results) == [keep]
