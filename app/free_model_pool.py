"""Strict free-tier LLM orchestration for the NanoTech AI Assistant.

The registry is produced by the model curator and contains only routes that
answered a probe without a billing requirement. Runtime checks still fail
closed: OpenRouter ids must end in ``:free`` and direct-provider entries must
carry ``free: true``. The local GPT-OSS model is always kept as the final
quota-independent fallback.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
PROVIDER_API_URL = {
    "groq": "https://api.groq.com/openai/v1/chat/completions",
    "openrouter": OPENROUTER_API_URL,
    "huggingface": "https://router.huggingface.co/v1/chat/completions",
    "mistral": "https://api.mistral.ai/v1/chat/completions",
    "nvidia": "https://integrate.api.nvidia.com/v1/chat/completions",
    "cohere": "https://api.cohere.ai/compatibility/v1/chat/completions",
}
PROVIDER_KEY_ENV = {
    "groq": ("GROQ_API_KEY",),
    "openrouter": ("OPENROUTER_API_KEY",),
    "huggingface": ("HF_INFERENCE_TOKEN", "HF_TOKEN", "HUGGINGFACE_API_KEY"),
    "mistral": ("MISTRAL_API_KEY",),
    "nvidia": ("NVIDIA_API_KEY",),
    "cohere": ("COHERE_API_KEY",),
    "cloudflare": ("CLOUDFLARE_API_TOKEN",),
}
FREE_DIRECT_PROVIDERS = {
    "groq",
    "huggingface",
    "mistral",
    "nvidia",
    "cohere",
    "cloudflare",
    "local",
}
PROVIDER_ORDER = (
    "groq",
    "cohere",
    "cloudflare",
    "mistral",
    "huggingface",
    "nvidia",
    "openrouter",
)

LOCAL_MODEL = {
    "id": "gpt-oss:120b",
    "label": "Local GPT-OSS 120B",
    "provider": "local",
    "free": True,
    "tier": "H",
    "reasoning": True,
}
SAFE_SEED_MODELS = [
    {
        "id": "openai/gpt-oss-20b",
        "label": "GPT-OSS 20B",
        "provider": "groq",
        "free": True,
        "tier": "M",
    },
    {
        "id": "openai/gpt-oss-120b",
        "label": "GPT-OSS 120B",
        "provider": "groq",
        "free": True,
        "tier": "H",
        "reasoning": True,
    },
    {
        "id": "meta-llama/llama-3.3-70b-instruct:free",
        "label": "Llama 3.3 70B (free)",
        "provider": "openrouter",
        "free": True,
        "tier": "H",
    },
    LOCAL_MODEL,
]

_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)
_THINK_UNCLOSED_RE = re.compile(r"<think>.*", re.IGNORECASE | re.DOTALL)


def _env_truthy(name: str, default: str = "1") -> bool:
    return (os.environ.get(name, default) or "").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def is_free_only_model(model: dict | None) -> bool:
    """Return whether a model is allowed to execute in free-only mode."""
    if not model or not _env_truthy("FREE_ONLY_MODE"):
        return False
    provider = str(model.get("provider", ""))
    model_id = str(model.get("id", ""))
    if provider == "openrouter":
        return bool(model.get("free")) and model_id.endswith(":free")
    return bool(model.get("free")) and provider in FREE_DIRECT_PROVIDERS


def _registry_path() -> Path:
    configured = (os.environ.get("NANOTECH_MODEL_REGISTRY") or "").strip()
    return Path(configured) if configured else Path(__file__).with_name("models_registry.json")


def load_models(path: Path | None = None) -> list[dict]:
    source = path or _registry_path()
    models: list[dict] = []
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
        candidates = payload.get("models", []) if isinstance(payload, dict) else []
        models = [dict(item) for item in candidates if isinstance(item, dict) and is_free_only_model(item)]
    except (OSError, ValueError):
        models = [dict(item) for item in SAFE_SEED_MODELS if is_free_only_model(item)]

    seen: set[tuple[str, str]] = set()
    clean: list[dict] = []
    for model in models:
        provider = str(model.get("provider", ""))
        model_id = str(model.get("id", ""))
        key = (provider, model_id)
        if not model_id or key in seen or not is_free_only_model(model):
            continue
        seen.add(key)
        model.setdefault("label", model_id.split("/")[-1])
        model.setdefault("tier", "M")
        clean.append(model)

    local_key = (LOCAL_MODEL["provider"], LOCAL_MODEL["id"])
    if local_key not in seen:
        clean.append(dict(LOCAL_MODEL))
    return clean


def _strip_reasoning(text: str) -> str:
    stripped = _THINK_BLOCK_RE.sub("", text or "")
    return _THINK_UNCLOSED_RE.sub("", stripped).strip()


def _uses_visible_reasoning(model: dict) -> bool:
    model_id = str(model.get("id", "")).lower()
    return bool(model.get("reasoning")) or any(
        marker in model_id
        for marker in ("qwq", "reasoning", "deepseek-r1", "magistral", "nemotron")
    )


def _extract_reply(data: dict) -> str:
    try:
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    except (AttributeError, IndexError, TypeError):
        return ""
    if isinstance(content, str):
        return _strip_reasoning(content)
    if isinstance(content, list):
        chunks = [
            item.get("text", "").strip()
            for item in content
            if isinstance(item, dict) and isinstance(item.get("text"), str) and item.get("text", "").strip()
        ]
        return _strip_reasoning("\n".join(chunks))
    return ""


def _parse_retry_seconds(value: str | None) -> int | None:
    if not value:
        return None
    raw = str(value).strip()
    try:
        return max(0, int(float(raw)))
    except ValueError:
        pass
    match = re.fullmatch(r"(?:(\d+(?:\.\d+)?)h)?(?:(\d+(?:\.\d+)?)m)?(?:(\d+(?:\.\d+)?)s)?", raw)
    if match and any(match.groups()):
        hours, minutes, seconds = (float(item or 0) for item in match.groups())
        return int(hours * 3600 + minutes * 60 + seconds)
    try:
        parsed = parsedate_to_datetime(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return max(0, int((parsed - datetime.now(timezone.utc)).total_seconds()))
    except Exception:
        return None


def _seconds_until_next_utc_day() -> int:
    now = datetime.now(timezone.utc)
    tomorrow = datetime.combine((now + timedelta(days=1)).date(), datetime.min.time(), timezone.utc)
    return max(60, int((tomorrow - now).total_seconds()))


class FreeModelPool:
    """Thread-safe free-only router with provider/model cooldowns."""

    def __init__(self, models: list[dict] | None = None):
        self.models = [dict(model) for model in (models or load_models()) if is_free_only_model(model)]
        if not any(model.get("provider") == "local" for model in self.models):
            self.models.append(dict(LOCAL_MODEL))
        self._lock = threading.Lock()
        self._health: dict[str, dict] = {}
        self._cursor: dict[str, int] = {}

    def provider_api_key(self, provider: str) -> str:
        for name in PROVIDER_KEY_ENV.get(provider, ()):
            value = (os.environ.get(name) or "").strip()
            if value:
                return value
        return ""

    def provider_available(self, provider: str) -> bool:
        if provider == "local":
            return True
        if provider == "cloudflare" and not (os.environ.get("CLOUDFLARE_ACCOUNT_ID") or "").strip():
            return False
        return bool(self.provider_api_key(provider))

    @staticmethod
    def _provider_key(provider: str) -> str:
        return f"provider:{provider}"

    @staticmethod
    def _model_key(model: dict) -> str:
        return f"model:{model.get('provider')}:{model.get('id')}"

    def is_available(self, model: dict) -> bool:
        if not is_free_only_model(model) or not self.provider_available(str(model.get("provider", ""))):
            return False
        now = time.time()
        keys = [self._provider_key(str(model.get("provider"))), self._model_key(model)]
        with self._lock:
            for key in keys:
                item = self._health.get(key)
                if item and item.get("until", 0) > now:
                    return False
                if item and item.get("until", 0) <= now:
                    self._health.pop(key, None)
        return True

    def _rotate(self, key: str, items: list[dict]) -> list[dict]:
        if len(items) < 2:
            return items
        with self._lock:
            start = self._cursor.get(key, 0) % len(items)
            self._cursor[key] = start + 1
        return items[start:] + items[:start]

    def pick(self, candidates: list[dict], key: str = "default") -> dict | None:
        available = [model for model in candidates if self.is_available(model)]
        cloud = [model for model in available if model.get("provider") != "local"]
        if cloud:
            available = cloud
        non_reasoning = [model for model in available if not _uses_visible_reasoning(model)]
        if non_reasoning:
            available = non_reasoning
        rotated = self._rotate(key, available)
        return rotated[0] if rotated else None

    def fallback_chain(self, current: dict, tier: str, require_vision: bool = False) -> list[dict]:
        tier_order = ("S", "M", "H") if tier == "S" else ("M", "H", "S")
        pool = [
            model
            for wanted in tier_order
            for model in self.models
            if model.get("tier") == wanted
            and (not require_vision or model.get("vision"))
            and self.is_available(model)
            and (model.get("provider"), model.get("id"))
            != (current.get("provider"), current.get("id"))
        ]

        local = [model for model in pool if model.get("provider") == "local"]
        cloud = [model for model in pool if model.get("provider") != "local"]

        def provider_chain(models: list[dict], cursor_key: str) -> list[dict]:
            buckets: dict[str, list[dict]] = {}
            order = [
                provider
                for provider in PROVIDER_ORDER
                if any(model.get("provider") == provider for model in models)
            ]
            current_provider = str(current.get("provider", ""))
            if current_provider in order:
                order.remove(current_provider)
                order.append(current_provider)
            for model in models:
                buckets.setdefault(str(model.get("provider")), []).append(model)
            rotated = self._rotate(cursor_key, [{"provider": provider} for provider in order])
            providers = [item["provider"] for item in rotated]
            result: list[dict] = []
            while any(buckets.values()):
                for provider in providers:
                    provider_models = buckets.get(provider, [])
                    if provider_models:
                        result.append(provider_models.pop(0))
            return result

        ordinary = [model for model in cloud if not _uses_visible_reasoning(model)]
        reasoning = [model for model in cloud if _uses_visible_reasoning(model)]
        return (
            provider_chain(ordinary, "fallback-providers")
            + provider_chain(reasoning, "fallback-reasoning-providers")
            + local
        )

    def _cooldown(self, model: dict, error: dict | str | None) -> tuple[str, int, str]:
        provider = str(model.get("provider", ""))
        status = error.get("status") if isinstance(error, dict) else None
        body = (error.get("body", "") if isinstance(error, dict) else str(error or "")).lower()
        headers = error.get("headers", {}) if isinstance(error, dict) else {}
        lower_headers = {str(key).lower(): str(value) for key, value in headers.items()}
        retry = _parse_retry_seconds(lower_headers.get("retry-after"))

        if status == 429:
            if provider == "openrouter" and any(marker in body for marker in ("per day", "daily", "free-models-per-day")):
                return self._provider_key(provider), _seconds_until_next_utc_day(), "daily_free_limit"
            return self._provider_key(provider), min(max(retry or 120, 30), 3600), "rate_limit"
        if status in (401, 402, 403):
            return self._provider_key(provider), 3600, "free_access_unavailable"
        if status == 404 or "model not found" in body or "no endpoints" in body:
            return self._model_key(model), 24 * 3600, "model_unavailable"
        if status and status >= 500:
            return self._model_key(model), 180, "provider_error"
        return self._model_key(model), 90, "transient_error"

    def record_failure(self, model: dict, error: dict | str | None) -> None:
        if not error:
            return
        key, seconds, reason = self._cooldown(model, error)
        with self._lock:
            self._health[key] = {
                "provider": model.get("provider"),
                "model": model.get("id"),
                "reason": reason,
                "until": time.time() + seconds,
            }

    def call_model(
        self,
        model: dict,
        system_prompt: str,
        user_content,
        max_tokens: int = 512,
        history: list[dict] | None = None,
    ) -> tuple[str | None, dict | None]:
        provider = str(model.get("provider", ""))
        if not is_free_only_model(model):
            return None, {"code": "paid_model_disabled", "provider": provider, "model": model.get("id")}

        api_key = self.provider_api_key(provider)
        if provider != "local" and not api_key:
            return None, {"code": "missing_key", "provider": provider, "model": model.get("id")}

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history or [])
        messages.append({"role": "user", "content": user_content})
        payload = {
            "model": model["id"],
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": max_tokens,
            "stream": False,
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "NanoTech-Free-Orchestrator/1.0",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        if provider == "openrouter":
            headers["HTTP-Referer"] = os.environ.get("OPENROUTER_HTTP_REFERER", "https://nanotech.icu")
            headers["X-Title"] = os.environ.get("OPENROUTER_X_TITLE", "NanoTech AI Assistant")

        if provider == "local":
            base = os.environ.get("BOSGAME_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
            url = f"{base}/v1/chat/completions"
        elif provider == "cloudflare":
            account = (os.environ.get("CLOUDFLARE_ACCOUNT_ID") or "").strip()
            url = f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/v1/chat/completions"
        else:
            url = PROVIDER_API_URL.get(provider, "")
        if not url:
            return None, {"code": "provider_disabled", "provider": provider, "model": model.get("id")}

        timeout = float(os.environ.get("LOCAL_LLM_TIMEOUT", "90")) if provider == "local" else 25.0
        request = Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        try:
            with urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8", "replace")
            if raw.lstrip().startswith("<"):
                return None, {"code": "html_response", "provider": provider, "model": model.get("id")}
            reply = _extract_reply(json.loads(raw))
            if not reply:
                return None, {
                    "code": "empty_response",
                    "provider": provider,
                    "model": model.get("id"),
                    "body": raw[:300],
                }
            return reply, None
        except HTTPError as error:
            try:
                body = error.read().decode("utf-8", "replace")[:1000]
            except Exception:
                body = ""
            return None, {
                "code": f"http_{error.code}",
                "status": error.code,
                "headers": dict(error.headers.items()) if error.headers else {},
                "body": body,
                "provider": provider,
                "model": model.get("id"),
            }
        except (URLError, TimeoutError) as error:
            return None, {
                "code": "timeout",
                "provider": provider,
                "model": model.get("id"),
                "body": str(error)[:300],
            }
        except Exception as error:
            return None, {
                "code": "unknown",
                "provider": provider,
                "model": model.get("id"),
                "body": str(error)[:300],
            }

    def public_status(self) -> dict:
        available = [model for model in self.models if self.is_available(model)]
        providers = Counter(str(model.get("provider")) for model in available)
        return {
            "mode": "free-only",
            "models": len(self.models),
            "available_models": len(available),
            "providers": dict(sorted(providers.items())),
            "local_fallback": any(model.get("provider") == "local" for model in self.models),
        }
