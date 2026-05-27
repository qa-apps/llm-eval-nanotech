import shutil
import pathlib
import pytest
from playwright.sync_api import Page
from pages.landing_sections import LandingSections
from pages.user_auth import UserAuth
from pages.common_components import CommonComponents
from pages.interactive_tools import InteractiveTools

@pytest.fixture(scope='session', autouse=True)
def clean_test_results():
    output = pathlib.Path('test-results')
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(exist_ok=True)
    yield


@pytest.fixture
def landing(page: Page) -> LandingSections:
    return LandingSections(page)

@pytest.fixture
def auth(page: Page) -> UserAuth:
    return UserAuth(page)

@pytest.fixture
def common(page: Page) -> CommonComponents:
    return CommonComponents(page)

@pytest.fixture
def tools(page: Page) -> InteractiveTools:
    return InteractiveTools(page)

@pytest.fixture(autouse=True)
def set_default_timeouts(page: Page):
    page.set_default_timeout(15_000)
    page.set_default_navigation_timeout(15_000)
    yield
