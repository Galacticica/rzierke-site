from django.contrib import admin as django_admin
from django.test import TestCase

import networkx as nx
from networkx.exception import NetworkXNoPath

from .admin import CharacterAdmin, CharacterAdminForm
from .graph_service import MCUGraphService
from .models import AlterEgo, Character, Earth, Movie, Relationship, Team, TeamMembership


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

	def test_filtered_subgraph_filters_by_earth_number(self):
		earth_616 = Earth.objects.create(number="Earth-616")
		earth_838 = Earth.objects.create(number="Earth-838")

		character_616 = self._character("Main Timeline")
		character_616.earth_number = earth_616
		character_616.save(update_fields=["earth_number"])

		character_838 = self._character("Illuminati")
		character_838.earth_number = earth_838
		character_838.save(update_fields=["earth_number"])

		_, characters = self.graph_service.filtered_subgraph(earth=["Earth-838"])
		self.assertEqual(list(characters.values_list("name", flat=True)), ["Illuminati"])

	def test_character_admin_form_syncs_movie_membership(self):
		movie_one = self._movie("Movie One", "2024-01-01")
		movie_two = self._movie("Movie Two", "2025-01-01")
		character = self._character("Test Character")

		form = CharacterAdminForm(
			data={
				"name": character.name,
				"phase_introduced": "",
				"movie_introduced": "",
				"latest_appearance": "",
				"alignment": "",
				"status": "",
				"earth_number": "",
				"photo_path": "",
				"movies": [str(movie_one.id), str(movie_two.id)],
			},
			instance=character,
		)

		self.assertTrue(form.is_valid(), form.errors)
		form.save(commit=False)
		CharacterAdmin(Character, django_admin.site).save_related(None, form, [], False)

		self.assertEqual(list(character.movies.order_by("title").values_list("title", flat=True)), ["Movie One", "Movie Two"])

	def test_to_cytoscape_format_includes_character_details(self):
		introducing_movie = self._movie("Introducing Movie", "2024-05-01")
		later_movie = self._movie("Later Movie", "2025-06-01")
		earth = Earth.objects.create(number="Earth-616")
		character = self._character("Mockingbird")
		character.status = "Alive"
		character.earth_number = earth
		character.movie_introduced = introducing_movie
		character.save(update_fields=["status", "earth_number", "movie_introduced"])
		introducing_movie.characters.add(character)
		later_movie.characters.add(character)

		AlterEgo.objects.create(character=character, name="Bobbi Morse")

		team = Team.objects.create(name="Avengers")
		TeamMembership.objects.create(character=character, team=team, is_current_member=False)

		graph = nx.DiGraph()
		graph.add_node(character.id)

		payload = self.graph_service.to_cytoscape_format(graph)
		node = payload["nodes"][0]["data"]

		self.assertEqual(node["details"]["status_label"], "Alive")
		self.assertEqual(node["details"]["earth"], "Earth-616")
		self.assertEqual(node["details"]["aliases"], ["Bobbi Morse"])
		self.assertEqual(node["details"]["teams"], [{"name": "Avengers", "status": "Former"}])
		self.assertEqual(
			node["details"]["movies"],
			[
				{"id": introducing_movie.id, "title": "Introducing Movie", "year": 2024},
				{"id": later_movie.id, "title": "Later Movie", "year": 2025},
			],
		)
