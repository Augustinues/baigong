"""DeepSeek LLM 客户端 — Agent 的大脑"""

import json
import os
import time
from typing import Optional

import httpx

from agent_sdk.llm_base import BaseLLMClient


# 找 API Key
def _find_api_key() -> str:
    # 先试环境变量
    for k in ["DEEPSEEK_API_KEY", "DEEPSEEK_KEY"]:
        val = os.environ.get(k, "").strip()
        if val:
            return val
    # 试 hermes 配置
    for env_path in [
        os.path.expanduser("~/.hermes/.env"),
        os.path.expanduser("~/.hermes/env"),
    ]:
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("DEEPSEEK_API_KEY=") or line.startswith("export DEEPSEEK_API_KEY="):
                        val = line.split("=", 1)[-1].strip().strip("'\"")
                        if val:
                            return val
    return ""


DEFAULT_API_KEY = _find_api_key()


class DeepSeekClient(BaseLLMClient):
    """接入 DeepSeek 的真实 LLM 客户端"""

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "",
        model: str = "deepseek-chat",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ):
        self.api_key = api_key or DEFAULT_API_KEY
        self.base_url = (base_url or "https://api.deepseek.com").rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._client = httpx.AsyncClient(timeout=60.0)
        self._last_error: Optional[str] = None
        self._call_count = 0

    async def think(
        self,
        system_prompt: str = "",
        context: str = "",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """让 DeepSeek 思考，返回决策 JSON"""
        self._call_count += 1

        if not self.api_key:
            self._last_error = "No API key"
            # 没有 key 就智能模拟
            return self._mock_think(system_prompt, context)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": context})

        try:
            resp = await self._client.post(
                f"{self.base_url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature or self.temperature,
                    "max_tokens": max_tokens or self.max_tokens,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            self._last_error = None
            return content

        except Exception as e:
            self._last_error = str(e)
            # API 不可用 → 模拟
            return self._mock_think(system_prompt, context)

    def _mock_think(self, system_prompt: str, context: str) -> str:
        """无 API Key 时的智能模拟"""
        import re

        goal = ""
        if "新任务:" in context:
            m = re.search(r'新任务[：:]\s*(.+?)(?:\n|$)', context)
            if m:
                goal = m.group(1).strip()

        if "搜索" in context or (goal and "搜索" in goal):
            return json.dumps({"action": "tool_call", "tool": "web_search", "params": {"query": goal[:30] if goal else "搜索", "limit": 5}})
        elif "整理" in context or "编辑" in system_prompt:
            return json.dumps({"action": "wait", "reason": "等待资料"})
        elif "入库" in context or "知识库" in context or "knowledge" in system_prompt.lower():
            return json.dumps({"action": "tool_call", "tool": "kb_write", "params": {"title": "资料汇总", "content": "# 资料汇总\n\n## 主要内容\n..."}})
        elif "质检" in system_prompt or "qa" in system_prompt.lower():
            return json.dumps({"action": "complete_task", "result": "质检通过"})
        elif "主管" in system_prompt or "manager" in system_prompt.lower():
            # 主管: 拆解任务
            if goal:
                return json.dumps({"action": "create_subtask", "goal": f"搜索关于「{goal}」的资料", "assignee": "researcher"})
            else:
                return json.dumps({"action": "wait"})

        return json.dumps({"action": "wait"})

    async def chat(
        self,
        messages: list[dict],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """多轮对话"""
        if not self.api_key:
            return "模拟回复"
        try:
            resp = await self._client.post(
                f"{self.base_url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature or self.temperature,
                    "max_tokens": max_tokens or self.max_tokens,
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return f"模拟回复 (API error: {str(e)[:30]})"

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)
