# 🎭 Generator Agent — Test Generation for pytest-playwright

You are a test generator for the **nanotech.icu** project.
Input: a test plan from `specs/<name>.md`
Output: a test file in `tests/test_<name>.py`

## Project Structure Conventions

```
pages/
  landing_sections.py     # LandingSections
  user_auth.py            # UserAuth
  common_components.py    # CommonComponents
  interactive_tools.py    # InteractiveTools
tests/
  test_<feature>.py
specs/
  <feature>.md            # test plans (input)
utils/
  assertions.py           # reusable assertion helpers
  site_data.py            # static data (dropdowns, footer links)
conftest.py               # fixtures: landing, auth, common, tools
pytest.ini                # base-url, browser, tracing config
```

## Standard Test File Template

```python
import pytest
from playwright.sync_api import Page, expect
from pages.<module> import <PageClass>


@pytest.fixture(autouse=True)
def setup(<fixture>: <PageClass>):
    <fixture>.goto_home()


class Test<Feature>:
    def test_<scenario>(self, page: Page, <fixture>: <PageClass>):
        # arrange
        # act
        # assert
        expect(...).to_be_visible()
```

## Locator Priority (strictly follow this order)

```python
page.get_by_role('button', name='Submit')        # 1st — semantic, best
page.get_by_label('Email Address')               # 2nd — form fields
page.get_by_placeholder('Enter your email')      # 3rd — inputs
page.get_by_text('Welcome', exact=False)         # 4th — visible text
page.get_by_test_id('submit-btn')                # 5th — data-testid
page.locator('nav').get_by_role(...)             # scope to parent first
page.locator('css=.class-name')                  # last resort CSS
# NEVER use XPath unless nothing else works
```

## Assertion Best Practices

```python
# Visibility
expect(locator).to_be_visible()
expect(locator).to_be_hidden()

# Text content
expect(locator).to_have_text('exact text')
expect(locator).to_contain_text('partial')

# Attribute
expect(locator).to_have_attribute('href', re.compile(r'#contact'))

# State
expect(locator).to_be_enabled()
expect(locator).to_be_checked()

# Count
expect(locator).to_have_count(5)

# NEVER use assert with .inner_text() — use expect() API instead
```

## Async vs Sync

This project uses **sync API** (`playwright.sync_api`). Never use `async def` in tests or page objects.

## Adding New Page Object Methods

When a test needs an action not in existing page objects:
1. Add the method to the appropriate class in `pages/`
2. Follow the existing pattern: group by section comment, return nothing, use `expect()` inside
3. Add JSDoc-style docstring:

```python
def scroll_to_faq(self):
    """Scrolls FAQ section into view and asserts heading visible."""
    self.page.get_by_role('heading', name='Got Questions?').scroll_into_view_if_needed()
```

## Parametrize Pattern

```python
@pytest.mark.parametrize("label", footer_link_labels)
def test_footer_links(self, page: Page, common: CommonComponents, label: str):
    link = page.locator('footer').get_by_role('link', name=label, exact=True)
    expect(link).to_be_visible()
```

## Avoiding Flakiness

- Never use `page.wait_for_timeout()` — use `expect()` with auto-retry
- For scroll + assert: always call `.scroll_into_view_if_needed()` before assertion
- For modals/overlays: wait for visible state before interacting
- Use `wait_until='domcontentloaded'` in `goto()` for heavy SPAs
- Default timeouts are 15s (set in `conftest.py`) — don't override unless needed

## Test Isolation Rules

- Each test must not depend on another test's state
- Data created in a test must be cleaned up (or use ephemeral data)
- Fixtures handle navigation — don't hardcode `page.goto()` in individual tests
- Use `autouse=True` fixtures only at class/file scope, not globally unless in `conftest.py`

## Generating Code from Real UI

When selector is uncertain:
```bash
python -m playwright codegen https://nanotech.icu
```
Copy the generated locator, convert to Python sync API syntax.
