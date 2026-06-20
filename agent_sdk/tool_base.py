"""工具系统——接口定义 + 注册表"""

from abc import ABC, abstractmethod
from typing import Any

from .models import ToolMetadata, ToolResult


class BaseTool(ABC):
    """所有工具的基类——用户继承这个实现自己的工具"""

    @property
    @abstractmethod
    def metadata(self) -> ToolMetadata:
        """工具元信息"""
        ...

    @abstractmethod
    async def execute(self, **params) -> ToolResult:
        """执行工具的核心逻辑"""
        ...

    async def validate_params(self, **params) -> bool:
        """参数校验"""
        for param in self.metadata.parameters:
            if param.required and param.name not in params:
                raise ValueError(f"缺少必填参数: {param.name}")
            if param.enum and params.get(param.name) not in param.enum:
                raise ValueError(f"参数 {param.name} 值必须在 {param.enum} 中")
        return True


class ToolRegistry:
    """全局工具注册表"""

    _tools: dict[str, BaseTool] = {}

    @classmethod
    def register(cls, tool: BaseTool):
        """注册一个工具"""
        cls._tools[tool.metadata.name] = tool

    @classmethod
    def get(cls, name: str) -> BaseTool | None:
        return cls._tools.get(name)

    @classmethod
    def list_by_category(cls, category: str) -> list[BaseTool]:
        return [t for t in cls._tools.values() if t.metadata.category == category]

    @classmethod
    def list_all(cls) -> list[BaseTool]:
        return list(cls._tools.values())

    @classmethod
    def clear(cls):
        cls._tools.clear()
