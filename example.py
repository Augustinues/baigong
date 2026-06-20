"""
完整示例——使用百工 SDK 搭建多 Agent 协作系统

这个示例演示：
1. 注册角色定义
2. 创建自定义工具
3. 创建多个 Agent
4. 创建任务
5. 记忆系统
6. Skill 自动形成
"""

import asyncio
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_sdk import (
    AgentManager, AgentStatus, MessageBus, TaskBoard,
    RoleDefinition, ModelConfig,
    BaseTool, ToolRegistry, ToolMetadata, ToolParam, ToolResult,
    BaseLLMClient,
    MemoryType,
    init_db,
)


# ── 你的工具实现 ──

class MyWebSearch(BaseTool):
    @property
    def metadata(self):
        return ToolMetadata(
            name="web_search",
            display_name="网络搜索",
            description="搜索网络获取信息。当你需要查找资料时使用。",
            parameters=[
                ToolParam(name="query", type="string", description="搜索关键词", required=True),
                ToolParam(name="limit", type="integer", description="返回结果数量", default=5),
            ],
            category="search",
        )

    async def execute(self, query: str, limit: int = 5) -> ToolResult:
        print(f"  [🛠 web_search] query='{query}'")
        return ToolResult(success=True, data={
            "results": [
                {"title": f"关于 {query} 的结果1", "url": "https://example.com/1"},
                {"title": f"关于 {query} 的结果2", "url": "https://example.com/2"},
            ]
        })


class MyKnowledgeWrite(BaseTool):
    @property
    def metadata(self):
        return ToolMetadata(
            name="kb_write",
            display_name="知识库写入",
            description="将内容写入知识库。",
            parameters=[
                ToolParam(name="content", type="string", description="内容", required=True),
                ToolParam(name="title", type="string", description="标题", required=True),
            ],
            category="knowledge",
        )

    async def execute(self, content: str, title: str) -> ToolResult:
        print(f"  [🛠 kb_write] '{title}' ({len(content)}字)")
        return ToolResult(success=True, data={"status": "written", "title": title})


# ── 主逻辑 ──

