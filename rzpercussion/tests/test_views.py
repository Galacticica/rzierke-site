"""
File: test_views.py
Description: Unit tests for rzpercussion views — PiecesListView (full page,
HTMX partials, pagination, ordering, context counts) and PieceDetailView.

NOTE: Piece.public and Piece.super_private flags are NOT enforced by either
PiecesListView or PieceDetailView — non-public and super_private pieces are
served to anonymous visitors. That current behavior is deliberately not
asserted as "correct" here; if visibility enforcement is ever added, the
fixtures below (which leave the defaults public=True) will keep working.
"""

import datetime

import pytest
from django.urls import reverse

from rzpercussion.models import Instrument, Piece, PieceType

pytestmark = pytest.mark.django_db

LIST_URL_NAME = "pieces-list"


@pytest.fixture
def list_url():
    return reverse(LIST_URL_NAME)


def make_pieces(n, **kwargs):
    """bulk_create bypasses save(), so slugs must be set explicitly."""
    return Piece.objects.bulk_create(
        Piece(title=f"Piece {i:03d}", composer="Anon", slug=f"piece-{i:03d}", **kwargs)
        for i in range(n)
    )


class TestPiecesListView:
    def test_url_resolves(self, list_url):
        assert list_url == "/rzpercussion/"

    def test_full_page_uses_list_template(self, client, list_url):
        response = client.get(list_url)
        assert response.status_code == 200
        template_names = [t.name for t in response.templates]
        assert "rzpercussion/pieces_list.html" in template_names

    def test_htmx_request_returns_results_partial(self, client, list_url, htmx_headers):
        response = client.get(list_url, **htmx_headers)
        assert response.status_code == 200
        template_names = [t.name for t in response.templates]
        assert "rzpercussion/partials/piece_results.html" in template_names
        assert "rzpercussion/pieces_list.html" not in template_names

    def test_htmx_layout_target_returns_layout_partial(self, client, list_url, htmx_headers):
        response = client.get(
            list_url, HTTP_HX_TARGET="piece-layout", **htmx_headers
        )
        assert response.status_code == 200
        template_names = [t.name for t in response.templates]
        assert "rzpercussion/partials/piece_layout.html" in template_names
        assert "rzpercussion/pieces_list.html" not in template_names

    def test_non_htmx_ignores_hx_target_header(self, client, list_url):
        response = client.get(list_url, HTTP_HX_TARGET="piece-layout")
        assert "rzpercussion/pieces_list.html" in [t.name for t in response.templates]

    def test_pagination_25_per_page(self, client, list_url):
        make_pieces(30)

        response = client.get(list_url)
        assert len(response.context["pieces"]) == 25
        assert response.context["paginator"].num_pages == 2

        response = client.get(list_url, {"page": 2})
        assert len(response.context["pieces"]) == 5

    def test_out_of_range_page_returns_last_page(self, client, list_url):
        make_pieces(30)
        response = client.get(list_url, {"page": 99})
        assert response.status_code == 200
        assert response.context["page_obj"].number == 2

    def test_invalid_page_returns_first_page(self, client, list_url):
        make_pieces(3)
        response = client.get(list_url, {"page": "not-a-number"})
        assert response.status_code == 200
        assert response.context["page_obj"].number == 1

    def test_ordering_by_date_desc_then_title(self, client, list_url):
        newer = Piece.objects.create(
            title="Zeta", composer="A", date_performed=datetime.date(2025, 6, 1)
        )
        older_b = Piece.objects.create(
            title="Beta", composer="A", date_performed=datetime.date(2024, 1, 1)
        )
        older_a = Piece.objects.create(
            title="Alpha", composer="A", date_performed=datetime.date(2024, 1, 1)
        )

        response = client.get(list_url)
        assert list(response.context["pieces"]) == [newer, older_a, older_b]

    def test_context_counts_unfiltered(self, client, list_url):
        make_pieces(3)
        response = client.get(list_url)
        context = response.context
        assert context["total_count"] == 3
        assert context["filtered_count"] == 3
        assert context["piece_type_filter_count"] == 0
        assert context["instrument_filter_count"] == 0
        assert context["q"] == ""

    def test_context_counts_with_filters(self, client, list_url):
        solo = PieceType.objects.create(name="Solo")
        duo = PieceType.objects.create(name="Duo")
        marimba = Instrument.objects.create(name="Marimba")
        Piece.objects.create(title="Match Me", composer="Anon", piece_type=solo)
        Piece.objects.create(title="Other", composer="Anon", piece_type=duo)

        response = client.get(
            f"{list_url}?q=match&piece_type={solo.pk}&piece_type={duo.pk}"
            f"&instrument={marimba.pk}"
        )
        context = response.context
        assert context["total_count"] == 2
        assert context["filtered_count"] == 0  # q matches, but no instrument tagged
        assert context["piece_type_filter_count"] == 2
        assert context["instrument_filter_count"] == 1
        assert context["q"] == "match"

    def test_q_filters_results(self, client, list_url):
        keep = Piece.objects.create(title="Rebonds B", composer="Xenakis")
        Piece.objects.create(title="Velocities", composer="Schwantner")

        response = client.get(list_url, {"q": "rebonds"})
        assert list(response.context["pieces"]) == [keep]
        assert response.context["filtered_count"] == 1
        assert response.context["total_count"] == 2


class TestPieceDetailView:
    def test_detail_by_slug(self, client):
        piece = Piece.objects.create(title="Rebonds B", composer="Xenakis")
        response = client.get(reverse("piece-detail", kwargs={"slug": piece.slug}))
        assert response.status_code == 200
        assert response.context["piece"] == piece
        assert "rzpercussion/piece_detail.html" in [t.name for t in response.templates]

    def test_unknown_slug_404s(self, client):
        response = client.get(reverse("piece-detail", kwargs={"slug": "no-such-piece"}))
        assert response.status_code == 404
