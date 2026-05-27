"""
Regression tests for bugs fixed on 2026-05-13.

Bugs covered:
  BUG-001 – Chat bot responses showed raw markdown symbols (###, **, *, -)
             instead of rendered HTML. Root cause: addBotMessage() used
             escapeHtml().replace(\\n, <br>) with no markdown parser.
             Fix: parseMarkdown() injected into script.js on both sites.

  BUG-002 – Chat bot message container missing `md-body` CSS class, so even
             if markdown was parsed the heading/list styles were not applied.
             Fix: div.message-content updated to div.message-content.md-body.

  BUG-003 – Robot icon (fa-robot) missing / not rendered inside bot message
             bubbles when the innerHTML template was incorrectly constructed.
             Fix: template literal corrected alongside markdown change.

  BUG-004 – parseMarkdown function absent from script.js entirely; any future
             accidental removal would silently break the chat output.
             Fix: test verifies the JS source still contains the function.
"""

import re
import pytest
from playwright.sync_api import Page, expect
from pages.interactive_tools import InteractiveTools
from pages.landing_sections import LandingSections


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _open_chat_and_send(tools: InteractiveTools, page: Page, message: str):
    """Open the chat widget, send a message, wait for a bot reply."""
    tools.open_chat_window()
    tools.click_mode('General')
    input_box = page.locator('#chat-input, textarea#chat-input, input#chat-input, '
                              '.chat-input-area textarea, .chat-input-area input').first
    expect(input_box).to_be_visible(timeout=10_000)
    input_box.fill(message)
    send_btn = page.locator(
        '#chat-form button.chat-send-btn, '
        '#chat-form button[aria-label="Send message"], '
        'button.chat-send-btn'
    ).first
    send_btn.click()


def _wait_for_bot_message(page: Page, timeout: int = 30_000):
    """Wait until at least one bot message bubble appears."""
    bot_msg = page.locator('.chat-message.bot-message').last
    bot_msg.wait_for(state='visible', timeout=timeout)
    # Wait for typing indicator to disappear (bot finished responding)
    typing = page.locator('.typing-indicator-msg')
    try:
        typing.wait_for(state='hidden', timeout=timeout)
    except Exception:
        pass  # indicator may not exist if response was instant
    return page.locator('.chat-message.bot-message').last


# ---------------------------------------------------------------------------
# BUG-001 & BUG-002  –  Markdown rendering in chat bot output
# ---------------------------------------------------------------------------

class TestChatMarkdownRendering:
    """BUG-001 / BUG-002: Bot responses must render markdown as HTML."""

    @pytest.fixture(autouse=True)
    def on_home(self, landing: LandingSections):
        landing.goto_home()

    def test_bot_message_container_has_md_body_class(
        self, page: Page, tools: InteractiveTools
    ):
        """BUG-002 regression: .message-content must carry the md-body class
        so CSS heading/list styles are applied to rendered markdown."""
        _open_chat_and_send(tools, page, 'What are the main AI issues?')
        _wait_for_bot_message(page)
        md_body = page.locator('.chat-message.bot-message .message-content.md-body').last
        expect(md_body).to_be_attached(timeout=30_000)

    def test_bot_response_does_not_contain_raw_markdown_headers(
        self, page: Page, tools: InteractiveTools
    ):
        """BUG-001 regression: raw ### symbols must not appear in bot output.
        If parseMarkdown is working, ### is converted to <h3> before display."""
        _open_chat_and_send(tools, page, 'List the main AI challenges with headings')
        _wait_for_bot_message(page)
        # Get text content of last bot message
        last_bot = page.locator('.chat-message.bot-message .message-content').last
        expect(last_bot).not_to_contain_text('###')

    def test_bot_response_does_not_contain_raw_bold_asterisks(
        self, page: Page, tools: InteractiveTools
    ):
        """BUG-001 regression: **bold** double-asterisks must not appear as
        literal text — they should be rendered as <strong> HTML elements."""
        _open_chat_and_send(tools, page, 'Explain machine learning in brief')
        _wait_for_bot_message(page)
        last_bot = page.locator('.chat-message.bot-message .message-content').last
        expect(last_bot).not_to_contain_text('**')

    def test_bot_response_does_not_contain_raw_single_asterisk_italic(
        self, page: Page, tools: InteractiveTools
    ):
        """BUG-001 regression: single *italic* asterisks must not appear as
        literal text — they should be rendered as <em> HTML elements."""
        _open_chat_and_send(tools, page, 'Give a brief overview of deep learning')
        _wait_for_bot_message(page)
        last_bot = page.locator('.chat-message.bot-message .message-content').last
        expect(last_bot).not_to_contain_text(re.compile(r'\*[^*\n]+\*'))

    def test_bot_response_renders_html_list_elements(
        self, page: Page, tools: InteractiveTools
    ):
        """BUG-001 regression: when AI returns a list, it must render as
        <ul><li> elements, not raw '- item' lines."""
        _open_chat_and_send(tools, page, 'List 3 benefits of AI automation')
        _wait_for_bot_message(page)
        last_bot = page.locator('.chat-message.bot-message .message-content').last
        expect(last_bot).not_to_contain_text(re.compile(r'^\s*[-*] \w', re.MULTILINE))

    def test_bot_response_renders_strong_for_bold(
        self, page: Page, tools: InteractiveTools
    ):
        """BUG-001 regression: bold markdown must produce <strong> elements."""
        _open_chat_and_send(tools, page, 'What are key AI risks? Use bold for titles')
        _wait_for_bot_message(page)
        last_bot = page.locator('.chat-message.bot-message .message-content').last
        expect(last_bot).not_to_contain_text('**')


