"""API views for the MCU graph endpoints."""

import json

from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.core.cache import cache

from networkx.exception import NetworkXNoPath, NodeNotFound

from .graph_service import MCUGraphService
from .models import Character, Movie, Relationship, Team, WatchEntry, WatchProgress
from .watch_order_service import WatchOrderService


graph_service = MCUGraphService()
watch_order_service = WatchOrderService()


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
				"aliases": [alter_ego.name for alter_ego in character.alter_egos.all()],
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
	characters = Character.objects.select_related("movie_introduced", "earth_number").prefetch_related("alter_egos").order_by(
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

	version = graph_service._get_cache_version()
	payload_cache_key = (
		f"connections:filter_payload:v{version}"
		f":a={','.join(sorted(alignment)) or '-'}"
		f":p={phase or '-'}"
		f":s={','.join(sorted(status)) or '-'}"
		f":e={','.join(sorted(earth)) or '-'}"
		f":t={','.join(sorted(team)) or '-'}"
		f":m={','.join(sorted(movie)) or '-'}"
		f":r={','.join(sorted(relationship_types)) or '-'}"
	)
	cached_payload = cache.get(payload_cache_key)
	if cached_payload is not None:
		return JsonResponse(cached_payload)

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
	cache.set(payload_cache_key, payload, graph_service.CACHE_TIMEOUT)
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


# --------------------------------------------------------------------------
# Watch order chart
# --------------------------------------------------------------------------


def _watched_slugs(user):
	if not user.is_authenticated:
		return []
	return list(
		WatchProgress.objects.filter(user=user).values_list("entry__slug", flat=True)
	)


@require_GET
def watch_order_page_view(request):
	"""The watch-order chart.

	Both payloads are inlined with json_script rather than fetched, so the chart
	paints in one pass with the right progress already applied.
	"""
	return render(
		request,
		"connections/watch_order.html",
		{
			"watch_order_payload": watch_order_service.build_payload(),
			"watched_slugs": _watched_slugs(request.user),
		},
	)


def _require_login(request):
	"""401 JSON instead of a login redirect, which fetch() cannot follow usefully."""
	if not request.user.is_authenticated:
		return JsonResponse({"error": "Sign in to save your progress."}, status=401)
	return None


def _json_body(request):
	try:
		return json.loads(request.body or "{}"), None
	except json.JSONDecodeError:
		return None, _bad_request("Request body must be JSON.")


@require_POST
def watch_order_watched_view(request):
	"""Mark a single entry watched or unwatched for the signed-in user."""
	unauthorized = _require_login(request)
	if unauthorized:
		return unauthorized

	body, error = _json_body(request)
	if error:
		return error

	slug = body.get("slug")
	if not slug:
		return _bad_request("'slug' is required.")

	try:
		entry = WatchEntry.objects.get(slug=slug)
	except WatchEntry.DoesNotExist:
		return JsonResponse({"error": "That entry was not found."}, status=404)

	if body.get("watched"):
		WatchProgress.objects.get_or_create(user=request.user, entry=entry)
	else:
		WatchProgress.objects.filter(user=request.user, entry=entry).delete()

	return JsonResponse(
		{
			"slug": slug,
			"watched": bool(body.get("watched")),
			"watched_count": WatchProgress.objects.filter(user=request.user).count(),
		}
	)


@require_POST
def watch_order_sync_view(request):
	"""Merge slugs ticked while signed out into the account.

	Union only - this never removes progress, so a stale localStorage list can
	never wipe out what the account already has.
	"""
	unauthorized = _require_login(request)
	if unauthorized:
		return unauthorized

	body, error = _json_body(request)
	if error:
		return error

	slugs = body.get("slugs")
	if not isinstance(slugs, list):
		return _bad_request("'slugs' must be a list.")

	entries = WatchEntry.objects.filter(slug__in=slugs)
	WatchProgress.objects.bulk_create(
		[WatchProgress(user=request.user, entry=entry) for entry in entries],
		ignore_conflicts=True,
	)

	return JsonResponse({"watched": _watched_slugs(request.user)})


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
