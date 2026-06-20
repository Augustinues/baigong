"""数据模型——Agent、消息、任务、记忆等核心类型"""

from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum
from datetime import datetime


# ═══════════════════════════════════════════
# Agent 相关
# ═══════════════════════════════════════════

class AgentStatus(Enum):
    BOOTING = "booting"
    IDLE = "idle"
    WORKING = "working"
    WAITING = "waiting"
    DEGRADED = "degraded"
    STUCK = "stuck"
    ERROR = "error"
    PAUSED = "paused"
    FROZEN = "frozen"
    SHUTTING_DOWN = "shutting_down"
    OFFLINE = "offline"
    DEAD = "dead"


@dataclass
class ModelConfig:
    """模型配置——每个 Agent 可独立指定"""
    provider: str = "deepseek"        # deepseek | dashscope | openai | ...
    model: str = "deepseek-v4-flash"
    api_key: str = ""                 # 空 = 用系统默认
    base_url: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: int = 30


@dataclass
class ToolParam:
    """工具参数定义"""
    name: str
    type: str                         # string | integer | boolean | array | object
    description: str
    required: bool = False
    default: Any = None
    enum: list[str] | None = None


@dataclass
class ToolMetadata:
    """工具元信息"""
    name: str
    display_name: str = ""
    description: str = ""
    parameters: list[ToolParam] = field(default_factory=list)
    category: str = "general"
    timeout: int = 30
    requires_confirmation: bool = False


@dataclass
class ToolResult:
    """工具调用结果"""
    success: bool
    data: Any = None
    error: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class RoleDefinition:
    """角色定义"""
    role_id: str
    display_name: str
    description: str
    icon: str = "🤖"

    # 职责
    responsibilities: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    # 行为
    system_prompt_template: str = ""
    work_mode: str = "mixed"           # proactive | passive | mixed
    communication_style: str = "brief" # brief | detailed | executive
    decision_bias: str = "balanced"    # conservative | balanced | aggressive
    check_interval: int = 5

    # 工具
    default_tools: list[str] = field(default_factory=list)
    forbidden_tools: list[str] = field(default_factory=list)

    # 社交
    reports_to: str = "ceo"
    task_acquisition: str = "both"     # assigned | self_claim | both
    conflict_resolution: str = "obey_superior"

    # 成长
    reflection_frequency: str = "after_task"


@dataclass
class AgentConfig:
    """Agent 完整配置"""
    agent_id: str
    name: str
    role_id: str
    role: Optional[RoleDefinition] = None

    model_config: ModelConfig = field(default_factory=ModelConfig)
    tools: list[str] = field(default_factory=list)
    system_prompt: str = ""

    auto_restart: bool = True
    max_concurrent_tasks: int = 3


# ═══════════════════════════════════════════
# 消息系统
# ═══════════════════════════════════════════

class MessageType(Enum):
    TASK_ASSIGN = "task_assign"
    TASK_RESULT = "task_result"
    STATUS_UPDATE = "status_update"
    QUERY = "query"
    REPLY = "reply"
    REQUEST_HELP = "request_help"
    NOTIFICATION = "notification"
    FEEDBACK = "feedback"
    SYSTEM = "system"


@dataclass
class Message:
    """Agent 间消息"""
    id: str
    type: MessageType
    sender: str
    recipients: list[str]
    body: str
    parent_task_id: str = ""
    thread_id: str = ""
    attachments: dict = field(default_factory=dict)
    created_at: float = 0.0
    status: str = "pending"  # pending | read | resolved


# ═══════════════════════════════════════════
# 任务系统
# ═══════════════════════════════════════════

class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    STUCK = "stuck"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """任务工单"""
    id: str
    goal: str
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0           # 0.0 ~ 1.0
    creator: str = ""               # ceo | agent_id
    assignee: str = ""
    parent_task_id: str = ""
    subtask_ids: list[str] = field(default_factory=list)

    # 内容
    description: str = ""
    attachments: list[str] = field(default_factory=list)

    # 时间
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # 审计
    flow_log: list[dict] = field(default_factory=list)

    def log(self, event: str, by: str):
        self.flow_log.append({
            "time": datetime.now().isoformat(),
            "event": event,
            "by": by
        })


# ═══════════════════════════════════════════
# 记忆系统
# ═══════════════════════════════════════════

class MemoryType(Enum):
    EPISODIC = "episodic"       # 情景记忆——经历过的事
    SEMANTIC = "semantic"       # 语义记忆——知道的知识
    PROCEDURAL = "procedural"   # 程序记忆——会做的流程
    SOCIAL = "social"           # 社交记忆——对别人的了解
    PATTERN = "pattern"         # 模式——从多次经历中提炼


@dataclass
class MemoryNode:
    """记忆节点——树上的一个概念"""
    id: str
    type: MemoryType
    content: str
    summary: str = ""
    tags: list[str] = field(default_factory=list)
    parent_id: Optional[str] = None
    level: int = 0
    confidence: float = 0.5
    importance: float = 0.3
    access_count: int = 0
    last_accessed: Optional[float] = None
    source_task: str = ""
    source_agent: str = ""
    created_at: float = 0.0
    metadata: dict = field(default_factory=dict)


@dataclass
class MemoryLink:
    """记忆链接——节点之间的关系"""
    id: str
    source_id: str
    target_id: str
    link_type: str               # reminds_of | opposite | part_of | co_occurred | derived_from
    strength: float = 0.5
    context: str = ""
    created_at: float = 0.0
    last_reinforced: Optional[float] = None


# ═══════════════════════════════════════════
# Skill 系统
# ═══════════════════════════════════════════

@dataclass
class SkillStep:
    """Skill 中的一步"""
    type: str                     # tool_call | sub_task | condition | wait
    tool_name: str = ""
    params: dict = field(default_factory=dict)
    condition: str = ""
    description: str = ""


@dataclass
class Skill:
    """可复用的工作能力"""
    name: str
    description: str
    triggers: list[str] = field(default_factory=list)    # 触发关键词
    steps: list[SkillStep] = field(default_factory=list)
    confidence: float = 0.5
    use_count: int = 0
    success_count: int = 0
    success_rate: float = 0.0
    formed_at: float = 0.0
    last_used: Optional[float] = None
