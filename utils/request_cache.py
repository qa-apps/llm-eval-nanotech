import hashlib
import json
import os
from pathlib import Path
from threading import Lock
from typing import Any, Optional


class RequestCache:
    def __init__(self, name: str):
        cache_dir = Path(os.getenv('NANOTECH_LLM_CACHE_DIR', '.deepeval'))
        self.path = cache_dir / f'{name}.json'
        self.enabled = os.getenv('NANOTECH_LLM_USE_CACHE', '1') == '1'
        self._lock = Lock()
        self._loaded = False
        self._data: dict[str, Any] = {}

    def get(self, payload: dict[str, Any]) -> Optional[Any]:
        if not self.enabled:
            return None
        key = self._make_key(payload)
        with self._lock:
            self._load()
            return self._data.get(key)

    def set(self, payload: dict[str, Any], value: Any) -> None:
        if not self.enabled:
            return
        key = self._make_key(payload)
        with self._lock:
            self._load()
            self._data[key] = value
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.path.with_suffix(f'{self.path.suffix}.tmp')
            temp_path.write_text(
                json.dumps(self._data, ensure_ascii=False, sort_keys=True),
                encoding='utf-8',
            )
            temp_path.replace(self.path)

    def _load(self) -> None:
        if self._loaded:
            return
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding='utf-8'))
            except (OSError, json.JSONDecodeError):
                self._data = {}
        self._loaded = True

    def _make_key(self, payload: dict[str, Any]) -> str:
        normalized = self._normalize(payload)
        raw = json.dumps(normalized, ensure_ascii=False, separators=(',', ':'), sort_keys=True)
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()

    def _normalize(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: self._normalize(value[key]) for key in sorted(value)}
        if isinstance(value, (list, tuple)):
            return [self._normalize(item) for item in value]
        return value
