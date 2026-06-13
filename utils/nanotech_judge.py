"""
DeepEval judge backed by nanotech.icu's POST /api/chat — no OpenAI key needed.
Uses free open-source models (Qwen, Llama, Mistral) with fallback:
auto → general → coding → research
"""

import os
import re
import time
from typing import Optional
import httpx
from deepeval.models import DeepEvalBaseLLM
from utils.request_cache import RequestCache


_AGENTS = ['auto', 'general', 'coding', 'research']
_THINK_RE = re.compile(r'<think>.*?</think>', re.DOTALL)
_RETRYABLE_STATUSES = {429, 502, 503, 504}
_JUDGE_CACHE = RequestCache('nanotech_judge_cache')


class NanotechJudge(DeepEvalBaseLLM):
    """LLM-as-a-judge powered by nanotech.icu's orchestrated open-source models."""

    def __init__(self, base_url: str = 'https://nanotech.icu', timeout: float = 60.0):
        self.base_url = base_url
        self.timeout = timeout
        self._last_model: Optional[str] = None
        self.max_attempts = int(os.getenv('NANOTECH_LLM_MAX_ATTEMPTS', '5'))
        self.retry_base_delay = float(os.getenv('NANOTECH_LLM_RETRY_BASE_DELAY', '2.0'))
        self.request_pause = float(os.getenv('NANOTECH_LLM_REQUEST_PAUSE', '0.5'))

    def get_model_name(self) -> str:
        return self._last_model or 'nanotech-orchestrator'

    def load_model(self):
        return self

    def _strip_think(self, text: str) -> str:
        return _THINK_RE.sub('', text).strip()

    def _call_chat(self, prompt: str, agent: str) -> Optional[str]:
        cache_payload = {'base_url': self.base_url, 'agent': agent, 'prompt': prompt}
        cached = _JUDGE_CACHE.get(cache_payload)
        if isinstance(cached, dict):
            reply = cached.get('reply')
            if reply:
                self._last_model = cached.get('model', agent)
                return reply
        with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
            for attempt in range(1, self.max_attempts + 1):
                try:
                    resp = client.post(
                        '/api/chat',
                        json={'message': prompt, 'agent': agent, 'attachments': []},
                    )
                    if resp.status_code in _RETRYABLE_STATUSES and attempt < self.max_attempts:
                        time.sleep(self.retry_base_delay * attempt)
                        continue
                    if resp.status_code != 200:
                        return None
                    data = resp.json()
                    reply = self._strip_think(data.get('reply', ''))
                    if not reply:
                        return None
                    self._last_model = data.get('model', agent)
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
        for agent in _AGENTS:
            result = self._call_chat(prompt, agent)
            if result:
                return result
        raise RuntimeError(
            f'All nanotech agents exhausted for prompt: {prompt[:120]}...'
        )

    async def a_generate(self, prompt: str, **kwargs) -> str:
        return self.generate(prompt, **kwargs)
