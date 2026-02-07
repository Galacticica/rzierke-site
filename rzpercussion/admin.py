"""
File: admin.py
Author: Reagan Zierke <reaganzierke@gmail.com>
Date: 2026-02-07
Description: The admin configurations for rzpercussion models.
- Provides enhanced interfaces for managing pieces, performers, instruments, and piece types.
"""

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import Piece, Performer, Instrument, PieceType


@admin.register(Performer)
class PerformerAdmin(admin.ModelAdmin):
    """Register Performer model in admin with basic configurations."""
    search_fields = ("name",)


@admin.register(Instrument)
class InstrumentAdmin(admin.ModelAdmin):
    """Register Instrument model in admin with basic configurations."""
    search_fields = ("name",)


@admin.register(PieceType)
class PieceTypeAdmin(admin.ModelAdmin):
    """Register PieceType model in admin with basic configurations."""
    search_fields = ("name",)


@admin.register(Piece)
class PieceAdmin(admin.ModelAdmin):
    """
    Register Piece model in admin with enhanced configurations.
    This includes filter_horizontal for easy relationship management,
    custom list displays, search fields, and optimized queryset.
    """
    list_display = ("title", "composer", "piece_type_name", "performers", "instruments", "public_link")
    search_fields = ("title", "composer", "performer__name", "instrument__name", "piece_type__name")
    list_filter = ("public", "piece_type", "date_performed")
    filter_horizontal = ("performer", "instrument")
    readonly_fields = ("slug",)
    fieldsets = (
        ("Basic Info", {
            "fields": ("title", "composer", "slug", "description")
        }),
        ("Relationships", {
            "fields": ("performer", "instrument", "piece_type")
        }),
        ("Metadata", {
            "fields": ("public", "date_performed", "recording_url")
        }),
    )

    @admin.display(description="Piece Type")
    def piece_type_name(self, obj):
        return obj.piece_type.name if obj.piece_type else "—"

    @admin.display(description="Performers")
    def performers(self, obj):
        names = list(obj.performer.values_list("name", flat=True))
        return ", ".join(names) if names else "—"

    @admin.display(description="Instruments")
    def instruments(self, obj):
        names = list(obj.instrument.values_list("name", flat=True))
        return ", ".join(names) if names else "—"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related("performer", "instrument", "piece_type")

    @admin.display(description="Public page")
    def public_link(self, obj):
        """
        Link to /percussion/pieces/<slug>/ using the named URL 'piece-detail'.
        """
        if not obj.public or not getattr(obj, "slug", None):
            return "—"
        url = reverse("piece-detail", kwargs={"slug": obj.slug})
        return format_html('<a href="{}" target="_blank">View</a>', url)
