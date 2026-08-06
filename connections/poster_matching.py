"""Match watch-order entries to the poster files committed in the repo.

Posters live in static/public/watch-order/ under names like
`spider-man_no_way_home_2021.jpg`. Rather than making anyone type that path,
both sides get flattened to a comparable key and looked up.

Used by the admin form (fills poster_path on save) and by the
link_watch_posters management command (backfills in bulk).
"""

import re
from pathlib import Path

from django.conf import settings

from .title_parsing import parse_title

POSTER_DIR = Path(settings.BASE_DIR) / "static" / "public" / "watch-order"
POSTER_PREFIX = "watch-order/"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".avif"}


def normalize(value):
	"""Collapse a title or filename to a comparable key.

	'Spider-Man: No Way Home' and 'spider-man_no_way_home' both become
	'spider man no way home', which is what makes the two sides line up.
	Apostrophes are deleted rather than split on, so "Marvel's Daredevil"
	matches marvels_daredevil.png instead of becoming "marvel s daredevil".
	"""
	value = value.lower().replace("'", "").replace("’", "")
	return re.sub(r"[^a-z0-9]+", " ", value).strip()


def poster_files():
	if not POSTER_DIR.is_dir():
		return []
	return [
		path
		for path in sorted(POSTER_DIR.iterdir())
		if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
	]


def collapse_initials(key):
	"""'agents of s h i e l d 2013' -> 'agents of shield 2013'.

	Stripping the dots out of S.H.I.E.L.D. leaves it spelled letter by letter,
	which no one types. Runs of three or more single letters are joined back up.
	"""
	return re.sub(r"\b(?:[a-z] ){2,}[a-z]\b", lambda match: match.group(0).replace(" ", ""), key)


def poster_index():
	"""Map each normalized key to the files that claim it.

	A key can have more than one file - the same title as both .jpg and .png -
	which is exactly the case that must never be auto-assigned. Files whose name
	contains a spelled-out acronym are indexed under both spellings.
	"""
	index = {}
	for path in poster_files():
		key = normalize(path.stem)
		index.setdefault(key, []).append(path)

		collapsed = collapse_initials(key)
		if collapsed != key:
			index.setdefault(collapsed, []).append(path)
	return index


def _tokens(value):
	return set(normalize(value).split())


def _best_containing(index, required):
	"""The file whose tokens contain `required` with the least left over.

	Filenames carry extra words the title does not - a studio prefix, the year -
	so "Daredevil Season 1" has to be able to find
	marvels_daredevil_2015_-_season_1.png. Ranking by how much is left over
	keeps "Daredevil" on the series poster rather than a season one. A tie means
	genuinely undecidable, so nothing is returned.
	"""
	# Keyed by path: one file can be indexed under several spellings, and hitting
	# two of them is one match, not an ambiguous pair.
	best_by_path = {}
	for key, paths in index.items():
		file_tokens = set(key.split())
		if required and required <= file_tokens:
			extras = len(file_tokens - required)
			for path in paths:
				best_by_path[path] = min(extras, best_by_path.get(path, extras))

	if not best_by_path:
		return None, []

	fewest_extras = min(best_by_path.values())
	winners = [path for path, extras in best_by_path.items() if extras == fewest_extras]
	return (winners[0], []) if len(winners) == 1 else (None, sorted(winners))


def resolve_poster(title, release_year=None, index=None):
	"""Find this title's poster. Returns (poster_path or None, tied candidates).

	Matching runs in tiers, strictest first, so an exact filename always beats a
	looser token match:
	  1. the whole title plus year, exactly
	  2. the whole title, exactly (for files that carry no year)
	  3. every title word plus the year appearing somewhere in the filename
	  4. every title word appearing somewhere in the filename
	"""
	if not title:
		return None, []
	if index is None:
		index = poster_index()

	# Posters exist per season, so an entry covering only part of a season still
	# wants that season's poster - the episode range is dropped for matching.
	title = parse_title(title).poster_title

	exact_keys = []
	if release_year:
		exact_keys.append(normalize(f"{title} {release_year}"))
	exact_keys.append(normalize(title))

	for key in exact_keys:
		candidates = index.get(key)
		if candidates:
			if len(candidates) == 1:
				return POSTER_PREFIX + candidates[0].name, []
			return None, candidates

	required_sets = []
	if release_year:
		required_sets.append(_tokens(title) | {str(release_year)})
	required_sets.append(_tokens(title))

	for required in required_sets:
		winner, tied = _best_containing(index, required)
		if winner:
			return POSTER_PREFIX + winner.name, []
		if tied:
			return None, tied

	return None, []


def find_poster(title, release_year=None, index=None):
	"""The one poster matching this title, or None when absent or ambiguous."""
	return resolve_poster(title, release_year, index)[0]
