"""
File: test_chatbot.py
Description: Chatbot playground: auth gating, HTMX send flow (OpenAI is faked
by the autouse `fake_openai` fixture), model locking after the first message,
conversation deletion, and GPT creator console gating.
"""

from playwright.sync_api import Page, expect

CHATBOT_URL = "/development-portfolio/chatbot/"
CREATOR_URL = "/development-portfolio/chatbot/gpt-creator/"
USER_MSG = '[data-testid="chat-message-user"]'
AI_MSG = '[data-testid="chat-message-ai"]'
SIDEBAR_ROW = '[data-testid="sidebar-conversation"]'
EMPTY_STATE = "Start a conversation by sending your first message."


def _send(page: Page, text: str):
    page.fill('textarea[name="content"]', text)
    page.locator("[data-send-btn]").click()


def test_anonymous_user_redirected_to_login(page: Page, live_server, db):
    page.goto(live_server.url + CHATBOT_URL)

    assert "/account/login/" in page.url
    expect(page.get_by_role("button", name="Log In")).to_be_visible()


def test_send_message_gets_fake_ai_reply_and_titles_conversation(
    page: Page, live_server, login, user, ai_model
):
    login(user)
    page.goto(live_server.url + CHATBOT_URL)

    expect(page.locator("body")).to_contain_text(EMPTY_STATE)
    expect(page.locator('select[name="model_id"]')).to_have_value(str(ai_model.id))

    _send(page, "Hello there")

    expect(page.locator(USER_MSG)).to_contain_text("Hello there")
    expect(page.locator(AI_MSG)).to_contain_text("FAKE-AI reply to: Hello there")
    expect(page.locator(SIDEBAR_ROW)).to_have_count(1)
    expect(page.locator(SIDEBAR_ROW)).to_contain_text("Test Chat Title")


def test_second_message_uses_locked_model(page: Page, live_server, login, user, ai_model):
    login(user)
    page.goto(live_server.url + CHATBOT_URL)

    _send(page, "First message")
    expect(page.locator(AI_MSG)).to_have_count(1)

    # After the first exchange the model can no longer be changed.
    expect(page.locator("#chat-main")).to_contain_text("Test Model (locked)")
    expect(page.locator('select[name="model_id"]')).to_have_count(0)

    _send(page, "Second message")

    expect(page.locator(USER_MSG)).to_have_count(2)
    expect(page.locator(USER_MSG).nth(0)).to_contain_text("First message")
    expect(page.locator(USER_MSG).nth(1)).to_contain_text("Second message")
    expect(page.locator(AI_MSG).nth(1)).to_contain_text("FAKE-AI reply to: Second message")
    expect(page.locator("#chat-main")).to_contain_text("(locked)")


def test_delete_conversation_resets_to_empty_state(page: Page, live_server, login, user, ai_model):
    login(user)
    page.goto(live_server.url + CHATBOT_URL)

    _send(page, "Delete me please")
    expect(page.locator(SIDEBAR_ROW)).to_have_count(1)

    page.locator('[data-testid="sidebar-conversation-delete"]').click()

    expect(page.locator("body")).to_contain_text(EMPTY_STATE)
    expect(page.locator(SIDEBAR_ROW)).to_have_count(0)


def test_creator_console_redirects_non_creators(page: Page, live_server, login, user):
    login(user)
    page.goto(live_server.url + CREATOR_URL)

    # Non-creators bounce back to the chat home page.
    expect(page).to_have_url(live_server.url + CHATBOT_URL)
    expect(page.get_by_role("heading", name="GPT Creator Console")).to_have_count(0)


def test_creator_console_renders_for_gpt_creator(page: Page, live_server, login, gpt_creator_user):
    login(gpt_creator_user)
    page.goto(live_server.url + CREATOR_URL)

    expect(page.get_by_role("heading", name="GPT Creator Console")).to_be_visible()
    expect(page.get_by_role("heading", name="Create AI Model")).to_be_visible()
    expect(page.get_by_role("heading", name="Create AI Quirk")).to_be_visible()
    expect(page.get_by_role("button", name="Create Model")).to_be_visible()
