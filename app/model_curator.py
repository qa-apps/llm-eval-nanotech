#!/usr/bin/env python3
"""
model_curator.py — periodic free-tier model-pool janitor for NanoTech AI chat.

Runs out-of-process (systemd timer, ~every 60h). For every provider that has an
API key in the environment it:
  1. DISCOVER  — lists the provider's currently-offered free models,
  2. PROBE     — sends a tiny completion to each candidate to see if it answers,
  3. CLASSIFY  — alive / throttled / dead / key_error / paid, reusing the same
                 signal mapping the runtime orchestration uses,
  4. PERSIST   — writes a curated registry + quarantine + audit report to DATA_DIR.

The web app only READS models_registry.json / models_quarantine.json, so the heavy
sweep never runs inside the request path. Secrets are read from env, never logged.

Includes the local BosGame Ollama box as provider "local" (no key, no quota) — the
one pool member that never 429/401/402s, gated by a fast reachability check.

Usage:
  model_curator.py                 # full sweep, writes JSON files
  model_curator.py --dry-run       # sweep + print summary, write nothing
  model_curator.py --provider groq # sweep a single provider
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(os.environ.get("NANOTECH_MODEL_DATA_DIR", "/var/lib/nanotech-chat"))
REGISTRY_FILE = DATA_DIR / "models_registry.json"
QUARANTINE_FILE = DATA_DIR / "models_quarantine.json"
AUDIT_FILE = DATA_DIR / "models_audit.json"

PROBE_PROMPT = "Reply with exactly: ok"
PROBE_TIMEOUT = int(os.environ.get("CURATOR_PROBE_TIMEOUT", "20"))
LIST_TIMEOUT = int(os.environ.get("CURATOR_LIST_TIMEOUT", "20"))
LOCAL_TIMEOUT = int(os.environ.get("CURATOR_LOCAL_TIMEOUT", "75"))  # 120b cold-load is slow
INTER_PROBE_DELAY = float(os.environ.get("CURATOR_PROBE_DELAY", "0.35"))
MAX_MODELS_PER_PROVIDER = int(os.environ.get("CURATOR_MAX_PER_PROVIDER", "60"))
# A soft-dead model must fail this many consecutive sweeps before it is dropped;
# a hard-dead signal (404 / model_not_found / decommissioned) drops immediately.
SOFT_DEAD_STRIKES = 2
QUARANTINE_RETEST_DAYS = 14

OPENROUTER_REFERER = "https://nanotech.icu"
OPENROUTER_TITLE = "NanoTech Free Curator"
HTTP_USER_AGENT = "NanoTech-Free-Model-Curator/1.0"

# Local BosGame Ollama — reached on the box via a tunnel/tailscale on 127.0.0.1:11434.
LOCAL_OLLAMA_BASE = os.environ.get("BOSGAME_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")

# Non-chat models to keep out of the pool regardless of provider: safety/guard
# classifiers (they answer with a safety verdict, not a reply), and embed/rerank/
# speech/vision-only endpoints. Applied to every provider's discovered ids.
_EXCLUDE_MARKERS = ("guard", "shield", "moderat", "safety", "nemoguard", "wildguard",
                    "calibration", "embed", "rerank", "reranker", "whisper", "-tts",
                    "-ocr", "-asr", "parakeet", "canary")


def _is_chat_model(model_id: str) -> bool:
    low = model_id.lower()
    return not any(k in low for k in _EXCLUDE_MARKERS)


def _now() -> float:
    return time.time()


def _iso(ts: float | None = None) -> str:
    return datetime.fromtimestamp(ts or _now(), timezone.utc).isoformat(timespec="seconds")


def _env(*names: str) -> str:
    for n in names:
        v = (os.environ.get(n) or "").strip()
        if v:
            return v
    return ""


# ── HTTP ─────────────────────────────────────────────────────────────────────

def _request(url: str, headers: dict | None = None, data: bytes | None = None,
             timeout: int = 20, method: str | None = None) -> tuple[int, str]:
    """Return (status, body). status=0 on connection/timeout failure (body=reason)."""
    request_headers = {
        "Accept": "application/json",
        "User-Agent": HTTP_USER_AGENT,
    }
    request_headers.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=request_headers,
                                 method=method or ("POST" if data else "GET"))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", "replace")
        except Exception:
            body = ""
        return e.code, body
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        return 0, f"conn_error: {e}"
    except Exception as e:  # noqa: BLE001 - diagnostics tool
        return 0, f"error: {type(e).__name__}: {e}"


# ── Provider config ──────────────────────────────────────────────────────────
# Every provider is OpenAI-compatible for chat. `discover` returns candidate model
# ids; `probe` reuses the shared chat call. Seeds are fallbacks used when a listing
# endpoint is unavailable — every seed still has to pass the probe to enter the pool.

def _bearer(key: str, extra: dict | None = None) -> dict:
    h = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if extra:
        h.update(extra)
    return h


def _openai_list_ids(url: str, headers: dict) -> list[str]:
    status, body = _request(url, headers, timeout=LIST_TIMEOUT)
    if status != 200:
        return []
    try:
        data = json.loads(body)
    except ValueError:
        return []
    items = data.get("data", data if isinstance(data, list) else [])
    ids = []
    for m in items:
        mid = m.get("id") or m.get("name") if isinstance(m, dict) else None
        if mid:
            ids.append(mid)
    return ids


def _discover_openrouter(key, account):
    status, body = _request("https://openrouter.ai/api/v1/models", timeout=LIST_TIMEOUT)
    if status != 200:
        return []
    try:
        data = json.loads(body).get("data", [])
    except ValueError:
        return []
    out = []
    for m in data:
        mid = m.get("id", "")
        pricing = m.get("pricing", {})
        if not mid.endswith(":free"):
            continue
        if pricing.get("prompt") not in ("0", 0) or pricing.get("completion") not in ("0", 0):
            continue
        low = mid.lower()
        if any(k in low for k in ("guard", "shield", "moderat", "safety", "test", "experimental")):
            continue
        out.append(mid)
    return out


def _discover_cloudflare(key, account):
    if not account:
        return []
    url = (f"https://api.cloudflare.com/client/v4/accounts/{account}"
           f"/ai/models/search?task=Text+Generation&per_page=100")
    status, body = _request(url, _bearer(key), timeout=LIST_TIMEOUT)
    if status != 200:
        return []
    try:
        result = json.loads(body).get("result", [])
    except ValueError:
        return []
    return [m.get("name") for m in result if m.get("name")]


def _discover_local(key, account):
    """List models on the BosGame Ollama box (no key). Empty list == box offline."""
    status, body = _request(f"{LOCAL_OLLAMA_BASE}/api/tags", timeout=8)
    if status != 200:
        return []
    try:
        models = json.loads(body).get("models", [])
    except ValueError:
        return []
    chat_models = [m["name"] for m in models if m.get("name") and "embed" not in m["name"].lower()]
    # Keep this public reserve focused on GPT-OSS while it is installed; the
    # other Ollama models remain available for BosGame's separate workloads.
    gpt_oss = [name for name in chat_models if "gpt-oss" in name.lower()]
    return gpt_oss or chat_models


PROVIDERS = {
    "openrouter": {
        "keys": ("OPENROUTER_API_KEY",),
        "chat_url": "https://openrouter.ai/api/v1/chat/completions",
        "headers": lambda key: _bearer(key, {"HTTP-Referer": OPENROUTER_REFERER, "X-Title": OPENROUTER_TITLE}),
        "discover": _discover_openrouter,
        "seeds": ("meta-llama/llama-3.3-70b-instruct:free", "google/gemma-3-27b-it:free",
                  "deepseek/deepseek-r1-0528:free", "qwen/qwen3-coder:free"),
    },
    "groq": {
        "keys": ("GROQ_API_KEY",),
        "chat_url": "https://api.groq.com/openai/v1/chat/completions",
        "headers": lambda key: _bearer(key),
        "discover": lambda k, a: _openai_list_ids("https://api.groq.com/openai/v1/models", _bearer(k)),
        # gpt-oss first: Groq retired the free llama ids (404); gpt-oss is the live free route.
        "seeds": ("openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3-32b"),
    },
    "mistral": {
        "keys": ("MISTRAL_API_KEY",),
        "chat_url": "https://api.mistral.ai/v1/chat/completions",
        "headers": lambda key: _bearer(key),
        "discover": lambda k, a: _openai_list_ids("https://api.mistral.ai/v1/models", _bearer(k)),
        "seeds": ("mistral-small-latest", "codestral-latest"),
    },
    "nvidia": {
        "keys": ("NVIDIA_API_KEY",),
        "chat_url": "https://integrate.api.nvidia.com/v1/chat/completions",
        "headers": lambda key: _bearer(key),
        "discover": lambda k, a: _openai_list_ids("https://integrate.api.nvidia.com/v1/models", _bearer(k)),
        "seeds": ("meta/llama-3.3-70b-instruct", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"),
    },
    "cohere": {
        "keys": ("COHERE_API_KEY",),
        "chat_url": "https://api.cohere.ai/compatibility/v1/chat/completions",
        "headers": lambda key: _bearer(key),
        "discover": lambda k, a: _openai_list_ids("https://api.cohere.ai/compatibility/v1/models", _bearer(k)),
        "seeds": ("command-r7b-12-2024", "command-r-plus-08-2024"),
    },
    "cloudflare": {
        "keys": ("CLOUDFLARE_API_TOKEN",),
        "account_env": "CLOUDFLARE_ACCOUNT_ID",
        "chat_url": None,  # filled per-run once account id is known
        "headers": lambda key: _bearer(key),
        "discover": _discover_cloudflare,
        "seeds": ("@cf/meta/llama-3.1-8b-instruct", "@cf/qwen/qwen1.5-14b-chat-awq"),
    },
    "huggingface": {
        "keys": ("HF_INFERENCE_TOKEN", "HF_TOKEN", "HUGGINGFACE_API_KEY"),
        "chat_url": "https://router.huggingface.co/v1/chat/completions",
        "headers": lambda key: _bearer(key),
        "discover": lambda k, a: _openai_list_ids("https://router.huggingface.co/v1/models", _bearer(k)),
        "seeds": (),
    },
    "local": {
        "keys": (),  # no key needed
        "chat_url": f"{LOCAL_OLLAMA_BASE}/v1/chat/completions",
        "headers": lambda key: {"Content-Type": "application/json"},
        "discover": _discover_local,
        "seeds": (),
        "timeout": LOCAL_TIMEOUT,
    },
}

# ── Classification ───────────────────────────────────────────────────────────

_DEAD_MARKERS = ("model_not_found", "no endpoints", "not found", "does not exist",
                 "unknown model", "invalid model", "decommission", "deprecat",
                 "no longer", "unsupported model")


def classify(status: int, body: str) -> str:
    low = (body or "").lower()
    if status == 200:
        return "alive"
    if status == 429:
        return "throttled"          # alive, just rate-limited
    if status in (401, 403):
        return "key_error"          # provider-level auth problem
    if status == 402 or any(s in low for s in ("insufficient credit", "payment required", "billing", "quota exceeded")):
        return "paid"               # not usable on the free tier
    if status == 404 or any(s in low for s in _DEAD_MARKERS):
        return "dead"               # discontinued / gone
    if status == 400 and any(s in low for s in _DEAD_MARKERS):
        return "dead"
    if status == 0 or status >= 500:
        return "error"              # transient (timeout / provider 5xx)
    return "error"


def _looks_like_guard(body: str) -> bool:
    """A safety/guard model answers with a verdict object, not a chat reply."""
    low = (body or "").lower()
    return ('"user safety"' in low or '"response safety"' in low
            or '"safety_categories"' in low or '"is_safe"' in low)


def _has_text(body: str) -> bool:
    try:
        data = json.loads(body)
    except ValueError:
        return False
    try:
        content = data["choices"][0]["message"]["content"]
        return bool(content and str(content).strip())
    except (KeyError, IndexError, TypeError):
        return False


def probe(provider: str, cfg: dict, model_id: str) -> tuple[str, int]:
    key = _env(*cfg["keys"]) if cfg["keys"] else ""
    chat_url = cfg["chat_url"]
    probe_tokens = 256 if provider == "local" and "gpt-oss" in model_id.lower() else 8
    payload = json.dumps({
        "model": model_id,
        "messages": [{"role": "user", "content": PROBE_PROMPT}],
        "max_tokens": probe_tokens,
        "stream": False,
    }).encode()
    status, body = _request(chat_url, cfg["headers"](key), payload,
                            timeout=cfg.get("timeout", PROBE_TIMEOUT))
    verdict = classify(status, body)
    if verdict == "alive":
        if not _has_text(body):
            verdict = "error"       # 200 but empty payload
        elif _looks_like_guard(body):
            verdict = "dead"        # safety classifier, not a chat model
    return verdict, status


# ── Capability / tier tagging (mirrors chat_server heuristics) ────────────────

def tag_model(provider: str, model_id: str) -> dict:
    low = model_id.lower()
    m = {"id": model_id, "provider": provider, "free": True,
         "label": model_id.split("/")[-1]}
    if any(k in low for k in ("70b", "72b", "120b", "405b", "480b", "r1", "gpt-oss")):
        m["tier"] = "H"
    elif any(k in low for k in ("27b", "32b", "34b", "24b", "14b")):
        m["tier"] = "M"
    else:
        m["tier"] = "S"
    if "vision" in low or "-vl" in low or "vl-" in low:
        m["vision"] = True
    if "coder" in low or "code" in low or "codestral" in low:
        m["coding"] = True
    if any(k in low for k in ("r1", "reason", "think", "nemotron", "qwq", "magistral")):
        m["reasoning"] = True
    m["created"] = int(_now())
    return m


# ── Persistence ──────────────────────────────────────────────────────────────

def _load_json(path: Path, default):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def _write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path == REGISTRY_FILE and path.exists():
        history_dir = path.parent / "registry-history"
        history_dir.mkdir(parents=True, exist_ok=True)
        snapshot = history_dir / f"models_registry.{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
        shutil.copy2(path, snapshot)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False))
    tmp.replace(path)
    try:
        os.chmod(path, 0o640)
    except OSError:
        pass


# ── Sweep ────────────────────────────────────────────────────────────────────

def sweep(only_provider: str | None = None, dry_run: bool = False) -> dict:
    started = _now()
    prev_registry = {m["id"]: m for m in _load_json(REGISTRY_FILE, {}).get("models", [])}
    quarantine = _load_json(QUARANTINE_FILE, {})

    registry: dict[str, dict] = {}
    audit = {"run_at": _iso(started), "providers": {}, "added": [], "removed": [], "flagged_providers": []}

    for provider, cfg in PROVIDERS.items():
        if only_provider and provider != only_provider:
            continue
        key = _env(*cfg["keys"]) if cfg["keys"] else "local"
        pinfo = {"key": "present" if key else "MISSING", "listed": 0,
                 "alive": 0, "throttled": 0, "dead": [], "paid": 0, "restricted": 0, "status": "ok"}

        if not key:
            pinfo["status"] = "no_key"
            audit["providers"][provider] = pinfo
            continue

        # cloudflare needs the account id baked into the chat url
        if provider == "cloudflare":
            acct = _env(cfg.get("account_env", ""))
            if not acct:
                pinfo["status"], pinfo["key"] = "no_account", "MISSING_ACCOUNT"
                audit["providers"][provider] = pinfo
                continue
            cfg = dict(cfg, chat_url=f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/v1/chat/completions")

        account = _env(cfg["account_env"]) if cfg.get("account_env") else ""
        discovered = [m for m in cfg["discover"](key, account) if _is_chat_model(m)]
        pinfo["listed"] = len(discovered)
        # A successful listing proves the key is valid, so a later per-model 401/403
        # is a model restriction (e.g. OpenRouter data-policy), not a dead key.
        key_proven = len(discovered) > 0

        if provider == "local" and not discovered:
            pinfo["status"] = "offline"        # box asleep — skip, don't quarantine
            audit["providers"][provider] = pinfo
            continue

        now_iso = _iso(started)
        cand = list(dict.fromkeys(list(discovered) + list(cfg["seeds"])))
        # skip models still serving a quarantine cooldown (speeds up later sweeps)
        cand = [m for m in cand if (quarantine.get(m, {}).get("retest_after") or now_iso) <= now_iso]
        candidates = cand[:MAX_MODELS_PER_PROVIDER]

        provider_key_dead = False
        for i, mid in enumerate(candidates):
            verdict, status = probe(provider, cfg, mid)

            if verdict == "key_error":
                if not key_proven:
                    provider_key_dead = True   # listing + probe both 401 ⇒ key really dead
                    pinfo["status"] = "key_error"
                    break
                pinfo["restricted"] += 1       # single model gated; key itself is fine
                quarantine[mid] = {"provider": provider, "reason": f"restricted_http_{status}",
                                   "first_seen": quarantine.get(mid, {}).get("first_seen", now_iso),
                                   "last_checked": now_iso, "strikes": SOFT_DEAD_STRIKES,
                                   "retest_after": _iso(started + QUARANTINE_RETEST_DAYS * 86400)}
                time.sleep(INTER_PROBE_DELAY)
                continue

            if verdict in ("alive", "throttled"):
                entry = dict(prev_registry.get(mid) or {})
                entry.update(tag_model(provider, mid))
                entry["free"] = True
                entry["last_verified"] = _iso()
                entry["last_status"] = verdict
                registry[mid] = entry
                quarantine.pop(mid, None)
                pinfo[verdict] += 1
            elif verdict == "paid":
                pinfo["paid"] += 1
                quarantine.pop(mid, None)      # not free, but not "dead"; just excluded
            elif verdict == "dead":
                pinfo["dead"].append(mid)
                q = quarantine.get(mid, {"provider": provider, "first_seen": _iso(), "strikes": 0})
                q.update({"reason": f"dead_http_{status}", "last_checked": _iso(),
                          "strikes": q.get("strikes", 0) + SOFT_DEAD_STRIKES,  # hard dead ⇒ drop now
                          "retest_after": _iso(started + QUARANTINE_RETEST_DAYS * 86400)})
                quarantine[mid] = q
            else:  # transient error
                q = quarantine.get(mid, {"provider": provider, "first_seen": _iso(), "strikes": 0})
                q.update({"reason": f"error_http_{status}", "last_checked": _iso(),
                          "strikes": q.get("strikes", 0) + 1,
                          "retest_after": _iso(started + QUARANTINE_RETEST_DAYS * 86400)})
                quarantine[mid] = q

            time.sleep(INTER_PROBE_DELAY)

        # provider whose key just died: keep its previously-good models (unverified) so
        # a transient outage never nukes the pool; flag it loudly for a key refresh.
        if provider_key_dead:
            audit["flagged_providers"].append(provider)
            for mid, m in prev_registry.items():
                if m.get("provider") == provider:
                    m["last_status"] = "unverified_key_error"
                    registry.setdefault(mid, m)

        audit["providers"][provider] = pinfo

    # only drop soft-dead once they cross the strike threshold; hard-dead already there
    live_quarantine = {mid: q for mid, q in quarantine.items() if q.get("strikes", 0) >= SOFT_DEAD_STRIKES}

    new_ids = set(registry)
    old_ids = set(prev_registry)
    audit["added"] = sorted(new_ids - old_ids)
    audit["removed"] = sorted(old_ids - new_ids)
    audit["registry_size"] = len(registry)
    audit["quarantine_size"] = len(live_quarantine)
    audit["duration_s"] = round(_now() - started, 1)

    if not dry_run and not only_provider:
        registry_payload = {"updated_at": _iso(), "models": list(registry.values())}
        _write_json(REGISTRY_FILE, registry_payload)
        _write_json(QUARANTINE_FILE, live_quarantine)
        _write_json(AUDIT_FILE, audit)

    return audit


def _print_summary(audit: dict) -> None:
    print(f"\nmodel-curator sweep @ {audit['run_at']}  ({audit['duration_s']}s)")
    print(f"  registry: {audit.get('registry_size', 0)} live   quarantine: {audit.get('quarantine_size', 0)}")
    for name, p in audit["providers"].items():
        tail = f" dead={len(p['dead'])}" if p["dead"] else ""
        print(f"  {name:12} key={p['key']:16} status={p['status']:10} "
              f"listed={p['listed']:3} alive={p['alive']:2} throttled={p['throttled']:2} "
              f"restricted={p.get('restricted', 0):2} paid={p['paid']}{tail}")
    if audit["flagged_providers"]:
        print(f"  ⚠ providers needing a key refresh: {', '.join(audit['flagged_providers'])}")
    if audit["removed"]:
        print(f"  removed: {', '.join(audit['removed'][:12])}{' …' if len(audit['removed']) > 12 else ''}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Free-tier model pool curator")
    ap.add_argument("--dry-run", action="store_true", help="probe but write nothing")
    ap.add_argument("--provider", help="sweep a single provider")
    args = ap.parse_args()
    audit = sweep(only_provider=args.provider, dry_run=args.dry_run or bool(args.provider))
    _print_summary(audit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
