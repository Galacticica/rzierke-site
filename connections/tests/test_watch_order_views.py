"""Tests for the watch-order page, payload, and watched-state endpoints."""

import json

import pytest
from django.urls import reverse

from connections.models import WatchCollection, WatchEntry, WatchProgress, WatchTrack
from connections.watch_order_service import WatchOrderService


@pytest.fixture
def tracks(db):
    return {
        "mcu": WatchTrack.objects.create(name="MCU", slug="mcu", lane_order=0, color="#8B5CF6"),
        "xmen": WatchTrack.objects.create(name="Fox X-Men", slug="fox-x-men", lane_order=1, color="#22D3EE"),
    }


@pytest.fixture
def chart(tracks):
    """Two lanes that merge: the X-Men track feeds into Doomsday on the MCU track."""
    iron_man = WatchEntry.objects.create(
        track=tracks["mcu"], title="Iron Man", slug="iron-man", release_year=2008, runtime_minutes=126
    )
    doomsday = WatchEntry.objects.create(
        track=tracks["mcu"], title="Avengers: Doomsday", slug="doomsday", release_year=2026, runtime_minutes=150
    )
    xmen = WatchEntry.objects.create(
        track=tracks["xmen"], title="X-Men", slug="x-men", release_year=2000, runtime_minutes=104
    )
    doomsday.prerequisites.add(xmen)
    return {"iron_man": iron_man, "doomsday": doomsday, "xmen": xmen}


