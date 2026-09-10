"""
DeepEval judge backed by GPT-OSS 120B on the local bosgame Ollama server.
"""

import os
import re
import time
from typing import Optional
import httpx
from deepeval.models import DeepEvalBaseLLM
from utils.request_cache import RequestCache


_THINK_RE = re.compile(r'<think>.*?</think>', re.DOTALL | re.IGNORECASE)
_RETRYABLE_STATUSES = {429, 502, 503, 504}
_JUDGE_CACHE = RequestCache('nanotech_judge_cache')


class NanotechJudge(DeepEvalBaseLLM):
    """LLM-as-a-judge powered by a local OpenAI-compatible Ollama endpoint."""

    def __init__(self, base_url: Optional[str] = None, timeout: Optional[float] = None):
        self.base_url = (base_url or os.getenv('LOCAL_LLM_BASE_URL', 'http://127.0.0.1:11434/v1')).rstrip('/')
        self.model = os.getenv('LOCAL_LLM_MODEL', 'gpt-oss:120b')
        self.api_key = os.getenv('LOCAL_LLM_API_KEY', 'ollama')
        self.timeout = timeout or float(os.getenv('LOCAL_LLM_TIMEOUT_SEC', '300'))
        self._last_model: Optional[str] = None
        self.max_attempts = int(os.getenv('NANOTECH_LLM_MAX_ATTEMPTS', '3'))
        self.retry_base_delay = float(os.getenv('NANOTECH_LLM_RETRY_BASE_DELAY', '2.0'))
        self.request_pause = float(os.getenv('NANOTECH_LLM_REQUEST_PAUSE', '0.5'))

    def get_model_name(self) -> str:
        return self._last_model or self.model

    def load_model(self):
        return self

    def _strip_think(self, text: str) -> str:
        return _THINK_RE.sub('', text).strip()

    def _call_chat(self, prompt: str) -> Optional[str]:
        cache_payload = {'base_url': self.base_url, 'model': self.model, 'prompt': prompt}
        cached = _JUDGE_CACHE.get(cache_payload)
        if isinstance(cached, dict):
            reply = cached.get('reply')
            if reply:
                self._last_model = cached.get('model', self.model)
                return reply
        headers = {'Authorization': f'Bearer {self.api_key}'}
        with httpx.Client(base_url=self.base_url, timeout=self.timeout, headers=headers) as client:
            for attempt in range(1, self.max_attempts + 1):
                try:
                    resp = client.post(
                        '/chat/completions',
                        json={
                            'model': self.model,
                            'messages': [{'role': 'user', 'content': prompt}],
                            'temperature': 0,
                            'max_tokens': 2048,
                            'response_format': {'type': 'json_object'},
                            'stream': False,
                        },
                    )
                    if resp.status_code in _RETRYABLE_STATUSES and attempt < self.max_attempts:
                        time.sleep(self.retry_base_delay * attempt)
                        continue
                    if resp.status_code != 200:
                        return None
                    data = resp.json()
                    reply = self._strip_think(data['choices'][0]['message'].get('content', ''))
                    if not reply:
                        return None
                    self._last_model = data.get('model', self.model)
                    _JUDGE_CACHE.set(
                        cache_payload,
                        {'reply': reply, 'model': self._last_model},
                    )
                    time.sleep(self.request_pause)
                    return reply
                except (httpx.HTTPError, KeyError, ValueError):
                    if attempt == self.max_attempts:
                        return None
                    time.sleep(self.retry_base_delay * attempt)
        return None

    def generate(self, prompt: str, **kwargs) -> str:
        result = self._call_chat(prompt)
        if result:
            return result
        raise RuntimeError(f'Local judge failed for prompt: {prompt[:120]}...')

    async def a_generate(self, prompt: str, **kwargs) -> str:
        return self.generate(prompt, **kwargs)
