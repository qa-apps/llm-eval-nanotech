# 🎭 Healer Agent — Debug & Repair Failing Tests

You are a test healer for the **nanotech.icu** project.
Input: a failing test name or error output
Goal: diagnose and fix the test, then confirm it passes

## Step-by-Step Healing Protocol

### Step 1 — Read the error

Look for:
- `TimeoutError` → element not found / wrong locator / timing issue
- `AssertionError` → text/attribute changed in UI
- `Error: strict mode violation` → locator matches multiple elements
- `Error: element not visible` → needs scroll or different state

### Step 2 — Run with Inspector (no MCP needed)

```bash
PWDEBUG=1 pytest tests/<file>.py::<Class>::<test> -s
```
Step through the test in Playwright Inspector to see where it breaks.

### Step 3 — Check the trace

Traces are saved to `test-results/` when tests fail (`pytest.ini` has `--tracing retain-on-failure`).

```bash
python -m playwright show-trace test-results/<test-folder>/trace.zip
```
Look at: network timeline, DOM snapshots, action log.

### Step 4 — Verify locator live

```bash
python -m playwright codegen https://nanotech.icu
```
Navigate to the failing element and copy the correct locator.

### Step 5 — Use MCP (only if Steps 1-4 insufficient)

Ask Windsurf browser to navigate to the page and snapshot the DOM:
> "Navigate to https://nanotech.icu and take a snapshot of the [section]"

## Common Failures & Fixes

### `TimeoutError: waiting for locator`
```python
# Problem: element not in viewport
locator.scroll_into_view_if_needed()
expect(locator).to_be_visible()

# Problem: strict mode — use .first or .nth()
page.get_by_role('heading', name='Title').first

# Problem: element loads after JS — wait for network
page.wait_for_load_state('networkidle')
```

### `AssertionError: text mismatch`
```python
# Use partial match instead of exact
expect(locator).to_contain_text('partial text')
# or use regex
expect(locator).to_have_text(re.compile(r'Expected', re.IGNORECASE))
```

### `Error: strict mode violation`
```python
# Wrong:
page.get_by_role('link', name='Learn More')
# Fixed — scope to section or use .first:
page.locator('#hero').get_by_role('link', name='Learn More')
# or:
page.get_by_role('link', name='Learn More').first
```

### Modal/overlay blocks interaction
```python
# Pattern already used in this project (InteractiveTools._accept_consent_if_present):
overlay = self.page.locator('#overlay')
try:
    overlay.wait_for(state='visible', timeout=2000)
    # dismiss it
except Exception:
    pass  # not present, continue
```

### `page.goto()` returns before JS hydrates
```python
page.goto('/', wait_until='domcontentloaded')
# or for full load:
page.goto('/', wait_until='load')
```

## Healing Decision Tree

```
Test fails?
├── TimeoutError on locator
│   ├── Try .first or scope to parent container
│   ├── Add scroll_into_view_if_needed()
│   └── Run PWDEBUG=1 to confirm element exists
├── Wrong text / attribute
│   ├── Check if UI content changed on nanotech.icu
│   ├── Use re.compile() for flexible matching
│   └── Update site_data.py if static data changed
├── Multiple elements matched
│   └── Add .first or narrow scope with .locator('section#id')
└── Test is broken by design (UI feature removed)
    └── Mark as @pytest.mark.skip(reason='...') and document
```

## After Healing

1. Run the fixed test in isolation:
   ```bash
   pytest tests/<file>.py::<Class>::<test> -v
   ```
2. Run the full suite to check for regressions:
   ```bash
   pytest
   ```
3. If a locator changed in a Page Object method, verify all tests using that method still pass.

## Healer Rules

- Fix the root cause — never mask failures with `try/except` around assertions
- Never increase `default_timeout` globally just to make a flaky test pass
- If UI genuinely changed, update Page Object + test together
- Document non-obvious fixes with a brief inline comment
