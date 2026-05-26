"""API views for the MCU graph endpoints."""

from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from networkx.exception import NetworkXNoPath, NodeNotFound

from .graph_service import MCUGraphService
from .models import Character, Team


graph_service = MCUGraphService()


def _bad_request(message):
	return JsonResponse({"error": message}, status=400)


def _serialize_graph_response(graph, characters=None):
	return JsonResponse(graph_service.to_cytoscape_format(graph, characters), safe=False)


@require_GET
def graph_page_view(request):
	characters = Character.objects.order_by("name")
	phase_choices = (
		Character.objects.exclude(phase_introduced__isnull=True)
		.order_by("phase_introduced")
		.values_list("phase_introduced", flat=True)
		.distinct()
	)

	context = {
		"alignment_choices": Character.ALIGNMENT_CHOICES,
		"status_choices": Character.STATUS_CHOICES,
		"phase_choices": list(phase_choices),
		"team_choices": Team.objects.order_by("name"),
		"character_options": [
			{"id": character.id, "name": character.name}
			for character in characters
		],
	}
	return render(request, "connections/graph.html", context)


@require_GET
def graph_view(request):
	graph = graph_service.build_graph()
	return JsonResponse(graph_service.to_cytoscape_format(graph))


@require_GET
def graph_filter_view(request):
	alignment = request.GET.get("alignment")
	phase = request.GET.get("phase")
	status = request.GET.get("status")
	team = request.GET.get("team")

	graph, characters = graph_service.filtered_subgraph(
		alignment=alignment,
		phase=phase,
		status=status,
		team=team,
	)
	payload = graph_service.to_cytoscape_format(graph, characters)
	payload["filters"] = {
		"alignment": alignment,
		"phase": phase,
		"status": status,
		"team": team,
	}
	return JsonResponse(payload)


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
