"""
File: views.py
Author: Reagan Zierke <reaganzierke@gmail.com>
Date: 2026-01-21
Description: Views for the home app.
"""


from django.shortcuts import redirect, render
from django.views import View

class HomeView(View):
    def get(self, request, *args, **kwargs):
        return render(request, 'home/homepage.html')
    
class AboutView(View):
    def get(self, request, *args, **kwargs):
        return render(request, 'home/about.html')
    
class BlogView(View):
    def get(self, request, *args, **kwargs):
        return render(request, 'home/blog.html')
    
class ResourcesView(View):
    def get(self, request, *args, **kwargs):
        return render(request, 'home/resources.html')