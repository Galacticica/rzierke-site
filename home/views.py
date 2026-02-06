"""
File: views.py
Author: Reagan Zierke <reaganzierke@gmail.com>
Date: 2026-01-21
Description: Views for the home app.
"""


from django.shortcuts import redirect, render
from django.views import View

class HomeView(View):
    """The homepage view."""
    def get(self, request, *args, **kwargs):
        return render(request, 'home/homepage.html')
    
class AboutView(View):
    """The about page view."""
    def get(self, request, *args, **kwargs):
        return render(request, 'home/about.html')
    