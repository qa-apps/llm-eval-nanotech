# Performance tests (k6)

Smoke checks for nanotech.icu live endpoints. These run independently of pytest
so they can be wired into CI separately and stay out of the Playwright job.

## Install

```bash
brew install k6   # macOS
```

## Run

```bash
k6 run performance/k6/smoke.js
# Override target:
k6 run -e BASE_URL=https://nanotech.icu performance/k6/smoke.js
```

## Thresholds (gate the smoke as pass/fail)

- `http_req_failed` &lt; 1%
- `http_req_duration` p(95) &lt; 1500ms
- `errors` (custom rate) &lt; 1%
- `checks` &gt; 99%
