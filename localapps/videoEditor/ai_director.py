"""
AI Director — calls nanotech.icu's free open-source model orchestration
(Qwen / Llama / Mistral) to convert a user's natural-language goal into
concrete video-editing parameters. No external API key required.
"""

import json
import re
import httpx
from typing import Optional

_NANOTECH_BASE = "https://nanotech.icu"
_AGENTS = ["auto", "general", "research"]

_PROMPT = """\
You are a professional video editor AI. The user wants to create a video with this goal:

"{goal}"

Reply with ONLY a single JSON object (no markdown fences, no explanation outside the JSON):
{{
  "mood": "<comedy|drama|joy|calm|energetic|romantic|documentary|other>",
  "threshold": <float 0.10–0.60>,
  "max_segments_v1": <int 2–12>,
  "max_segments_v2": <int 2–8>,
  "strategy": "<rapid_interleave|spaced_interleave|bookend|sandwich>",
  "brief": "<one sentence, max 90 chars, describing the editing approach>"
}}

Parameter guide:
- comedy / energetic  → threshold 0.15–0.25, many short segments, rapid_interleave
- drama / romantic    → threshold 0.35–0.50, few long segments, spaced_interleave
- joy / upbeat        → threshold 0.20–0.30, medium segments, rapid_interleave
- calm / documentary  → threshold 0.40–0.55, very few segments, bookend
- sandwich: main clip bookends a cluster of inserts (M … I I I … M)
- bookend:  insert clip wraps around the main sequence (I M M M I)
"""

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)

_DEFAULTS = {
    "mood": "other",
    "threshold": 0.30,
    "max_segments_v1": 6,
    "max_segments_v2": 4,
    "strategy": "rapid_interleave",
    "brief": "Balanced interleave with standard scene detection.",
    "model": "fallback",
}


def get_ai_guidance(user_goal: str) -> dict:
    """
    Ask nanotech.icu's orchestrated models to interpret the user's editing goal.
    Returns a dict with mood, threshold, segment counts, strategy, and a brief.
    Falls back to sensible defaults if the API is unavailable.
    """
    prompt = _PROMPT.format(goal=user_goal[:400])

    for agent in _AGENTS:
        try:
            with httpx.Client(base_url=_NANOTECH_BASE, timeout=25.0) as client:
                resp = client.post(
                    "/api/chat",
                    json={"message": prompt, "agent": agent, "attachments": []},
                )
                if resp.status_code != 200:
                    continue

                data = resp.json()
                reply = _THINK_RE.sub("", data.get("reply", "")).strip()

                m = re.search(r"\{.*\}", reply, re.DOTALL)
                if not m:
                    continue

                parsed = json.loads(m.group())
                parsed["model"] = data.get("model", agent)

                # Clamp values to safe ranges
                parsed["threshold"] = max(0.10, min(0.60, float(parsed.get("threshold", 0.30))))
                parsed["max_segments_v1"] = max(2, min(12, int(parsed.get("max_segments_v1", 6))))
                parsed["max_segments_v2"] = max(2, min(8, int(parsed.get("max_segments_v2", 4))))
                if parsed.get("strategy") not in {
                    "rapid_interleave", "spaced_interleave", "bookend", "sandwich"
                }:
                    parsed["strategy"] = "rapid_interleave"

                return parsed

        except Exception:
            continue

    return dict(_DEFAULTS)
