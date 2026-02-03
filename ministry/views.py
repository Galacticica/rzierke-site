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
    
    