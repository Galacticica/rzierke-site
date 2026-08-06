"""TMDB lookups for watch-order metadata: release year, runtime, episode counts.

Only ever fills in what an entry is missing. Nothing here is required for the
chart to work - if the key is unset or TMDB is down, entries simply keep
whatever they were given by hand, so adding a film never depends on the network.

A series is entered one season per tile ("Daredevil Season 1"), so the season
number is parsed off the title when it isn't set explicitly, and the episode
count and runtime come from that season rather than the whole show.
"""

import hashlib
import logging
import re
import statistics

import requests
from django.conf import settings
from django.core.cache import cache

from .title_parsing import parse_title

logger = logging.getLogger(__name__)

API_BASE = "https://api.themoviedb.org/3"
REQUEST_TIMEOUT = 8
CACHE_TTL = 60 * 60 * 24 * 7  # metadata for released titles barely changes

# Which TMDB endpoint a media type belongs to. Specials are usually filed as
# movies, but the search falls back to the other endpoint either way.
MEDIA_TYPE_ENDPOINTS = {"Series": "tv", "Film": "movie", "Special": "movie"}


class TMDBError(RuntimeError):
	"""Any reason a lookup could not be completed."""


def is_configured():
	return bool(getattr(settings, "TMDB_API_KEY", ""))


def split_season(title):
	"""'Daredevil Season 1' -> ('Daredevil', 1). No suffix -> (title, None)."""
	parsed = parse_title(title)
	return parsed.base, parsed.season


def _get(path, **params):
	if not is_configured():
		raise TMDBError("TMDB_API_KEY is not set. Add it to .env to enable lookups.")

	# Hashed because titles contain spaces and punctuation, which are not valid
	# in a memcached key even though locmem tolerates them.
	fingerprint = path + "?" + "&".join(
		f"{key}={value}" for key, value in sorted(params.items()) if value not in (None, "")
	)
	cache_key = "connections:tmdb:" + hashlib.sha1(fingerprint.encode()).hexdigest()
	cached = cache.get(cache_key)
	if cached is not None:
		return cached

	query = {key: value for key, value in params.items() if value not in (None, "")}
	query["api_key"] = settings.TMDB_API_KEY

	try:
		response = requests.get(f"{API_BASE}{path}", params=query, timeout=REQUEST_TIMEOUT)
		response.raise_for_status()
		payload = response.json()
	except requests.RequestException as error:
		raise TMDBError(f"TMDB request failed: {error}") from error

	cache.set(cache_key, payload, CACHE_TTL)
	return payload


def search(title, endpoint, year=None):
	"""The best-matching TMDB id for a title, or None."""
	year_field = "first_air_date_year" if endpoint == "tv" else "year"
	results = _get(f"/search/{endpoint}", query=title, **{year_field: year}).get("results") or []
	if not results and year:
		# The year on file can disagree with TMDB's (a season's air date vs the
		# show's première), so retry without it before giving up.
		results = _get(f"/search/{endpoint}", query=title).get("results") or []
	return results[0]["id"] if results else None


def _year_of(date_string):
	if date_string and len(date_string) >= 4 and date_string[:4].isdigit():
		return int(date_string[:4])
	return None


def _movie_metadata(tmdb_id):
	details = _get(f"/movie/{tmdb_id}")
	return {
		"release_year": _year_of(details.get("release_date")),
		"runtime_minutes": details.get("runtime") or None,
		"episode_count": None,
	}


def _tv_metadata(tmdb_id, season=None, episode_range=None):
	details = _get(f"/tv/{tmdb_id}")
	runtimes = details.get("episode_run_time") or []
	show_runtime = round(statistics.mean(runtimes)) if runtimes else None

	if season is None:
		return {
			"release_year": _year_of(details.get("first_air_date")),
			"runtime_minutes": show_runtime,
			"episode_count": details.get("number_of_episodes") or None,
		}

	season_details = _get(f"/tv/{tmdb_id}/season/{season}")
	episodes = season_details.get("episodes") or []

	air_date = season_details.get("air_date")
	if episode_range:
		# An entry covering only part of a season counts and times just those
		# episodes, so the runtime total reflects what you actually sit through.
		first, last = episode_range
		episodes = [
			episode for episode in episodes
			if first <= episode.get("episode_number", 0) <= last
		]
		if episodes:
			air_date = episodes[0].get("air_date") or air_date

	episode_runtimes = [episode["runtime"] for episode in episodes if episode.get("runtime")]

	return {
		"release_year": _year_of(air_date) or _year_of(details.get("first_air_date")),
		# Per-episode runtime, so total_minutes multiplies out correctly.
		"runtime_minutes": round(statistics.mean(episode_runtimes)) if episode_runtimes else show_runtime,
		"episode_count": len(episodes) or None,
	}


def fetch_metadata(title, media_type="Film", release_year=None, tmdb_id=None, tmdb_type="", season=None):
	"""Look up one title. Returns the metadata dict, or raises TMDBError.

	A stored `tmdb_id` skips the search entirely, which is how a wrong match
	gets corrected: set the id by hand and re-run.
	"""
	parsed = parse_title(title)
	search_title = parsed.base

	# The title is what the tile displays, so when it names a season that wins
	# over the stored one. tmdb_season is the override for titles that don't say.
	if parsed.season is not None:
		season = parsed.season

	endpoint = tmdb_type or MEDIA_TYPE_ENDPOINTS.get(media_type, "movie")
	# A title with a season suffix is a series whatever the media type says.
	if season is not None:
		endpoint = "tv"

	if not tmdb_id:
		tmdb_id = search(search_title, endpoint, release_year)
		if not tmdb_id:
			fallback = "movie" if endpoint == "tv" else "tv"
			tmdb_id = search(search_title, fallback, release_year)
			if tmdb_id:
				endpoint = fallback
	if not tmdb_id:
		raise TMDBError(f"Nothing on TMDB matched '{search_title}'.")

	if endpoint == "tv":
		metadata = _tv_metadata(tmdb_id, season, parsed.episode_range)
	else:
		metadata = _movie_metadata(tmdb_id)
	metadata.update({"tmdb_id": tmdb_id, "tmdb_type": endpoint, "tmdb_season": season})
	return metadata


FILLABLE_FIELDS = ("release_year", "runtime_minutes", "episode_count")


def apply_to_entry(entry, overwrite=False, save=True):
	"""Fill an entry's blank metadata from TMDB. Returns the field names changed.

	Blank-only by default, so anything typed by hand is safe. Raises TMDBError,
	which callers are expected to catch - a failed lookup must never stop an
	entry from being saved.
	"""
	metadata = fetch_metadata(
		title=entry.title,
		media_type=entry.media_type,
		release_year=entry.release_year,
		tmdb_id=entry.tmdb_id,
		tmdb_type=entry.tmdb_type,
		season=entry.tmdb_season,
	)

	changed = []
	for field in FILLABLE_FIELDS:
		value = metadata.get(field)
		if value is None:
			continue
		if overwrite or getattr(entry, field) in (None, ""):
			if getattr(entry, field) != value:
				setattr(entry, field, value)
				changed.append(field)

	for field in ("tmdb_id", "tmdb_type", "tmdb_season"):
		value = metadata.get(field)
		if value is not None and getattr(entry, field) != value:
			setattr(entry, field, value)
			changed.append(field)

	if changed and save:
		entry.save(update_fields=changed)
	return changed
