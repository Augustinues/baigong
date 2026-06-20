"""LLM 客户端——抽象接口"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class LLMResponse:
    content: str
    model: str = ""
    usage: dict | None = None


class BaseLLMClient(ABC):
    """LLM 客户端抽象基类——用户需要继承并实现"""

    @abstractmethod
    async def think(
        self,
        system_prompt: str,
        context: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """让 LLM 思考并返回结果"""
        ...

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """多轮对话"""
        ...
