"""
File: views.py
Author: Reagan Zierke <reaganzierke@gmail.com>
Date: 2026-03-05
Description: Creates views for chatbot interactions, including listing conversations, viewing a conversation, and sending messages. Uses HTMX for dynamic updates.
"""


from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

from .helpers.get_convo_title import get_conversation_title_from_first_message
from .helpers.get_prompt import get_response_from_ai
from .models import AIModel, Conversation, Message


def _conversation_list_for_user(request: HttpRequest):
	return (
		Conversation.objects.filter(user=request.user)
		.select_related("model")
		.order_by("-created_at")
	)


@login_required
@require_GET
def chat_home(request: HttpRequest) -> HttpResponse:
	'''The main chat page showing the sidebar and the most recent conversation.'''
	conversations = _conversation_list_for_user(request)
	selected = conversations.first()
	selected_messages = selected.messages.order_by("timestamp") if selected else []
	models = AIModel.objects.order_by("name")
	return render(
		request,
		"chatbot/chatbot_page.html",
		{
			"conversations": conversations,
			"selected_conversation": selected,
			"selected_messages": selected_messages,
			"models": models,
		},
	)


@login_required
@require_GET
def chat_sidebar(request: HttpRequest) -> HttpResponse:
	'''The sidebar showing the list of conversations. This is loaded separately for HTMX updates.'''
	conversations = _conversation_list_for_user(request)
	selected_id = request.GET.get("selected")
	return render(
		request,
		"chatbot/partials/sidebar.html",
		{
			"conversations": conversations,
			"selected_conversation_id": int(selected_id) if selected_id and selected_id.isdigit() else None,
		},
	)


@login_required
@require_GET
def chat_new(request: HttpRequest) -> HttpResponse:
	'''Create a new conversation.'''
	models = AIModel.objects.order_by("name")
	conversations = _conversation_list_for_user(request)
	return render(
		request,
		"chatbot/partials/chat_panel_with_sidebar_oob.html",
		{
			"conversation": None,
			"messages": [],
			"models": models,
			"selected_model": models.first(),
			"conversations": conversations,
			"selected_conversation_id": None,
		},
	)


@login_required
@require_GET
def chat_conversation(request: HttpRequest, conversation_id: int) -> HttpResponse:
	'''View an existing conversation.'''
	conversation = get_object_or_404(
		Conversation.objects.select_related("model"),
		pk=conversation_id,
		user=request.user,
	)
	models = AIModel.objects.order_by("name")
	messages = conversation.messages.order_by("timestamp")
	conversations = _conversation_list_for_user(request)
	return render(
		request,
		"chatbot/partials/chat_panel_with_sidebar_oob.html",
		{
			"conversation": conversation,
			"messages": messages,
			"models": models,
			"selected_model": conversation.model,
			"conversations": conversations,
			"selected_conversation_id": conversation.id,
		},
	)


@login_required
@require_POST
def chat_send_message(request: HttpRequest) -> HttpResponse:
	'''Handle sending a message from the user, getting a response from the AI, and returning the updated conversation.'''
	user_content = (request.POST.get("content") or "").strip()
	if not user_content:
		return HttpResponseBadRequest("Message cannot be empty.")

	conversation_id = request.POST.get("conversation_id")
	selected_model_id = request.POST.get("model_id")

	if conversation_id:
		conversation = get_object_or_404(
			Conversation.objects.select_related("model"),
			pk=conversation_id,
			user=request.user,
		)
	else:
		model = None
		if selected_model_id and selected_model_id.isdigit():
			model = AIModel.objects.filter(pk=selected_model_id).first()
		conversation = Conversation.objects.create(user=request.user, model=model)

	if not conversation.model and selected_model_id and selected_model_id.isdigit():
		chosen_model = AIModel.objects.filter(pk=selected_model_id).first()
		if chosen_model:
			conversation.model = chosen_model
			conversation.save(update_fields=["model"])

	Message.objects.create(conversation=conversation, sender="user", content=user_content)

	if conversation.messages.count() == 1:
		conversation.title = get_conversation_title_from_first_message(user_content)
		conversation.save(update_fields=["title"])

	ai_content = get_response_from_ai(conversation, user_content)
	if ai_content:
		Message.objects.create(conversation=conversation, sender="ai", content=ai_content)

	models = AIModel.objects.order_by("name")
	messages = conversation.messages.order_by("timestamp")
	response = render(
		request,
		"chatbot/partials/chat_panel_with_sidebar_oob.html",
		{
			"conversation": conversation,
			"messages": messages,
			"models": models,
			"selected_model": conversation.model,
			"conversations": _conversation_list_for_user(request),
			"selected_conversation_id": conversation.id,
		},
	)
	response["HX-Trigger"] = "conversations-changed"
	return response
