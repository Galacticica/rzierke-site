"""Tests for the connections app views (API endpoints + graph page)."""

from unittest.mock import MagicMock

import pytest
from django.urls import reverse

from connections import views as connections_views
from connections.models import Character, Earth, Movie, Relationship, Team


pytestmark = pytest.mark.django_db


def _character(name, **kwargs):
    return Character.objects.create(name=name, **kwargs)


def _relationship(character1, character2, relationship_type="Ally", directional=False):
    return Relationship.objects.create(
        character1=character1,
        character2=character2,
        relationship_type=relationship_type,
        directional=directional,
    )


class TestGraphView:
    def test_returns_nodes_and_edges_in_cytoscape_shape(self, client):
        tony = _character("Tony Stark")
        peter = _character("Peter Parker")
        relationship = _relationship(tony, peter, relationship_type="Mentor", directional=True)

        response = client.get(reverse("graph"))

        assert response.status_code == 200
        payload = response.json()
        assert set(payload.keys()) == {"nodes", "edges"}

        node_ids = {node["data"]["id"] for node in payload["nodes"]}
        assert node_ids == {str(tony.id), str(peter.id)}

        # Light serialization: no per-node details block.
        for node in payload["nodes"]:
            assert "details" not in node["data"]
            assert node["data"]["label"] == node["data"]["name"]

        assert len(payload["edges"]) == 1
        edge = payload["edges"][0]["data"]
        assert edge["source"] == str(tony.id)
        assert edge["target"] == str(peter.id)
        assert edge["relationship_type"] == "Mentor"
        assert edge["relationship_ids"] == [relationship.id]
        assert edge["directional"] is True
        assert payload["edges"][0]["classes"] == "directional"

    def test_empty_database_returns_empty_graph(self, client):
        response = client.get(reverse("graph"))

        assert response.status_code == 200
        assert response.json() == {"nodes": [], "edges": []}

    def test_rejects_non_get(self, client):
        response = client.post(reverse("graph"))

        assert response.status_code == 405


class TestGraphPathView:
    def test_missing_params_returns_400(self, client):
        response = client.get(reverse("graph-path"))

        assert response.status_code == 400
        assert response.json() == {"error": "Both 'from' and 'to' are required."}

    def test_missing_one_param_returns_400(self, client):
        response = client.get(reverse("graph-path"), {"from": "1"})

        assert response.status_code == 400
        assert "required" in response.json()["error"]

    def test_non_numeric_ids_return_400(self, client):
        response = client.get(reverse("graph-path"), {"from": "tony", "to": "peter"})

        assert response.status_code == 400
        assert response.json() == {"error": "'from' and 'to' must be numeric character IDs."}

    def test_unknown_character_id_returns_404(self, client):
        tony = _character("Tony Stark")
        peter = _character("Peter Parker")
        _relationship(tony, peter)

        response = client.get(reverse("graph-path"), {"from": tony.id, "to": 999999})

        assert response.status_code == 404
        assert response.json() == {"error": "One or both characters were not found."}

    def test_disconnected_characters_return_404(self, client):
        tony = _character("Tony Stark")
        peter = _character("Peter Parker")
        wanda = _character("Wanda Maximoff")
        pietro = _character("Pietro Maximoff")
        _relationship(tony, peter, relationship_type="Mentor")
        _relationship(wanda, pietro, relationship_type="Family")

        response = client.get(reverse("graph-path"), {"from": tony.id, "to": wanda.id})

        assert response.status_code == 404
        assert response.json() == {"error": "No path exists between those characters."}

    def test_successful_path_payload(self, client):
        tony = _character("Tony Stark")
        happy = _character("Happy Hogan")
        peter = _character("Peter Parker")
        _relationship(tony, happy, relationship_type="Ally")  # weight 4
        _relationship(happy, peter, relationship_type="Ally")  # weight 4

        response = client.get(reverse("graph-path"), {"from": tony.id, "to": peter.id})

        assert response.status_code == 200
        payload = response.json()
        assert set(payload.keys()) == {
            "character_ids",
            "highlighted_nodes",
            "highlighted_edges",
            "total_cost",
        }
        assert payload["character_ids"] == [tony.id, happy.id, peter.id]
        # Highlighted node ids are strings (Cytoscape node ids).
        assert payload["highlighted_nodes"] == [str(tony.id), str(happy.id), str(peter.id)]
        assert payload["total_cost"] == 8

        assert len(payload["highlighted_edges"]) == 2
        first_edge = payload["highlighted_edges"][0]
        assert first_edge["source"] == str(tony.id)
        assert first_edge["target"] == str(happy.id)
        assert first_edge["relationship_type"] == "Ally"
        assert first_edge["relationship_types"] == ["Ally"]
        assert first_edge["weight"] == 4
        assert first_edge["directional"] is False


