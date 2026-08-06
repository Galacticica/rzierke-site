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
def superuser(db):
    from accounts.models import User

    return User.objects.create_superuser(email="e2e-admin@example.com", password="password123")


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
def watch_order(db):
    """Two lanes that converge.

    MCU: Iron Man -> Avengers -> Doomsday (3 deep).
    X-Men: X-Men -> X2 -> Deadpool & Wolverine (also 3 deep).

    Deadpool & Wolverine is a prerequisite of Doomsday. The X-Men lane is
    deliberately long enough that the merge pushes Doomsday a row *past* where
    its own track chain would put it, so hiding the X-Men lane visibly moves it
    back up.
    """
    from connections.models import WatchCollection, WatchEntry, WatchTrack

    mcu = WatchTrack.objects.create(name="MCU", slug="mcu", lane_order=0, color="#8B5CF6")
    xmen = WatchTrack.objects.create(name="Fox X-Men", slug="fox-x-men", lane_order=1, color="#22D3EE")

    entries = {
        "iron_man": WatchEntry.objects.create(
            track=mcu, title="Iron Man", slug="iron-man", release_year=2008, runtime_minutes=126
        ),
        "avengers": WatchEntry.objects.create(
            track=mcu, title="The Avengers", slug="the-avengers", release_year=2012, runtime_minutes=143
        ),
        "doomsday": WatchEntry.objects.create(
            track=mcu, title="Avengers: Doomsday", slug="doomsday", release_year=2026, runtime_minutes=150
        ),
        "xmen": WatchEntry.objects.create(
            track=xmen, title="X-Men", slug="x-men", release_year=2000, runtime_minutes=104
        ),
        "x2": WatchEntry.objects.create(
            track=xmen, title="X2", slug="x2", release_year=2003, runtime_minutes=134
        ),
        "deadpool": WatchEntry.objects.create(
            track=xmen, title="Deadpool & Wolverine", slug="deadpool-wolverine",
            release_year=2024, runtime_minutes=128,
        ),
    }
    entries["doomsday"].prerequisites.add(entries["deadpool"])

    # A collection holding two entries from the same lane with a hole between
    # them, and nothing else. Doomsday's only prerequisite is outside the
    # collection, so the lane chain is the sole thing keeping the two apart -
    # rebuild it wrong and they land on the same row in the same column.
    prep = WatchCollection.objects.create(name="Doomsday Prep", slug="doomsday-prep")
    prep.entries.add(entries["iron_man"], entries["doomsday"])

    entries["tracks"] = {"mcu": mcu, "xmen": xmen}
    entries["collection"] = prep
    return entries


@pytest.fixture
def continued_sagas(db):
    """Infinity Saga continuing into Multiverse Saga, plus a parallel X-Men lane."""
    from connections.models import WatchEntry, WatchTrack

    infinity = WatchTrack.objects.create(
        name="Infinity Saga", slug="infinity-saga", lane_order=0, color="#8B5CF6"
    )
    multiverse = WatchTrack.objects.create(
        name="Multiverse Saga", slug="multiverse-saga", lane_order=1, color="#22D3EE",
        continues_from=infinity,
    )
    xmen = WatchTrack.objects.create(
        name="Fox X-Men", slug="fox-x-men", lane_order=2, color="#F97316"
    )

    def entry(track, title, slug, year):
        return WatchEntry.objects.create(
            track=track, title=title, slug=slug, release_year=year, runtime_minutes=120
        )

    return {
        "iron_man": entry(infinity, "Iron Man", "iron-man", 2008),
        "gotg2": entry(infinity, "Guardians of the Galaxy Vol. 2", "gotg-2", 2017),
        "groot": entry(multiverse, "I Am Groot", "i-am-groot", 2022),
        "wakanda": entry(multiverse, "Eyes of Wakanda", "eyes-of-wakanda", 2025),
        "xmen": entry(xmen, "X-Men", "x-men", 2000),
    }


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
