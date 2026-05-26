from django.test import TestCase

from networkx.exception import NetworkXNoPath

from .graph_service import MCUGraphService
from .models import Character, Movie, Relationship


class MCUGraphServiceTests(TestCase):
	def setUp(self):
		super().setUp()
		self.graph_service = MCUGraphService()

	def _character(self, name):
		return Character.objects.create(name=name)

	def _movie(self, title, release_date):
		return Movie.objects.create(title=title, release_date=release_date)

	def test_shortest_path_traverses_non_directional_edges_both_ways(self):
		hub = self._character("Hub")
		start = self._character("Start")
		finish = self._character("Finish")

		Relationship.objects.create(
			character1=hub,
			character2=start,
			relationship_type="Ally",
			directional=False,
		)
		Relationship.objects.create(
			character1=hub,
			character2=finish,
			relationship_type="Ally",
			directional=False,
		)

		forward = self.graph_service.shortest_path(start.id, finish.id)
		reverse = self.graph_service.shortest_path(finish.id, start.id)

		self.assertEqual(forward["character_ids"], [start.id, hub.id, finish.id])
		self.assertEqual(reverse["character_ids"], [finish.id, hub.id, start.id])

	def test_shortest_path_respects_directional_edges(self):
		origin = self._character("Origin")
		target = self._character("Target")

		Relationship.objects.create(
			character1=origin,
			character2=target,
			relationship_type="Mentor",
			directional=True,
		)

		self.graph_service.shortest_path(origin.id, target.id)

		with self.assertRaises(NetworkXNoPath):
			self.graph_service.shortest_path(target.id, origin.id)

	def test_filtered_subgraph_filters_by_any_movie_appearance(self):
		introduced_movie = self._movie("Intro Movie", "2024-01-01")
		later_movie = self._movie("Later Movie", "2025-01-01")
		other_movie = self._movie("Other Movie", "2026-01-01")

		introduced_only = self._character("Introduced Only")
		introduced_only.movie_introduced = introduced_movie
		introduced_only.save(update_fields=["movie_introduced"])
		introduced_movie.characters.add(introduced_only)

		appears_later = self._character("Appears Later")
		appears_later.movie_introduced = introduced_movie
		appears_later.save(update_fields=["movie_introduced"])
		introduced_movie.characters.add(appears_later)
		later_movie.characters.add(appears_later)

		other_character = self._character("Other Character")
		other_character.movie_introduced = other_movie
		other_character.save(update_fields=["movie_introduced"])
		other_movie.characters.add(other_character)

		_, characters = self.graph_service.filtered_subgraph(movie=[str(later_movie.id)])
		self.assertEqual(list(characters.values_list("name", flat=True)), ["Appears Later"])
