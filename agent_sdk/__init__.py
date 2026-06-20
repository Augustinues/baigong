"""
Agent Company SDK — 多 Agent 协作系统

一个让 AI Agent 像公司员工一样协作的系统。
每个 Agent 是独立的个体，通过消息和看板协作，
拥有自己的记忆树（会自动生长），技能会从经验中自然形成。
"""

__version__ = "0.1.0"

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
