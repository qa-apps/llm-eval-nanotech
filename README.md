# PW_nanotech

LLM evaluation and end-to-end quality suite for the
**[nanotech.icu](https://nanotech.icu)** AI chatbot, plus the production sources
of the assistant it evaluates.

78 tests across four layers, gated in CI:

| Layer | Path | Tests | What it covers |
| --- | --- | ---: | --- |
| LLM evaluation | `tests/llmEval/` | 12 | DeepEval metrics and browser-level judge checks against the live assistant |
| End-to-end | `tests/*.py` | 44 | Landing sections, navigation and layout, regression bugs, site integrity and tools, auth flows |
| API | `tests/api/` | 10 | HTTP contract and behaviour of the live site |
| Unit | `tests/unit/` | 12 | The evaluation tooling itself — report building and the free-model pool |

## LLM evaluation

`tests/llmEval/test_chatbot_deepeval.py` runs DeepEval against the deployed
chatbot using `HallucinationMetric`, `BiasMetric`, `ToxicityMetric`, and custom
`GEval` criteria — including an explicit refusal criterion that checks the
assistant declines unsafe requests rather than merely avoiding bad words.

`tests/llmEval/test_chatbot_judge_ui.py` runs the same style of judgement
through the real browser UI, so the verdict covers what a user actually
receives, not just what the API returns.

### The judge runs locally

`utils/nanotech_judge.py` implements `NanotechJudge`, a `DeepEvalBaseLLM` backed
by **GPT-OSS 120B on a self-hosted Ollama gateway** rather than a commercial
API. No OpenAI key is required. The judge adds the things a nightly evaluation
needs in order to be trustworthy and repeatable:

- On-disk request caching, so an unchanged prompt is not re-judged and re-billed
  in wall-clock time.
- Bounded retries with backoff on 429/502/503/504.
- A priority wait, so a scheduled run queues for the shared model instead of
  silently passing with zero cases executed.
- `<think>` blocks stripped from reasoning-model output before scoring.

Evaluations are opt-in: they run only when `RUN_LLM_EVALS=1`, so an ordinary
E2E run never depends on model availability.

## The application under test

`app/` holds the production sources of the assistant — `chat_server.py`,
`free_model_pool.py`, `model_curator.py` — together with the systemd units under
`deploy/`. See [`app/README.md`](app/README.md) for the deployment contract.

The notable policy is that the model pool **fails closed**: OpenRouter models
must carry a `:free` id, direct providers must be explicitly tagged `free: true`
in the curated registry, and paid or unmarked models are rejected before any
network request is made. Providers that return 401/402/403/429, time out, or
error are put on cooldown before failover continues.

## Running locally

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
cp .env.example .env    # then fill in the values
```

Run the E2E and API suites — no model access needed:

```bash
pytest
```

Run the LLM evaluations, which require a reachable judge:

```bash
RUN_LLM_EVALS=1 pytest tests/llmEval/
```

Read the most recent DeepEval run:

```bash
python tests/llmEval/show_report.py
```

Markers are declared in `pytest.ini`: `api` for HTTP coverage and `llm` for
DeepEval evaluations. The base URL defaults to `https://nanotech.icu` and traces,
screenshots, and video are retained on failure.

## Continuous integration

| Workflow | Trigger | What it does |
| --- | --- | --- |
| `playwright.yml` | push, pull request, 3:05 AM New York | Runs the Playwright E2E and API suites on a hosted runner. |
| `deepeval-nightly.yml` | 7:15 AM New York, manual | Runs the full DeepEval suite on a self-hosted GPU runner, validates the report contract, publishes a dashboard to GitHub Pages, and reports to Slack. |

Both scheduled workflows use two UTC cron entries with a New York time gate, so
the schedule stays correct across daylight-saving changes.

The nightly job does not simply trust the exit code. It validates the emitted
report before accepting the run: the report must be newer than the run start,
contain the expected number of cases, and carry a prompt, an answer, judge
metrics, and a boolean verdict for every case — and the step outcome must agree
with the report's own verdict. A run that produced no real evaluation fails
instead of reporting green.

## Performance

`performance/k6/smoke.js` holds the k6 smoke profile; see
[`performance/README.md`](performance/README.md).

## Layout

```text
app/            Production sources of the assistant under test
deploy/         systemd units and the free-only nginx drop-in
pages/          Page objects
performance/    k6 profiles
scripts/        DeepEval Pages dashboard builder
tests/          api/ · llmEval/ · unit/ · E2E specs
utils/          Judge, assertions, request cache, site data
```
