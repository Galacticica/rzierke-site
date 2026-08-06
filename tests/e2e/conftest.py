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
def long_lane(db):
    """One lane of 9 entries, so wrapping can be turned on and observed."""
    from connections.models import WatchEntry, WatchTrack

    saga = WatchTrack.objects.create(name="Saga", slug="saga", lane_order=0, color="#8B5CF6")
    return [
        WatchEntry.objects.create(
            track=saga, title=f"Film {number}", slug=f"film-{number}",
            release_year=2000 + number, runtime_minutes=120,
        )
        for number in range(1, 10)
    ]


@pytest.fixture
def fan_out(db):
    """The Defenders, then its four follow-up seasons, then Punisher S2.

    All four seasons name The Defenders as their prerequisite, so they are
    branches: they belong side by side on one row, not stacked in single file.
    """
    from connections.models import WatchEntry, WatchTrack

    netflix = WatchTrack.objects.create(
        name="Netflix", slug="netflix", lane_order=0, color="#F97316"
    )

    def entry(title, slug):
        return WatchEntry.objects.create(
            track=netflix, title=title, slug=slug, media_type="Series",
            runtime_minutes=54, episode_count=13,
        )

    defenders = entry("The Defenders", "defenders")
    branches = [
        entry("Daredevil Season 3", "dd-s3"),
        entry("Jessica Jones Season 3", "jj-s3"),
        entry("Luke Cage Season 2", "lc-s2"),
        entry("Iron Fist Season 2", "if-s2"),
    ]
    for branch in branches:
        branch.prerequisites.add(defenders)

    punisher = entry("The Punisher Season 2", "punisher-s2")
    return {"defenders": defenders, "branches": branches, "punisher": punisher}


@pytest.fixture
def fan_in(db):
    """Four unconnected Netflix shows all feeding The Defenders.

    Daredevil has a season 1 ahead of its season 2, so the four converging
    entries sit at different depths - they still have to end up abreast.
    """
    from connections.models import WatchEntry, WatchTrack

    netflix = WatchTrack.objects.create(
        name="Netflix", slug="netflix", lane_order=0, color="#F97316"
    )

    def entry(title, slug):
        return WatchEntry.objects.create(
            track=netflix, title=title, slug=slug, media_type="Series",
            runtime_minutes=54, episode_count=13,
        )

    dd1 = entry("Daredevil Season 1", "dd-s1")
    dd2 = entry("Daredevil Season 2", "dd-s2")
    jj1 = entry("Jessica Jones Season 1", "jj-s1")
    lc1 = entry("Luke Cage Season 1", "lc-s1")
    if1 = entry("Iron Fist Season 1", "if-s1")
    defenders = entry("The Defenders", "defenders")

    for source in (dd2, jj1, lc1, if1):
        defenders.prerequisites.add(source)

    return {"dd1": dd1, "sources": [dd2, jj1, lc1, if1], "defenders": defenders}


@pytest.fixture
def netflix_block(db):
    """The real Netflix shape: 4 shows -> Defenders -> 5 shows, plus a side branch.

    Daredevil S2 also feeds The Punisher S1, so one member of the fan-in has an
    extra outgoing edge that must not disturb the bracket.
    """
    from connections.models import WatchEntry, WatchTrack

    netflix = WatchTrack.objects.create(
        name="Netflix", slug="netflix", lane_order=0, color="#EC4899"
    )

    def entry(title, slug):
        return WatchEntry.objects.create(
            track=netflix, title=title, slug=slug, media_type="Series",
            runtime_minutes=54, episode_count=13,
        )

    dd1 = entry("Daredevil Season 1", "dd-s1")
    jj1 = entry("Jessica Jones Season 1", "jj-s1")
    dd2 = entry("Daredevil Season 2", "dd-s2")
    lc1 = entry("Luke Cage Season 1", "lc-s1")
    if1 = entry("Iron Fist Season 1", "if-s1")
    defenders = entry("The Defenders", "defenders")
    punisher1 = entry("The Punisher Season 1", "punisher-s1")

    dd2.prerequisites.add(dd1)
    for source in (jj1, dd2, lc1, if1):
        defenders.prerequisites.add(source)
    punisher1.prerequisites.add(dd2)

    after = []
    for title, slug in [
        ("Jessica Jones Season 2", "jj-s2"), ("Luke Cage Season 2", "lc-s2"),
        ("Iron Fist Season 2", "if-s2"), ("Daredevil Season 3", "dd-s3"),
        ("The Punisher Season 2", "punisher-s2"),
    ]:
        made = entry(title, slug)
        made.prerequisites.add(defenders)
        after.append(made)

    return {"first": dd1, "fan_in": [jj1, dd2, lc1, if1], "defenders": defenders, "after": after}