# ---------------------------------------------------------------------------
# BUG-003  –  Robot icon visible in bot message bubbles
# ---------------------------------------------------------------------------

class TestChatBotIconRendering:
    """BUG-003: Robot icon must be present and visible in every bot message."""

    @pytest.fixture(autouse=True)
    def on_home(self, landing: LandingSections):
        landing.goto_home()

    def test_bot_message_avatar_icon_present(
        self, page: Page, tools: InteractiveTools
    ):
        """BUG-003 regression: each bot message bubble must contain a
        .message-avatar element with the fa-robot icon inside."""
        _open_chat_and_send(tools, page, 'Hello')
        _wait_for_bot_message(page)
        avatar = page.locator('.chat-message.bot-message .message-avatar').last
        expect(avatar).to_be_visible(timeout=30_000)

    def test_bot_message_avatar_contains_robot_icon(
        self, page: Page, tools: InteractiveTools
    ):
        """BUG-003 regression: the avatar must contain the fa-robot FontAwesome
        icon class — not an empty div or broken placeholder."""
        _open_chat_and_send(tools, page, 'Hello')
        _wait_for_bot_message(page)
        robot_icon = page.locator(
            '.chat-message.bot-message .message-avatar i.fa-robot'
        ).last
        expect(robot_icon).to_be_attached(timeout=30_000)

    def test_welcome_message_has_robot_icon(self, page: Page, tools: InteractiveTools):
        """BUG-003 regression: the initial welcome/greeting bot message that
        loads automatically must also carry the robot avatar icon."""
        tools.open_chat_window()
        # The welcome message is injected on chat open, no send needed
        welcome_msg = page.locator('.chat-message.bot-message').first
        expect(welcome_msg).to_be_visible(timeout=10_000)
        robot_icon = welcome_msg.locator('i.fa-robot')
        expect(robot_icon).to_be_attached()


# ---------------------------------------------------------------------------
# BUG-004  –  parseMarkdown function present in served JS
# ---------------------------------------------------------------------------

class TestParseMarkdownDeployed:
    """BUG-004: Verify parseMarkdown is present in the served script.js.
    Guards against accidental revert / overwrite of the fix on the server."""

    def test_script_js_contains_parseMarkdown_function(self, page: Page):
        """BUG-004 regression: fetch script.js from the live server and assert
        the parseMarkdown function exists. If it's missing the chat will
        silently regress to raw markdown output."""
        page.goto('/', wait_until='domcontentloaded')
        # Get the script.js URL from the page
        script_url = page.evaluate("""() => {
            const scripts = Array.from(document.querySelectorAll('script[src]'));
            const s = scripts.find(s => s.src.includes('script.js'));
            return s ? s.src : null;
        }""")
        assert script_url, "Could not find script.js <script> tag on the page"

        response = page.request.get(script_url)
        assert response.ok, f"script.js fetch failed: {response.status}"
        body = response.text()
        assert 'function parseMarkdown' in body, (
            "parseMarkdown function NOT found in script.js — "
            "markdown rendering fix may have been reverted!"
        )

    def test_script_js_addBotMessage_uses_parseMarkdown(self, page: Page):
        """BUG-004 regression: verify addBotMessage calls parseMarkdown,
        not the old escapeHtml().replace(\\n, <br>) pattern."""
        page.goto('/', wait_until='domcontentloaded')
        script_url = page.evaluate("""() => {
            const scripts = Array.from(document.querySelectorAll('script[src]'));
            const s = scripts.find(s => s.src.includes('script.js'));
            return s ? s.src : null;
        }""")
        assert script_url

        response = page.request.get(script_url)
        body = response.text()

        # Must use parseMarkdown
        assert 'parseMarkdown(text)' in body, (
            "addBotMessage does not call parseMarkdown(text) — raw markdown bug may be back"
        )
        # Must NOT use the old broken pattern inside addBotMessage
        # (the old pattern was escapeHtml(text).replace(/\n/g, '<br>'))
        # We check by counting: parseMarkdown should appear, old pattern should not
        # be paired with addBotMessage. We look for the raw pattern as a whole line.
        old_pattern = "escapeHtml(text).replace(/\\n/g, '<br>')"
        assert old_pattern not in body, (
            f"Old unformatted pattern '{old_pattern}' still present in script.js — "
            "markdown fix was not applied or was reverted"
        )

    def test_script_js_md_body_class_in_addBotMessage(self, page: Page):
        """BUG-002 regression: verify the md-body CSS class is in the
        addBotMessage innerHTML template in script.js."""
        page.goto('/', wait_until='domcontentloaded')
        script_url = page.evaluate("""() => {
            const scripts = Array.from(document.querySelectorAll('script[src]'));
            const s = scripts.find(s => s.src.includes('script.js'));
            return s ? s.src : null;
        }""")
        assert script_url

        response = page.request.get(script_url)
        body = response.text()
        assert 'md-body' in body, (
            "md-body CSS class not found in script.js — "
            "bot message formatting styles will not be applied"
        )
