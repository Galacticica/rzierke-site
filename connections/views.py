"""API views for the MCU graph endpoints."""

from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from networkx.exception import NetworkXNoPath, NodeNotFound

from .graph_service import MCUGraphService
from .models import Character, Movie, Relationship, Team


graph_service = MCUGraphService()


def _group_character_options(characters):
	grouped_options = []
	current_group_label = None
	current_group = []

	for character in characters:
		movie = character.movie_introduced
		group_label = movie.title if movie else "No first appearance"
		if group_label != current_group_label:
			if current_group_label is not None:
				grouped_options.append({"label": current_group_label, "characters": current_group})
			current_group_label = group_label
			current_group = []

		current_group.append(
			{
				"id": character.id,
				"name": character.name,
				"display_name": f"{character.name} ({character.earth_number.number})" if character.earth_number else character.name,
			}
		)

	if current_group_label is not None:
		grouped_options.append({"label": current_group_label, "characters": current_group})

	return grouped_options


def _bad_request(message):
	return JsonResponse({"error": message}, status=400)


def _serialize_graph_response(graph, characters=None):
	return JsonResponse(graph_service.to_cytoscape_format(graph, characters), safe=False)


def _serialize_light_graph_response(graph, characters=None):
	return JsonResponse(graph_service.to_cytoscape_format(graph, characters, include_details=False), safe=False)


@require_GET
def graph_page_view(request):
	characters = Character.objects.select_related("movie_introduced", "earth_number").order_by(
		"movie_introduced__release_date",
		"phase_introduced",
		"name",
	)

	context = {
		"alignment_choices": Character.ALIGNMENT_CHOICES,
		"status_choices": Character.STATUS_CHOICES,
		"relationship_choices": Relationship.RELATIONSHIP_CHOICES,
		"movie_choices": Movie.objects.order_by("release_date", "title"),
		"team_choices": Team.objects.order_by("name"),
		"grouped_character_options": _group_character_options(characters),
		"character_options": [
			{
				"id": character.id,
				"name": character.name,
				"display_name": f"{character.name} ({character.earth_number.number})" if character.earth_number else character.name,
			}
			for character in characters
		],
	}
	return render(request, "connections/graph.html", context)


@require_GET
def graph_view(request):
	graph = graph_service.build_graph()
	return _serialize_light_graph_response(graph)


@require_GET
def graph_filter_view(request):
	alignment = request.GET.getlist("alignment")
	phase = request.GET.get("phase")
	status = request.GET.getlist("status")
	earth = request.GET.getlist("earth")
	team = request.GET.getlist("team")
	movie = request.GET.getlist("movie")
	relationship_types = request.GET.getlist("relationship_types")

	graph, characters = graph_service.filtered_subgraph(
		alignment=alignment,
		phase=phase,
		status=status,
		earth=earth,
		team=team,
		movie=movie,
		relationship_types=relationship_types,
	)
	payload = graph_service.to_cytoscape_format(graph, characters, include_details=False)
	payload["filters"] = {
		"alignment": alignment,
		"phase": phase,
		"status": status,
		"earth": earth,
		"team": team,
		"movie": movie,
		"relationship_types": relationship_types,
	}
	return JsonResponse(payload)


@require_GET
def graph_character_detail_view(request, character_id):
	try:
		character_id = int(character_id)
	except ValueError:
		return _bad_request("'character_id' must be a numeric character ID.")

	details = graph_service.character_detail_payload(character_id)
	if details is None:
		return JsonResponse({"error": "Character was not found."}, status=404)

	return JsonResponse(details)


@require_GET
def graph_path_view(request):
	from_id = request.GET.get("from")
	to_id = request.GET.get("to")

	if not from_id or not to_id:
		return _bad_request("Both 'from' and 'to' are required.")

	try:
		path_data = graph_service.shortest_path(from_id, to_id)
	except ValueError:
		return _bad_request("'from' and 'to' must be numeric character IDs.")
	except NodeNotFound:
		return JsonResponse({"error": "One or both characters were not found."}, status=404)
	except NetworkXNoPath:
		return JsonResponse({"error": "No path exists between those characters."}, status=404)

	return JsonResponse(
		{
			"character_ids": path_data["character_ids"],
			"highlighted_nodes": [str(character_id) for character_id in path_data["character_ids"]],
			"highlighted_edges": [
				{
					"source": str(edge["source"]),
					"target": str(edge["target"]),
					"relationship_type": edge["relationship_type"],
					"relationship_types": edge["relationship_types"],
					"relationship_ids": edge["relationship_ids"],
					"weight": edge["weight"],
					"directional": edge["directional"],
				}
				for edge in path_data["edges"]
			],
			"total_cost": path_data["total_cost"],
		}
	)
