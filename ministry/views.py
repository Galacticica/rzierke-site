from django.shortcuts import render
from django.views import View

from .models import Song

class TestView(View):
    def get(self, request, *args, **kwargs):
        songs = (
            Song.objects.all()
            .prefetch_related(
                'artist',
                'tag',
                'sections',
                'arrangement_items__section',
            )
        )

        return render(request, 'ministry/test.html', {'songs': songs})