class TestPayload:
    def test_only_merges_are_sent_as_edges(self, chart):
        """Lane chains are rebuilt client-side; sending them would break collections.

        A collection can leave a hole in a track, and a stored chain would leave
        the entries either side of the hole unconnected and stacked on one row.
        """
        payload = WatchOrderService().build_payload()

        assert {edge["kind"] for edge in payload["edges"]} == {"prerequisite"}

    def test_entries_arrive_in_track_then_position_order(self, chart):
        """The client rebuilds lane chains in one pass, which relies on this order."""
        payload = WatchOrderService().build_payload()

        slugs = [entry["slug"] for entry in payload["entries"]]
        assert slugs.index("iron-man") < slugs.index("doomsday")

    def test_prerequisites_become_edges(self, chart):
        payload = WatchOrderService().build_payload()

        assert {"source": "x-men", "target": "doomsday", "kind": "prerequisite"} in payload["edges"]

    def test_lanes_are_contiguous_over_active_tracks(self, chart, tracks):
        tracks["mcu"].lane_order = 50
        tracks["mcu"].save()

        payload = WatchOrderService().build_payload()
        assert sorted(track["lane"] for track in payload["tracks"]) == [0, 1]

    def test_unpublished_entries_are_excluded(self, chart):
        chart["iron_man"].is_published = False
        chart["iron_man"].save()

        payload = WatchOrderService().build_payload()
        slugs = {entry["slug"] for entry in payload["entries"]}
        assert "iron-man" not in slugs
        assert not any("iron-man" in (edge["source"], edge["target"]) for edge in payload["edges"])

    def test_collections_are_listed_with_their_size(self, chart):
        prep = WatchCollection.objects.create(name="Doomsday Prep", slug="doomsday-prep")
        prep.entries.add(chart["iron_man"], chart["xmen"])

        payload = WatchOrderService().build_payload()

        assert payload["collections"] == [
            {"slug": "doomsday-prep", "name": "Doomsday Prep", "description": "", "count": 2}
        ]

    def test_an_entry_carries_every_collection_it_belongs_to(self, chart):
        """A lane is exclusive, a collection is not - this is the whole point."""
        prep = WatchCollection.objects.create(name="Doomsday Prep", slug="doomsday-prep")
        essentials = WatchCollection.objects.create(name="Essentials", slug="essentials")
        chart["iron_man"].collections.add(prep, essentials)

        payload = WatchOrderService().build_payload()
        entry = next(item for item in payload["entries"] if item["slug"] == "iron-man")

        assert entry["track"] == "mcu"
        assert sorted(entry["collections"]) == ["doomsday-prep", "essentials"]

    def test_inactive_collections_are_excluded(self, chart):
        WatchCollection.objects.create(name="Draft List", slug="draft", is_active=False)

        payload = WatchOrderService().build_payload()
        assert payload["collections"] == []

    def test_changing_collection_membership_invalidates_the_cache(self, chart):
        service = WatchOrderService()
        prep = WatchCollection.objects.create(name="Doomsday Prep", slug="doomsday-prep")
        assert service.build_payload()["collections"][0]["count"] == 0

        prep.entries.add(chart["iron_man"])
        assert service.build_payload()["collections"][0]["count"] == 1

    def test_inactive_tracks_are_excluded(self, chart, tracks):
        tracks["xmen"].is_active = False
        tracks["xmen"].save()

        payload = WatchOrderService().build_payload()
        assert {track["slug"] for track in payload["tracks"]} == {"mcu"}
        # The merge edge must go too, so the client never draws a dangling arrow.
        assert not any(edge["kind"] == "prerequisite" for edge in payload["edges"])

    def test_blank_poster_serializes_as_empty_string(self, chart):
        payload = WatchOrderService().build_payload()
        entry = next(item for item in payload["entries"] if item["slug"] == "iron-man")
        assert entry["poster_url"] == ""

    def test_poster_path_becomes_a_static_url(self, chart):
        chart["iron_man"].poster_path = "iron-man.jpg"
        chart["iron_man"].save()

        payload = WatchOrderService().build_payload()
        entry = next(item for item in payload["entries"] if item["slug"] == "iron-man")
        assert entry["poster_url"].endswith("watch-order/iron-man.jpg")

    def test_saving_an_entry_invalidates_the_cache(self, chart):
        service = WatchOrderService()
        assert len(service.build_payload()["entries"]) == 3

        WatchEntry.objects.create(track=chart["iron_man"].track, title="Hulk", slug="hulk")
        assert len(service.build_payload()["entries"]) == 4

    def test_changing_prerequisites_invalidates_the_cache(self, chart):
        service = WatchOrderService()
        assert any(edge["kind"] == "prerequisite" for edge in service.build_payload()["edges"])

        chart["doomsday"].prerequisites.clear()
        assert not any(edge["kind"] == "prerequisite" for edge in service.build_payload()["edges"])


class TestPage:
    def test_renders(self, client, chart):
        response = client.get(reverse("connections-watch-order"))
        assert response.status_code == 200
        assert b"watch-order-chart" in response.content

    def test_renders_a_tile_per_entry(self, client, chart):
        response = client.get(reverse("connections-watch-order"))
        assert response.content.count(b"data-watch-entry=") == 3

    def test_empty_chart_says_so_instead_of_breaking(self, client, db):
        response = client.get(reverse("connections-watch-order"))
        assert response.status_code == 200
        assert b"No entries yet" in response.content

    def test_anonymous_watched_list_is_empty(self, client, chart):
        response = client.get(reverse("connections-watch-order"))
        assert response.context["watched_slugs"] == []

    def test_signed_in_progress_is_inlined(self, auth_client, chart, user):
        WatchProgress.objects.create(user=user, entry=chart["iron_man"])

        response = auth_client.get(reverse("connections-watch-order"))
        assert response.context["watched_slugs"] == ["iron-man"]

    def test_original_graph_page_still_resolves(self, client, db):
        assert reverse("connections-graph") == "/mcu-relationships/"


