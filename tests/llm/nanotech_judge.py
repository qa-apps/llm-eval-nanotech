"""
DeepEval judge backed by nanotech.icu's POST /api/chat — no OpenAI key needed.
Uses free open-source models (Qwen, Llama, Mistral) with fallback:
auto → general → coding → research
"""

import re
from typing import Optional
import httpx
from deepeval.models import DeepEvalBaseLLM


_AGENTS = ['auto', 'general', 'coding', 'research']
_THINK_RE = re.compile(r'<think>.*?</think>', re.DOTALL)


class NanotechJudge(DeepEvalBaseLLM):
    """LLM-as-a-judge powered by nanotech.icu's orchestrated open-source models."""

    def __init__(self, base_url: str = 'https://nanotech.icu', timeout: float = 60.0):
        self.base_url = base_url
        self.timeout = timeout
        self._last_model: Optional[str] = None

    def get_model_name(self) -> str:
        return self._last_model or 'nanotech-orchestrator'

    def load_model(self):
        return self

    def _strip_think(self, text: str) -> str:
        return _THINK_RE.sub('', text).strip()

    def _call_chat(self, prompt: str, agent: str) -> Optional[str]:
        try:
            with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
                resp = client.post(
                    '/api/chat',
                    json={'message': prompt, 'agent': agent, 'attachments': []},
                )
                if resp.status_code != 200:
                    return None
                data = resp.json()
                self._last_model = data.get('model', agent)
                return self._strip_think(data.get('reply', ''))
        except (httpx.HTTPError, KeyError):
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
