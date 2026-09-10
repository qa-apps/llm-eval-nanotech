# NanoTech AI Assistant production sources

`chat_server.py` is the backend and static-file server used by `nanotech-chat.service`.
Its LLM calls go through `free_model_pool.py`, which enforces the following rules:

- OpenRouter models must have a `:free` id.
- Direct providers must be explicitly tagged `free: true` in the curated registry.
- 401, 402, 403, 429, missing-model, timeout, and provider errors put the affected
  provider or model on cooldown before failover continues.
- Cloud providers are traversed round-robin; local `gpt-oss:120b` is always last.
- Paid providers and unmarked models fail closed before any network request.

The registry in `models_registry.json` is a boot-safe snapshot. The systemd timer
runs `model_curator.py` every 60 hours to discover and probe currently available
free routes. Production overrides the registry path with:

```text
NANOTECH_MODEL_REGISTRY=/var/lib/nanotech-chat/models_registry.json
```

The production web bundle is tracked under `web/`. Its chat renderer escapes model
output before applying a small allowlisted Markdown subset, so model-generated HTML
cannot be injected into the page. Deploy these files to `/var/www/nanotech/`:

```text
chat_server.py
free_model_pool.py
model_curator.py
models_registry.json
web/index.html
web/script.js
web/style.css
```

The systemd drop-in enables strict free-only mode. The curator service and timer
refresh the runtime registry every 60 hours and restart the chat service only after
a successful refresh. Existing environment files, user data, and registry history
must remain outside the repository and must not be replaced during deployment.
