from django.urls import path

from . import views

urlpatterns = [
    path("", views.chat_home, name="chatbot-home"),
    path("sidebar/", views.chat_sidebar, name="chatbot-sidebar"),
    path("new/", views.chat_new, name="chatbot-new"),
    path("conversation/<int:conversation_id>/", views.chat_conversation, name="chatbot-conversation"),
    path("send/", views.chat_send_message, name="chatbot-send"),
]