@pytest.fixture
def xmen_franchise(db):
    """The X-Men tangle: story order and list order disagree.

    Listed in release order, but told in story order via prerequisites:
      First Class -> Origins: Wolverine   (1962 then 1979)
      X-Men -> X2 -> The Last Stand       (the original trilogy)
      Days of Future Past follows BOTH branches.

    First Class sits *later* in the list than Origins, so the implied
    "next in the list" edge runs opposite to the stated one.
    """
    from connections.models import WatchEntry, WatchTrack

    fox = WatchTrack.objects.create(name="Fox X-Men", slug="fox", lane_order=0, color="#F97316")

    def entry(title, slug, year):
        return WatchEntry.objects.create(
            track=fox, title=title, slug=slug, release_year=year, runtime_minutes=120
        )

    # Listed in release order.
    xmen = entry("X-Men", "x-men", 2000)
    x2 = entry("X2: X-Men United", "x2", 2003)
    last_stand = entry("X-Men: The Last Stand", "last-stand", 2006)
    origins = entry("X-Men Origins: Wolverine", "origins", 2009)
    first_class = entry("X-Men: First Class", "first-class", 2011)
    dofp = entry("X-Men: Days of Future Past", "dofp", 2014)

    x2.prerequisites.add(xmen)
    last_stand.prerequisites.add(x2)
    origins.prerequisites.add(first_class)   # points backwards through the list
    dofp.prerequisites.add(last_stand, origins)

    return {
        "xmen": xmen, "x2": x2, "last_stand": last_stand,
        "origins": origins, "first_class": first_class, "dofp": dofp,
    }


@pytest.fixture
def scattered_fan_in(db):
    """A fan-in whose sources are NOT next to each other in the list.

    Real lists interleave: a Punisher season sits between two of the shows that
    feed The Defenders. The group must still be recognised as one fan.
    """
    from connections.models import WatchEntry, WatchTrack

    netflix = WatchTrack.objects.create(
        name="Netflix", slug="netflix", lane_order=0, color="#EC4899"
    )

    def entry(title, slug):
        return WatchEntry.objects.create(
            track=netflix, title=title, slug=slug, media_type="Series",
            runtime_minutes=54, episode_count=13,
        )

    jj1 = entry("Jessica Jones Season 1", "jj-s1")
    dd2 = entry("Daredevil Season 2", "dd-s2")
    filler = entry("A Standalone Special", "filler")   # <- breaks up the group
    lc1 = entry("Luke Cage Season 1", "lc-s1")
    if1 = entry("Iron Fist Season 1", "if-s1")
    defenders = entry("The Defenders", "defenders")

    for source in (jj1, dd2, lc1, if1):
        defenders.prerequisites.add(source)

    return {"sources": [jj1, dd2, lc1, if1], "filler": filler, "defenders": defenders}


@pytest.fixture
def real_shape(db):
    """The two lanes as they actually are, taken from dump_watch_order.

    Netflix: DD S1 -> {JJ S1, DD S2, LC S1, IF S1} -> Defenders -> four seasons,
    with the Punisher line running alongside off Daredevil S2.
    Fox: a straight list where Days of Future Past states First Class and The
    Last Stand - two entries four apart, so they are sequential, not parallel.
    """
    from connections.models import WatchEntry, WatchTrack

    fox = WatchTrack.objects.create(name="Fox X-Men", slug="fox", lane_order=0, color="#F97316")
    netflix = WatchTrack.objects.create(name="Netflix", slug="netflix", lane_order=1, color="#EC4899")

    def add(track, title, slug):
        return WatchEntry.objects.create(track=track, title=title, slug=slug, runtime_minutes=120)

    fc = add(fox, "First Class", "fc")
    add(fox, "Origins Wolverine", "ow")
    add(fox, "X-Men", "xm")
    x2 = add(fox, "X2", "x2")
    ls = add(fox, "The Last Stand", "ls")
    add(fox, "The Wolverine", "tw")
    dofp = add(fox, "Days of Future Past", "dofp")
    add(fox, "Apocalypse", "apoc")
    dofp.prerequisites.add(fc, ls)

    dd1 = add(netflix, "Daredevil S1", "dd1")
    jj1 = add(netflix, "Jessica Jones S1", "jj1")
    dd2 = add(netflix, "Daredevil S2", "dd2")
    lc1 = add(netflix, "Luke Cage S1", "lc1")
    if1 = add(netflix, "Iron Fist S1", "if1")
    defenders = add(netflix, "The Defenders", "dfn")
    punisher1 = add(netflix, "Punisher S1", "pn1")
    after = [add(netflix, n, s) for n, s in
             [("Jessica Jones S2", "jj2"), ("Luke Cage S2", "lc2"),
              ("Iron Fist S2", "if2"), ("Daredevil S3", "dd3")]]
    punisher2 = add(netflix, "Punisher S2", "pn2")

    dd2.prerequisites.add(dd1)
    defenders.prerequisites.add(jj1, dd2, lc1, if1)
    punisher1.prerequisites.add(dd2)
    for entry in after:
        entry.prerequisites.add(defenders)
    punisher2.prerequisites.add(punisher1)

    return {"heads": ["fc", "dd1"]}


@pytest.fixture
def long_reach(db):
    """One column where Days of Future Past reaches back to First Class.

    Six films apart in the same column, so a straight arrow between them would
    pass through every tile in between.
    """
    from connections.models import WatchEntry, WatchTrack

    fox = WatchTrack.objects.create(name="Fox X-Men", slug="fox", lane_order=0, color="#F97316")

    def add(title, slug):
        return WatchEntry.objects.create(track=fox, title=title, slug=slug, runtime_minutes=120)

    first_class = add("First Class", "fc")
    add("Origins Wolverine", "ow")
    add("X-Men", "xm")
    add("X2", "x2")
    add("The Last Stand", "ls")
    wolverine = add("The Wolverine", "tw")
    dofp = add("Days of Future Past", "dofp")
    add("Apocalypse", "apoc")

    dofp.prerequisites.add(first_class, wolverine)
    return {"first_class": first_class, "wolverine": wolverine, "dofp": dofp}


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
