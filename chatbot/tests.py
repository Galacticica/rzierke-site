from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from chatbot.models import AIModel, Conversation


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
