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

Channel resolution is automatic and needs no manual setup: if no channel id is
given (secret SLACK_NIGHTLY_BOSGAME_CHANNEL_ID unset), the bot finds the channel
named `--channel-name` (default "nightly-bosgame-run"), creating and joining it
on first run. Requires the bot to have channels:read + channels:manage (or
channels:join + chat:write.public) — if it lacks them, the step no-ops cleanly.

Events:
  --event down     bosgame not reachable / model missing
  --event up       bosgame reachable, run starting
  --event skip     already completed for today (daily marker hit)
  --event result   tests finished — parse results and post summary + thread

Env:
  SLACK_BOT_TOKEN   Slack bot token (xoxb-...). If unset, the script no-ops
                    with exit 0 so it never fails the CI job.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

SLACK_API = "https://slack.com/api/"
# Slack hard limits: 3000 chars per text object, 50 blocks per message.
_CHUNK_CHARS = 2800
_MAX_LINES_PER_REPLY = 60


def _now(tz: str) -> str:
    try:
        return datetime.now(ZoneInfo(tz)).strftime("%H:%M")
    except Exception:
        return datetime.now().strftime("%H:%M")


def _api_post(method: str, token: str, payload: dict) -> dict:
    req = urllib.request.Request(
        SLACK_API + method,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        print(f"[notify_bosgame] Slack POST {method} failed: {exc}", file=sys.stderr)
        return {"ok": False, "error": str(exc)}


def _api_get(method: str, token: str, params: dict) -> dict:
    url = SLACK_API + method + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        print(f"[notify_bosgame] Slack GET {method} failed: {exc}", file=sys.stderr)
        return {"ok": False, "error": str(exc)}


def resolve_channel(token: str, channel_id: str, channel_name: str) -> str | None:
    """Return a usable channel id: the given id, else find-or-create by name."""
    channel_id = (channel_id or "").strip()
    if channel_id:
        return channel_id
    name = (channel_name or "").strip().lstrip("#")
    if not name:
        return None

    # Find an existing public (or private) channel by name.
    for types in ("public_channel", "private_channel"):
        cursor = ""
        for _ in range(20):  # cap pagination
            params = {"types": types, "limit": 1000, "exclude_archived": "true"}
            if cursor:
                params["cursor"] = cursor
            r = _api_get("conversations.list", token, params)
            if not r.get("ok"):
                break
            for c in r.get("channels", []) or []:
                if c.get("name") == name:
                    _api_post("conversations.join", token, {"channel": c["id"]})  # best effort
                    return c["id"]
            cursor = (r.get("response_metadata") or {}).get("next_cursor") or ""
            if not cursor:
                break

    # Not found — create it (bot becomes a member automatically).
    r = _api_post("conversations.create", token, {"name": name, "is_private": False})
    if r.get("ok"):
        cid = r["channel"]["id"]
        _api_post("conversations.setPurpose", token, {
            "channel": cid,
            "purpose": "Nightly bosgame LLM-eval heartbeat: hourly up/down + per-run test results.",
        })
        return cid
    if r.get("error") == "name_taken":
        # Race or private-only visibility: re-list public channels once more.
        r2 = _api_get("conversations.list", token,
                      {"types": "public_channel", "limit": 1000, "exclude_archived": "true"})
        for c in r2.get("channels", []) or []:
            if c.get("name") == name:
                return c["id"]
    print(f"[notify_bosgame] could not resolve/create channel '{name}': "
          f"{r.get('error')}", file=sys.stderr)
    return None


def _post(channel: str, token: str, text: str, blocks=None, thread_ts=None) -> str | None:
    payload = {"channel": channel, "text": text, "unfurl_links": False}
    if blocks is not None:
        payload["blocks"] = blocks
    if thread_ts:
        payload["thread_ts"] = thread_ts
    body = _api_post("chat.postMessage", token, payload)
    if not body.get("ok"):
        print(f"[notify_bosgame] chat.postMessage error: {body.get('error')}", file=sys.stderr)
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
            out.append((spec.get("title") or "test", bool(spec.get("ok", False))))
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
    ap.add_argument("--channel", default="")
    ap.add_argument("--channel-name", default="nightly-bosgame-run")
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

    channel = resolve_channel(token, args.channel, args.channel_name)
    if not channel:
        print("[notify_bosgame] no channel resolved — no-op.")
        return 0

    now = _now(args.tz)
    suite = args.suite

    if args.event == "down":
        _post(channel, token,
              f":red_circle: *{suite}* — bosgame unavailable at {now} ({args.tz}). "
              f"Tests not started; will retry on the next hourly check.")
        return 0

    if args.event == "skip":
        _post(channel, token,
              f":fast_forward: *{suite}* — already completed for today at {now}. Skipping.")
        return 0

    if args.event == "up":
        _post(channel, token,
              f":large_green_circle: *{suite}* — bosgame available at {now} ({args.tz}). "
              f"Warming gpt-oss and starting the suite…")
        return 0

    # event == result
    if args.format == "none":
        msg = (f":checkered_flag: *{suite}* — evaluation finished at {now}. "
               f"See the suite's own Slack channel for per-metric detail.")
        _post(channel, token, msg, blocks=_button_blocks(msg, args.run_url))
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
    ts = _post(channel, token, headline, blocks=_button_blocks(headline, args.run_url))
    if ts and cases:
        for chunk in _detail_replies(cases):
            _post(channel, token, chunk, thread_ts=ts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
