"""Build and serialize the Marvel watch-order chart.

The chart is a DAG. Entries inside a track are chained in `position` order, and
explicit `prerequisites` links carry the interesting part: merges across tracks,
like the X-Men lane feeding into Doomsday or the older Spider-Man lanes feeding
into No Way Home.

Row assignment lives in the browser (static/src/watch-order.js) so that toggling
a track re-lays-out without a round trip. This module only serializes the raw
nodes and edges. The two share one contract: edges point from "watch this first"
to "watch this after".
"""

from django.core.cache import cache
from django.templatetags.static import static

from .models import WatchCollection, WatchEntry, WatchOrderConfig, WatchTrack


class WatchOrderService:
	"""Serialize the watch-order DAG, with the same versioned caching as the graph."""

	CACHE_PREFIX = "connections:watchorder"
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

	def _poster_url(self, poster_path):
		"""Static URL for a committed poster, or "" so the tile falls back to text.

		Entries added from production have no poster until the image file is
		committed and deployed, so a blank path is a normal state, not an error.
		"""
		if not poster_path:
			return ""
		if poster_path.startswith(("http://", "https://", "/")):
			return poster_path
		return static(poster_path)

	def _entry_payload(self, entry, lanes):
		return {
			"slug": entry.slug,
			"title": entry.title,
			"track": entry.track.slug,
			"track_name": entry.track.name,
			"track_color": entry.track.color,
			"lane": lanes[entry.track.slug],
			"media_type": entry.media_type,
			"year": entry.release_year,
			"runtime_minutes": entry.runtime_minutes,
			"episode_count": entry.episode_count,
			"total_minutes": entry.total_minutes,
			"poster_url": self._poster_url(entry.poster_path),
			"note": entry.note,
			"movie_id": entry.movie_id,
			"connects_to_previous": entry.connects_to_previous,
			"collections": [collection.slug for collection in entry.collections.all()],
		}

	def _columns(self, tracks):
		"""Group tracks into columns by following continues_from chains.

		Returns a list of chains, each ordered head first. A track with no
		continues_from starts its own column; one that continues another is
		appended below it in the same column.
		"""
		by_id = {track.pk: track for track in tracks}

		# continues_from points backwards, so invert it to walk a column downwards.
		next_of = {}
		for track in tracks:
			if track.continues_from_id in by_id:
				next_of[track.continues_from_id] = track

		roots = sorted(
			(track for track in tracks if track.continues_from_id not in by_id),
			key=lambda track: (track.lane_order, track.name),
		)

		columns, placed = [], set()
		for root in roots:
			chain, track = [], root
			while track is not None and track.pk not in placed:
				chain.append(track)
				placed.add(track.pk)
				track = next_of.get(track.pk)
			columns.append(chain)

		# Anything left is caught in a continues_from loop. Give each its own
		# column rather than dropping it off the chart entirely.
		for track in tracks:
			if track.pk not in placed:
				placed.add(track.pk)
				columns.append([track])

		return columns

	def published_entries(self):
		return (
			WatchEntry.objects.filter(is_published=True, track__is_active=True)
			.select_related("track")
			.prefetch_related("prerequisites", "collections")
			.order_by("track__lane_order", "position", "pk")
		)

	def build_payload(self):
		"""Serialize tracks, entries, and edges for the client-side layout."""
		cache_key = self._cache_key("payload")
		cached = cache.get(cache_key)
		if cached is not None:
			return cached

		tracks = list(WatchTrack.objects.filter(is_active=True).select_related("continues_from"))
		columns = self._columns(tracks)

		# Tracks that continue one another share a lane, so two halves of one
		# storyline read as a single column rather than two parallel ones.
		lanes, sequences = {}, {}
		for lane, chain in enumerate(columns):
			for sequence, track in enumerate(chain):
				lanes[track.slug] = lane
				sequences[track.slug] = sequence

		# Ordered by position alone within a lane, never by which track an entry
		# belongs to: position is scoped to the column, so a Multiverse Saga entry
		# can sit between two Infinity Saga ones.
		entries = sorted(
			self.published_entries(),
			key=lambda entry: (lanes[entry.track.slug], entry.position, entry.pk),
		)
		visible_slugs = {entry.slug for entry in entries}

		# Only the explicit merges are sent. The chain down each lane is rebuilt in
		# the browser from whatever is currently on screen, because a collection
		# filter can leave gaps in a track - a stored chain would drop the entries
		# either side of the gap onto the same row, on top of each other.
		# Prerequisites pointing at a hidden entry are skipped so the client never
		# has to render a dangling arrow.
		edges = [
			{"source": prerequisite.slug, "target": entry.slug, "kind": "prerequisite"}
			for entry in entries
			for prerequisite in entry.prerequisites.all()
			if prerequisite.slug in visible_slugs
		]

		payload = {
			"tracks": [
				{
					"slug": track.slug,
					"name": track.name,
					"color": track.color,
					"lane": lanes[track.slug],
				}
				for track in sorted(tracks, key=lambda track: (lanes[track.slug], sequences[track.slug]))
			],
			"collections": [
				{
					"slug": collection.slug,
					"name": collection.name,
					"description": collection.description,
					"count": sum(1 for entry in entries if collection in entry.collections.all()),
				}
				for collection in WatchCollection.objects.filter(is_active=True)
			],
			"entries": [self._entry_payload(entry, lanes) for entry in entries],
			"edges": edges,
			"items_per_row": WatchOrderConfig.current().items_per_row or 0,
		}
		cache.set(cache_key, payload, self.CACHE_TIMEOUT)
		return payload


