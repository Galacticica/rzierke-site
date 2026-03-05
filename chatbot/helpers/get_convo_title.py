"""Conversation title helpers."""

from __future__ import annotations

from openai import OpenAI
from django.conf import settings


client = OpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None


def _fallback_title(user_message: str) -> str:
    text = " ".join((user_message or "").strip().split())
    if not text:
        return "New Chat"
    snippet = text[:34].rstrip(" ,.;:-")
    return f"Chat: {snippet}"[:40]


def get_conversation_title_from_first_message(user_message: str) -> str:
    """Generate a concise chat title (max 40 chars) summarizing the first user message."""
    fallback = _fallback_title(user_message)
    if not client:
        return fallback

    try:
        resp = client.responses.create(
            model="gpt-5.2-mini",
            input=(
                "Create a short chat title based on the topic of this first user message. "
                "Do not repeat the message verbatim. Max 40 characters. "
                "Output only the title.\n\n"
                f"Message: {user_message}"
            ),
        )
        title = " ".join((resp.output_text or "").strip().split())
        if not title:
            return fallback
        return title[:40]
    except Exception:
        return fallback
