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


def test_token_delivery_failure_is_fatal_when_required(monkeypatch, tmp_path):
    notify = _load_notify_module()
    result = tmp_path / ".latest_run_full.json"
    result.write_text('{"testCases": []}', encoding="utf-8")
    monkeypatch.setenv("SLACK_BOT_TOKEN", "test")
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


def test_standard_workflow_collects_all_twelve_deepeval_cases():
    workflow = (ROOT / ".github/workflows/deepeval-nightly.yml").read_text(encoding="utf-8")
    assert "LOCAL_LLM_API_KEY: ${{ secrets.LOCAL_LLM_API_KEY }}" in workflow
    assert "LOCAL_LLM_API_KEY: ollama" not in workflow
    assert "tests/llmEval/test_chatbot_deepeval.py \\" in workflow
    assert "tests/llmEval/test_chatbot_judge_ui.py \\" in workflow
    assert "EXPECTED_CASES: ${{ steps.eval_day.outputs.scope == 'smoke' && '1' || '12' }}" in workflow
    assert "does not match " in workflow and "complete report quality verdict" in workflow

    api_suite = (ROOT / "tests/llmEval/test_chatbot_deepeval.py").read_text(encoding="utf-8")
    browser_suite = (ROOT / "tests/llmEval/test_chatbot_judge_ui.py").read_text(encoding="utf-8")
    assert api_suite.count("assert_test(") == 6
    assert browser_suite.count("assert_test(") == 1
    assert browser_suite.count("_assert_reply_quality(") == 7
