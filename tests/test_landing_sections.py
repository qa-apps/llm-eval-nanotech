import pytest
from playwright.sync_api import Page, expect
import re
from pages.landing_sections import LandingSections
from utils.site_data import industries, services, tech_keywords

@pytest.fixture(autouse=True)
def setup(landing: LandingSections):
    landing.goto_home()

class TestHeroSection:
    def test_hero_visibility(self, landing: LandingSections):
        landing.expect_hero_visible()

    def test_schedule_ai_assessment_link_is_visible(self, page: Page):
        link = page.get_by_role('link', name='Schedule AI Assessment')
        expect(link).to_be_visible()

    def test_schedule_ai_assessment_link_has_correct_href(self, page: Page):
        link = page.get_by_role('link', name='Schedule AI Assessment')
        expect(link).to_have_attribute('href', re.compile(r'#contact'))

    def test_see_ai_in_action_link_is_visible(self, page: Page):
        link = page.get_by_role('link', name='See AI in Action')
        expect(link).to_be_visible()

    def test_top_announcement_banner_is_visible(self, landing: LandingSections):
        landing.expect_top_banner()

    def test_learn_more_link_has_correct_href(self, page: Page):
        learn_more = page.get_by_role('link', name=re.compile(r'Learn More', re.IGNORECASE)).first
        expect(learn_more).to_have_attribute('href', re.compile(r'#services'))

class TestAboutSection:
    def test_about_heading_is_visible(self, page: Page):
        expect(page.get_by_text('Leading AI Automation & Intelligence', exact=False).first).to_be_visible()

    @pytest.mark.parametrize("stat", ['200+', '70%', '50+', '15+', '99.9%', '24/7'])
    def test_about_stats_visible(self, page: Page, stat: str):
        expect(page.get_by_text(stat, exact=True).first).to_be_visible()

class TestIndustriesSection:
    def test_industries_heading_is_visible(self, landing: LandingSections):
        landing.scroll_to_industries()

    @pytest.mark.parametrize("industry", industries)
    def test_industry_card_visible(self, landing: LandingSections, industry: str):
        landing.expect_industry_card(industry)

class TestServicesSection:
    def test_services_heading_is_visible(self, landing: LandingSections):
        landing.scroll_to_services()

    @pytest.mark.parametrize("service", services)
    def test_service_card_visible(self, landing: LandingSections, service: str):
        landing.expect_service_card(service)

class TestMetricsAndStatistics:
    def test_impact_heading_is_visible(self, landing: LandingSections):
        landing.scroll_to_metrics()

    @pytest.mark.parametrize("metric", ['70% Cost Reduction', '99.9% Accuracy'])
    def test_metric_card_visible(self, landing: LandingSections, metric: str):
        landing.expect_metric_card(metric)

class TestTestimonials:
    def test_testimonials_heading_is_visible(self, landing: LandingSections):
        landing.scroll_to_testimonials()

    def test_next_button_works(self, landing: LandingSections):
        landing.scroll_to_testimonials()
        landing.click_next_testimonial()

class TestTechnologyTicker:
    @pytest.mark.parametrize("keyword", tech_keywords)
    def test_ticker_keyword_present(self, landing: LandingSections, keyword: str):
        landing.expect_ticker_keyword(keyword)
