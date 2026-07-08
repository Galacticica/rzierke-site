from django.test import TestCase

import networkx as nx

from ..graph_service import MCUGraphService
from ..models import AlterEgo, Character, Earth, Movie, Relationship, Team, TeamMembership


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

	def test_shortest_path_traverses_directional_edges_both_ways(self):
		# Relationship direction is display-only: a directional edge still
		# connects the two characters, so the path search must walk it either way.
		origin = self._character("Origin")
		target = self._character("Target")

		Relationship.objects.create(
			character1=origin,
			character2=target,
			relationship_type="Mentor",
			directional=True,
		)

		forward = self.graph_service.shortest_path(origin.id, target.id)
		reverse = self.graph_service.shortest_path(target.id, origin.id)

		self.assertEqual(forward["character_ids"], [origin.id, target.id])
		self.assertEqual(reverse["character_ids"], [target.id, origin.id])

		# Even when walked in reverse, the edge keeps its stored orientation and
		# directional flag so the arrow renders correctly.
		reverse_edge = reverse["edges"][0]
		self.assertEqual(reverse_edge["source"], origin.id)
		self.assertEqual(reverse_edge["target"], target.id)
		self.assertTrue(reverse_edge["directional"])
		self.assertEqual(reverse_edge["relationship_type"], "Mentor")

	def test_shortest_path_prefers_fewest_hops_over_lower_weight(self):
		# A direct connection (1 hop) must win over a longer path even when the
		# longer path has a lower total relationship weight.
		ross = self._character("Thaddeus")
		bruce = self._character("Bruce")
		betty = self._character("Betty")

		# Direct heavy edge: Enemy (weight 6).
		Relationship.objects.create(
			character1=ross, character2=bruce, relationship_type="Enemy", directional=False,
		)
		# Two-hop lighter route: Family (2) + Romantic (3) = 5 < 6.
		Relationship.objects.create(
			character1=ross, character2=betty, relationship_type="Family", directional=False,
		)
		Relationship.objects.create(
			character1=betty, character2=bruce, relationship_type="Romantic", directional=False,
		)

		result = self.graph_service.shortest_path(ross.id, bruce.id)

		self.assertEqual(result["character_ids"], [ross.id, bruce.id])
		self.assertEqual(len(result["edges"]), 1)
		self.assertEqual(result["edges"][0]["relationship_type"], "Enemy")

	def test_shortest_path_breaks_hop_ties_by_weight(self):
		# Among paths with the same number of hops, the lower-weight relationship wins.
		start = self._character("Start")
		finish = self._character("Finish")
		cheap = self._character("CheapHub")
		pricey = self._character("PriceyHub")

		# Route via cheap hub: Variant (1) + Variant (1) = 2.
		Relationship.objects.create(character1=start, character2=cheap, relationship_type="Variant", directional=False)
		Relationship.objects.create(character1=cheap, character2=finish, relationship_type="Variant", directional=False)
		# Route via pricey hub: Enemy (6) + Enemy (6) = 12. Same hop count, higher weight.
		Relationship.objects.create(character1=start, character2=pricey, relationship_type="Enemy", directional=False)
		Relationship.objects.create(character1=pricey, character2=finish, relationship_type="Enemy", directional=False)

		result = self.graph_service.shortest_path(start.id, finish.id)

		self.assertEqual(result["character_ids"], [start.id, cheap.id, finish.id])

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
		self.assertEqual([character.name for character in characters], ["Appears Later"])

	def test_filtered_subgraph_filters_by_team_membership(self):
		team_one = Team.objects.create(name="Team One")
		team_two = Team.objects.create(name="Team Two")
		character = self._character("Team Member")

		TeamMembership.objects.create(character=character, team=team_one)
		TeamMembership.objects.create(character=character, team=team_two)

		_, characters = self.graph_service.filtered_subgraph(team=[str(team_one.id)])
		self.assertEqual([character.name for character in characters], ["Team Member"])

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
		self.assertEqual([character.name for character in characters], ["Illuminati"])

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

	def test_to_cytoscape_format_renders_one_edge_per_relationship_type(self):
		# Two characters sharing multiple kinds of relationship (e.g. Thor and
		# Hela are both Enemy and Family) must render as distinct lines, one per
		# relationship type, rather than a single merged edge.
		thor = self._character("Thor")
		hela = self._character("Hela")

		Relationship.objects.create(
			character1=thor, character2=hela, relationship_type="Enemy", directional=False,
		)
		Relationship.objects.create(
			character1=thor, character2=hela, relationship_type="Family", directional=False,
		)

		graph = self.graph_service.build_graph(
			queryset=Relationship.objects.all(), include_details=False,
		)
		payload = self.graph_service.to_cytoscape_format(graph, include_details=False)

		self.assertEqual(len(payload["edges"]), 2)
		types = sorted(edge["data"]["relationship_type"] for edge in payload["edges"])
		self.assertEqual(types, ["Enemy", "Family"])
		# Each edge carries a unique id so Cytoscape renders both lines.
		ids = [edge["data"]["id"] for edge in payload["edges"]]
		self.assertEqual(len(set(ids)), 2)

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
