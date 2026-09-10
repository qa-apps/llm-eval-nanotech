import json
from pathlib import Path

import app.free_model_pool as pool_module
from app.free_model_pool import FreeModelPool, is_free_only_model, load_models


def _model(model_id, provider, tier="M", **extra):
    return {
        "id": model_id,
        "label": model_id,
        "provider": provider,
        "tier": tier,
        "free": True,
        **extra,
    }


def test_paid_and_unmarked_routes_fail_closed(monkeypatch):
    monkeypatch.setenv("FREE_ONLY_MODE", "1")

    assert is_free_only_model(_model("vendor/model:free", "openrouter"))
    assert not is_free_only_model(_model("vendor/model", "openrouter"))
    assert not is_free_only_model({"id": "openai/gpt-5", "provider": "openai", "free": True})
    assert not is_free_only_model({"id": "codestral-latest", "provider": "mistral"})


def test_registry_filters_paid_routes_and_keeps_local_backup(tmp_path, monkeypatch):
    monkeypatch.setenv("FREE_ONLY_MODE", "1")
    registry = tmp_path / "models.json"
    registry.write_text(
        json.dumps(
            {
                "models": [
                    _model("vendor/free:free", "openrouter"),
                    _model("vendor/paid", "openrouter"),
                    _model("openai/gpt-oss-20b", "groq"),
                    _model("gpt-5", "openai"),
                ]
            }
        ),
        encoding="utf-8",
    )

    models = load_models(Path(registry))
    ids = {model["id"] for model in models}

    assert ids == {"vendor/free:free", "openai/gpt-oss-20b", "gpt-oss:120b"}


def test_fallback_chain_round_robins_providers_and_keeps_local_last(monkeypatch):
    monkeypatch.setenv("FREE_ONLY_MODE", "1")
    monkeypatch.setenv("GROQ_API_KEY", "test")
    monkeypatch.setenv("COHERE_API_KEY", "test")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    models = [
        _model("openai/gpt-oss-20b", "groq"),
        _model("openai/gpt-oss-120b", "groq", tier="H"),
        _model("command-r7b", "cohere"),
        _model("vendor/free:free", "openrouter"),
        _model("gpt-oss:120b", "local", tier="H"),
    ]
    pool = FreeModelPool(models)

    chain = pool.fallback_chain(models[0], "M")
    providers = [model["provider"] for model in chain]

    assert providers[-1] == "local"
    assert providers[:3] == ["cohere", "openrouter", "groq"]


def test_payment_error_cools_down_entire_provider(monkeypatch):
    monkeypatch.setenv("FREE_ONLY_MODE", "1")
    monkeypatch.setenv("GROQ_API_KEY", "test")
    first = _model("openai/gpt-oss-20b", "groq")
    second = _model("openai/gpt-oss-120b", "groq", tier="H")
    pool = FreeModelPool([first, second])

    pool.record_failure(first, {"status": 402, "body": "payment required"})

    assert not pool.is_available(first)
    assert not pool.is_available(second)


def test_reasoning_models_are_reserve_when_ordinary_model_is_available(monkeypatch):
    monkeypatch.setenv("FREE_ONLY_MODE", "1")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "test")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "test")
    reasoning = _model("@cf/qwen/qwq-32b", "cloudflare", reasoning=True)
    ordinary = _model("@cf/ibm-granite/granite-4.0-h-micro", "cloudflare")
    pool = FreeModelPool([reasoning, ordinary])

    assert pool.pick([reasoning, ordinary]) == ordinary


def test_call_model_rejects_paid_route_without_network(monkeypatch):
    monkeypatch.setenv("FREE_ONLY_MODE", "1")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    pool = FreeModelPool([_model("vendor/free:free", "openrouter")])

    reply, error = pool.call_model(
        {"id": "vendor/paid", "provider": "openrouter", "free": True, "tier": "H"},
        "system",
        "hello",
    )

    assert reply is None
    assert error["code"] == "paid_model_disabled"


def test_groq_request_stays_below_free_tier_output_limit(monkeypatch):
    monkeypatch.setenv("FREE_ONLY_MODE", "1")
    monkeypatch.setenv("GROQ_API_KEY", "test")
    model = _model("openai/gpt-oss-20b", "groq")
    pool = FreeModelPool([model])
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"choices":[{"message":{"content":"ok"}}]}'

    def fake_urlopen(request, timeout):
        captured["payload"] = json.loads(request.data)
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(pool_module, "urlopen", fake_urlopen)

    reply, error = pool.call_model(model, "system", "hello", max_tokens=2048)

    assert error is None
    assert reply == "ok"
    assert captured["payload"]["max_tokens"] == 900


def test_shipped_registry_is_large_and_strictly_free(monkeypatch):
    monkeypatch.setenv("FREE_ONLY_MODE", "1")
    registry = Path(__file__).parents[2] / "app" / "models_registry.json"

    models = load_models(registry)
    cloud = [model for model in models if model["provider"] != "local"]

    assert len(cloud) >= 70
    assert {model["provider"] for model in cloud} == {
        "cloudflare",
        "cohere",
        "groq",
        "huggingface",
        "mistral",
        "nvidia",
        "openrouter",
    }
    assert all(is_free_only_model(model) for model in models)
