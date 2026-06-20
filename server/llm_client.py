"""通用 LLM 客户端 — 支持 DeepSeek / OpenAI / DashScope / Ollama / 自定义"""

import json
import os
from typing import Optional

import httpx

from agent_sdk.llm_base import BaseLLMClient
from .config import config, PROVIDER_DEFAULTS


class LLMClient(BaseLLMClient):
    """通用 LLM 客户端（OpenAI 兼容 API）"""

    def __init__(self):
        cfg = config.get("llm", {})
        self.provider = cfg.get("provider", "deepseek")
        self.api_key = cfg.get("api_key", "")
        self.base_url = (cfg.get("base_url", "https://api.deepseek.com/v1")).rstrip("/")
        self.model = cfg.get("model", "deepseek-v4-flash")
        self.temperature = cfg.get("temperature", 0.7)
        self.max_tokens = cfg.get("max_tokens", 4096)

        # Ollama 不需要 API Key
        if self.provider == "ollama" and not self.api_key:
            self.api_key = "ollama"

        self._client = httpx.AsyncClient(timeout=120.0)
        self._call_count = 0
        self._last_error: Optional[str] = None

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)

    @property
    def chat_endpoint(self) -> str:
        if self.provider == "dashscope":
            return f"{self.base_url}/chat/completions"
        return f"{self.base_url}/chat/completions"

    async def chat(self, messages: list[dict], **kwargs) -> str:
        """多轮对话"""
        self._call_count += 1
        if not self.api_key:
            self._last_error = "No API key"
            return ""

        url = kwargs.get("url") or self.chat_endpoint
        model = kwargs.get("model") or self.model
        temperature = kwargs.get("temperature") or self.temperature
        max_tokens = kwargs.get("max_tokens") or self.max_tokens

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        # OpenRouter 需要额外 header
        if self.provider == "openrouter":
            headers["HTTP-Referer"] = "https://github.com/Augustinues/baigong"
            headers["X-Title"] = "Baigong"

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            resp = await self._client.post(
                url, headers=headers, json=payload
            )
            resp.raise_for_status()
            data = resp.json()
            self._last_error = None
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            self._last_error = str(e)
            raise

    async def think(self, system_prompt: str = "", context: str = "", **kwargs) -> str:
        """单次思考（兼容 BaseLLMClient）"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": context})
        return await self.chat(messages, **kwargs)

    async def close(self):
        await self._client.aclose()
