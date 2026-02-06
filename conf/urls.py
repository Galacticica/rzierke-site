"""
File: urls.py
Author: Reagan Zierke <reaganzierke@gmail.com>
Date: 2026-02-05
Description: The main URL configurations for the project.
"""


from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('account/', include('accounts.urls')),
    path('__reload__/', include('django_browser_reload.urls')),
    path('admin/', admin.site.urls),
    path('', include('home.urls')),
    path('ministry/', include('ministry.urls')),
]
