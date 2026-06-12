# Debugging Strategy — CLI First, MCP Second

## Step-by-step priority

1. **Run the failing test with `PWDEBUG=1`**
   ```bash
   PWDEBUG=1 pytest tests/<file>.py::<TestClass>::<test_name> -s
   ```
   Opens Playwright Inspector — no MCP needed.

2. **Use `codegen` to find the right locator**
   ```bash
   python -m playwright codegen https://nanotech.icu
   ```
   Pick the selector visually, copy it into the test.

3. **Inspect a trace if test failed with `retain-on-failure`**
   ```bash
   python -m playwright show-trace test-results/<test>/trace.zip
   ```

4. **Use MCP (Windsurf browser control) only when:**
   - You need Windsurf to navigate and describe what it sees
   - You need live DOM snapshots that CLI can't easily provide
   - You're generating new test plans for unknown pages

## Project test-run reference

```bash
# Full suite
pytest

# Single file
pytest tests/test_landing_sections.py

# Single test
pytest tests/test_landing_sections.py::TestHeroSection::test_hero_visibility

# With visible browser + slow motion
pytest --headed --slowmo=300

# Keep traces always
pytest --tracing on
```

## Trace output location

Traces are saved to `test-results/` when `--tracing retain-on-failure` is active (already set in `pytest.ini`).
