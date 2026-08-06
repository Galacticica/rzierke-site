"""Read the season and episode range back off a watch-order title.

Titles are written for people first - "Agents of S.H.I.E.L.D. Season 1 Ep 1-7" -
rather than split across fields, so the structured parts are parsed off the end
of the string. Both the poster matcher and the TMDB lookup need them, and they
need to agree, so the parsing lives here rather than in either one.
"""

import re
from dataclasses import dataclass

# "Ep 1-7", "Episodes 1 to 7", "E1", "eps 3-5". A bare "e" must start a word, so
# "Avengers 2" and "Spider-Man 3" are never read as episodes.
EPISODE_SUFFIX = re.compile(
	r"\s*[-–—:,]?\s*"
	r"(?:(?:episodes?|eps?)\s*|\be)"
	r"(\d+)"
	r"(?:\s*(?:[-–—]|through|thru|to)\s*(\d+))?"
	r"\s*$",
	re.IGNORECASE,
)

# "Season 1", "- Season 2", "S3". The word boundary keeps "Avengers 2" from
# being read as "Avenger" season 2.
SEASON_SUFFIX = re.compile(r"\s*[-–—:,]?\s*(?:season|\bs)\s*(\d+)\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class ParsedTitle:
	base: str
	season: int = None
	first_episode: int = None
	last_episode: int = None

	@property
	def episode_range(self):
		"""(first, last) inclusive, or None. A single episode is a range of one."""
		if self.first_episode is None:
			return None
		return (self.first_episode, self.last_episode or self.first_episode)

	@property
	def poster_title(self):
		"""What to match a poster file against.

		Posters exist per season, not per episode range, so an entry covering
		episodes 1-7 of season 1 wants the season 1 poster.
		"""
		if self.season is not None:
			return f"{self.base} Season {self.season}"
		return self.base


def parse_title(title):
	"""'Agents of S.H.I.E.L.D. Season 1 Ep 1-7' -> base, season 1, episodes 1-7."""
	text = (title or "").strip()

	first_episode = last_episode = None
	episode_match = EPISODE_SUFFIX.search(text)
	if episode_match:
		first_episode = int(episode_match.group(1))
		last_episode = int(episode_match.group(2)) if episode_match.group(2) else None
		text = EPISODE_SUFFIX.sub("", text).strip()

	season = None
	season_match = SEASON_SUFFIX.search(text)
	if season_match:
		season = int(season_match.group(1))
		text = SEASON_SUFFIX.sub("", text).strip()

	return ParsedTitle(text, season, first_episode, last_episode)
