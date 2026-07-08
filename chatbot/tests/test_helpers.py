"""
File: test_helpers.py
Description: Unit tests for chatbot helper functions: get_base_context,
get_response_from_ai, and get_conversation_title_from_first_message.
"""

import datetime

import pytest
from django.conf import settings
from django.test import override_settings
from django.utils import timezone

from chatbot.helpers.get_convo_title import get_conversation_title_from_first_message
from chatbot.helpers.get_prompt import EFFORT_CONTEXT_LIMITS, get_base_context, get_response_from_ai
from chatbot.models import AIModel, AIQuirk, Conversation, Message


@pytest.fixture
def ai_model(db):
    return AIModel.objects.create(name="Pirate", description="Talks like a pirate.")


@pytest.fixture
def conversation(user, ai_model):
    return Conversation.objects.create(user=user, model=ai_model, title="Test Convo")


def _add_messages(conversation, count, sender="user"):
    """Create messages with strictly increasing, deterministic timestamps.

    Message.timestamp uses auto_now_add, so rapid creation can produce ties;
    force distinct values so order_by("-timestamp") slicing is deterministic.
    """
    base = timezone.now() - datetime.timedelta(minutes=count + 1)
    messages = []
    for i in range(count):
        message = Message.objects.create(
            conversation=conversation, sender=sender, content=f"msg {i + 1}"
        )
        Message.objects.filter(pk=message.pk).update(
            timestamp=base + datetime.timedelta(seconds=i)
        )
        messages.append(message)
    return messages


class TestGetBaseContext:
    def test_none_conversation_returns_empty_string(self):
        assert get_base_context(None) == ""

    def test_conversation_without_model_returns_empty_string(self, user):
        conversation = Conversation.objects.create(user=user, model=None, title="No model")
        assert get_base_context(conversation) == ""

    def test_includes_model_description_when_set(self, conversation):
        context = get_base_context(conversation)
        assert "Model description:" in context
        assert "Talks like a pirate." in context

    def test_quirk_descriptions_rendered_as_bullet_lines(self, conversation, ai_model):
        quirk_a = AIQuirk.objects.create(name="Funny", description="Adds humor.")
        quirk_b = AIQuirk.objects.create(name="Brief", description="Keeps it short.")
        ai_model.quirk.add(quirk_a, quirk_b)

        context = get_base_context(conversation)
        assert "- Adds humor." in context
        assert "- Keeps it short." in context

    def test_blank_and_whitespace_quirk_descriptions_skipped(self, conversation, ai_model):
        blank = AIQuirk.objects.create(name="Blank", description="")
        whitespace = AIQuirk.objects.create(name="Whitespace", description="   \n  ")
        real = AIQuirk.objects.create(name="Real", description="Actually here.")
        ai_model.quirk.add(blank, whitespace, real)

        context = get_base_context(conversation)
        assert "- Actually here." in context
        # Only the real quirk produces a bullet line; blank ones are skipped.
        bullet_lines = [line for line in context.splitlines() if line.startswith("- ")]
        assert bullet_lines == ["- Actually here."]


