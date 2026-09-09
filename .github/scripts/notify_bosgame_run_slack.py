#!/usr/bin/env python3
"""
notify_bosgame_run_slack.py — heartbeat + result reporter for the dedicated
"Nightly Bosgame Run" Slack channel.

Unlike the per-suite notifiers (promptfoo/ragas/deepeval channels), this one is
the single place that answers "did the nightly LLM evaluation actually run on
bosgame tonight?". It is called on EVERY hourly schedule tick:

  * bosgame DOWN  -> post "unavailable at HH:MM, will retry next hour"
  * bosgame UP    -> post "available at HH:MM, warming + starting <suite>"
  * after tests   -> post a pass/fail summary and the full, collapsed list of
                     every test as a threaded reply.

Events:
  --event down     bosgame not reachable / model missing
  --event up       bosgame reachable, run starting
  --event skip     already completed for today (daily marker hit)
  --event result   tests finished — parse results and post summary + thread

Env:
  SLACK_BOT_TOKEN   Slack bot token (xoxb-...). If unset, the script no-ops
                    with exit 0 so it never fails the CI job.

The bot must be a member of the target channel (invite it once).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

SLACK_POST_URL = "https://slack.com/api/chat.postMessage"
# Slack hard limits: 3000 chars per text object, 50 blocks per message.
_CHUNK_CHARS = 2800
_MAX_LINES_PER_REPLY = 60


def _now(tz: str) -> str:
    try:
        return datetime.now(ZoneInfo(tz)).strftime("%H:%M")
    except Exception:
        return datetime.now().strftime("%H:%M")


def _post(channel: str, token: str, text: str, blocks=None, thread_ts=None) -> str | None:
    """Post one message; return its ts (for threading) or None on failure."""
    payload = {"channel": channel, "text": text, "unfurl_links": False}
    if blocks is not None:
        payload["blocks"] = blocks
    if thread_ts:
        payload["thread_ts"] = thread_ts
    req = urllib.request.Request(
        SLACK_POST_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        print(f"[notify_bosgame] Slack request failed: {exc}", file=sys.stderr)
        return None
    if not body.get("ok"):
        print(f"[notify_bosgame] Slack API error: {body.get('error')}", file=sys.stderr)
        return None
    return body.get("ts")


# ─── Result parsers (best-effort; never raise) ──────────────────────────────

def _parse_playwright(path: Path) -> list[tuple[str, bool]]:
    out: list[tuple[str, bool]] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return out

    def walk(suite):
        for spec in suite.get("specs", []) or []:
            title = spec.get("title") or "test"
            ok = bool(spec.get("ok", False))
            out.append((title, ok))
        for child in suite.get("suites", []) or []:
            walk(child)

    for s in data.get("suites", []) or []:
        walk(s)
    return out


def _parse_promptfoo(path: Path) -> list[tuple[str, bool]]:
    out: list[tuple[str, bool]] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return out
    raw = data.get("results", {})
    rows = raw.get("results") if isinstance(raw, dict) else raw
    for r in rows or []:
        tc = r.get("testCase") or {}
        desc = tc.get("description") or (r.get("vars") or {}).get("prompt", "")
        out.append((str(desc)[:120] or "probe", bool(r.get("success"))))
    return out


def _parse_deepeval(path: Path) -> list[tuple[str, bool]]:
    out: list[tuple[str, bool]] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return out
    for case in data.get("testCases", []) or []:
        out.append((str(case.get("name") or "case"), bool(case.get("success"))))
    return out


def _latest(results: Path, patterns: list[str]) -> Path | None:
    if results.is_file():
        return results
    if not results.is_dir():
        return None
    cands: list[Path] = []
    for pat in patterns:
        cands.extend(sorted(results.glob(pat), reverse=True))
    return cands[0] if cands else None


def _collect(fmt: str, results: str | None) -> list[tuple[str, bool]]:
    if not results:
        return []
    p = Path(results)
    if fmt == "playwright":
        f = _latest(p, ["results.json", "*.json"])
        return _parse_playwright(f) if f else []
    if fmt == "promptfoo":
        f = _latest(p, ["promptfoo-results.json", "*.json"])
        return _parse_promptfoo(f) if f else []
    if fmt == "deepeval":
        f = _latest(p, [".latest_run_full.json", "test_run_*.json", "*.json"])
        return _parse_deepeval(f) if f else []
    return []


# ─── Message builders ───────────────────────────────────────────────────────

def _button_blocks(text: str, run_url: str | None) -> list[dict]:
    section = {"type": "section", "text": {"type": "mrkdwn", "text": text}}
    if run_url:
        section["accessory"] = {
            "type": "button",
            "text": {"type": "plain_text", "text": "View run"},
            "url": run_url,
        }
    return [section]


def _detail_replies(cases: list[tuple[str, bool]]) -> list[str]:
    """Chunk the full test list into thread-reply-sized code blocks."""
    lines = [f"{'✅' if ok else '❌'} {name}" for name, ok in cases]
    replies: list[str] = []
    buf: list[str] = []
    size = 0
    for ln in lines:
        if len(buf) >= _MAX_LINES_PER_REPLY or size + len(ln) + 1 > _CHUNK_CHARS:
            replies.append("```\n" + "\n".join(buf) + "\n```")
            buf, size = [], 0
        buf.append(ln)
        size += len(ln) + 1
    if buf:
        replies.append("```\n" + "\n".join(buf) + "\n```")
    return replies


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", required=True)
    ap.add_argument("--suite", required=True)
    ap.add_argument("--event", required=True, choices=["down", "up", "skip", "result"])
    ap.add_argument("--tz", default="America/New_York")
    ap.add_argument("--run-url", default=os.environ.get("GITHUB_RUN_URL"))
    ap.add_argument("--format", default="none",
                    choices=["none", "playwright", "promptfoo", "deepeval"])
    ap.add_argument("--results", default=None)
    args = ap.parse_args()

    token = os.environ.get("SLACK_BOT_TOKEN", "").strip()
    if not token:
        print("[notify_bosgame] SLACK_BOT_TOKEN unset — no-op.")
        return 0
    if not args.channel:
        print("[notify_bosgame] no channel id — no-op.")
        return 0

    now = _now(args.tz)
    suite = args.suite

    if args.event == "down":
        _post(args.channel, token,
              f":red_circle: *{suite}* — bosgame unavailable at {now} ({args.tz}). "
              f"Tests not started; will retry on the next hourly check.")
        return 0

    if args.event == "skip":
        _post(args.channel, token,
              f":fast_forward: *{suite}* — already completed for today at {now}. Skipping.")
        return 0

    if args.event == "up":
        _post(args.channel, token,
              f":large_green_circle: *{suite}* — bosgame available at {now} ({args.tz}). "
              f"Warming gpt-oss and starting the suite…")
        return 0

    # event == result
    if args.format == "none":
        msg = (f":checkered_flag: *{suite}* — evaluation finished at {now}. "
               f"See the suite's own Slack channel for per-metric detail.")
        _post(args.channel, token, msg, blocks=_button_blocks(msg, args.run_url))
        return 0

    cases = _collect(args.format, args.results)
    total = len(cases)
    passed = sum(1 for _, ok in cases if ok)
    failed = total - passed
    icon = ":white_check_mark:" if failed == 0 and total > 0 else (
        ":warning:" if total > 0 else ":grey_question:")
    headline = (
        f"{icon} *{suite}* — finished at {now}: *{passed}/{total} passed*"
        + (f", {failed} failed" if failed else "")
        + ("  ·  no parseable results" if total == 0 else "")
    )
    ts = _post(args.channel, token, headline, blocks=_button_blocks(headline, args.run_url))
    if ts and cases:
        for chunk in _detail_replies(cases):
            _post(args.channel, token, chunk, thread_ts=ts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
