"""
File: urls.py
Author: Reagan Zierke <reaganzierke@gmail.com>
Date: 2026-03-05
Description: Route URLs for chatbot app views.
"""


from django.urls import path

from . import views

urlpatterns = [
    path("", views.chat_home, name="chatbot-home"),
    path("gpt-creator/", views.gpt_creator_console, name="chatbot-gpt-creator"),
    path("gpt-creator/action/", views.gpt_creator_console_action, name="chatbot-gpt-creator-action"),
    path("sidebar/", views.chat_sidebar, name="chatbot-sidebar"),
    path("new/", views.chat_new, name="chatbot-new"),
    path("conversation/<int:conversation_id>/", views.chat_conversation, name="chatbot-conversation"),
    path("send/", views.chat_send_message, name="chatbot-send"),
]
