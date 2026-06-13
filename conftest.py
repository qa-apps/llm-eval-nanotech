import os
import shutil
import pathlib
import re
import httpx
import pytest

os.environ.setdefault('DEEPEVAL', '1')
os.environ.setdefault('DEEPEVAL_RESULTS_FOLDER', str(pathlib.Path('.deepeval').resolve()))
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


@pytest.fixture(scope='session')
def site_base_url(pytestconfig) -> str:
    base_url = getattr(pytestconfig.option, 'base_url', None)
    if not base_url:
        addopts = pytestconfig.getini('addopts')
        if isinstance(addopts, (list, tuple)):
            addopts = ' '.join(addopts)
        match = re.search(r'--base-url\s+(\S+)', addopts or '')
        base_url = match.group(1) if match else 'https://nanotech.icu'
    return base_url


@pytest.fixture
def api_client(site_base_url: str):
    with httpx.Client(base_url=site_base_url, follow_redirects=True, timeout=20.0) as client:
        yield client


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


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):
    try:
        from deepeval.test_run import global_test_run_manager
        global_test_run_manager.save_test_run_locally()
    except Exception:
        pass
