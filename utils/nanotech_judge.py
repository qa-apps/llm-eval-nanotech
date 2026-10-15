"""
DeepEval judge backed by the DeepSeek cloud API (OpenAI-compatible).
"""

import os
import re
import time
from typing import Optional
import httpx
from deepeval.models import DeepEvalBaseLLM
from utils.request_cache import RequestCache


_THINK_RE = re.compile(r'<think>.*?</think>', re.DOTALL | re.IGNORECASE)
_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
_JUDGE_CACHE = RequestCache('nanotech_judge_cache')


class NanotechJudge(DeepEvalBaseLLM):
    """LLM-as-a-judge powered by DeepSeek's OpenAI-compatible endpoint."""

    def __init__(self, base_url: Optional[str] = None, timeout: Optional[float] = None):
        self.base_url = (base_url or os.getenv('JUDGE_BASE_URL', 'https://api.deepseek.com/v1')).rstrip('/')
        self.model = os.getenv('DEEPSEEK_MODEL', 'deepseek-v4-pro')
        self.api_key = os.getenv('DEEPSEEK_API_KEY', '')
        self.run_id = os.getenv('GITHUB_RUN_ID', 'nanotech-deepeval')
        self.timeout = timeout or float(os.getenv('JUDGE_TIMEOUT_SEC', '120'))
        self.max_tokens = max(1, int(os.getenv('JUDGE_MAX_TOKENS', '4096')))
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
        if not self.api_key:
            raise RuntimeError('DEEPSEEK_API_KEY is required for the cloud judge')
        cache_payload = {'base_url': self.base_url, 'model': self.model, 'prompt': prompt}
        cached = _JUDGE_CACHE.get(cache_payload)
        if isinstance(cached, dict):
            reply = cached.get('reply')
            if reply:
                self._last_model = cached.get('model', self.model)
                return reply
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'X-QA-Run-ID': self.run_id,
        }
        body = {
            'model': self.model,
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0,
            'max_tokens': self.max_tokens,
            'reasoning_effort': 'low',
            'response_format': {'type': 'json_object'},
            'stream': False,
        }
        with httpx.Client(base_url=self.base_url, timeout=self.timeout, headers=headers) as client:
            attempt = 0
            while True:
                attempt += 1
                try:
                    resp = client.post('/chat/completions', json=body)
                    # JSON mode rejects prompts that never mention JSON; judge those as plain text.
                    if resp.status_code == 400 and 'response_format' in body:
                        body = {key: value for key, value in body.items() if key != 'response_format'}
                        attempt -= 1
                        continue
                    if resp.status_code in _RETRYABLE_STATUSES and attempt < self.max_attempts:
                        time.sleep(self.retry_base_delay * attempt)
                        continue
                    if resp.status_code != 200:
                        return None
                    data = resp.json()
                    reply = self._strip_think(data['choices'][0]['message'].get('content') or '')
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
                    if attempt >= self.max_attempts:
                        return None
                    time.sleep(self.retry_base_delay * attempt)
        return None

    def generate(self, prompt: str, **kwargs) -> str:
        result = self._call_chat(prompt)
        if result:
            return result
        raise RuntimeError(f'Cloud judge failed for prompt: {prompt[:120]}...')

    async def a_generate(self, prompt: str, **kwargs) -> str:
        return self.generate(prompt, **kwargs)
