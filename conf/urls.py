"""
File: urls.py
Author: Reagan Zierke <reaganzierke@gmail.com>
Date: 2026-02-05
Description: The main URL configurations for the project.
"""


from django.conf import settings
from django.contrib import admin
from django.urls import path, include

handler404 = "conf.views.custom_page_not_found"
handler500 = "conf.views.custom_server_error"

urlpatterns = [
    path('account/', include('accounts.urls')),
    path('admin/', admin.site.urls),
    path('', include('home.urls')),
    path('ministry/', include('ministry.urls')),
    path('rzpercussion/', include('rzpercussion.urls')),
    path('development-portfolio/', include('development_portfolio.urls')),
    path('development-portfolio/chatbot/', include('chatbot.urls')),
]

if settings.DEBUG:
    urlpatterns.insert(1, path('__reload__/', include('django_browser_reload.urls')))
