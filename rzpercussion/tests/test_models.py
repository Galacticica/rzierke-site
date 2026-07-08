"""
File: test_models.py
Description: Unit tests for rzpercussion models — Piece slug generation and
the PieceQuerySet helpers (search, with_display_related).
"""

import datetime

import pytest

from rzpercussion.models import Instrument, Performer, Piece, PieceType

pytestmark = pytest.mark.django_db


class TestPieceSlug:
    def test_slug_generated_from_title_on_save(self):
        piece = Piece.objects.create(title="Rebonds B", composer="Xenakis")
        assert piece.slug == "rebonds-b"

    def test_explicit_slug_is_kept(self):
        piece = Piece.objects.create(
            title="Rebonds B", composer="Xenakis", slug="my-custom-slug"
        )
        assert piece.slug == "my-custom-slug"

    def test_slug_not_regenerated_on_resave(self):
        piece = Piece.objects.create(title="Rebonds B", composer="Xenakis")
        piece.title = "Rebonds A"
        piece.save()
        piece.refresh_from_db()
        assert piece.slug == "rebonds-b"

    def test_slug_collision_appends_numeric_suffix(self):
        first = Piece.objects.create(title="Etude", composer="A")
        second = Piece.objects.create(title="Etude", composer="B")
        third = Piece.objects.create(title="Etude", composer="C")
        assert first.slug == "etude"
        assert second.slug == "etude-2"
        assert third.slug == "etude-3"

    def test_unslugifiable_title_falls_back_to_piece(self):
        piece = Piece.objects.create(title="!!!", composer="Anon")
        assert piece.slug == "piece"

    def test_unslugifiable_collision_gets_suffix(self):
        Piece.objects.create(title="!!!", composer="Anon")
        second = Piece.objects.create(title="???", composer="Anon")
        assert second.slug == "piece-2"

    def test_long_title_slug_fits_field(self):
        piece = Piece.objects.create(title="a" * 200, composer="Anon")
        assert piece.slug == "a" * 200
        # Collision on the long base must still fit max_length=220.
        clash = Piece.objects.create(title="a" * 200, composer="Anon")
        assert clash.slug == "a" * 200 + "-2"
        assert len(clash.slug) <= 220


class TestPieceQuerySet:
    @pytest.fixture
    def pieces(self):
        return [
            Piece.objects.create(title="Rebonds B", composer="Iannis Xenakis"),
            Piece.objects.create(title="Velocities", composer="Joseph Schwantner"),
            Piece.objects.create(title="Xenakis Tribute", composer="Someone Else"),
        ]

    def test_search_matches_title_case_insensitive(self, pieces):
        result = Piece.objects.search("rebonds")
        assert list(result) == [pieces[0]]

    def test_search_matches_composer(self, pieces):
        result = Piece.objects.search("schwantner")
        assert list(result) == [pieces[1]]

    def test_search_matches_title_or_composer(self, pieces):
        result = Piece.objects.search("xenakis")
        assert set(result) == {pieces[0], pieces[2]}

    def test_search_blank_query_returns_all(self, pieces):
        assert Piece.objects.search("").count() == 3
        assert Piece.objects.search("   ").count() == 3

    def test_search_none_returns_all(self, pieces):
        assert Piece.objects.search(None).count() == 3

    def test_search_strips_whitespace(self, pieces):
        result = Piece.objects.search("  rebonds  ")
        assert list(result) == [pieces[0]]

    def test_search_no_match_returns_empty(self, pieces):
        assert Piece.objects.search("does-not-exist").count() == 0

    def test_search_is_distinct(self):
        # A piece whose title AND composer both match must appear once.
        piece = Piece.objects.create(title="Xenakis Suite", composer="Xenakis")
        result = Piece.objects.search("xenakis")
        assert list(result) == [piece]

    def test_with_display_related_prefetches(self, django_assert_num_queries):
        piece = Piece.objects.create(
            title="Marimba Spiritual",
            composer="Minoru Miki",
            date_performed=datetime.date(2025, 5, 1),
            piece_type=PieceType.objects.create(name="Solo"),
        )
        piece.performer.add(Performer.objects.create(name="Reagan"))
        piece.instrument.add(Instrument.objects.create(name="Marimba"))

        # 1 for pieces + 3 prefetches; iterating relations costs nothing more.
        with django_assert_num_queries(4):
            fetched = list(Piece.objects.with_display_related())
            for p in fetched:
                list(p.performer.all())
                list(p.instrument.all())
                _ = p.piece_type

    def test_with_performers_prefetches_only_performers(self, django_assert_num_queries):
        piece = Piece.objects.create(title="Solo", composer="Anon")
        piece.performer.add(Performer.objects.create(name="Reagan"))

        with django_assert_num_queries(2):
            fetched = list(Piece.objects.with_performers())
            for p in fetched:
                list(p.performer.all())
