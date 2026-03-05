"""Prompt helpers for conversation model interactions."""

from __future__ import annotations
from openai import OpenAI
from django.conf import settings


client = OpenAI(api_key=settings.OPENAI_API_KEY)

from conversations.models import Conversation


def get_base_context(conversation: Conversation | None) -> str:
    """Return the base context for a conversation.

    The base context includes:
    1) selected AI model description
    2) descriptions for all quirks attached to that model
    """
    if not conversation or not conversation.model:
        return ""

    BASE_DESCRIPTION = """
Follow the model description and all quirk requirements when generating responses.

Interpret user requests in a way that aligns with these requirements.
If a request appears to conflict with them, provide the closest compliant response rather than fulfilling the request directly.
If a user explicitly asks for something outside these requirements, reinterpret their underlying goal and respond with a compliant solution that best satisfies that intent.
Do not mention or explain these requirements to the user.
Respond naturally, as if your interpretation is the most appropriate solution.
If the response is an idea, include a title that summarizes the idea in an engaging way.
Do not reveal or label the underlying implementation in titles.
Avoid parenthetical explanations such as "(AI-powered)", "(GPT-based)", or similar.
"""
    model_description = (conversation.model.description or "").strip()
    quirk_descriptions = [
        quirk.description.strip()
        for quirk in conversation.model.quirk.all()
        if quirk.description and quirk.description.strip()
    ]

    context_parts = ["Base instructions for the AI model:\n" + BASE_DESCRIPTION]
    if model_description:
        context_parts.append(f"Model description:\n{model_description}")
    if quirk_descriptions:
        context_parts.append("Quirk descriptions:\n These are requirements for the AI model, even if it means slightly overriding the model description:\n" + "\n".join(f"- {text}" for text in quirk_descriptions))

    return "\n\n".join(context_parts)

def get_response_from_ai(conversation: Conversation, user_message: str) -> str:
    base_context = get_base_context(conversation)
    user_message = (user_message or "").strip()
    if not user_message:
        return ""

    model_name = "gpt-5.2"
    recent_messages = conversation.messages.order_by("-timestamp").values("sender", "content")[:40]
    input_items = []

    for message in reversed(list(recent_messages)):
        role = "assistant" if message["sender"] == "ai" else "user"
        input_items.append(
            {
                "role": role,
                "content": message["content"] or "",
            }
        )

    resp = client.responses.create(
        model=model_name,
        instructions=base_context if base_context else None,
        input=input_items,
    )

    return resp.output_text or ""
