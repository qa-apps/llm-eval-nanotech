import re
from playwright.sync_api import Page, expect
from typing import Literal

Mode = Literal['Auto', 'General', 'Code', 'Analyst', 'Research', 'Vision']

class InteractiveTools:
    def __init__(self, page: Page):
        self.page = page

    # AI Widget
    def open_chat_window(self):
        self.page.get_by_role('button', name='Open chat').click()
        expect(self.page.locator('#chat-window')).to_be_visible()
        self._accept_consent_if_present()
        self._maximize_chat_if_present()

    def _accept_consent_if_present(self):
        overlay = self.page.locator('#chat-consent-overlay')
        try:
            overlay.wait_for(state='visible', timeout=2000)
        except Exception:
            return
        self.page.locator('#chat-consent-checkbox').check()
        self.page.locator('#chat-consent-agree').click()

    def _maximize_chat_if_present(self):
        button = self.page.get_by_role('button', name='Maximize chat')
        try:
            button.wait_for(state='visible', timeout=2000)
        except Exception:
            return
        button.click()
        try:
            button.wait_for(state='hidden', timeout=2000)
        except Exception:
            pass

    def click_mode(self, mode: Mode):
        self._accept_consent_if_present()
        btn = self.page.locator('#chat-agent-bar .agent-btn').filter(has_text=mode).first
        btn.click(force=True)

    def expect_send_button_visible(self):
        expect(self.page.locator('#chat-form button.chat-send-btn, #chat-form button[aria-label="Send message"]').first).to_be_visible()

    # ROI Calculator
    def scroll_to_calculator(self):
        self.page.get_by_role('heading', name='Quick ROI Calculator').scroll_into_view_if_needed()

    def fill_manual_hours(self, hours: str):
        self.page.get_by_label('Manual hours per month').fill(hours)

    def fill_hourly_cost(self, cost: str):
        self.page.get_by_label('Average hourly cost (USD)').fill(cost)

    def click_calculate(self):
        self.page.get_by_role('button', name='Calculate ROI').click()

    def expect_download_button_visible(self):
        expect(self.page.get_by_role('button', name='Download ROI Summary')).to_be_visible()

    # FAQ
    def scroll_to_faq(self):
        self.page.get_by_role('heading', name='Got Questions? We Have Answers').scroll_into_view_if_needed()

    def click_question(self, question_text: str):
        self.page.get_by_role('button', name=re.compile(re.escape(question_text), re.IGNORECASE)).click()

    def expect_answer_visible(self, answer_text: str):
        expect(self.page.get_by_text(answer_text, exact=False).first).to_be_visible()

    # Combo AI Cards
    def expect_model_label_present(self, name: str):
        expect(self.page.get_by_text(name, exact=False).first).to_be_attached(timeout=15_000)