class TestWatchedEndpoint:
    def test_requires_sign_in(self, client, chart):
        response = client.post(
            reverse("watch-order-watched"),
            data=json.dumps({"slug": "iron-man", "watched": True}),
            content_type="application/json",
        )
        assert response.status_code == 401

    def test_marks_watched(self, auth_client, chart, user):
        response = auth_client.post(
            reverse("watch-order-watched"),
            data=json.dumps({"slug": "iron-man", "watched": True}),
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.json()["watched_count"] == 1
        assert WatchProgress.objects.filter(user=user, entry__slug="iron-man").exists()

    def test_marking_twice_is_idempotent(self, auth_client, chart, user):
        payload = json.dumps({"slug": "iron-man", "watched": True})
        auth_client.post(reverse("watch-order-watched"), data=payload, content_type="application/json")
        response = auth_client.post(reverse("watch-order-watched"), data=payload, content_type="application/json")

        assert response.status_code == 200
        assert WatchProgress.objects.filter(user=user).count() == 1

    def test_unmarks_watched(self, auth_client, chart, user):
        WatchProgress.objects.create(user=user, entry=chart["iron_man"])

        auth_client.post(
            reverse("watch-order-watched"),
            data=json.dumps({"slug": "iron-man", "watched": False}),
            content_type="application/json",
        )
        assert not WatchProgress.objects.filter(user=user).exists()

    def test_unknown_slug_is_404(self, auth_client, chart):
        response = auth_client.post(
            reverse("watch-order-watched"),
            data=json.dumps({"slug": "nope", "watched": True}),
            content_type="application/json",
        )
        assert response.status_code == 404

    def test_missing_slug_is_400(self, auth_client, chart):
        response = auth_client.post(
            reverse("watch-order-watched"),
            data=json.dumps({"watched": True}),
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_get_is_rejected(self, auth_client, chart):
        assert auth_client.get(reverse("watch-order-watched")).status_code == 405


class TestSyncEndpoint:
    def test_requires_sign_in(self, client, chart):
        response = client.post(
            reverse("watch-order-sync"),
            data=json.dumps({"slugs": ["iron-man"]}),
            content_type="application/json",
        )
        assert response.status_code == 401

    def test_merges_local_progress(self, auth_client, chart, user):
        response = auth_client.post(
            reverse("watch-order-sync"),
            data=json.dumps({"slugs": ["iron-man", "x-men"]}),
            content_type="application/json",
        )
        assert response.status_code == 200
        assert set(response.json()["watched"]) == {"iron-man", "x-men"}

    def test_never_removes_existing_progress(self, auth_client, chart, user):
        WatchProgress.objects.create(user=user, entry=chart["doomsday"])

        response = auth_client.post(
            reverse("watch-order-sync"),
            data=json.dumps({"slugs": ["iron-man"]}),
            content_type="application/json",
        )
        assert set(response.json()["watched"]) == {"doomsday", "iron-man"}

    def test_already_watched_slugs_do_not_conflict(self, auth_client, chart, user):
        WatchProgress.objects.create(user=user, entry=chart["iron_man"])

        response = auth_client.post(
            reverse("watch-order-sync"),
            data=json.dumps({"slugs": ["iron-man"]}),
            content_type="application/json",
        )
        assert response.status_code == 200
        assert WatchProgress.objects.filter(user=user).count() == 1

    def test_unknown_slugs_are_ignored(self, auth_client, chart, user):
        response = auth_client.post(
            reverse("watch-order-sync"),
            data=json.dumps({"slugs": ["iron-man", "does-not-exist"]}),
            content_type="application/json",
        )
        assert set(response.json()["watched"]) == {"iron-man"}

    def test_non_list_payload_is_400(self, auth_client, chart):
        response = auth_client.post(
            reverse("watch-order-sync"),
            data=json.dumps({"slugs": "iron-man"}),
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_malformed_json_is_400(self, auth_client, chart):
        response = auth_client.post(
            reverse("watch-order-sync"), data="not json", content_type="application/json"
        )
        assert response.status_code == 400


class TestTemplatesRenderClean:
    """No raw template syntax may reach the page.

    Regression guard: Django's {# #} comment is single-line only, so a multi-line
    one is not a comment at all - it renders verbatim to the visitor.
    """

    @pytest.mark.parametrize("route", ["connections-graph", "connections-watch-order"])
    def test_no_stray_template_syntax(self, client, chart, route):
        content = client.get(reverse(route)).content.decode()

        for token in ("{#", "#}", "{% comment", "{{", "{%"):
            assert token not in content, f"{token!r} leaked into {route}"


class TestContinuedTracks:
    """Two halves of one storyline share a column instead of running in parallel."""

    @pytest.fixture
    def sagas(self, db):
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
        return {"infinity": infinity, "multiverse": multiverse, "xmen": xmen}

    @pytest.fixture
    def entries(self, sagas):
        """Your case: GotG Vol 2 ends Infinity, I Am Groot starts Multiverse."""
        return {
            "gotg2": WatchEntry.objects.create(
                track=sagas["infinity"], title="Guardians of the Galaxy Vol. 2", slug="gotg-2"
            ),
            "groot": WatchEntry.objects.create(
                track=sagas["multiverse"], title="I Am Groot", slug="i-am-groot"
            ),
            "wakanda": WatchEntry.objects.create(
                track=sagas["multiverse"], title="Eyes of Wakanda", slug="eyes-of-wakanda"
            ),
            "xmen": WatchEntry.objects.create(track=sagas["xmen"], title="X-Men", slug="x-men"),
        }

    def test_continued_tracks_share_a_lane(self, entries):
        payload = WatchOrderService().build_payload()
        lanes = {track["slug"]: track["lane"] for track in payload["tracks"]}

        assert lanes["infinity-saga"] == lanes["multiverse-saga"]

    def test_an_unrelated_track_gets_its_own_lane(self, entries):
        payload = WatchOrderService().build_payload()
        lanes = {track["slug"]: track["lane"] for track in payload["tracks"]}

        assert lanes["fox-x-men"] != lanes["infinity-saga"]

    def test_the_continuing_track_follows_the_one_it_continues(self, entries):
        """Entry order drives the chain, so Infinity must come out before Multiverse."""
        payload = WatchOrderService().build_payload()
        slugs = [entry["slug"] for entry in payload["entries"]]

        assert slugs.index("gotg-2") < slugs.index("i-am-groot") < slugs.index("eyes-of-wakanda")

    def test_no_prerequisite_is_needed_across_the_handover(self, entries):
        """The whole point: the handover needs no manual link, so no stray arrow."""
        payload = WatchOrderService().build_payload()

        assert payload["edges"] == []

    def test_entries_carry_the_shared_lane(self, entries):
        payload = WatchOrderService().build_payload()
        by_slug = {entry["slug"]: entry for entry in payload["entries"]}

        assert by_slug["gotg-2"]["lane"] == by_slug["i-am-groot"]["lane"]
        assert by_slug["x-men"]["lane"] != by_slug["gotg-2"]["lane"]

    def test_each_track_keeps_its_own_color(self, entries):
        """The colour change is what makes the handover visible in one column."""
        payload = WatchOrderService().build_payload()
        by_slug = {entry["slug"]: entry for entry in payload["entries"]}

        assert by_slug["gotg-2"]["track_color"] != by_slug["i-am-groot"]["track_color"]

    def test_a_continues_from_loop_still_renders(self, sagas, entries):
        """A bad edit must not take the page down."""
        WatchTrack.objects.filter(pk=sagas["infinity"].pk).update(
            continues_from=sagas["multiverse"]
        )

        payload = WatchOrderService().build_payload()
        assert len(payload["entries"]) == 4

    def test_a_track_cannot_continue_itself(self, sagas):
        from django.core.exceptions import ValidationError

        sagas["xmen"].continues_from = sagas["xmen"]
        with pytest.raises(ValidationError):
            sagas["xmen"].full_clean()

    def test_a_loop_is_rejected(self, sagas):
        from django.core.exceptions import ValidationError

        sagas["infinity"].continues_from = sagas["multiverse"]
        with pytest.raises(ValidationError):
            sagas["infinity"].full_clean()


class TestInterleavedColumns:
    """A Multiverse entry can sit between two Infinity ones - the Black Widow case."""

    @pytest.fixture
    def sagas(self, db):
        infinity = WatchTrack.objects.create(
            name="Infinity Saga", slug="infinity-saga", lane_order=0, color="#8B5CF6"
        )
        multiverse = WatchTrack.objects.create(
            name="Multiverse Saga", slug="multiverse-saga", lane_order=1, color="#22D3EE",
            continues_from=infinity,
        )
        return infinity, multiverse

    @pytest.fixture
    def interleaved(self, sagas):
        from decimal import Decimal

        infinity, multiverse = sagas
        return {
            "civil_war": WatchEntry.objects.create(
                track=infinity, title="Captain America: Civil War", slug="civil-war",
                position=Decimal("10"),
            ),
            # Multiverse Saga by release, but set between two Infinity films.
            "black_widow": WatchEntry.objects.create(
                track=multiverse, title="Black Widow", slug="black-widow",
                position=Decimal("15"),
            ),
            "infinity_war": WatchEntry.objects.create(
                track=infinity, title="Avengers: Infinity War", slug="infinity-war",
                position=Decimal("20"),
            ),
        }

    def test_order_follows_position_not_track(self, interleaved):
        payload = WatchOrderService().build_payload()
        slugs = [entry["slug"] for entry in payload["entries"]]

        assert slugs == ["civil-war", "black-widow", "infinity-war"]

    def test_the_interleaved_entry_keeps_its_own_saga_colour(self, interleaved):
        payload = WatchOrderService().build_payload()
        by_slug = {entry["slug"]: entry for entry in payload["entries"]}

        assert by_slug["black-widow"]["track"] == "multiverse-saga"
        assert by_slug["black-widow"]["track_color"] != by_slug["civil-war"]["track_color"]

    def test_they_all_share_one_lane(self, interleaved):
        payload = WatchOrderService().build_payload()

        assert len({entry["lane"] for entry in payload["entries"]}) == 1

    def test_appending_continues_past_the_whole_column(self, sagas, interleaved):
        """A new entry in either track lands after everything, not after its track."""
        from connections.models import append_position

        infinity, multiverse = sagas
        assert append_position(infinity) == append_position(multiverse)
        assert append_position(multiverse) > interleaved["infinity_war"].position

    def test_insert_after_crosses_tracks_within_the_column(self, sagas, interleaved):
        """Inserting after a Multiverse entry from the Infinity track must work."""
        from decimal import Decimal
        from connections.models import next_position_after

        assert next_position_after(interleaved["black_widow"]) == Decimal("17.5")

    def test_renormalize_merges_two_numberings_without_reordering(self, sagas):
        """The one-time fix after linking two tracks that both start at 10."""
        from decimal import Decimal
        from connections.models import renormalize_track

        infinity, multiverse = sagas
        WatchEntry.objects.create(track=infinity, title="A", slug="a", position=Decimal("10"))
        WatchEntry.objects.create(track=infinity, title="B", slug="b", position=Decimal("20"))
        WatchEntry.objects.create(track=multiverse, title="C", slug="c", position=Decimal("10"))
        WatchEntry.objects.create(track=multiverse, title="D", slug="d", position=Decimal("20"))

        assert renormalize_track(multiverse) == 4

        payload = WatchOrderService().build_payload()
        assert [entry["slug"] for entry in payload["entries"]] == ["a", "b", "c", "d"]
        positions = list(
            WatchEntry.objects.order_by("position").values_list("position", flat=True)
        )
        assert positions == [Decimal("10"), Decimal("20"), Decimal("30"), Decimal("40")]
