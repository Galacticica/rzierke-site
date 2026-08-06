"""Tests for reading season and episode ranges off a title.

The dangerous direction is over-eager matching: a film whose title ends in a
number must never be read as a season or an episode.
"""

import pytest

from connections.title_parsing import parse_title


class TestSeason:
    @pytest.mark.parametrize(
        "title,base,season",
        [
            ("Daredevil Season 1", "Daredevil", 1),
            ("Loki - Season 2", "Loki", 2),
            ("Hawkeye: Season 1", "Hawkeye", 1),
            ("Daredevil S1", "Daredevil", 1),
            ("Agents of S.H.I.E.L.D. Season 7", "Agents of S.H.I.E.L.D.", 7),
        ],
    )
    def test_parses_a_season(self, title, base, season):
        parsed = parse_title(title)
        assert (parsed.base, parsed.season) == (base, season)


class TestEpisodeRange:
    @pytest.mark.parametrize(
        "title,base,season,episodes",
        [
            ("Agents of Shield Season 1 Ep 1-7", "Agents of Shield", 1, (1, 7)),
            ("Agents of Shield Season 1 Episodes 8-13", "Agents of Shield", 1, (8, 13)),
            ("Daredevil Season 1 E1", "Daredevil", 1, (1, 1)),
            ("Loki Season 2 Ep 3 to 6", "Loki", 2, (3, 6)),
            ("Daredevil S1 Ep 1-4", "Daredevil", 1, (1, 4)),
            ("Daredevil Season 2 eps 5-8", "Daredevil", 2, (5, 8)),
        ],
    )
    def test_parses_an_episode_range(self, title, base, season, episodes):
        parsed = parse_title(title)
        assert (parsed.base, parsed.season, parsed.episode_range) == (base, season, episodes)

    def test_a_single_episode_is_a_range_of_one(self):
        assert parse_title("Loki Season 1 Ep 4").episode_range == (4, 4)

    def test_no_episode_suffix_means_the_whole_season(self):
        assert parse_title("Daredevil Season 1").episode_range is None


class TestFilmsAreNotMisread:
    """The failure that would matter: a film treated as a season or episode."""

    @pytest.mark.parametrize(
        "title",
        [
            "Iron Man",
            "Iron Man 2",
            "Iron Man 3",
            "Spider-Man 3",
            "Avengers 2",
            "Deadpool 2",
            "X2",
            "Guardians of the Galaxy Vol. 3",
            "Ant-Man and the Wasp",
            "The Marvels",
            "Blade II",
            "Fantastic Four",
        ],
    )
    def test_left_completely_alone(self, title):
        parsed = parse_title(title)
        assert parsed.base == title
        assert parsed.season is None
        assert parsed.episode_range is None


class TestPosterTitle:
    def test_an_episode_range_still_asks_for_the_season_poster(self):
        """Posters exist per season, never per episode range."""
        assert parse_title("Agents of Shield Season 1 Ep 1-7").poster_title == (
            "Agents of Shield Season 1"
        )

    def test_a_season_keeps_its_season(self):
        assert parse_title("Daredevil Season 2").poster_title == "Daredevil Season 2"

    def test_a_film_is_unchanged(self):
        assert parse_title("Iron Man").poster_title == "Iron Man"
