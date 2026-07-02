"""
File: bible_verses.py
Author: Reagan Zierke
Date: 2026-07-02
Description: Loads themed Bible verse references from JSON and fetches verse
text from bible-api.com, memoized through the Django cache.
"""

import json
import logging
import random
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

import requests
from django.core.cache import cache
from django.utils.text import slugify

logger = logging.getLogger(__name__)

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "bible_verses.json"
BIBLE_API_BASE = "https://bible-api.com/"
CACHE_TTL = 60 * 60 * 24 * 30  # verse text never changes
REQUEST_TIMEOUT = 6


@lru_cache(maxsize=1)
def load_verse_data():
    """
    Parse bible_verses.json once per process into an ordered list of
    categories, each with slugified themes:
    [{"name", "slug", "themes": [{"name", "slug", "verses": [...]}]}]
    """
    with open(DATA_PATH, encoding="utf-8") as f:
        raw = json.load(f)

    categories = []
    for category_name, themes in raw.items():
        categories.append({
            "name": category_name,
            "slug": slugify(category_name),
            "themes": [
                {"name": theme_name, "slug": slugify(theme_name), "verses": refs}
                for theme_name, refs in themes.items()
            ],
        })
    return categories


def get_categories():
    return load_verse_data()


def get_theme(category_slug, theme_slug):
    """Return (category, theme) dicts, or None if either slug is unknown."""
    for category in get_categories():
        if category["slug"] == category_slug:
            for theme in category["themes"]:
                if theme["slug"] == theme_slug:
                    return category, theme
    return None


def pick_random_reference(theme, exclude=None):
    """Random ref from the theme, avoiding an immediate repeat when possible."""
    refs = theme["verses"]
    candidates = [ref for ref in refs if ref != exclude] or refs
    return random.choice(candidates)


def reference_to_api_query(ref):
    """Convert '1-John:4:7-12' to the human form bible-api.com expects: '1 John 4:7-12'."""
    book, chapter, verses = ref.split(":", 2)
    return f"{book.replace('-', ' ')} {chapter}:{verses}"


def fetch_verse(ref):
    """
    Return {"reference", "text", "translation_name"} for a ref like
    'John:3:16', using the Django cache. Returns None on API failure.
    """
    cache_key = f"bible_verse:{ref}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    url = BIBLE_API_BASE + quote(reference_to_api_query(ref))
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        verse = {
            "reference": data["reference"],
            "text": " ".join(data["text"].split()),
            "translation_name": data.get("translation_name", ""),
        }
    except (requests.RequestException, KeyError, ValueError) as exc:
        logger.warning("bible-api.com fetch failed for %s: %s", ref, exc)
        return None

    cache.set(cache_key, verse, CACHE_TTL)
    return verse
