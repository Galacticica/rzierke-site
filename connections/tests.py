from django.contrib import admin as django_admin
from django.test import TestCase

import networkx as nx
from networkx.exception import NetworkXNoPath

from .admin import CharacterAdmin, CharacterAdminForm, RelationshipAdmin, RelationshipAdminForm
from .graph_service import MCUGraphService
from .models import AlterEgo, Character, Earth, Movie, Relationship, Team, TeamMembership
from .views import _group_character_options


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

	def test_character_admin_movie_selects_are_chronological(self):
		later_movie = self._movie("Later Movie", "2025-01-01")
		earliest_movie = self._movie("Earliest Movie", "2023-01-01")
		middle_movie = self._movie("Middle Movie", "2024-01-01")

		form = CharacterAdminForm()

		self.assertEqual(
			list(form.fields["movie_introduced"].queryset.values_list("title", flat=True)),
			["Earliest Movie", "Middle Movie", "Later Movie"],
		)
		self.assertEqual(
			list(form.fields["latest_appearance"].queryset.values_list("title", flat=True)),
			["Earliest Movie", "Middle Movie", "Later Movie"],
		)

	def test_character_admin_sorts_earth_choices_alphabetically(self):
		Earth.objects.create(number="Earth-838")
		Earth.objects.create(number="Earth-616")
		Earth.objects.create(number="Earth-1610")

		form_field = CharacterAdmin(Character, django_admin.site).formfield_for_foreignkey(
			Character._meta.get_field("earth_number"),
			None,
		)

		self.assertEqual(
			list(form_field.queryset.values_list("number", flat=True)),
			["Earth-1610", "Earth-616", "Earth-838"],
		)

	def test_group_character_options_includes_earth_display_name(self):
		earth = Earth.objects.create(number="Earth-616")
		movie = self._movie("Movie One", "2024-01-01")
		character = self._character("Test Character")
		character.earth_number = earth
		character.movie_introduced = movie
		character.save(update_fields=["earth_number", "movie_introduced"])

		grouped_options = _group_character_options(Character.objects.select_related("movie_introduced", "earth_number").order_by("name"))
		self.assertEqual(grouped_options[0]["characters"][0]["display_name"], "Test Character (Earth-616)")

	def test_relationship_admin_groups_characters_by_every_movie_and_shows_earth(self):
		movie_one = self._movie("Movie One", "2024-01-01")
		movie_two = self._movie("Movie Two", "2025-01-01")
		earth = Earth.objects.create(number="Earth-616")
		character = self._character("Test Character")
		character.earth_number = earth
		character.save(update_fields=["earth_number"])
		movie_one.characters.add(character)
		movie_two.characters.add(character)

		form_field = RelationshipAdmin(Relationship, django_admin.site).formfield_for_foreignkey(
			Relationship._meta.get_field("character1"),
			None,
		)

		grouped_choices = {label: choices for label, choices in form_field.choices}
		self.assertIn("Movie One", grouped_choices)
		self.assertIn("Movie Two", grouped_choices)
		self.assertEqual(grouped_choices["Movie One"], [(character.id, "Test Character (Earth-616)")])
		self.assertEqual(grouped_choices["Movie Two"], [(character.id, "Test Character (Earth-616)")])

	def test_relationship_admin_form_can_reverse_direction(self):
		first = self._character("First")
		second = self._character("Second")

		form = RelationshipAdminForm(
			data={
				"character1": str(first.id),
				"character2": str(second.id),
				"relationship_type": "Ally",
				"directional": True,
				"notes": "",
				"direction": "reverse",
			}
		)

		self.assertTrue(form.is_valid(), form.errors)
		relationship = form.save(commit=False)

		self.assertEqual((relationship.character1_id, relationship.character2_id), (second.id, first.id))
		self.assertTrue(relationship.directional)

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

	def test_to_cytoscape_format_can_omit_character_details(self):
		earth = Earth.objects.create(number="Earth-616")
		character = self._character("Lightweight")
		character.earth_number = earth
		character.status = "Alive"
		character.save(update_fields=["earth_number", "status"])

		graph = nx.DiGraph()
		graph.add_node(character.id, **{"earth": earth.number, "status": character.status, "alignment": character.alignment})

		payload = self.graph_service.to_cytoscape_format(graph, include_details=False)
		node = payload["nodes"][0]["data"]

		self.assertNotIn("details", node)
		self.assertEqual(node["earth"], "Earth-616")
		self.assertEqual(node["status"], "Alive")

	def test_character_detail_payload_returns_full_details(self):
		movie = self._movie("Detail Movie", "2024-02-02")
		earth = Earth.objects.create(number="Earth-838")
		character = self._character("Detailed")
		character.status = "Unknown"
		character.earth_number = earth
		character.movie_introduced = movie
		character.save(update_fields=["status", "earth_number", "movie_introduced"])
		movie.characters.add(character)
		AlterEgo.objects.create(character=character, name="Alias One")
		team = Team.objects.create(name="Fantastic Four")
		TeamMembership.objects.create(character=character, team=team, is_current_member=True)

		details = self.graph_service.character_detail_payload(character.id)

		self.assertEqual(details["name"], "Detailed")
		self.assertEqual(details["earth"], "Earth-838")
		self.assertEqual(details["aliases"], ["Alias One"])
		self.assertEqual(details["teams"], [{"name": "Fantastic Four", "status": "Current"}])
		self.assertEqual(details["movies"], [{"id": movie.id, "title": "Detail Movie", "year": 2024}])
