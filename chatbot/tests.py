"""
File: tests.py
Author: Reagan Zierke <reaganzierke@gmail.com>
Date: 2026-03-11
Description: Tests created by copilot for chatbot app, focusing on the message sending functionality and ensuring that the AI model is locked after the first message. Uses unittest.mock to patch AI response generation and title extraction for consistent testing.
"""


from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from chatbot.models import AIModel, AIQuirk, Conversation


class ChatbotSendMessageTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(email="tester@example.com", password="password123")
		self.client.force_login(self.user)
		self.model_a = AIModel.objects.create(name="Model A", description="First model")
		self.model_b = AIModel.objects.create(name="Model B", description="Second model")

	@patch("chatbot.views.get_conversation_title_from_first_message", return_value="Helpful Plan")
	@patch("chatbot.views.get_response_from_ai", return_value="AI response")
	def test_first_send_creates_conversation_and_locks_model(self, mocked_ai, mocked_title):
		response = self.client.post(
			reverse("chatbot-send"),
			{
				"content": "Plan my week",
				"model_id": str(self.model_a.id),
			},
		)

		self.assertEqual(response.status_code, 200)
		conversation = Conversation.objects.get(user=self.user)
		self.assertEqual(conversation.title, "Helpful Plan")
		self.assertEqual(conversation.model, self.model_a)

		messages = list(conversation.messages.order_by("timestamp").values_list("sender", "content"))
		self.assertEqual(messages, [("user", "Plan my week"), ("ai", "AI response")])

		mocked_title.assert_called_once_with("Plan my week")
		mocked_ai.assert_called_once()

	@patch("chatbot.views.get_response_from_ai", return_value="next")
	def test_model_does_not_change_after_first_message(self, _mocked_ai):
		conversation = Conversation.objects.create(user=self.user, model=self.model_a, title="Existing")
		conversation.messages.create(sender="user", content="First")
		conversation.messages.create(sender="ai", content="Reply")

		response = self.client.post(
			reverse("chatbot-send"),
			{
				"conversation_id": str(conversation.id),
				"model_id": str(self.model_b.id),
				"content": "Try to switch model",
			},
		)

		self.assertEqual(response.status_code, 200)
		conversation.refresh_from_db()
		self.assertEqual(conversation.model, self.model_a)


class GPTCreatorConsoleTests(TestCase):
	def setUp(self):
		self.creator = User.objects.create_user(
			email="creator@example.com",
			password="password123",
			gpt_creator=True,
		)
		self.non_creator = User.objects.create_user(
			email="viewer@example.com",
			password="password123",
		)

	def test_console_requires_gpt_creator_flag(self):
		self.client.force_login(self.non_creator)
		response = self.client.get(reverse("chatbot-gpt-creator"))
		self.assertRedirects(response, reverse("chatbot-home"))

	def test_action_requires_gpt_creator_flag(self):
		self.client.force_login(self.non_creator)
		response = self.client.post(
			reverse("chatbot-gpt-creator-action"),
			{
				"entity": "quirk",
				"action": "create",
				"name": "No Access",
				"description": "Should not be created",
			},
		)
		self.assertRedirects(response, reverse("chatbot-home"))
		self.assertFalse(AIQuirk.objects.filter(name="No Access").exists())

	def test_console_allows_creator(self):
		self.client.force_login(self.creator)
		response = self.client.get(reverse("chatbot-gpt-creator"))
		self.assertEqual(response.status_code, 200)

	def test_creator_can_create_model_and_quirk(self):
		self.client.force_login(self.creator)

		quirk_response = self.client.post(
			reverse("chatbot-gpt-creator-action"),
			{
				"entity": "quirk",
				"action": "create",
				"name": "Friendly",
				"description": "Keeps a warm tone.",
			},
		)
		self.assertEqual(quirk_response.status_code, 302)
		quirk = AIQuirk.objects.get(name="Friendly")

		model_response = self.client.post(
			reverse("chatbot-gpt-creator-action"),
			{
				"entity": "model",
				"action": "create",
				"name": "Composer",
				"description": "Creates lyric ideas.",
				"quirk": [str(quirk.id)],
			},
		)
		self.assertEqual(model_response.status_code, 302)

		model = AIModel.objects.get(name="Composer")
		self.assertEqual(model.description, "Creates lyric ideas.")
		self.assertEqual(list(model.quirk.values_list("id", flat=True)), [quirk.id])
		self.assertEqual(model.created_by, self.creator)
		self.assertEqual(quirk.created_by, self.creator)

	def test_creator_can_update_existing_model(self):
		self.client.force_login(self.creator)
		quirk_a = AIQuirk.objects.create(name="Funny", description="Adds humor.", created_by=self.creator)
		quirk_b = AIQuirk.objects.create(name="Direct", description="Avoids extra fluff.", created_by=self.creator)
		model = AIModel.objects.create(name="Model 1", description="First", created_by=self.creator)
		model.quirk.add(quirk_a)

		response = self.client.post(
			reverse("chatbot-gpt-creator-action"),
			{
				"entity": "model",
				"action": "update",
				"id": str(model.id),
				"name": "Model One",
				"description": "Updated.",
				"quirk": [str(quirk_b.id)],
			},
		)

		self.assertEqual(response.status_code, 302)
		model.refresh_from_db()
		self.assertEqual(model.name, "Model One")
		self.assertEqual(model.description, "Updated.")
		self.assertEqual(list(model.quirk.values_list("id", flat=True)), [quirk_b.id])

	def test_creator_cannot_update_another_users_model(self):
		other_creator = User.objects.create_user(
			email="other.creator@example.com",
			password="password123",
			gpt_creator=True,
		)
		other_quirk = AIQuirk.objects.create(name="Other Quirk", description="Owned by other", created_by=other_creator)
		model = AIModel.objects.create(name="Locked Model", description="Do not edit", created_by=other_creator)
		model.quirk.add(other_quirk)

		self.client.force_login(self.creator)
		response = self.client.post(
			reverse("chatbot-gpt-creator-action"),
			{
				"entity": "model",
				"action": "update",
				"id": str(model.id),
				"name": "Hacked Name",
				"description": "Hacked Desc",
				"quirk": [],
			},
		)

		self.assertEqual(response.status_code, 302)
		model.refresh_from_db()
		self.assertEqual(model.name, "Locked Model")
		self.assertEqual(model.description, "Do not edit")

	def test_creator_cannot_delete_another_users_quirk(self):
		other_creator = User.objects.create_user(
			email="other.creator2@example.com",
			password="password123",
			gpt_creator=True,
		)
		quirk = AIQuirk.objects.create(name="Private Quirk", description="Keep", created_by=other_creator)

		self.client.force_login(self.creator)
		response = self.client.post(
			reverse("chatbot-gpt-creator-action"),
			{
				"entity": "quirk",
				"action": "delete",
				"id": str(quirk.id),
			},
		)

		self.assertEqual(response.status_code, 302)
		self.assertTrue(AIQuirk.objects.filter(pk=quirk.id).exists())