async def main():
    print("=" * 60)
    print("  Agent Company — 多 Agent 协作系统")
    print("=" * 60)

    # 初始化
    init_db()
    message_bus = MessageBus()
    task_board = TaskBoard()
    agent_manager = AgentManager(message_bus, task_board)
    ToolRegistry.register(MyWebSearch())
    ToolRegistry.register(MyKnowledgeWrite())

    # 注册角色
    for role in get_roles():
        agent_manager.register_role(role)

    # 创建 Agent
    print("\n📋 创建 Agent...")
    manager = await agent_manager.create_agent("张经理", "manager")
    researcher = await agent_manager.create_agent("王研究员", "researcher")
    editor = await agent_manager.create_agent("李编辑", "editor")
    kb_admin = await agent_manager.create_agent("陈管理员", "knowledge_admin")

    # 设置 LLM（替换为你的真实 API 调用）
    llm_client = SimpleLLM()
    for agent in [manager, researcher, editor, kb_admin]:
        agent.llm = llm_client
        await agent_manager.start_agent(agent.agent_id)

    print(f"✅ {len(agent_manager.agents)} 个 Agent 已上线")

    # 创建任务
    print("\n📋 CEO 下派任务: 收集10篇翡翠鉴别资料并入库")
    task = task_board.create_task(
        goal="收集10篇翡翠鉴别资料，整理后入库到知识库",
        creator="ceo",
        assignee=manager.agent_id,
    )
    print(f"   任务 ID: {task.id}")

    # 给 Agent 时间处理
    print("\n⏳ Agent 正在工作...")
    await asyncio.sleep(2)

    # ── 阶段 1: 主管拆解任务，创建子任务 ──
    print("\n── 阶段 1: 主管拆解任务 ──")
    subtask1 = task_board.create_task(
        goal="搜索5篇翡翠鉴别资料",
        creator=manager.agent_id,
        assignee=researcher.agent_id,
        parent_task_id=task.id,
    )
    subtask2 = task_board.create_task(
        goal="整理和去重收集到的资料",
        creator=manager.agent_id,
        assignee=editor.agent_id,
        parent_task_id=task.id,
    )
    subtask3 = task_board.create_task(
        goal="将整理好的资料写入知识库",
        creator=manager.agent_id,
        assignee=kb_admin.agent_id,
        parent_task_id=task.id,
    )
    print(f"   创建了 3 个子任务")
    task_board.update_task(task.id, progress=0.2)

    # ── 阶段 2: 研究员执行搜索 ──
    print("\n── 阶段 2: 研究员执行搜索 ──")
    researcher.working_memory.set_task(subtask1.id, {"goal": "搜索5篇翡翠鉴别资料"})
    researcher.status = AgentStatus.WORKING
    researcher.short_term.record("action", "开始搜索翡翠鉴别资料")

    # 模拟搜索
    web_search_tool = ToolRegistry.get("web_search")
    result1 = await web_search_tool.execute(query="翡翠鉴别 A货 B货", limit=5)
    result2 = await web_search_tool.execute(query="翡翠真假鉴别方法", limit=5)
    researcher.tool_call_count += 2

    # 记录到短期记忆
    researcher.short_term.record(
        "result",
        "搜索完成，找到10篇相关文章",
        importance=0.6,
        task_id=subtask1.id,
    )

    # 模拟自动巩固到长期记忆
    researcher.long_term.create_node(
        content="搜索翡翠鉴别资料时，关键词'翡翠鉴别 A货 B货'和'翡翠真假鉴别方法'效果最好",
        type=MemoryType.SEMANTIC,
        summary="翡翠搜索关键词经验",
        tags=["翡翠", "搜索", "关键词"],
        confidence=0.6,
        importance=0.5,
        source_task=subtask1.id,
    )
    researcher.long_term.create_node(
        content="百度百科是翡翠鉴别资料的最佳来源（质量高、权威）",
        type=MemoryType.SEMANTIC,
        summary="百度百科质量高",
        tags=["翡翠", "来源评估", "百度百科"],
        confidence=0.7,
        importance=0.5,
        source_task=subtask1.id,
    )

    # 在"翡翠"根节点下建树
    jade_node = researcher.long_term.find_node_by_name("翡翠")
    if not jade_node:
        jade_node = researcher.long_term.create_node(
            content="翡翠相关知识的根节点",
            type=MemoryType.SEMANTIC,
            summary="翡翠",
            importance=0.8,
        )

    # 挂子节点
    search_exp = researcher.long_term.create_node(
        content="搜了2轮，每轮5条结果，百度百科质量最高",
        type=MemoryType.EPISODIC,
        summary="翡翠第一次搜索经验",
        parent_id=jade_node.id,
        tags=["翡翠", "搜索"],
        source_task=subtask1.id,
    )

    # 建立链接
    researcher.long_term.create_link(
        jade_node.id, search_exp.id,
        link_type="reminds_of", strength=0.7,
    )

    # 标记完成
    task_board.complete_task(subtask1.id, "成功搜索到10篇翡翠鉴别资料")
    task_board.update_task(task.id, progress=0.5)
    researcher.task_count += 1

    # 记忆巩固
    researcher.short_term.record("reflection", "这次搜索很顺利，百度百科质量确实高")
    await asyncio.sleep(0.3)

    # ── 阶段 3: 编辑整理 ──
    print("\n── 阶段 3: 编辑整理 ──")
    editor.working_memory.set_task(subtask2.id, {"goal": "整理和去重"})
    editor.status = AgentStatus.WORKING
    editor.short_term.record("action", "开始整理搜索到的资料")

    editor.short_term.record(
        "result",
        "已去重，10篇保留8篇，按科普/鉴定/市场分类",
        importance=0.5,
        task_id=subtask2.id,
    )

    task_board.complete_task(subtask2.id, "8篇资料已整理分类")
    task_board.update_task(task.id, progress=0.8)
    editor.task_count += 1

    # ── 阶段 4: 知识库管理员入库 ──
    print("\n── 阶段 4: 知识库管理员入库 ──")
    kb_admin.working_memory.set_task(subtask3.id, {"goal": "写入知识库"})
    kb_admin.status = AgentStatus.WORKING

    kb_tool = ToolRegistry.get("kb_write")
    result = await kb_tool.execute(
        title="翡翠鉴别方法汇总",
        content="# 翡翠鉴别方法\n\n## A货鉴别\n...\n\n## B货鉴别\n...",
    )
    kb_admin.tool_call_count += 1

    task_board.complete_task(subtask3.id, "8篇资料已入库")
    task_board.update_task(task.id, progress=1.0)
    task_board.complete_task(task.id, "全部完成")
    kb_admin.task_count += 1

    # ── 最终状态 ──
    print("\n" + "=" * 60)
    print("  📊 系统最终状态")
    print("=" * 60)

    status = agent_manager.get_status_summary()
    for d in status["details"]:
        print(f"  {d['name']:10s} | 工具调用: {d['tool_calls']:2d} | "
              f"完成任务: {d['tasks']:2d} | 技能: {d['skills']} | 记忆: ...")

    # 显示记忆树
    print("\n🌳 王研究员的记忆树（翡翠相关）:")
    tree = researcher.long_term.export_subtree("翡翠")
    print(tree)

    # 模拟技能挖掘
    print("\n🎯 技能系统:")
    await researcher._mine_skills()
    for s in researcher.skills.values():
        print(f"  - {s.name} (置信度: {s.confidence:.0%}, 使用: {s.use_count}次)")

    # 知识传承
    print("\n📤 知识导出:")
    exported = researcher.long_term.export_subtree("翡翠")
    print(f"  导出了 {len(exported)} 字的知识")
    print(f"  摘要: {exported[:100]}...")

    # 记忆检索
    print("\n🔍 联想检索（从'翡翠'出发）:")
    results = researcher.long_term.associative_recall("翡翠", depth=2, max_nodes=5)
    for r in results:
        print(f"  [{r.type.value}] {r.summary} (置信度: {r.confidence:.0%})")

    # 清理
    print("\n🔌 关闭系统...")
    for agent_id in list(agent_manager.agents.keys()):
        agent_manager.agents[agent_id].status = AgentStatus.OFFLINE
    print("✅ 已关闭\n")


