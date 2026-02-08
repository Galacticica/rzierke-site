"""
File: views.py
Author: Reagan Zierke <reaganzierke@gmail.com>
Date: 2026-02-07
Description: The views for the rzpercussion app, including piece listing with filtering.
"""

from django.shortcuts import render, get_object_or_404
from django.views import View
from django.views.generic import DetailView
from django.utils.text import slugify
from django.http import HttpResponse
from django.core.paginator import Paginator

from .models import Piece, Performer, Instrument
from .filters import PieceFilter


class PiecesListView(View):
    """
    The list view for pieces, with filtering and pagination.
    25 pieces per page.
    Supports HTMX for partial updates.
    """

    def get(self, request):
        base_qs = Piece.objects.with_display_related().order_by("title")

        piece_filter = PieceFilter(request.GET, queryset=base_qs)
        pieces = piece_filter.qs

        paginator = Paginator(pieces, 25)
        page_number = request.GET.get("page", 1)
        page_obj = paginator.get_page(page_number)

        context = {
            "pieces": page_obj.object_list,
            "page_obj": page_obj,
            "paginator": paginator,
            "filter": piece_filter,
            "q": request.GET.get("q", ""),
            "total_count": Piece.objects.count(),
            "filtered_count": pieces.count(),
        }

        if getattr(request, "htmx", False):
            target = request.headers.get("HX-Target", "")
            if target == "piece-layout":
                return render(request, "rzpercussion/partials/piece_layout.html", context)
            return render(request, "rzpercussion/partials/piece_results.html", context)

        return render(
            request,
            "rzpercussion/pieces_list.html",
            context,
        )


class PieceDetailView(DetailView):
    """
    The detail view for a single piece.
    Uses the queryset with related objects for display optimization.
    """

    model = Piece
    template_name = 'rzpercussion/piece_detail.html'
    context_object_name = 'piece'

    def get_queryset(self):
        return Piece.objects.with_display_related()