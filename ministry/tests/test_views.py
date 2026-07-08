"""
File: test_views.py
Description: View tests for the ministry app: song list (HTMX variants,
pagination, counts), song detail, devotions ordering, playlists, and the
Bible verse pages.
"""

import datetime

import pytest
from django.urls import reverse

from ministry.models import Devotion, Playlist, Song
from ministry.utils.bible_verses import load_verse_data

pytestmark = pytest.mark.django_db


def template_names(response):
    return [t.name for t in response.templates]


class TestSongListView:
    url = reverse("song-list")

    def test_full_page_uses_song_list_template(self, client):
        response = client.get(self.url)
        assert response.status_code == 200
        assert "ministry/song_list.html" in template_names(response)

    def test_htmx_request_returns_results_partial(self, client, htmx_headers):
        response = client.get(self.url, **htmx_headers)
        assert response.status_code == 200
        names = template_names(response)
        assert "ministry/partials/song_results.html" in names
        assert "ministry/song_list.html" not in names

    def test_htmx_song_layout_target_returns_layout_partial(self, client, htmx_headers):
        response = client.get(
            self.url, **htmx_headers, HTTP_HX_TARGET="song-layout"
        )
        assert response.status_code == 200
        names = template_names(response)
        assert "ministry/partials/song_layout.html" in names
        # The layout partial includes song_results.html, but the full page
        # template must not be rendered.
        assert "ministry/song_list.html" not in names


class TestSongListPagination:
    url = reverse("song-list")

    @pytest.fixture
    def songs(self):
        return [Song.objects.create(title=f"Song {i:02d}") for i in range(26)]

    def test_first_page_has_25_songs(self, client, songs):
        response = client.get(self.url)
        assert len(response.context["songs"]) == 25

    def test_second_page_has_remaining_song(self, client, songs):
        response = client.get(self.url, {"page": "2"})
        assert response.status_code == 200
        assert len(response.context["songs"]) == 1

    def test_invalid_page_falls_back_gracefully(self, client, songs):
        response = client.get(self.url, {"page": "notanumber"})
        assert response.status_code == 200
        assert len(response.context["songs"]) == 25
        assert response.context["page_obj"].number == 1


class TestSongListCounts:
    url = reverse("song-list")

    def test_total_vs_filtered_count_with_query(self, client):
        Song.objects.create(title="Amazing Grace")
        Song.objects.create(title="How Great Thou Art")

        response = client.get(self.url, {"q": "amazing"})

        assert response.context["total_count"] == 2
        assert response.context["filtered_count"] == 1
        assert response.context["q"] == "amazing"


class TestSongDetailView:
    def test_detail_by_slug(self, client, song):
        response = client.get(reverse("song-detail", args=[song.slug]))
        assert response.status_code == 200
        assert response.context["song"] == song

    def test_unknown_slug_404s(self, client):
        response = client.get(reverse("song-detail", args=["no-such-song"]))
        assert response.status_code == 404


class TestDevotionsView:
    url = reverse("devotions")

    @pytest.fixture
    def devotions(self):
        old = Devotion.objects.create(
            title="Old", content="c", date=datetime.date(2026, 1, 1)
        )
        new = Devotion.objects.create(
            title="New", content="c", date=datetime.date(2026, 6, 1)
        )
        return old, new

    def test_default_order_is_newest_first(self, client, devotions):
        old, new = devotions
        response = client.get(self.url)
        assert list(response.context["devotions"]) == [new, old]
        assert response.context["order"] == "newest"

    def test_oldest_order(self, client, devotions):
        old, new = devotions
        response = client.get(self.url, {"order": "oldest"})
        assert list(response.context["devotions"]) == [old, new]
        assert response.context["order"] == "oldest"

    def test_invalid_order_defaults_to_newest(self, client, devotions):
        old, new = devotions
        response = client.get(self.url, {"order": "bogus"})
        assert list(response.context["devotions"]) == [new, old]
        assert response.context["order"] == "newest"

    def test_htmx_returns_section_partial(self, client, devotions, htmx_headers):
        response = client.get(self.url, **htmx_headers)
        names = template_names(response)
        assert "ministry/partials/devos_section.html" in names
        assert "ministry/devos.html" not in names


class TestPlaylistsView:
    def test_playlists_ordered_by_name(self, client):
        zebra = Playlist.objects.create(
            name="Zebra", description="d", spotify_playlist_id="z1"
        )
        alpha = Playlist.objects.create(
            name="Alpha", description="d", spotify_playlist_id="a1"
        )

        response = client.get(reverse("playlists"))
        assert response.status_code == 200
        assert list(response.context["playlists"]) == [alpha, zebra]


class TestVersesView:
    def test_context_contains_categories(self, client):
        response = client.get(reverse("verses"))
        assert response.status_code == 200
        categories = response.context["categories"]
        assert len(categories) > 0
        assert "slug" in categories[0]


class TestRandomVerseView:
    @pytest.fixture
    def theme_url(self):
        category = load_verse_data()[0]
        theme = category["themes"][0]
        return reverse("verse-random", args=[category["slug"], theme["slug"]])

    @pytest.fixture
    def patched_verse(self, monkeypatch):
        """Patch the names imported into ministry.views; record pick calls."""
        calls = {}

        def fake_pick(theme, exclude=None):
            calls["theme"] = theme
            calls["exclude"] = exclude
            return "John:3:16"

        verse = {
            "reference": "John 3:16",
            "text": "For God so loved the world",
            "translation_name": "WEB",
        }
        monkeypatch.setattr("ministry.views.pick_random_reference", fake_pick)
        monkeypatch.setattr("ministry.views.fetch_verse", lambda ref: verse)
        calls["verse"] = verse
        return calls

    def test_unknown_category_404s(self, client):
        url = reverse("verse-random", args=["no-such-category", "no-such-theme"])
        assert client.get(url).status_code == 404

    def test_unknown_theme_404s(self, client):
        category = load_verse_data()[0]
        url = reverse("verse-random", args=[category["slug"], "no-such-theme"])
        assert client.get(url).status_code == 404

    def test_htmx_returns_verse_card_with_context(
        self, client, htmx_headers, theme_url, patched_verse
    ):
        response = client.get(theme_url, **htmx_headers)

        assert response.status_code == 200
        assert "ministry/partials/verse_card.html" in template_names(response)
        assert response.context["verse"] == patched_verse["verse"]
        assert response.context["ref"] == "John:3:16"

    def test_full_page_includes_categories(self, client, theme_url, patched_verse):
        response = client.get(theme_url)

        assert response.status_code == 200
        assert "ministry/verses.html" in template_names(response)
        assert len(response.context["categories"]) > 0

    def test_current_param_forwarded_as_exclude(
        self, client, htmx_headers, theme_url, patched_verse
    ):
        client.get(theme_url, {"current": "Romans:5:8"}, **htmx_headers)
        assert patched_verse["exclude"] == "Romans:5:8"

    def test_missing_current_means_no_exclude(
        self, client, htmx_headers, theme_url, patched_verse
    ):
        client.get(theme_url, **htmx_headers)
        assert patched_verse["exclude"] is None

    def test_fetch_verse_none_still_renders(
        self, client, htmx_headers, theme_url, monkeypatch
    ):
        monkeypatch.setattr(
            "ministry.views.pick_random_reference", lambda theme, exclude=None: "John:3:16"
        )
        monkeypatch.setattr("ministry.views.fetch_verse", lambda ref: None)

        response = client.get(theme_url, **htmx_headers)
        assert response.status_code == 200
        assert response.context["verse"] is None