def get_roles():
    return [
        RoleDefinition(
            role_id="manager", display_name="主管", icon="👔",
            description="负责分析任务、拆解分配、跟踪进度",
            responsibilities=["分析CEO下发的任务，拆解为子任务", "分配任务给合适的Agent", "跟踪进度"],
            limitations=["不直接执行具体工作"],
            default_tools=["send_message"], reports_to="ceo",
            task_acquisition="self_claim",
        ),
        RoleDefinition(
            role_id="researcher", display_name="研究员", icon="🔍",
            description="负责收集、搜索、提取信息",
            responsibilities=["根据任务要求搜索信息", "对收集到的信息做初步质量评估"],
            limitations=["不直接修改文件", "不写入知识库"],
            default_tools=["web_search", "send_message"],
            task_acquisition="both",
        ),
        RoleDefinition(
            role_id="editor", display_name="编辑", icon="✏️",
            description="负责整理、去重、分类、格式化信息",
            responsibilities=["对收集来的资料进行去重", "分类和标准化格式"],
            limitations=["不主动搜索信息", "不写入知识库"],
            default_tools=["send_message"],
            task_acquisition="assigned",
        ),
        RoleDefinition(
            role_id="knowledge_admin", display_name="知识库管理员", icon="📚",
            description="负责将处理好的信息写入知识库",
            responsibilities=["将标准化后的资料写入知识库"],
            limitations=["不主动搜索信息"],
            default_tools=["kb_write", "send_message"],
            task_acquisition="assigned",
        ),
    ]


class SimpleLLM(BaseLLMClient):
    """简单的 LLM 模拟（替换为真实 API）"""
    async def think(self, system_prompt="", context="", temperature=0.7, max_tokens=4096) -> str:
        return '{"action": "wait"}'
    async def chat(self, messages, temperature=0.7, max_tokens=4096) -> str:
        return "ok"


if __name__ == "__main__":
    asyncio.run(main())
