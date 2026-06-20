"""百工 (Baigong) — 多 Agent 原生协作系统

让 AI Agent 像工匠一样协作的开源框架。
每个 Agent 是独立的个体，通过看板和消息协作，
拥有自动生长的记忆树，技能会从经验中自然形成。
"""

__version__ = "0.2.2"

from .models import (
    AgentConfig, AgentStatus, RoleDefinition, ModelConfig,
    Message, MessageType, Task, TaskStatus,
    MemoryNode, MemoryLink, MemoryType,
    ToolMetadata, ToolResult, ToolParam,
    Skill, SkillStep,
)
from .memory.long_term import LongTermMemory
from .memory.short_term import ShortTermMemory, WorkingMemory
from .message_bus import MessageBus
from .task_board import TaskBoard
from .agent_runtime import AgentRuntime
from .agent_manager import AgentManager
from .tool_base import BaseTool, ToolRegistry
from .database import init_db
from .llm_base import BaseLLMClient, LLMResponse

__all__ = [
    "AgentConfig", "AgentStatus", "RoleDefinition", "ModelConfig",
    "Message", "MessageType", "Task", "TaskStatus",
    "MemoryNode", "MemoryLink", "MemoryType",
    "ToolMetadata", "ToolResult", "ToolParam",
    "Skill", "SkillStep",
    "LongTermMemory", "ShortTermMemory", "WorkingMemory",
    "MessageBus", "TaskBoard",
    "AgentRuntime", "AgentManager",
    "BaseTool", "ToolRegistry",
    "BaseLLMClient", "LLMResponse",
    "init_db",
]
