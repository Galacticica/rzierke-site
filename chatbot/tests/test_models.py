"""
File: test_models.py
Description: Model-level tests for the chatbot app: Conversation auto-title
behavior and __str__ implementations.
"""

import re

import pytest

from chatbot.models import AIModel, AIQuirk, Conversation, Message

pytestmark = pytest.mark.django_db


class TestConversationAutoTitle:
    def test_blank_title_gets_timestamp_title_on_create(self, user):
        conversation = Conversation.objects.create(user=user)
        # On first save created_at is not yet set (auto_now_add applies inside
        # super().save()), so the model falls back to timezone.now().
        assert re.fullmatch(
            r"Conversation \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", conversation.title
        )

    def test_explicit_title_is_preserved(self, user):
        conversation = Conversation.objects.create(user=user, title="My Chat")
        assert conversation.title == "My Chat"
        conversation.refresh_from_db()
        assert conversation.title == "My Chat"

    def test_title_cleared_on_existing_row_regenerates_from_created_at(self, user):
        conversation = Conversation.objects.create(user=user, title="My Chat")
        conversation.title = ""
        conversation.save()
        expected = f"Conversation {conversation.created_at.strftime('%Y-%m-%d %H:%M:%S')}"
        assert conversation.title == expected


class TestStrMethods:
    def test_conversation_str_returns_title(self, user):
        conversation = Conversation.objects.create(user=user, title="My Chat")
        assert str(conversation) == "My Chat"

    def test_message_str_contains_sender_timestamp_and_truncated_content(self, user):
        conversation = Conversation.objects.create(user=user, title="My Chat")
        long_content = "a" * 80
        message = Message.objects.create(
            conversation=conversation, sender="user", content=long_content
        )
        assert str(message) == f"user at {message.timestamp}: {'a' * 50}..."

    def test_ai_model_str_returns_name(self):
        model = AIModel.objects.create(name="Composer", description="Writes music.")
        assert str(model) == "Composer"

    def test_ai_quirk_str_returns_name(self):
        quirk = AIQuirk.objects.create(name="Funny", description="Adds humor.")
        assert str(quirk) == "Funny"
