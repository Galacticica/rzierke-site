"""
File: test_bible_verses.py
Description: Unit tests for ministry.utils.bible_verses: reference parsing,
JSON data loading/integrity, theme lookup, random picking, and the cached
bible-api.com fetch.
"""

import requests
from django.utils.text import slugify

from ministry.utils.bible_verses import (
    fetch_verse,
    get_theme,
    load_verse_data,
    pick_random_reference,
    reference_to_api_query,
)


class TestReferenceToApiQuery:
    def test_hyphenated_book_name(self):
        assert reference_to_api_query("1-John:4:7-12") == "1 John 4:7-12"

    def test_simple_book_name(self):
        assert reference_to_api_query("John:3:16") == "John 3:16"


class TestLoadVerseData:
    def test_parses_real_json_into_categories(self):
        categories = load_verse_data()
        assert len(categories) > 0
        for category in categories:
            assert category["slug"] == slugify(category["name"])
            assert len(category["themes"]) > 0
            for theme in category["themes"]:
                assert theme["slug"] == slugify(theme["name"])
                assert len(theme["verses"]) >= 1

    def test_all_references_are_parseable(self):
        """Data-integrity guard: every ref in the JSON must fit book:chapter:verses."""
        for category in load_verse_data():
            for theme in category["themes"]:
                for ref in theme["verses"]:
                    query = reference_to_api_query(ref)
                    assert query.strip()


class TestGetTheme:
    def test_known_slugs_return_category_and_theme(self):
        first_category = load_verse_data()[0]
        first_theme = first_category["themes"][0]

        found = get_theme(first_category["slug"], first_theme["slug"])

        assert found is not None
        category, theme = found
        assert category["name"] == first_category["name"]
        assert theme["name"] == first_theme["name"]

    def test_unknown_category_returns_none(self):
        assert get_theme("no-such-category", "love") is None

    def test_unknown_theme_returns_none(self):
        real_category = load_verse_data()[0]
        assert get_theme(real_category["slug"], "no-such-theme") is None


class TestPickRandomReference:
    def test_excluded_reference_is_never_picked(self):
        theme = {"verses": ["John:3:16", "Romans:5:8"]}
        for _ in range(10):
            assert pick_random_reference(theme, exclude="John:3:16") == "Romans:5:8"

    def test_single_reference_theme_ignores_exclude(self):
        theme = {"verses": ["John:3:16"]}
        assert pick_random_reference(theme, exclude="John:3:16") == "John:3:16"


class TestFetchVerse:
    def test_success_returns_normalized_verse(self, mock_bible_api):
        mock_bible_api.return_value.json.return_value = {
            "reference": "John 3:16",
            "text": "For God so\n loved   the\r\nworld ",
            "translation_name": "WEB",
        }

        verse = fetch_verse("John:3:16")

        assert verse == {
            "reference": "John 3:16",
            "text": "For God so loved the world",
            "translation_name": "WEB",
        }
        assert set(verse.keys()) == {"reference", "text", "translation_name"}

    def test_second_call_is_served_from_cache(self, mock_bible_api):
        first = fetch_verse("John:3:16")
        second = fetch_verse("John:3:16")

        assert first == second
        assert mock_bible_api.call_count == 1

    def test_connection_error_returns_none_and_is_not_cached(self, mock_bible_api):
        mock_bible_api.side_effect = requests.ConnectionError("boom")

        assert fetch_verse("John:3:16") is None
        assert fetch_verse("John:3:16") is None
        assert mock_bible_api.call_count == 2

    def test_missing_text_key_returns_none(self, mock_bible_api):
        mock_bible_api.return_value.json.return_value = {
            "reference": "John 3:16",
            "translation_name": "WEB",
        }
        assert fetch_verse("John:3:16") is None

    def test_missing_reference_key_returns_none(self, mock_bible_api):
        mock_bible_api.return_value.json.return_value = {
            "text": "For God so loved the world",
            "translation_name": "WEB",
        }
        assert fetch_verse("John:3:16") is None

    def test_requested_url_is_percent_encoded(self, mock_bible_api):
        fetch_verse("1-John:4:7-12")

        url = mock_bible_api.call_args[0][0]
        # quote() escapes spaces and colons (safe defaults to "/"):
        assert url == "https://bible-api.com/1%20John%204%3A7-12"