class TestGetResponseFromAI:
    def test_blank_message_returns_empty_without_calling_api(self, conversation, mock_openai):
        assert get_response_from_ai(conversation, "   \t\n ") == ""
        mock_openai.responses.create.assert_not_called()

    def test_no_client_returns_unavailable_message(self, conversation, no_openai):
        _add_messages(conversation, 1)
        result = get_response_from_ai(conversation, "Hello")
        assert result == "I cannot reach the AI service right now."

    def test_calls_api_with_chat_model_and_instructions(self, conversation, mock_openai):
        _add_messages(conversation, 1)
        result = get_response_from_ai(conversation, "Hello")

        assert result == "AI response"
        mock_openai.responses.create.assert_called_once()
        kwargs = mock_openai.responses.create.call_args.kwargs
        assert kwargs["model"] == settings.OPENAI_CHAT_MODEL
        assert "Talks like a pirate." in kwargs["instructions"]

    def test_very_low_effort_limits_to_two_most_recent_in_order(self, conversation, mock_openai):
        assert EFFORT_CONTEXT_LIMITS["very_low"] == 2
        _add_messages(conversation, 5)
        conversation.effort = "very_low"

        get_response_from_ai(conversation, "next")

        input_items = mock_openai.responses.create.call_args.kwargs["input"]
        assert len(input_items) == 2
        assert [item["content"] for item in input_items] == ["msg 4", "msg 5"]

    def test_unknown_effort_falls_back_to_twelve(self, conversation, mock_openai):
        _add_messages(conversation, 15)
        conversation.effort = "warp_speed"  # not in EFFORT_CONTEXT_LIMITS

        get_response_from_ai(conversation, "next")

        input_items = mock_openai.responses.create.call_args.kwargs["input"]
        assert len(input_items) == 12
        assert [item["content"] for item in input_items] == [f"msg {i}" for i in range(4, 16)]

    def test_sender_maps_to_role(self, conversation, mock_openai):
        base = timezone.now() - datetime.timedelta(minutes=5)
        first = Message.objects.create(conversation=conversation, sender="user", content="question")
        second = Message.objects.create(conversation=conversation, sender="ai", content="answer")
        Message.objects.filter(pk=first.pk).update(timestamp=base)
        Message.objects.filter(pk=second.pk).update(timestamp=base + datetime.timedelta(seconds=1))

        get_response_from_ai(conversation, "next")

        input_items = mock_openai.responses.create.call_args.kwargs["input"]
        assert [(item["role"], item["content"]) for item in input_items] == [
            ("user", "question"),
            ("assistant", "answer"),
        ]

    @override_settings(DEBUG=False)
    def test_api_error_returns_generic_message_when_debug_off(self, conversation, mock_openai):
        _add_messages(conversation, 1)
        mock_openai.responses.create.side_effect = RuntimeError("boom")

        result = get_response_from_ai(conversation, "Hello")
        assert result == "I ran into a temporary issue while generating a response."

    @override_settings(DEBUG=True)
    def test_api_error_includes_exception_class_when_debug_on(self, conversation, mock_openai):
        _add_messages(conversation, 1)
        mock_openai.responses.create.side_effect = RuntimeError("boom")

        result = get_response_from_ai(conversation, "Hello")
        assert "RuntimeError" in result


class TestGetConversationTitleFromFirstMessage:
    def test_fallback_collapses_whitespace(self, no_openai):
        title = get_conversation_title_from_first_message("  Plan   my week  ")
        assert title == "Chat: Plan my week"
        assert len(title) <= 40

    def test_fallback_snips_long_input_and_strips_trailing_punctuation(self, no_openai):
        # Collapsed text is "x" * 32 + ", more stuff here"; [:34] ends in ", "
        # which is stripped by rstrip(" ,.;:-").
        title = get_conversation_title_from_first_message("x" * 32 + ", more stuff here")
        assert title == "Chat: " + "x" * 32
        assert len(title) <= 40

    def test_fallback_empty_input_returns_new_chat(self, no_openai):
        assert get_conversation_title_from_first_message("") == "New Chat"
        assert get_conversation_title_from_first_message("   \n\t ") == "New Chat"

    def test_ai_title_whitespace_collapsed_and_capped(self, mock_openai):
        mock_openai.responses.create.return_value.output_text = (
            "  A   very " + "long " * 20 + " title  "
        )
        title = get_conversation_title_from_first_message("Hello")

        collapsed = " ".join(("  A   very " + "long " * 20 + " title  ").strip().split())
        assert title == collapsed[:40]
        assert len(title) == 40
        assert "  " not in title

    def test_ai_title_whitespace_collapsed_short(self, mock_openai):
        mock_openai.responses.create.return_value.output_text = "  My   Neat\nTitle "
        assert get_conversation_title_from_first_message("Hello") == "My Neat Title"

    def test_empty_ai_output_falls_back(self, mock_openai):
        mock_openai.responses.create.return_value.output_text = ""
        assert get_conversation_title_from_first_message("Plan my week") == "Chat: Plan my week"

    def test_api_error_falls_back(self, mock_openai):
        mock_openai.responses.create.side_effect = RuntimeError("boom")
        assert get_conversation_title_from_first_message("Plan my week") == "Chat: Plan my week"
