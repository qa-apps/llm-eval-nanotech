#!/usr/bin/env python3
"""Post DeepEval run summaries to Slack."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _latest_result(results_dir: Path) -> Path | None:
    candidates = [results_dir / ".latest_run_full.json"]
    candidates.extend(sorted(results_dir.glob("test_run_*.json"), reverse=True))
    for path in candidates:
        if path.exists():
            return path
    return None


def _summary(data: dict[str, Any]) -> dict[str, Any]:
    cases = data.get("testCases") or []
    total = len(cases)
    passed = sum(1 for case in cases if case.get("success"))
    failed = total - passed
    metrics = [m for case in cases for m in (case.get("metricsData") or [])]
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "metric_total": len(metrics),
        "metric_failed": sum(1 for metric in metrics if not metric.get("success")),
    }


def _donut(passed: int, total: int) -> str:
    if total <= 0:
        return "`----------` 0/0 passed"
    filled = round((passed / total) * 10)
    return f"`{'#' * filled}{'-' * (10 - filled)}` {passed}/{total} passed"


def _failure_lines(data: dict[str, Any], limit: int = 5) -> list[str]:
    lines = []
    for case in data.get("testCases") or []:
        if case.get("success"):
            continue
        metrics = [
            str(m.get("name") or "metric")
            for m in (case.get("metricsData") or [])
            if not m.get("success")
        ]
        name = str(case.get("name") or "DeepEval test")
        suffix = f" - {', '.join(metrics[:3])}" if metrics else ""
        lines.append(f"- `{name}`{suffix}")
        if len(lines) >= limit:
            break
    return lines


def _post_json(url: str, payload: dict[str, Any], token: str = "") -> dict[str, Any]:
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=20) as resp:
        body = resp.read().decode("utf-8")
    try:
        return json.loads(body)
    except Exception:
        return {"ok": True, "raw": body}


def _block_payload(channel: str, data: dict[str, Any], dashboard_url: str, run_url: str) -> dict[str, Any]:
    summary = _summary(data)
    failed = summary["failed"]
    icon = "FAILED" if failed else ("PASSED" if summary["total"] else "NO RESULTS")
    color = "#cc2929" if failed else ("#2eb886" if summary["total"] else "#e9a820")
    failures = _failure_lines(data)
    text = (
        f"*DeepEval Nightly - {icon}*\n"
        f"{_donut(summary['passed'], summary['total'])}\n"
        f"*Metrics:* `{summary['metric_total']}` total, `{summary['metric_failed']}` failed"
    )
    if failures:
        text += "\n*Top failures:*\n" + "\n".join(failures)
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": f"DeepEval - {icon}", "emoji": True}},
        {"type": "section", "text": {"type": "mrkdwn", "text": text}},
    ]
    actions = []
    if dashboard_url:
        actions.append({
            "type": "button",
            "text": {"type": "plain_text", "text": "Open DeepEval UI", "emoji": True},
            "url": dashboard_url,
            "style": "primary" if not failed else "danger",
        })
    if run_url:
        actions.append({
            "type": "button",
            "text": {"type": "plain_text", "text": "View run", "emoji": True},
            "url": run_url,
        })
    if actions:
        blocks.append({"type": "actions", "elements": actions})
    payload = {"attachments": [{"color": color, "blocks": blocks, "fallback": f"DeepEval: {summary['passed']}/{summary['total']} passed"}]}
    if channel:
        payload["channel"] = channel
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", default="")
    parser.add_argument("--results-dir", default=".deepeval")
    parser.add_argument("--dashboard-url", default="")
    args = parser.parse_args()

    data = _load(_latest_result(Path(args.results_dir)) or Path(""))
    run_url = os.environ.get("GITHUB_RUN_URL", "")
    payload = _block_payload(args.channel, data, args.dashboard_url, run_url)

    token = os.environ.get("SLACK_BOT_TOKEN", "")
    if token and args.channel:
        try:
            _post_json("https://slack.com/api/conversations.join", {"channel": args.channel}, token=token)
        except Exception:
            pass
        resp = _post_json("https://slack.com/api/chat.postMessage", payload, token=token)
        if not resp.get("ok"):
            print(f"Slack post failed: {resp.get('error')}", file=sys.stderr)
            return 1
        print(f"Message posted to {args.channel}")
        return 0

    webhook = os.environ.get("SLACK_WEBHOOK_URL", "")
    if webhook:
        payload.pop("channel", None)
        _post_json(webhook, payload)
        print("Message posted via SLACK_WEBHOOK_URL fallback")
        return 0

    print("No Slack token/webhook configured; skipping Slack notification", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