class TestGraphCharacterDetailView:
    def test_existing_character_returns_details(self, client):
        earth = Earth.objects.create(number="Earth-616")
        character = _character("Steve Rogers", status="Alive", earth_number=earth)

        url = reverse("graph-character-detail", kwargs={"character_id": character.id})
        response = client.get(url)

        assert response.status_code == 200
        payload = response.json()
        assert payload["id"] == character.id
        assert payload["name"] == "Steve Rogers"
        assert payload["status"] == "Alive"
        assert payload["status_label"] == "Alive"
        assert payload["earth"] == "Earth-616"
        assert payload["aliases"] == []
        assert payload["teams"] == []
        assert payload["movies"] == []

    def test_unknown_character_returns_404(self, client):
        url = reverse("graph-character-detail", kwargs={"character_id": 999999})
        response = client.get(url)

        assert response.status_code == 404
        assert response.json() == {"error": "Character was not found."}


class TestGraphFilterView:
    def test_returns_payload_with_echoed_filters(self, client):
        hero = _character("Carol Danvers", alignment="Hero")
        villain = _character("Thanos", alignment="Villain")
        _relationship(hero, villain, relationship_type="Enemy")

        response = client.get(reverse("graph-filter"), {"alignment": "Hero"})

        assert response.status_code == 200
        payload = response.json()
        assert set(payload.keys()) == {"nodes", "edges", "filters"}
        assert payload["filters"] == {
            "alignment": ["Hero"],
            "phase": None,
            "status": [],
            "earth": [],
            "team": [],
            "movie": [],
            "relationship_types": [],
        }
        node_ids = {node["data"]["id"] for node in payload["nodes"]}
        assert node_ids == {str(hero.id)}
        # Villain filtered out, so the Enemy edge is gone too.
        assert payload["edges"] == []

    def test_second_identical_call_is_served_from_cache(self, client, monkeypatch):
        hero = _character("Carol Danvers", alignment="Hero")
        _character("Thanos", alignment="Villain")

        params = {"alignment": "Hero"}
        first = client.get(reverse("graph-filter"), params)
        assert first.status_code == 200

        # Same version + same filters -> payload cache hit; the service must
        # not be asked to rebuild the subgraph.
        spy = MagicMock(side_effect=AssertionError("filtered_subgraph should not be called"))
        monkeypatch.setattr(connections_views.graph_service, "filtered_subgraph", spy)

        second = client.get(reverse("graph-filter"), params)

        assert second.status_code == 200
        spy.assert_not_called()
        assert second.json() == first.json()
        node_ids = {node["data"]["id"] for node in second.json()["nodes"]}
        assert node_ids == {str(hero.id)}

    def test_different_filters_bypass_the_cached_payload(self, client, monkeypatch):
        _character("Carol Danvers", alignment="Hero")

        first = client.get(reverse("graph-filter"), {"alignment": "Hero"})
        assert first.status_code == 200

        real_filtered_subgraph = connections_views.graph_service.filtered_subgraph
        spy = MagicMock(side_effect=real_filtered_subgraph)
        monkeypatch.setattr(connections_views.graph_service, "filtered_subgraph", spy)

        response = client.get(reverse("graph-filter"), {"alignment": "Villain"})

        assert response.status_code == 200
        spy.assert_called_once()
        assert response.json()["filters"]["alignment"] == ["Villain"]


class TestGraphPageView:
    def test_renders_with_filter_and_character_options(self, client):
        movie = Movie.objects.create(title="Iron Man", release_date="2008-05-02")
        earth = Earth.objects.create(number="Earth-616")
        team = Team.objects.create(name="Avengers")
        character = _character(
            "Tony Stark",
            alignment="Hero",
            movie_introduced=movie,
            earth_number=earth,
        )
        orphan = _character("Uatu")  # no first-appearance movie

        response = client.get(reverse("connections-graph"))

        assert response.status_code == 200
        context = response.context

        assert context["alignment_choices"] == Character.ALIGNMENT_CHOICES
        assert context["status_choices"] == Character.STATUS_CHOICES
        assert context["relationship_choices"] == Relationship.RELATIONSHIP_CHOICES
        assert list(context["movie_choices"]) == [movie]
        assert list(context["team_choices"]) == [team]

        options = context["character_options"]
        assert {option["id"] for option in options} == {character.id, orphan.id}
        by_id = {option["id"]: option for option in options}
        assert by_id[character.id]["name"] == "Tony Stark"
        assert by_id[character.id]["display_name"] == "Tony Stark (Earth-616)"
        assert by_id[orphan.id]["display_name"] == "Uatu"

        grouped = context["grouped_character_options"]
        labels = [group["label"] for group in grouped]
        assert "Iron Man" in labels
        assert "No first appearance" in labels
        iron_man_group = next(group for group in grouped if group["label"] == "Iron Man")
        assert [entry["name"] for entry in iron_man_group["characters"]] == ["Tony Stark"]
        assert iron_man_group["characters"][0]["aliases"] == []

    def test_rejects_non_get(self, client):
        response = client.post(reverse("connections-graph"))

        assert response.status_code == 405
