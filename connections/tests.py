from django.test import TestCase

from networkx.exception import NetworkXNoPath

from .graph_service import MCUGraphService
from .models import Character, Relationship


class MCUGraphServiceTests(TestCase):
	def setUp(self):
		super().setUp()
		self.graph_service = MCUGraphService()

	def _character(self, name):
		return Character.objects.create(name=name)

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
