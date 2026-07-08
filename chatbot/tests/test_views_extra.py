"""
File: test_views_extra.py
Description: Additional view tests for the chatbot app: auth requirements,
cross-user access, send-message edge cases, deletion behavior, and the
GPT creator console superuser bypass.
"""

from unittest.mock import patch

import pytest
from django.conf import settings
from django.urls import reverse

from accounts.models import User
from chatbot.models import AIModel, Conversation, Message

pytestmark = pytest.mark.django_db


@pytest.fixture
def other_user(db):
    return User.objects.create_user(email="other@example.com", password="password123")


@pytest.fixture
def ai_model(db):
    return AIModel.objects.create(name="Helper", description="Helps with things.")


class TestChatHomeAuth:
    def test_chat_home_requires_login(self, client):
        response = client.get(reverse("chatbot-home"))
        assert response.status_code == 302
        assert response.url.startswith(settings.LOGIN_URL)


class TestConversationAccess:
    def test_other_users_conversation_returns_404(self, auth_client, other_user):
        conversation = Conversation.objects.create(user=other_user, title="Private")
        response = auth_client.get(
            reverse("chatbot-conversation", args=[conversation.id])
        )
        assert response.status_code == 404


class TestChatSendMessage:
    def test_empty_content_returns_400(self, auth_client):
        response = auth_client.post(reverse("chatbot-send"), {"content": "   "})
        assert response.status_code == 400
        assert Conversation.objects.count() == 0

    @patch("chatbot.views.get_conversation_title_from_first_message", return_value="Title")
    @patch("chatbot.views.get_response_from_ai", return_value="AI response")
    def test_valid_effort_persists_on_conversation(self, _ai, _title, auth_client, user):
        response = auth_client.post(
            reverse("chatbot-send"),
            {"content": "Hello", "effort": "very_high"},
        )
        assert response.status_code == 200
        conversation = Conversation.objects.get(user=user)
        assert conversation.effort == "very_high"

    @patch("chatbot.views.get_conversation_title_from_first_message", return_value="Title")
    @patch("chatbot.views.get_response_from_ai", return_value="AI response")
    def test_invalid_effort_leaves_default(self, _ai, _title, auth_client, user):
        response = auth_client.post(
            reverse("chatbot-send"),
            {"content": "Hello", "effort": "turbo"},
        )
        assert response.status_code == 200
        conversation = Conversation.objects.get(user=user)
        assert conversation.effort == "medium"

    @patch("chatbot.views.get_conversation_title_from_first_message", return_value="Title")
    @patch("chatbot.views.get_response_from_ai", return_value="AI response")
    def test_send_response_carries_hx_trigger_header(self, _ai, _title, auth_client):
        response = auth_client.post(reverse("chatbot-send"), {"content": "Hello"})
        assert response.status_code == 200
        assert response["HX-Trigger"] == "conversations-changed"

    @patch("chatbot.views.get_conversation_title_from_first_message", return_value="Title")
    @patch("chatbot.views.get_response_from_ai", return_value="")
    def test_empty_ai_response_creates_no_ai_message(self, _ai, _title, auth_client, user):
        response = auth_client.post(reverse("chatbot-send"), {"content": "Hello"})
        assert response.status_code == 200
        conversation = Conversation.objects.get(user=user)
        senders = list(
            conversation.messages.order_by("timestamp").values_list("sender", flat=True)
        )
        assert senders == ["user"]


class TestChatDelete:
    def test_deleting_open_conversation_returns_chat_panel(self, auth_client, user, ai_model):
        conversation = Conversation.objects.create(user=user, model=ai_model, title="Open chat")
        Message.objects.create(conversation=conversation, sender="user", content="hi")

        response = auth_client.post(
            reverse("chatbot-delete", args=[conversation.id]),
            {"current_id": str(conversation.id)},
        )

        assert response.status_code == 200
        assert not Conversation.objects.filter(pk=conversation.id).exists()
        # The open conversation was deleted, so the full chat panel is
        # re-rendered (no HX-Reswap suppression header).
        assert "HX-Reswap" not in response
        assert response.content  # panel HTML is returned

    def test_deleting_background_conversation_sets_hx_reswap_none(self, auth_client, user):
        open_conversation = Conversation.objects.create(user=user, title="Still open")
        background = Conversation.objects.create(user=user, title="Background")

        response = auth_client.post(
            reverse("chatbot-delete", args=[background.id]),
            {"current_id": str(open_conversation.id)},
        )

        assert response.status_code == 200
        assert response["HX-Reswap"] == "none"
        assert not Conversation.objects.filter(pk=background.id).exists()
        assert Conversation.objects.filter(pk=open_conversation.id).exists()

    def test_deleting_other_users_conversation_returns_404(self, auth_client, other_user):
        conversation = Conversation.objects.create(user=other_user, title="Not yours")
        response = auth_client.post(
            reverse("chatbot-delete", args=[conversation.id]),
            {"current_id": str(conversation.id)},
        )
        assert response.status_code == 404
        assert Conversation.objects.filter(pk=conversation.id).exists()


class TestChatSidebar:
    def test_non_numeric_selected_param_does_not_crash(self, auth_client, user):
        Conversation.objects.create(user=user, title="A chat")
        response = auth_client.get(reverse("chatbot-sidebar"), {"selected": "notanumber"})
        assert response.status_code == 200


class TestGPTCreatorAccess:
    def test_superuser_without_flag_can_access_console(self, client, superuser):
        assert not getattr(superuser, "gpt_creator", False)
        client.force_login(superuser)
        response = client.get(reverse("chatbot-gpt-creator"))
        assert response.status_code == 200
