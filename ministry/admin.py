"""
File: admin.py
Author: Reagan Zierke <reaganzierke@gmail.com>
Date: 2026-02-05
Description: The admin configurations for ministry models.
- Provides enhanced interfaces for managing songs, artists, tags, sections, and arrangements.
"""


from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html

from .models import Song, Artist, Tag, SectionDefinition, ArrangementItem, Devotion

@admin.register(Devotion)
class DevotionAdmin(admin.ModelAdmin):
    """Register Devotion model in admin with basic configurations."""
    list_display = ("title", "date")
    date_hierarchy = "date"
    search_fields = ("title", "bible_passage")

@admin.register(Artist)
class ArtistAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    search_fields = ("name",)


class SectionDefinitionInline(admin.StackedInline):
    """Register SectionDefinition as inline in Song admin."""
    model = SectionDefinition
    extra = 0
    fields = ("section_type", "name", "lyrics")
    classes = ("collapse",) 
    show_change_link = True


class ArrangementItemInline(admin.TabularInline):
    """Register ArrangementItem as inline in Song admin."""
    model = ArrangementItem
    extra = 0
    fields = ("order", "section", "repeat_count")
    ordering = ("order",)
    autocomplete_fields = ("section",)
    classes = ("collapse",)  


@admin.register(SectionDefinition)
class SectionDefinitionAdmin(admin.ModelAdmin):
    """Register SectionDefinition model in admin with basic configurations."""
    list_display = ("song", "section_type", "name")
    list_filter = ("section_type",)
    search_fields = ("name", "lyrics", "song__title")


@admin.register(Song)
class SongAdmin(admin.ModelAdmin):
    """
    Register Song model in admin with enhanced configurations.
    This includes inlines for sections and arrangement items,
    custom list displays, search fields, and optimized queryset.
    """
    list_display = ("title", "artists", "lsb_number", "ccli_number", "public_link")
    search_fields = ("title", "lsb_number", "ccli_number", "artist__name", "tag__name")
    filter_horizontal = ("artist", "tag")
    inlines = [SectionDefinitionInline, ArrangementItemInline]

    @admin.display(description="Artists")
    def artists(self, obj):
        names = list(obj.artist.values_list("name", flat=True))
        return ", ".join(names) if names else "—"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related("artist", "tag")

    @admin.display(description="Public page")
    def public_link(self, obj):
        """
        Link to /ministry/songs/<slug>/ using the named URL 'song-detail'.
        """
        if not getattr(obj, "slug", None):
            return "—"
        url = reverse("song-detail", kwargs={"slug": obj.slug})
        return format_html('<a href="{}" target="_blank">View</a>', url)

    def save_related(self, request, form, formsets, change):
        """
        After saving sections, auto-create arrangement items (only if none exist).
        This solves the "can't add arrangement items until save" admin workflow.
        """
        super().save_related(request, form, formsets, change)

        song = form.instance

        if not song.arrangement_items.exists():
            sections = song.sections.all().order_by("id")
            bulk = []
            order = 1
            for s in sections:
                bulk.append(
                    ArrangementItem(song=song, section=s, order=order, repeat_count=1)
                )
                order += 5
            ArrangementItem.objects.bulk_create(bulk)

    def response_add(self, request, obj, post_url_continue=None):
        """
        After adding a new song, redirect to the change page automatically so the
        newly auto-created arrangement items show up immediately.
        """
        change_url = reverse(
            "admin:%s_%s_change" % (obj._meta.app_label, obj._meta.model_name),
            args=[obj.pk],
        )
        return HttpResponseRedirect(change_url)
