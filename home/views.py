from django.shortcuts import redirect, render
from django.views import View

class HomeView(View):
    def get(self, request, *args, **kwargs):
        return render(request, 'home/homepage.html')