# Playwright CLI — Python Reference

Use `python -m playwright` for local debugging tasks **before** reaching for MCP.

## Common Commands

```bash
# Open browser interactively and generate selectors/code
python -m playwright codegen https://nanotech.icu

# Open codegen with specific browser
python -m playwright codegen --browser firefox https://nanotech.icu

# Open Playwright Inspector to debug a specific test
PWDEBUG=1 pytest tests/test_landing_sections.py::TestHeroSection::test_hero_visibility -s

# Inspect a recorded trace
python -m playwright show-trace trace.zip

# Show installed browsers
python -m playwright install --list
```

## When to Use CLI vs MCP

| Task | Use |
|---|---|
| Generate or verify a locator | `codegen` CLI |
| Debug a failing test step-by-step | `PWDEBUG=1 pytest` |
| Inspect a recorded trace file | `show-trace` CLI |
| Ask Windsurf to navigate and inspect live page | MCP |
| Ask Windsurf to fill forms and check UI state | MCP |

**Rule: prefer CLI first. Use MCP only when interactive browser control via AI is needed.**

## Locator Priority (pytest-playwright)

```python
page.get_by_role(...)          # 1st choice
page.get_by_label(...)         # 2nd choice
page.get_by_text(...)          # 3rd choice
page.get_by_test_id(...)       # for data-testid attrs
page.locator("css=...")        # fallback CSS
```

## Useful pytest-playwright Flags

```bash
pytest --headed                      # run with visible browser
pytest --slowmo=500                  # slow down actions by 500ms
pytest --browser firefox             # use Firefox
pytest -k "test_hero"                # run specific test by name
pytest --tracing on                  # always record traces
```
