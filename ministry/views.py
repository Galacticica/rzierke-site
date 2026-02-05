from django.shortcuts import render, get_object_or_404
from django.views import View
from django.views.generic import DetailView
from django.utils.text import slugify
from django.http import HttpResponse
from django.core.paginator import Paginator
from .utils.build_slides import build_song_pptx_bytes
from .utils.build_pdf import build_song_print_pdf_bytes
from .models import Devotion, Song
from .filters import SongFilter

class SongDetailView(DetailView):
    model = Song
    template_name = 'ministry/song_detail.html'
    context_object_name = 'song'

    def get_queryset(self):
        return Song.objects.with_display_related()
    

class SongListView(View):
    def get(self, request):
        base_qs = Song.objects.with_display_related().order_by("title")

        song_filter = SongFilter(request.GET, queryset=base_qs)
        songs = song_filter.qs

        # Pagination
        paginator = Paginator(songs, 25)  # 25 items per page
        page_number = request.GET.get("page", 1)
        page_obj = paginator.get_page(page_number)

        context = {
            "songs": page_obj.object_list,
            "page_obj": page_obj,
            "paginator": paginator,
            "filter": song_filter,
            "q": request.GET.get("q", ""),
            "total_count": Song.objects.count(),
            "filtered_count": songs.count(),
        }

        if getattr(request, "htmx", False):
            target = request.headers.get("HX-Target", "")
            if target == "song-layout":
                return render(request, "ministry/partials/song_layout.html", context)
            return render(request, "ministry/partials/song_results.html", context)

        return render(
            request,
            "ministry/song_list.html",
            context,
        )
    

class SongPPTXExportView(View):
    """
    GET /ministry/songs/<slug>/export/pptx/
    Returns a PPTX with:
      - Title slide (90pt, Yu Gothic UI Semilight, white on black)
      - Blank slide
      - Lyric slides (80pt, Yu Gothic UI Semilight, white on black)
    """
    def get(self, request, slug: str, *args, **kwargs):
        song = get_object_or_404(Song, slug=slug)

        pptx_bytes = build_song_pptx_bytes(song)

        filename = f"{slugify(song.title) or 'song'}.pptx"
        response = HttpResponse(
            pptx_bytes,
            content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class SongPrintPDFView(View):
    def get(self, request, slug: str, *args, **kwargs):
        song = get_object_or_404(Song, slug=slug)

        pdf_bytes = build_song_print_pdf_bytes(song)

        filename = f"{slugify(song.title) or 'song'}-handout.pdf"
        resp = HttpResponse(pdf_bytes, content_type="application/pdf")
        resp["Content-Disposition"] = f'attachment; filename="{filename}"'
        return resp
    

class MinHomeView(View):
    def get(self, request):
        return render(request, "ministry/min_home.html")
    
class DevotionsView(View):
    def get(self, request):
        order = request.GET.get("order", "newest")
        if order not in {"newest", "oldest"}:
            order = "newest"

        devotions = Devotion.objects.order_by_date(newest_first=(order == "newest"))
        context = {"devotions": devotions, "order": order}

        if getattr(request, "htmx", False):
            return render(request, "ministry/partials/devos_section.html", context)

        return render(request, "ministry/devos.html", context)