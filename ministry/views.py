from django.shortcuts import render, get_object_or_404
from django.views import View
from django.views.generic import DetailView
from .models import Song

class SongDetailView(DetailView):
    model = Song
    template_name = 'ministry/song_detail.html'
    context_object_name = 'song'

    def get_queryset(self):
        return Song.objects.with_display_related()
    

class SongListView(View):
    def get(self, request):
        q = request.GET.get("q", "")
        songs = Song.objects.with_display_related().search(q).order_by("title")

        return render(
            request,
            "ministry/song_list.html",
            {
                "songs": songs,
                "q": q,
                "total_count": Song.objects.count(),
            },
        )