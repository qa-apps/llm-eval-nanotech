import os
import re
from playwright.sync_api import Page, expect


NAVIGATION_TIMEOUT_MS = int(os.getenv('NANOTECH_NAVIGATION_TIMEOUT_MS', '30000'))

class LandingSections:
    def __init__(self, page: Page):
        self.page = page

    # Home / General
    def goto_home(self, anchor: str = ''):
        self.page.goto(
            f'/{anchor}',
            wait_until='domcontentloaded',
            timeout=NAVIGATION_TIMEOUT_MS,
        )

    # Hero Section
    def expect_hero_visible(self):
        expect(self.page.get_by_role('heading', name=re.compile(r'Transforming Business', re.IGNORECASE)).first).to_be_visible()
        expect(self.page.get_by_text('We build custom AI solutions', exact=False).first).to_be_visible()

    def click_schedule_assessment(self):
        self.page.get_by_role('link', name='Schedule AI Assessment').click()

    def expect_top_banner(self):
        expect(self.page.get_by_text('Introducing Agentic AI Solutions', exact=False).first).to_be_visible()

    # Industries Section
    def scroll_to_industries(self):
        heading = self.page.get_by_text('AI Solutions Across Sectors', exact=False).first
        heading.scroll_into_view_if_needed()
        expect(heading).to_be_visible()

    def expect_industry_card(self, industry: str):
        card = self.page.get_by_role('heading', name=industry).first
        card.scroll_into_view_if_needed()
        expect(card).to_be_visible()

    # Services Section
    def scroll_to_services(self):
        heading = self.page.get_by_role('heading', name='Autonomous Agent Services').first
        heading.scroll_into_view_if_needed()
        expect(heading).to_be_visible()

    def expect_service_card(self, title: str):
        card = self.page.get_by_role('heading', name=title).first
        card.scroll_into_view_if_needed()
        expect(card).to_be_visible()

    # Metrics Section
    def scroll_to_metrics(self):
        heading = self.page.get_by_text('Measurable Business Impact', exact=False).first
        heading.scroll_into_view_if_needed()
        expect(heading).to_be_visible()

    def expect_metric_card(self, title: str):
        expect(self.page.get_by_text(title, exact=False).first).to_be_visible()

    # Testimonials
    def scroll_to_testimonials(self):
        heading = self.page.get_by_role('heading', name='What Our Clients Say')
        heading.scroll_into_view_if_needed()
        expect(heading).to_be_visible()

    def click_next_testimonial(self):
        self.page.get_by_role('button', name='Next').click()

    def click_prev_testimonial(self):
        self.page.get_by_role('button', name='Previous').click()

    # Ticker
    def expect_ticker_keyword(self, keyword: str):
        expect(self.page.get_by_text(keyword, exact=False).first).to_be_attached()
