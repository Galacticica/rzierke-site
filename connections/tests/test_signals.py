"""Tests for the connections post_save signals that invalidate the graph cache."""

import pytest
from django.core.cache import cache
from django.urls import reverse

from connections.graph_service import MCUGraphService
from connections.models import Character, Relationship


pytestmark = pytest.mark.django_db


class TestCharacterSaveSignal:
    def test_saving_a_character_bumps_the_cache_version(self):
        service = MCUGraphService()
        version_before = service._get_cache_version()

        Character.objects.create(name="Nick Fury")

        assert service._get_cache_version() > version_before

    def test_updating_a_character_bumps_the_cache_version(self):
        character = Character.objects.create(name="Nick Fury")
        service = MCUGraphService()
        version_before = service._get_cache_version()

        character.status = "Alive"
        character.save()

        assert service._get_cache_version() > version_before

    def test_saving_a_character_with_no_prior_version_seeds_version_two(self):
        # invalidate_cache with a cold cache jumps straight to version 2 so any
        # previously computed version-1 keys can never be served.
        cache.delete(MCUGraphService.VERSION_KEY)

        Character.objects.create(name="Maria Hill")

        assert MCUGraphService()._get_cache_version() == 2


class TestRelationshipSaveSignal:
    def test_saving_a_relationship_bumps_the_cache_version(self):
        steve = Character.objects.create(name="Steve Rogers")
        bucky = Character.objects.create(name="Bucky Barnes")
        service = MCUGraphService()
        version_before = service._get_cache_version()

        Relationship.objects.create(
            character1=steve, character2=bucky, relationship_type="Ally",
        )

        assert service._get_cache_version() > version_before

    def test_new_relationship_invalidates_cached_graph_data(self, client):
        # All characters exist up front so only the Relationship save fires
        # between the two requests.
        tony = Character.objects.create(name="Tony Stark")
        peter = Character.objects.create(name="Peter Parker")
        happy = Character.objects.create(name="Happy Hogan")
        Relationship.objects.create(
            character1=tony, character2=peter, relationship_type="Mentor",
        )

        # Warm the cache.
        first = client.get(reverse("graph"))
        assert first.status_code == 200
        assert len(first.json()["edges"]) == 1

        Relationship.objects.create(
            character1=tony, character2=happy, relationship_type="Ally",
        )

        second = client.get(reverse("graph"))
        assert second.status_code == 200
        payload = second.json()

        edge_pairs = {
            (edge["data"]["source"], edge["data"]["target"]) for edge in payload["edges"]
        }
        assert edge_pairs == {
            (str(tony.id), str(peter.id)),
            (str(tony.id), str(happy.id)),
        }
        node_ids = {node["data"]["id"] for node in payload["nodes"]}
        assert node_ids == {str(tony.id), str(peter.id), str(happy.id)}

    def test_new_relationship_invalidates_cached_service_graph(self):
        # Same guarantee at the service layer: build_graph must not return the
        # stale cached copy after a relationship is added.
        service = MCUGraphService()
        wanda = Character.objects.create(name="Wanda Maximoff")
        vision = Character.objects.create(name="Vision")
        pietro = Character.objects.create(name="Pietro Maximoff")
        Relationship.objects.create(
            character1=wanda, character2=vision, relationship_type="Romantic",
        )

        warm = service.build_graph()
        assert warm.number_of_edges() == 1

        Relationship.objects.create(
            character1=wanda, character2=pietro, relationship_type="Family",
        )

        rebuilt = service.build_graph()
        assert rebuilt.number_of_edges() == 2
        assert rebuilt.has_edge(wanda.id, pietro.id)
