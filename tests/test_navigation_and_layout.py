import re
import pytest
from playwright.sync_api import Page, expect
from pages.landing_sections import LandingSections
from pages.common_components import CommonComponents
from utils.site_data import header_dropdowns, footer_link_labels

VIEWPORTS = [
    {'name': 'Desktop 1440', 'width': 1440, 'height': 900},
    {'name': 'Mobile small', 'width': 375, 'height': 667}
]

@pytest.fixture(autouse=True)
def setup(landing: LandingSections):
    landing.goto_home()

class TestNavigation:
    @pytest.mark.parametrize("group", header_dropdowns, ids=lambda g: g['menuLabel'])
    def test_header_dropdowns(self, page: Page, common: CommonComponents, group):
        common.open_dropdown(group['menuLabel'])
        first_link_label = group['links'][0]['label']
        expect(page.locator('nav').get_by_role('link', name=first_link_label).first).to_be_visible()

    @pytest.mark.parametrize("label", footer_link_labels)
    def test_footer_links(self, page: Page, common: CommonComponents, label: str):
        link = page.locator('footer').get_by_role('link', name=label, exact=True)
        expect(link).to_be_visible()
        expect(link).to_have_attribute('href', re.compile(r'.+'))

    @pytest.mark.parametrize("anchor,text", [
        ('#about', 'Leading AI Automation'),
        ('#services', 'Autonomous Agent Services')
    ])
    def test_anchor_navigation(self, page: Page, landing: LandingSections, anchor, text):
        landing.goto_home(anchor)
        expect(page.get_by_role('heading', name=text).first).to_be_visible()

class TestLayout:
    @pytest.mark.parametrize("vp", VIEWPORTS, ids=lambda v: v['name'])
    def test_responsive_layout(self, page: Page, vp):
        page.set_viewport_size({'width': vp['width'], 'height': vp['height']})
        page.goto('/', wait_until='domcontentloaded')
        expect(page.get_by_text('Transforming Business', exact=False).first).to_be_visible()

    def test_theme_switching(self, common: CommonComponents, page: Page):
        common.select_theme('Dark')
        expect(page.get_by_text('Transforming Business', exact=False).first).to_be_visible()
