"""
File: conftest.py
Description: Shared pytest fixtures for the whole test suite: users, HTMX
headers, OpenAI/bible-api mocks, and common ministry model setups.
"""

from unittest.mock import MagicMock

import pytest
from django.core.cache import cache

from ministry.utils.bible_verses import load_verse_data


@pytest.fixture(autouse=True)
def _clear_cache():
    """The locmem cache and the verse-data lru_cache leak between tests."""
    yield
    cache.clear()
    load_verse_data.cache_clear()


@pytest.fixture
def user(db):
    from accounts.models import User

    return User.objects.create_user(email="user@example.com", password="password123")


@pytest.fixture
def gpt_creator_user(db):
    from accounts.models import User

    return User.objects.create_user(
        email="creator@example.com", password="password123", gpt_creator=True
    )


@pytest.fixture
def superuser(db):
    from accounts.models import User

    return User.objects.create_superuser(email="admin@example.com", password="password123")


@pytest.fixture
def auth_client(client, user):
    client.force_login(user)
    return client


@pytest.fixture
def htmx_headers():
    return {"HTTP_HX_REQUEST": "true"}


@pytest.fixture
def mock_openai(monkeypatch):
    """Replace the module-level OpenAI clients with a mock.

    The clients are created at import time in both helper modules, so tests
    must patch the module attribute (never rely on OPENAI_API_KEY being
    absent). Yields the mock; set
    ``mock.responses.create.return_value.output_text`` to change the reply.
    """
    mock = MagicMock()
    mock.responses.create.return_value.output_text = "AI response"
    monkeypatch.setattr("chatbot.helpers.get_prompt.client", mock)
    monkeypatch.setattr("chatbot.helpers.get_convo_title.client", mock)
    return mock


@pytest.fixture
def no_openai(monkeypatch):
    """Simulate a missing API key: both module-level clients are None."""
    monkeypatch.setattr("chatbot.helpers.get_prompt.client", None)
    monkeypatch.setattr("chatbot.helpers.get_convo_title.client", None)


@pytest.fixture
def mock_bible_api(monkeypatch):
    """Patch requests.get in the bible_verses module. Yields the mock."""
    mock_get = MagicMock()
    mock_get.return_value.json.return_value = {
        "reference": "John 3:16",
        "text": "For God so loved the world",
        "translation_name": "WEB",
    }
    monkeypatch.setattr("ministry.utils.bible_verses.requests.get", mock_get)
    return mock_get


@pytest.fixture
def song(db):
    from ministry.models import Song

    return Song.objects.create(title="Amazing Grace", lsb_number="744")


@pytest.fixture
def song_with_arrangement(db):
    """Song with two sections and an arrangement: verse once, chorus twice.

    The verse's lyrics hold two slide blocks (blank-line separated), the
    chorus one block, so PPTX lyric slides = 1*2 + 2*1 = 4.
    """
    from ministry.models import ArrangementItem, SectionDefinition, Song

    song = Song.objects.create(title="Amazing Grace", lsb_number="744")
    verse = SectionDefinition.objects.create(
        song=song,
        section_type=SectionDefinition.VERSE,
        name="Verse 1",
        lyrics="Amazing grace how sweet the sound\nThat saved a wretch like me\n\nI once was lost but now am found\nWas blind but now I see",
    )
    chorus = SectionDefinition.objects.create(
        song=song,
        section_type=SectionDefinition.CHORUS,
        name="Chorus",
        lyrics="My chains are gone\nI've been set free",
    )
    ArrangementItem.objects.create(song=song, section=verse, order=1, repeat_count=1)
    ArrangementItem.objects.create(song=song, section=chorus, order=2, repeat_count=2)
    return song
