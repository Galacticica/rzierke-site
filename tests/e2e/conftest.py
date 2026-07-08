"""
File: conftest.py
Description: Fixtures for the Playwright e2e suite. Run with:
    npm run build
    uv run pytest -m e2e --ds=conf.settings_e2e
Every test here gets the `e2e` marker automatically. OpenAI and
bible-api.com are faked in-process (the live_server thread shares this
process, so monkeypatching module attributes reaches the request handlers).
"""

import os
from unittest.mock import MagicMock

import pytest
from django.conf import settings
from django.test import Client

# Playwright's sync API drives an event loop in the test process, which trips
# Django's async-unsafe guard on ORM access. The DB calls here are genuinely
# synchronous (test fixtures), so allow them. Playwright docs recommend this
# for Django integration.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")


def pytest_collection_modifyitems(items):
    for item in items:
        if "tests/e2e" in str(item.fspath).replace("\\", "/"):
            item.add_marker(pytest.mark.e2e)


@pytest.fixture(autouse=True, scope="session")
def _require_e2e_settings():
    """Skip the whole e2e package (instead of erroring test-by-test on broken
    assets) when run without the e2e settings or a Vite build."""
    vite = settings.DJANGO_VITE["default"]
    if vite.get("dev_mode"):
        pytest.skip(
            "e2e tests need built assets: run with --ds=conf.settings_e2e "
            "(and `npm run build` first)"
        )
    manifest = vite["manifest_path"]
    if not manifest.exists():
        pytest.skip(f"Vite manifest missing at {manifest}: run `npm run build` first")


@pytest.fixture(autouse=True)
def fake_openai(monkeypatch):
    """Deterministic AI replies; asserts in specs match these exact strings."""

    def chat_create(**kwargs):
        input_items = kwargs.get("input") or []
        last_user = next(
            (item["content"] for item in reversed(input_items) if item.get("role") == "user"),
            "",
        )
        response = MagicMock()
        response.output_text = f"FAKE-AI reply to: {last_user}"
        return response

    chat_client = MagicMock()
    chat_client.responses.create.side_effect = chat_create

    title_client = MagicMock()
    title_client.responses.create.return_value.output_text = "Test Chat Title"

    monkeypatch.setattr("chatbot.helpers.get_prompt.client", chat_client)
    monkeypatch.setattr("chatbot.helpers.get_convo_title.client", title_client)


@pytest.fixture(autouse=True)
def fake_bible_api(monkeypatch):
    """RandomVerseView calls fetch_verse server-side; never hit the network."""
    monkeypatch.setattr(
        "ministry.views.fetch_verse",
        lambda ref: {
            "reference": "John 3:16",
            "text": "For God so loved the world that he gave his only Son.",
            "translation_name": "WEB",
        },
    )


@pytest.fixture
def user(db):
    from accounts.models import User

    return User.objects.create_user(
        email="e2e@example.com", password="password123", first_name="E2E", last_name="Tester"
    )


@pytest.fixture
def gpt_creator_user(db):
    from accounts.models import User

    return User.objects.create_user(
        email="e2e-creator@example.com", password="password123", gpt_creator=True
    )


@pytest.fixture
def login(context, live_server):
    """Cookie-injection login (fast path). Real form login is exercised once
    in test_auth.py; everything else logs in by copying the session cookie
    from a force_login'd django test client into the browser context."""

    def _login(user):
        client = Client()
        client.force_login(user)
        session_cookie = client.cookies[settings.SESSION_COOKIE_NAME]
        context.add_cookies(
            [
                {
                    "name": settings.SESSION_COOKIE_NAME,
                    "value": session_cookie.value,
                    "url": live_server.url,
                }
            ]
        )
        return user

    return _login


@pytest.fixture
def ai_model(db):
    from chatbot.models import AIModel, AIQuirk

    quirk = AIQuirk.objects.create(name="Friendly", description="Keeps a warm tone.")
    model = AIModel.objects.create(name="Test Model", description="A model for e2e tests.")
    model.quirk.add(quirk)
    return model


@pytest.fixture
def songs(db):
    """30 songs across 2 artists and 2 tags so pagination (25/page) kicks in."""
    from ministry.models import Artist, Song, Tag

    hymnal = Artist.objects.create(name="Hymnal Writers")
    modern = Artist.objects.create(name="Modern Worship")
    classic = Tag.objects.create(name="Classic")
    upbeat = Tag.objects.create(name="Upbeat")

    created = []
    for i in range(1, 31):
        song = Song.objects.create(title=f"Song Number {i:02d}")
        song.artist.add(hymnal if i % 2 else modern)
        song.tag.add(classic if i % 2 else upbeat)
        created.append(song)
    return created


@pytest.fixture
def characters(db):
    """Start—Hub—Finish chain so the shortest path has one intermediate node."""
    from connections.models import Character, Relationship

    start = Character.objects.create(name="Start Hero")
    hub = Character.objects.create(name="Hub Hero")
    finish = Character.objects.create(name="Finish Hero")
    Relationship.objects.create(
        character1=start, character2=hub, relationship_type="Ally", directional=False
    )
    Relationship.objects.create(
        character1=hub, character2=finish, relationship_type="Ally", directional=False
    )
    return {"start": start, "hub": hub, "finish": finish}
