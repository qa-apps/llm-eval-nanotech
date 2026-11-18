from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _load_notify_module():
    path = ROOT / ".github/scripts/notify_deepeval_slack.py"
    spec = importlib.util.spec_from_file_location("notify_deepeval_slack", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def _load_daily_notify_module():
    path = ROOT / ".github/scripts/notify_bosgame_run_slack.py"
    spec = importlib.util.spec_from_file_location("notify_bosgame_run_slack", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def test_token_delivery_failure_is_fatal_when_required(monkeypatch, tmp_path):
    notify = _load_notify_module()
    result = tmp_path / ".latest_run_full.json"
    result.write_text('{"testCases": []}', encoding="utf-8")
    monkeypatch.setenv("SLACK_BOT_TOKEN", "test")
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    monkeypatch.setattr(
        "sys.argv",
        [
            "notify_deepeval_slack.py",
            "--channel", "C123",
            "--results-dir", str(tmp_path),
            "--require-delivery",
        ],
    )
    responses = iter(({"ok": True}, {"ok": False, "error": "not_authed"}))
    monkeypatch.setattr(notify, "_post_json", lambda *args, **kwargs: next(responses))

    assert notify.main() == 1


def test_daily_notifier_joins_supplied_channel_and_enforces_delivery(monkeypatch):
    notify = _load_daily_notify_module()
    monkeypatch.setenv("SLACK_BOT_TOKEN", "test")
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    monkeypatch.setattr(
        "sys.argv",
        [
            "notify_bosgame_run_slack.py",
            "--channel", "C123",
            "--suite", "DeepEval Nightly",
            "--event", "up",
            "--require-delivery",
        ],
    )
    calls = []

    def fake_api_post(method, token, payload):
        calls.append((method, payload))
        if method == "conversations.join":
            return {"ok": False, "error": "missing_scope"}
        return {"ok": False, "error": "not_in_channel"}

    monkeypatch.setattr(notify, "_api_post", fake_api_post)

    assert notify.main() == 1
    assert calls[0] == ("conversations.join", {"channel": "C123"})


def test_standard_workflow_collects_all_twelve_deepeval_cases():
    workflow = (ROOT / ".github/workflows/deepeval-nightly.yml").read_text(encoding="utf-8")
    assert "DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}" in workflow
    assert "tests/llmEval/test_chatbot_deepeval.py \\" in workflow
    assert "tests/llmEval/test_chatbot_judge_ui.py \\" in workflow
    assert "EXPECTED_CASES: ${{ steps.eval_day.outputs.scope == 'smoke' && '1' || '12' }}" in workflow
    assert "does not match " in workflow and "complete report quality verdict" in workflow

    judge = (ROOT / "utils/nanotech_judge.py").read_text(encoding="utf-8")
    assert "os.getenv('DEEPSEEK_API_KEY', '')" in judge
    assert "DEEPSEEK_API_KEY is required for the cloud judge" in judge
    assert "'https://api.deepseek.com/v1'" in judge

    api_suite = (ROOT / "tests/llmEval/test_chatbot_deepeval.py").read_text(encoding="utf-8")
    browser_suite = (ROOT / "tests/llmEval/test_chatbot_judge_ui.py").read_text(encoding="utf-8")
    assert api_suite.count("assert_test(") == 6
    assert browser_suite.count("assert_test(") == 1
    assert browser_suite.count("_assert_reply_quality(") == 7


def test_workflow_runs_on_hosted_runner_and_fails_without_cloud_judge():
    workflow = (ROOT / ".github/workflows/deepeval-nightly.yml").read_text(encoding="utf-8")

    # The BosGame self-hosted runner and its local gateway are gone (2026-09-22).
    assert "self-hosted" not in workflow
    assert "bosgame" not in workflow.lower()
    assert "127.0.0.1" not in workflow
    assert "LOCAL_LLM_" not in workflow
    assert "runs-on: [" not in workflow
    assert "python3 .github/scripts/check_cloud_judge.py" in workflow
    assert "steps.local_llm" not in workflow
    assert "playwright install --with-deps chromium" in workflow