# Stand-in id for an entry that has not been saved yet, so a brand-new row can
# still be checked for cycles. Real ids are always positive.
UNSAVED_PK = -1


def build_edge_index(entries, extra_edges=(), ignore_saved_prerequisites_for=()):
	"""Adjacency over prerequisite links only.

	Position order is deliberately excluded. It is the order the list reads in,
	not a constraint, and folding it in here would reject perfectly good
	non-linear franchises: X-Men: First Class comes before Origins: Wolverine in
	story terms while sitting later in the list, which is a contradiction only if
	position is treated as a rule. The chart resolves that by letting the stated
	prerequisite win and dropping the implied one.

	`extra_edges` tests edges that are not saved yet, and
	`ignore_saved_prerequisites_for` drops an entry's stored prerequisites so the
	admin form can validate the set the user just submitted rather than the one
	still in the database.
	"""
	successors = {entry.pk: set() for entry in entries}
	ignored = set(ignore_saved_prerequisites_for)

	for entry in entries:
		if entry.pk in ignored or entry.pk == UNSAVED_PK:
			continue
		for prerequisite in entry.prerequisites.all():
			if prerequisite.pk in successors:
				successors[prerequisite.pk].add(entry.pk)

	for source_id, target_id in extra_edges:
		if source_id in successors and target_id in successors:
			successors[source_id].add(target_id)

	return successors


def find_cycle_nodes(successors):
	"""Ids left over after a topological sort, i.e. the ones caught in a cycle."""
	indegree = {node_id: 0 for node_id in successors}
	for targets in successors.values():
		for target_id in targets:
			indegree[target_id] += 1

	queue = [node_id for node_id, degree in indegree.items() if degree == 0]
	visited = 0
	while queue:
		node_id = queue.pop()
		visited += 1
		for target_id in successors[node_id]:
			indegree[target_id] -= 1
			if indegree[target_id] == 0:
				queue.append(target_id)

	if visited == len(successors):
		return set()
	return {node_id for node_id, degree in indegree.items() if degree > 0}


def would_create_cycle(entry, prerequisite_ids):
	"""True when giving `entry` these prerequisites closes a loop.

	Only a genuine loop among stated prerequisites counts - A before B before A.
	Contradicting the list order is allowed, because the list order is just how
	the chart reads top to bottom, not a claim about what has to come first.

	`entry` may be unsaved; its submitted prerequisites replace whatever is
	stored, so removing a prerequisite is never reported as still cyclic.
	"""
	entry_pk = entry.pk if entry.pk is not None else UNSAVED_PK

	entries = [
		item
		for item in WatchEntry.objects.select_related("track").prefetch_related("prerequisites")
		if item.pk != entry_pk
	]

	# A shallow copy keeps the caller's instance untouched while we give the
	# unsaved row a usable node key.
	probe = WatchEntry(
		pk=entry_pk,
		track_id=entry.track_id,
		position=entry.position,
	)
	entries.append(probe)

	successors = build_edge_index(
		entries,
		extra_edges=[(prerequisite_id, entry_pk) for prerequisite_id in prerequisite_ids],
		ignore_saved_prerequisites_for=[entry_pk],
	)
	return bool(find_cycle_nodes(successors))
