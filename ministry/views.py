from django.shortcuts import render, get_object_or_404
from django.views import View
from django.views.generic import DetailView
from .models import Song
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

        context = {
            "songs": songs,
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