'''
File: graph_service.py
Project: rzierke-site
Created Date: 2026-05-25
Author: Reagan Zierke
Email: reaganzierke@gmail.com
-----
Last Modified: 2026-05-25 18:14:10
Modified By: Reagan Zierke
-----
Description: 
'''

from itertools import pairwise

import networkx as nx
from django.core.cache import cache
from django.db.models import Exists, OuterRef, Prefetch
from django.templatetags.static import static

from .models import AlterEgo, Character, Movie, Relationship, TeamMembership


class MCUGraphService:
	"""Build and serialize the MCU relationship graph."""

	CACHE_PREFIX = "connections:graph"
	CACHE_TIMEOUT = 900
	VERSION_KEY = f"{CACHE_PREFIX}:version"

	def _cache_key(self, suffix, version=None):
		if version is None:
			version = self._get_cache_version()
		return f"{self.CACHE_PREFIX}:{suffix}:v{version}"

	def _get_cache_version(self):
		version = cache.get(self.VERSION_KEY)
		if version is None:
			version = 1
			cache.set(self.VERSION_KEY, version)
		return int(version)

	@classmethod
	def invalidate_cache(cls):
		version = cache.get(cls.VERSION_KEY)
		if version is None:
			cache.set(cls.VERSION_KEY, 2)
			return 2

		try:
			new_version = cache.incr(cls.VERSION_KEY)
		except (ValueError, NotImplementedError):
			new_version = int(version) + 1
			cache.set(cls.VERSION_KEY, new_version)

		return new_version

	def _photo_url(self, photo_path):
		if not photo_path:
			return ""
		if photo_path.startswith(("http://", "https://", "/")):
			return photo_path
		return static(photo_path)

	def _character_base_queryset(self, queryset):
		return queryset.select_related("movie_introduced", "latest_appearance", "earth_number")

	def _character_detail_queryset(self, queryset):
		return self._character_base_queryset(queryset).prefetch_related(
			Prefetch("alter_egos", queryset=AlterEgo.objects.order_by("name")),
			Prefetch(
				"team_memberships",
				queryset=TeamMembership.objects.select_related("team").order_by("team__name"),
			),
			Prefetch("movies", queryset=Movie.objects.order_by("release_date", "title")),
		)

	def _character_detail_payload(self, character):
		status = character.status or "Unknown"
		status_label = character.get_status_display() if character.status else "Unknown"

		return {
			"status": status,
			"status_label": status_label,
			"earth": character.earth_number.number if character.earth_number else None,
			"aliases": [alter_ego.name for alter_ego in character.alter_egos.all()],
			"teams": [
				{
					"name": membership.team.name,
					"status": "Current" if membership.is_current_member else "Former",
				}
				for membership in character.team_memberships.all()
			],
			"movies": [
				{
					"id": movie.id,
					"title": movie.title,
					"year": movie.release_date.year,
				}
				for movie in character.movies.all()
			],
		}

	def _character_node_data(self, character, include_details=True):
		data = {
			"id": character.id,
			"label": character.name,
			"name": character.name,
			"alignment": character.alignment,
			"status": character.status,
			"earth": character.earth_number.number if character.earth_number else None,
			"phase_introduced": character.phase_introduced,
			"movie_introduced_id": character.movie_introduced_id,
			"latest_appearance_id": character.latest_appearance_id,
			"photo_url": self._photo_url(character.photo_path),
		}

		if include_details:
			data["details"] = self._character_detail_payload(character)

		return data

	def _edge_payload(self, edge_data):
		relationship_types = sorted(set(edge_data.get("relationship_types", [])))
		relationship_ids = sorted(set(edge_data.get("relationship_ids", [])))
		label = " / ".join(relationship_types)
		edge_id_suffix = "-".join(str(identifier) for identifier in relationship_ids)
		return {
			"relationship_type": edge_data.get("relationship_type"),
			"relationship_types": relationship_types,
			"relationship_ids": relationship_ids,
			"weight": edge_data.get("weight", 1),
			"directional": edge_data.get("directional", False),
			"label": label,
			"edge_id": f"edge-{edge_data['source']}-{edge_data['target']}"
			if not edge_id_suffix
			else f"edge-{edge_data['source']}-{edge_data['target']}-{edge_id_suffix}",
		}

	def _add_edge(self, graph, source_id, target_id, relationship, edge_directional):
		graph.add_node(source_id)
		graph.add_node(target_id)

		payload = {
			"source": source_id,
			"target": target_id,
			"relationship_type": relationship.relationship_type,
			"relationship_types": [relationship.relationship_type],
			"relationship_ids": [relationship.id],
			"weight": relationship.weight,
			"directional": edge_directional,
		}

		if graph.has_edge(source_id, target_id):
			existing = graph[source_id][target_id]
			existing_types = list(existing.get("relationship_types", []))
			if relationship.relationship_type not in existing_types:
				existing_types.append(relationship.relationship_type)

			existing_ids = list(existing.get("relationship_ids", []))
			if relationship.id not in existing_ids:
				existing_ids.append(relationship.id)

			existing["relationship_types"] = existing_types
			existing["relationship_ids"] = existing_ids
			existing["relationship_type"] = existing.get("relationship_type") or relationship.relationship_type
			existing["weight"] = min(existing.get("weight", relationship.weight), relationship.weight)
			existing["directional"] = existing.get("directional", False) or edge_directional
			existing["source"] = source_id
			existing["target"] = target_id
			return

		graph.add_edge(source_id, target_id, **payload)

	def _build_graph_from_relationships(self, relationships, include_details=True):
		graph = nx.DiGraph()

		relationships = relationships.select_related("character1", "character2")
		if include_details:
			relationships = relationships.prefetch_related(
				Prefetch(
					"character1__alter_egos",
					queryset=AlterEgo.objects.order_by("name"),
				),
				Prefetch(
					"character1__team_memberships",
					queryset=TeamMembership.objects.select_related("team").order_by("team__name"),
				),
				Prefetch(
					"character1__movies",
					queryset=Movie.objects.order_by("release_date", "title"),
				),
				Prefetch(
					"character2__alter_egos",
					queryset=AlterEgo.objects.order_by("name"),
				),
				Prefetch(
					"character2__team_memberships",
					queryset=TeamMembership.objects.select_related("team").order_by("team__name"),
				),
				Prefetch(
					"character2__movies",
					queryset=Movie.objects.order_by("release_date", "title"),
				),
			)

		for relationship in relationships:
			graph.add_node(
				relationship.character1_id,
				**self._character_node_data(relationship.character1, include_details=include_details),
			)
			graph.add_node(
				relationship.character2_id,
				**self._character_node_data(relationship.character2, include_details=include_details),
			)

			# For directional relationships, mark directional True.
			# For non-directional relationships we create a single undirected edge
			# (directional=False) between the two nodes so Cytoscape shows one
			# edge with no arrowhead.
			self._add_edge(
				graph,
				relationship.character1_id,
				relationship.character2_id,
				relationship,
				relationship.directional,
			)

		return graph

	def build_graph(self, queryset=None, include_details=False):
		if queryset is None:
			cache_key = self._cache_key("full")
			cached_graph = cache.get(cache_key)
			if cached_graph is not None:
				return cached_graph.copy()

			relationships = Relationship.objects.all()
			graph = self._build_graph_from_relationships(relationships, include_details=include_details)
			cache.set(cache_key, graph.copy(), self.CACHE_TIMEOUT)
			return graph

		return self._build_graph_from_relationships(queryset, include_details=include_details)

	def _build_traversal_graph(self, graph):
		"""Create a traversal graph where non-directional edges are traversable both ways."""
		traversal_graph = graph.copy()

		for source_id, target_id, edge_data in graph.edges(data=True):
			if edge_data.get("directional", False):
				continue

			if traversal_graph.has_edge(target_id, source_id):
				existing = traversal_graph[target_id][source_id]
				existing["weight"] = min(existing.get("weight", edge_data.get("weight", 1)), edge_data.get("weight", 1))
				continue

			reverse_edge = dict(edge_data)
			reverse_edge["source"] = target_id
			reverse_edge["target"] = source_id
			traversal_graph.add_edge(target_id, source_id, **reverse_edge)

		return traversal_graph

	def _path_edge_data(self, graph, source_node, target_node):
		if graph.has_edge(source_node, target_node):
			edge_data = graph[source_node][target_node]
			return source_node, target_node, edge_data

		if graph.has_edge(target_node, source_node):
			reverse_edge = graph[target_node][source_node]
			if not reverse_edge.get("directional", False):
				return target_node, source_node, reverse_edge

		raise nx.NetworkXNoPath(f"No traversable edge between {source_node} and {target_node}.")

	def shortest_path(self, from_id, to_id):
		source_id = int(from_id)
		target_id = int(to_id)
		cache_key = self._cache_key(f"path:{source_id}:{target_id}")
		cached_path = cache.get(cache_key)
		if cached_path is not None:
			return cached_path

		graph = self.build_graph()
		traversal_graph = self._build_traversal_graph(graph)
		path = nx.shortest_path(traversal_graph, source=source_id, target=target_id, weight="weight")

		edges = []
		total_cost = 0
		for source_node, target_node in pairwise(path):
			edge_source, edge_target, edge_data = self._path_edge_data(graph, source_node, target_node)
			total_cost += edge_data.get("weight", 1)
			edges.append(
				{
					"source": edge_source,
					"target": edge_target,
					"relationship_type": edge_data.get("relationship_type"),
					"relationship_types": list(edge_data.get("relationship_types", [])),
					"relationship_ids": list(edge_data.get("relationship_ids", [])),
					"weight": edge_data.get("weight", 1),
					"directional": edge_data.get("directional", False),
				}
			)

		result = {
			"character_ids": [int(character_id) for character_id in path],
			"edges": edges,
			"total_cost": total_cost,
		}
		cache.set(cache_key, result, self.CACHE_TIMEOUT)
		return result

	def filtered_subgraph(self, alignment=None, phase=None, status=None, earth=None, team=None, movie=None, relationship_types=None, include_details=False):
		normalized_alignment = [
			value.strip()
			for value in (alignment or [])
			if isinstance(value, str) and value.strip()
		]
		normalized_status = [
			value.strip()
			for value in (status or [])
			if isinstance(value, str) and value.strip()
		]
		normalized_earth = [
			value.strip()
			for value in (earth or [])
			if isinstance(value, str) and value.strip()
		]
		normalized_team = [
			value.strip()
			for value in (team or [])
			if isinstance(value, str) and value.strip()
		]
		normalized_movie = [
			value.strip()
			for value in (movie or [])
			if isinstance(value, str) and value.strip()
		]
		phase_value = int(phase) if phase not in (None, "") else None
		normalized_relationship_types = [
			relationship_type.strip()
			for relationship_type in (relationship_types or [])
			if isinstance(relationship_type, str) and relationship_type.strip()
		]

		cache_key = self._cache_key(
			"filtered",
			version=self._get_cache_version(),
		)
		cache_key = (
			f"{cache_key}:alignment={','.join(sorted(normalized_alignment)) or 'all'}"
			f":phase={phase_value or 'all'}"
			f":status={','.join(sorted(normalized_status)) or 'all'}"
			f":earth={','.join(sorted(normalized_earth)) or 'all'}"
			f":team={','.join(sorted(normalized_team)) or 'all'}"
			f":movie={','.join(sorted(normalized_movie)) or 'all'}"
			f":relationships={','.join(sorted(normalized_relationship_types)) or 'all'}"
		)
		cached_graph = cache.get(cache_key)
		if cached_graph is not None:
			characters = list(self._filtered_character_queryset(
				normalized_alignment,
				phase_value,
				normalized_status,
				normalized_earth,
				normalized_team,
				normalized_movie,
			))
			return cached_graph.copy(), characters

		characters = list(self._filtered_character_queryset(
			normalized_alignment,
			phase_value,
			normalized_status,
			normalized_earth,
			normalized_team,
			normalized_movie,
		))
		character_ids = [c.id for c in characters]

		graph = nx.DiGraph()
		if character_ids:
			relationships = Relationship.objects.filter(
				character1_id__in=character_ids,
				character2_id__in=character_ids,
			)
			if normalized_relationship_types:
				relationships = relationships.filter(relationship_type__in=normalized_relationship_types)
			graph = self._build_graph_from_relationships(relationships, include_details=include_details)

		for character in characters:
			graph.add_node(character.id, **self._character_node_data(character, include_details=include_details))

		cache.set(cache_key, graph.copy(), self.CACHE_TIMEOUT)
		return graph, characters

	def _filtered_character_queryset(self, alignment=None, phase=None, status=None, earth=None, team=None, movie=None, include_details=False):
		base_queryset = Character.objects.all()
		queryset = self._character_detail_queryset(base_queryset) if include_details else self._character_base_queryset(base_queryset)

		if alignment:
			queryset = queryset.filter(alignment__in=alignment)

		if phase is not None:
			queryset = queryset.filter(phase_introduced=phase)

		if status:
			queryset = queryset.filter(status__in=status)

		if earth:
			queryset = queryset.filter(earth_number__number__in=earth)

		if team:
			team_memberships = TeamMembership.objects.filter(character_id=OuterRef("pk"), team_id__in=team)
			queryset = queryset.filter(Exists(team_memberships))

		if movie:
			movie_memberships = Movie.characters.through.objects.filter(character_id=OuterRef("pk"), movie_id__in=movie)
			queryset = queryset.filter(Exists(movie_memberships))

		return queryset.order_by("name")

	def character_detail_payload(self, character_id):
		character = self._character_detail_queryset(Character.objects.filter(pk=character_id)).first()
		if character is None:
			return None

		return {
			"id": character.id,
			"name": character.name,
			"status": character.status or "Unknown",
			"status_label": character.get_status_display() if character.status else "Unknown",
			"earth": character.earth_number.number if character.earth_number else None,
			"aliases": [alter_ego.name for alter_ego in character.alter_egos.all()],
			"teams": [
				{
					"name": membership.team.name,
					"status": "Current" if membership.is_current_member else "Former",
				}
				for membership in character.team_memberships.all()
			],
			"movies": [
				{
					"id": movie.id,
					"title": movie.title,
					"year": movie.release_date.year,
				}
				for movie in character.movies.all()
			],
		}

	def to_cytoscape_format(self, graph, characters=None, include_details=True):
		character_lookup = {}
		if characters is not None:
			for character in characters:
				character_lookup[character.id] = character

		missing_ids = [node_id for node_id in graph.nodes if node_id not in character_lookup]
		if include_details and missing_ids:
			for character in self._character_detail_queryset(Character.objects.filter(pk__in=missing_ids)):
				character_lookup[character.id] = character

		nodes = []
		for node_id in sorted(graph.nodes):
			node_data = dict(graph.nodes[node_id])
			character = character_lookup.get(node_id)

			label = node_data.get("label")
			if character is not None:
				label = character.name

			alignment = node_data.get("alignment")
			status = node_data.get("status")
			photo_url = node_data.get("photo_url")

			if character is not None:
				alignment = character.alignment
				status = character.status
				photo_url = self._photo_url(character.photo_path)
				details = self._character_detail_payload(character) if include_details else None
			else:
				details = node_data.get("details") if include_details else None

			node_payload = {
				"id": str(node_id),
				"label": label or str(node_id),
				"name": label or str(node_id),
				"alignment": alignment,
				"status": status,
				"earth": node_data.get("earth") or (character.earth_number.number if character is not None and character.earth_number else None),
				"phase_introduced": node_data.get("phase_introduced"),
				"movie_introduced_id": node_data.get("movie_introduced_id"),
				"latest_appearance_id": node_data.get("latest_appearance_id"),
				"photo_url": photo_url or "",
			}

			if include_details and details is not None:
				node_payload["details"] = details

			classes = []
			if alignment:
				classes.append(str(alignment).lower())
			if status:
				classes.append(str(status).lower())

			nodes.append({"data": node_payload, "classes": " ".join(classes)})

		edges = []
		for source_id, target_id, edge_data in sorted(graph.edges(data=True)):
			payload = self._edge_payload(
				{
					"source": source_id,
					"target": target_id,
					**edge_data,
				}
			)
			edges.append(
				{
					"data": {
						"id": payload["edge_id"],
						"source": str(source_id),
						"target": str(target_id),
						"label": payload["label"],
						"weight": payload["weight"],
						"relationship_type": payload["relationship_type"],
						"relationship_types": payload["relationship_types"],
						"relationship_ids": payload["relationship_ids"],
						"directional": payload["directional"],
					},
					"classes": "directional" if payload["directional"] else "undirected",
				}
			)

		return {"nodes": nodes, "edges": edges}

