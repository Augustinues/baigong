# Agent Company 🏢

**一个让 AI Agent 像公司员工一样协作的开源框架。**

这不是又一个工作流编排工具。Agent Company 的核心理念是：**每个 Agent 是独立运作的个体，通过发消息和看板协作，就像真人的"活的办公室"。**

没有集中调度器，没有预先画好的 DAG，没有中间的转发人。主管看到任务 → 拆解 → 写上看板 → 研究员看到 → 主动领取 → 干完写结果 → 其他人看到继续推进。这才是人协作的方式。

---

## 核心哲学

| 概念 | 说明 |
|------|------|
| **Agent 是员工，不是节点** | 每个 Agent 有独立模型、记忆、工具、性格，不是工作流里的一个"步骤" |
| **看板模式，没有中间人** | 信息公开在任务卡片上，Agent 自己去板上取，不需要谁转发结果 |
| **半主动 Agent** | 在自己的职责范围内可以主动领任务、催进度、做优化 |
| **记忆会自动生长** | 每次任务完成，记忆网络自动判断哪些值得记住——不需要人说"记住这个" |
| **Skill 从经验中自然形成** | 同类型事做多了，Agent 自动提炼出可复用的工作流程 |
| **独立模型配置** | 每个 Agent 可以混用不同厂商（DeepSeek, Claude, 本地 GGUF）不同档位 |

## 快速开始

```bash
pip install agent-company
```

### 迷你示例

```python
import asyncio
from agent_sdk import AgentManager, MessageBus, TaskBoard, BaseTool, ToolRegistry, BaseLLMClient, RoleDefinition, init_db

# 1. 定义你自己的工具
class MySearch(BaseTool):
    @property
    def metadata(self):
        return ToolMetadata(
            name="web_search",
            display_name="网络搜索",
            description="搜索网络信息",
            parameters=[ToolParam(name="query", type="string", description="关键词", required=True)],
            category="search",
        )
    async def execute(self, query: str, limit: int = 5) -> ToolResult:
        # 在这里写你的真实搜索逻辑
        return ToolResult(success=True, data={"results": [...]})

# 2. 初始化系统
init_db()
message_bus = MessageBus()
task_board = TaskBoard()
agent_manager = AgentManager(message_bus, task_board)
ToolRegistry.register(MySearch())

# 3. 注册角色
manager_role = RoleDefinition(
    role_id="manager", display_name="主管", icon="👔",
    description="负责分析任务、拆解分配、跟踪进度",
    responsibilities=["分析CEO下发的任务，拆解为子任务", "分配任务给合适的Agent"],
    default_tools=["send_message"],
    task_acquisition="self_claim",
)
agent_manager.register_role(manager_role)

# 4. 创建 Agent
ceo = await agent_manager.create_agent("CEO", "manager")
```

## 架构总览

```
agent_company/
├── agent_sdk/        # 核心 SDK（纯抽象接口）
│   ├── models.py          # 数据模型（Agent, 消息, 任务, 记忆, Skill）
│   ├── tool_base.py       # 工具接口 BaseTool + 注册表
│   ├── llm_base.py        # LLM 客户端抽象
│   ├── message_bus.py     # 消息总线（Agent 间通信）
│   ├── task_board.py      # 任务看板（共享工单）
│   ├── agent_runtime.py   # Agent 运行时（思考-行动循环）
│   ├── agent_manager.py   # Agent 生命周期管理
│   ├── database.py        # SQLite 持久化层
│   └── memory/
│       ├── long_term.py   # 长期记忆（树+图结构）
│       └── short_term.py  # 短期记忆 + 工作记忆
├── roles/             # 示例角色定义 YAML
├── examples/          # 示例空工具实现
└── web_ui/            # Web 管理界面（开发中）
```

## 五大核心组件

### 1. Agent 注册表（"花名册"）

每个 Agent 独立配置——模型、工具、权限、角色。甚至可以混用不同厂商的模型（主管用 Claude，收集员用本地 GGUF）。

### 2. 消息总线（"内网通信"）

Agent 之间发消息发送，不是函数调用。支持单播、广播、多轮对话（thread_id）。

### 3. 任务看板（"工单"）

所有信息公开在看板上，Agent 自己去取。任务流转是主管在运行时动态决定的，不是预先画好的 DAG。

### 4. Agent 运行时（"工位"）

每个 Agent 永久运行一个**思考-行动循环**：

```
感知(看板+信箱) → 思考(LLM) → 决策(权限检查) → 行动(工具/消息) → 更新状态
```

| 状态 | 工作模式 | 频率 |
|------|---------|------|
| 空闲 | 待机巡检 | 每 5 秒 |
| 工作中 | 全速执行 | 持续 |
| 等待 | 低频巡检 | 每 10-15 秒 |
| 离线 | 暂停 | 不运行 |

### 5. 记忆系统（"大脑"）

#### 四层记忆架构

| 层级 | 容量 | 持久性 | 说明 |
|------|------|--------|------|
| 工作记忆 | ~10条 | 内存 | "我正在干啥"，任务完清空 |
| 短期记忆 | ~100条 | 内存+SQLite | "刚发生了什么" |
| 长期记忆 | 大 | SQLite 树+图 | "我学到了什么" |
| 团队知识 | 大 | 永久 | 所有人都知道的事 |

#### 记忆会自动生长

Agent 每次完成任务后，自动判断这段经历值不值得记住（显著性检测）：

| 信号 | 分值 |
|------|------|
| CEO 反馈 | 0.9 |
| 任务失败/异常 | 0.7 |
| 新概念发现 | 0.6 |
| 信息冲突 | 0.5 |
| 重复模式 | 0.4 |
| 高代价 | 0.3-0.5 |

#### 联想式检索

类似人脑——想到"翡翠"时，自动浮现"鉴别→B货→证书"。从入口节点沿树和链接 BFS 遍历。

## 五层容错

```
第1层: LLM 调用 → 重试 → 指数退避 → 熔断器
第2层: 循环 → 死循环检测 → 强制打断
第3层: 任务 → 自动恢复 → 通知 CEO
第4层: Agent → 健康检查 → 自动重启 → 降级
第5层: 系统 → 崩溃恢复 → 记忆完整性检查
```

## Skill 自动形成

Agent 不需要被"训练"——同类型任务做 3 次以上，自动从记忆树中挖掘出可复用的 Skill。下次遇到同样任务直接执行 Skill，不再走完整的 LLM 思考流程。

## 开源友好设计

- **只给接口，不给实现** — 项目自带的只有抽象基类和接口定义
- **示例模板** — `examples/my_tools.py` 展示怎么写自己的工具
- **YAML 配置** — 角色、Agent、工具都用 YAML 定义
- **你的工具在外面** — 私有配置和工具实现不进入仓库
- **官方工具包（可选）** — `agent_toolkit/` 提供通用实现在另一个包

## 自己动手

1. 继承 `BaseTool` 实现你自己的工具（搜索、读文件、调 API 等等）
2. 继承 `BaseLLMClient` 接入你的模型（DeepSeek、Claude、OpenAI、本地 GGUF）
3. 写个 YAML 定义角色
4. `create_agent` → `start_agent` → 开工

完整示例见 [`example.py`](example.py)。

## License

MIT
