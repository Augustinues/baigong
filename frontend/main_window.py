"""百工 Baigong — PySide6 主窗口"""

import json
import os
import re
import time
import logging
from typing import Optional

from PySide6.QtCore import (
    Qt, QTimer, QThread, Signal, QSize,
)
from PySide6.QtGui import QFont, QColor, QPalette, QAction
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QListWidget, QListWidgetItem, QPushButton, QLabel,
    QTextBrowser, QLineEdit, QComboBox, QTabWidget, QScrollArea,
    QFrame, QProgressBar, QDialog, QDialogButtonBox, QFormLayout,
    QTextEdit, QCheckBox, QStackedWidget, QGridLayout, QSizePolicy,
    QMessageBox, QMenu,
)

from .api_client import api_get, api_post, api_patch, api_delete, SSEThread
from .theme_manager import THEMES, THEME_NAMES, build_qss

logger = logging.getLogger("baigong.frontend")

APP_NAME = "百工 Baigong"
VERSION = "0.8.0"


class ThemeDot(QPushButton):
    """主题色圆点按钮"""

    def __init__(self, theme_name: str, parent=None):
        super().__init__(parent)
        self.theme_name = theme_name
        theme = THEMES[theme_name]
        self.setFixedSize(20, 20)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(theme["name"])
        color = QColor(theme["dot"])
        self._color = color
        self._active = False
        self.setStyleSheet(
            f"""
            QPushButton {{
                background: {theme["dot"]};
                border: 2px solid transparent;
                border-radius: 10px;
            }}
            QPushButton:hover {{
                border: 2px solid {THEMES["indigo"]["vars"]["--ink"]};
            }}
            """
        )

    def set_active(self, active: bool):
        self._active = active
        ink = THEMES["indigo"]["vars"]["--ink"]
        border = f"2px solid {ink}" if active else "2px solid transparent"
        glow = (
            f"box-shadow: 0 0 8px {self._color.name()};"
            if active
            else ""
        )
        self.setStyleSheet(
            f"""
            QPushButton {{
                background: {self._color.name()};
                border: {border};
                border-radius: 10px;
                {glow}
            }}
            QPushButton:hover {{
                border: 2px solid {ink};
            }}
            """
        )


class AgentListWidget(QWidget):
    """左侧 Agent 列表"""

    agent_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._agents = {}
        self._selected_id = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标题
        hdr = QWidget()
        hdr_layout = QHBoxLayout(hdr)
        hdr_layout.setContentsMargins(14, 10, 14, 10)
        title = QLabel("🤖 Agent")
        title.setStyleSheet("font-size: 12px; font-weight: 600;")
        self._count = QLabel("0")
        self._count.setObjectName("dim")
        hdr_layout.addWidget(title)
        hdr_layout.addStretch()
        hdr_layout.addWidget(self._count)

        # 分隔线
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: var(--border);")

        # 列表
        self._list = QListWidget()
        self._list.itemClicked.connect(self._on_item_clicked)

        # 新建按钮
        btn_new = QPushButton("+ 新建 Agent")
        btn_new.setObjectName("btnGhost")
        btn_new.setCursor(Qt.PointingHandCursor)
        btn_new.setStyleSheet(
            "padding: 9px; border: 1.5px dashed palette(mid);"
            "border-radius: 8px; margin: 6px 8px; font-size: 12px;"
        )
        btn_new.clicked.connect(self._on_new_agent)

        layout.addWidget(hdr)
        layout.addWidget(sep)
        layout.addWidget(self._list, 1)
        layout.addWidget(btn_new)

    def set_agents(self, agents: list):
        self._agents = {a.get("id", ""): a for a in agents}
        self._count.setText(str(len(agents)))
        self._list.blockSignals(True)
        self._list.clear()
        for a in agents:
            item = QListWidgetItem()
            name = a.get("name", "?")
            role = a.get("role", "")
            status = a.get("status", "idle")
            temp = a.get("is_temporary", False)
            action = a.get("action", "等待任务...")
            status_icon = {
                "idle": "⚪",
                "thinking": "🤔",
                "acting": "🔧",
                "done": "✅",
                "error": "❌",
            }.get(status, "⚪")

            text = f"{status_icon} {name}"
            if temp:
                text += " 📎"
            if role:
                text += f"\n   {role}"
            text += f"\n   {action[:40]}"
            item.setText(text)
            item.setData(Qt.UserRole, a.get("id", ""))
            if a.get("id") == self._selected_id:
                item.setSelected(True)
            self._list.addItem(item)
        self._list.blockSignals(False)

    def _on_item_clicked(self, item):
        agent_id = item.data(Qt.UserRole)
        self._selected_id = agent_id
        self.agent_selected.emit(agent_id)

    def _on_new_agent(self):
        dlg = NewAgentDialog(self)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            if data and data.get("name"):
                api_post("/api/agents", data)

    def refresh_selection(self):
        """刷新选中的高亮"""
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.data(Qt.UserRole) == self._selected_id:
                self._list.setCurrentItem(item)
                break


class NewAgentDialog(QDialog):
    """新建 Agent 对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🆕 新建 Agent")
        self.setMinimumWidth(420)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._name = QLineEdit()
        self._name.setPlaceholderText("例如：王研究员")
        form.addRow("名字", self._name)

        self._role = QLineEdit()
        self._role.setPlaceholderText("例如：研究员、编辑、管理员")
        form.addRow("角色描述", self._role)

        self._prompt = QTextEdit()
        self._prompt.setPlaceholderText("定义 Agent 的人格和行为规则...")
        self._prompt.setMaximumHeight(100)
        form.addRow("System Prompt", self._prompt)

        self._provider = QComboBox()
        self._provider.addItem("使用全局", "")
        providers = api_get("/api/providers") or {}
        for k in providers:
            self._provider.addItem(k, k)
        form.addRow("LLM 提供商", self._provider)

        self._model = QComboBox()
        self._model.addItem("使用全局", "")
        form.addRow("模型", self._model)

        self._provider.currentIndexChanged.connect(self._on_provider_change)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.Ok).setText("✅ 创建")

        layout.addLayout(form)
        layout.addWidget(buttons)
        self.setStyleSheet(self.parent().styleSheet() if self.parent() else "")

    def _on_provider_change(self):
        self._model.clear()
        self._model.addItem("使用全局", "")
        p = self._provider.currentData()
        if p:
            providers = api_get("/api/providers") or {}
            models = providers.get(p, {}).get("models", [])
            for m in models:
                self._model.addItem(m, m)

    def get_data(self) -> dict:
        return {
            "name": self._name.text().strip(),
            "role": self._role.text().strip() or "worker",
            "system_prompt": self._prompt.toPlainText().strip(),
            "provider": self._provider.currentData() or "",
            "model": self._model.currentData() or "",
        }


class LogViewer(QWidget):
    """右侧日志面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        hdr = QWidget()
        hdr_layout = QHBoxLayout(hdr)
        hdr_layout.setContentsMargins(14, 10, 14, 10)
        title = QLabel("📜 日志")
        title.setStyleSheet("font-size: 12px; font-weight: 600;")
        self._count = QLabel("0")
        self._count.setObjectName("dim")
        hdr_layout.addWidget(title)
        hdr_layout.addStretch()
        hdr_layout.addWidget(self._count)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: var(--border);")

        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(False)
        self._browser.setMinimumWidth(200)

        layout.addWidget(hdr)
        layout.addWidget(sep)
        layout.addWidget(self._browser, 1)

    def set_logs(self, logs: list):
        self._count.setText(str(len(logs)))
        html_parts = []
        for entry in logs[-300:]:
            t = entry.get("t", "")
            msg = entry.get("msg", "")
            typ = entry.get("type", "")
            cls_map = {
                "act": "color: var(--accent);",
                "res": "color: var(--green);",
                "thk": "color: var(--amber); font-style: italic;",
                "mem": "color: var(--purple);",
                "err": "color: var(--red);",
            }
            style = cls_map.get(typ, "")
            if style:
                html_parts.append(
                    f'<div style="display:flex;gap:4px;padding:2px 6px;">'
                    f'<span style="color:var(--muted);flex-shrink:0">{self._esc(t)}</span>'
                    f'<span style="{style}">{self._esc(msg)}</span></div>'
                )
            else:
                html_parts.append(
                    f'<div style="display:flex;gap:4px;padding:2px 6px;">'
                    f'<span style="color:var(--muted);flex-shrink:0">{self._esc(t)}</span>'
                    f'<span>{self._esc(msg)}</span></div>'
                )
        if html_parts:
            self._browser.setHtml("".join(html_parts))
            self._browser.verticalScrollBar().setValue(
                self._browser.verticalScrollBar().maximum()
            )
        else:
            self._browser.setHtml(
                '<div style="text-align:center;padding:28px;color:var(--dim);font-size:12px">'
                "等待系统启动...</div>"
            )

    @staticmethod
    def _esc(s: str) -> str:
        if not s:
            return ""
        return (
            s.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )


class TaskCard(QFrame):
    """看板中的任务卡片"""

    def __init__(self, task: dict, parent=None):
        super().__init__(parent)
        self._task = task
        self._setup_ui()

    def _setup_ui(self):
        t = self._task
        status = t.get("status", "pending")
        goal = t.get("goal", "")
        assignee = t.get("assignee", "")
        result = t.get("result", "")
        progress = t.get("progress", 0) or 0

        border_color = {
            "pending": "var(--amber)",
            "in_progress": "var(--accent)",
            "assigned": "var(--accent)",
            "completed": "var(--green)",
            "done": "var(--green)",
            "failed": "var(--red)",
            "stuck": "var(--red)",
        }.get(status, "var(--amber)")

        self.setStyleSheet(
            f"""
            TaskCard {{
                background: var(--elevated);
                border: 1px solid var(--border);
                border-left: 3px solid {border_color};
                border-radius: 6px;
                padding: 9px 11px;
            }}
            TaskCard:hover {{
                border-color: var(--accent);
            }}
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(4)

        lbl_goal = QLabel(goal[:80] + ("..." if len(goal) > 80 else ""))
        lbl_goal.setWordWrap(True)
        lbl_goal.setStyleSheet("font-size: 12px; font-weight: 500;")
        layout.addWidget(lbl_goal)

        if assignee:
            lbl_asgn = QLabel(f"👤 <b style='color:var(--accent)'>{assignee}</b>")
            lbl_asgn.setTextFormat(Qt.RichText)
            lbl_asgn.setObjectName("dim")
            layout.addWidget(lbl_asgn)

        if result:
            lbl_res = QLabel(result[:80] + ("..." if len(result) > 80 else ""))
            lbl_res.setStyleSheet("color: var(--green); font-size: 11px;")
            lbl_res.setWordWrap(True)
            layout.addWidget(lbl_res)

        if progress > 0:
            bar = QProgressBar()
            bar.setValue(int(progress * 100))
            bar.setFixedHeight(4)
            layout.addWidget(bar)


class KanbanColumn(QWidget):
    """看板的一列"""

    def __init__(self, title: str, badge_cls: str, tasks: list, parent=None):
        super().__init__(parent)
        self._tasks = tasks
        self._setup_ui(title, badge_cls, tasks)

    def _setup_ui(self, title, badge_cls, tasks):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.setStyleSheet(
            f"""
            KanbanColumn {{
                background: var(--surface);
                border: 1px solid var(--border);
                border-radius: 10px;
            }}
            """
        )

        hdr = QWidget()
        hdr_layout = QHBoxLayout(hdr)
        hdr_layout.setContentsMargins(12, 8, 12, 8)
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("font-size: 11px; font-weight: 600;")
        hdr_layout.addWidget(lbl_title)
        hdr_layout.addStretch()
        badge = QLabel(str(len(tasks)))
        badge.setStyleSheet(
            f"""
            font-size: 10px; font-weight: 600;
            background: {badge_cls};
            border-radius: 10px;
            padding: 2px 8px;
            color: #fff;
            """
        )
        hdr_layout.addWidget(badge)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: var(--border);")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(6, 6, 6, 6)
        scroll_layout.setSpacing(5)
        scroll_layout.addStretch()

        if tasks:
            for task in tasks:
                card = TaskCard(task)
                scroll_layout.insertWidget(scroll_layout.count() - 1, card)
        else:
            empty = QLabel("暂无任务")
            empty.setAlignment(Qt.AlignCenter)
            empty.setObjectName("dim")
            empty.setStyleSheet("padding: 28px; font-size: 11px;")
            scroll_layout.insertWidget(scroll_layout.count() - 1, empty)

        scroll.setWidget(scroll_content)

        layout.addWidget(hdr)
        layout.addWidget(sep)
        layout.addWidget(scroll, 1)


class KanbanView(QWidget):
    """完整的看板视图"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._kanban_layout = QHBoxLayout(self)
        self._kanban_layout.setContentsMargins(10, 10, 10, 10)
        self._kanban_layout.setSpacing(10)

    def set_tasks(self, tasks: list):
        # 清除旧列
        while self._kanban_layout.count():
            item = self._kanban_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        cols = [
            ("待处理", "rgba(245,158,11,.8)", ["pending"]),
            ("进行中", "rgba(79,91,245,.8)", ["in_progress", "assigned"]),
            ("已完成", "rgba(16,185,129,.8)", ["completed", "done", "failed", "stuck", "cancelled"]),
        ]
        for title, badge_cls, states in cols:
            items = [t for t in tasks if t.get("status", "pending") in states]
            if not items and states[0] == "pending":
                items = [t for t in tasks if not t.get("status")]
            col = KanbanColumn(title, badge_cls, items)
            self._kanban_layout.addWidget(col, 1)


class AgentEditForm(QScrollArea):
    """Agent 编辑表单"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self._agent_id = None
        self._content = QWidget()
        self._setup_ui()
        self.setWidget(self._content)

    def _setup_ui(self):
        layout = QVBoxLayout(self._content)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        # 基本信息
        info_group = QWidget()
        info_layout = QVBoxLayout(info_group)
        info_layout.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel("📋 基本信息")
        lbl.setStyleSheet("font-size: 12px; font-weight: 600; color: var(--accent);")
        info_layout.addWidget(lbl)
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: var(--border);")
        info_layout.addWidget(sep)

        fg1 = QWidget()
        fg1_layout = QFormLayout(fg1)
        fg1_layout.setContentsMargins(0, 0, 0, 0)
        self._e_name = QLineEdit()
        fg1_layout.addRow("名字", self._e_name)
        self._e_role = QLineEdit()
        self._e_role.setPlaceholderText("例如：研究员、编辑、管理员")
        fg1_layout.addRow("角色描述", self._e_role)
        info_layout.addWidget(fg1)
        layout.addWidget(info_group)

        # Prompt
        prompt_group = QWidget()
        prompt_layout = QVBoxLayout(prompt_group)
        prompt_layout.setContentsMargins(0, 0, 0, 0)
        lbl2 = QLabel("🧠 人设 / System Prompt")
        lbl2.setStyleSheet("font-size: 12px; font-weight: 600; color: var(--accent);")
        prompt_layout.addWidget(lbl2)
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet("color: var(--border);")
        prompt_layout.addWidget(sep2)
        self._e_prompt = QTextEdit()
        self._e_prompt.setPlaceholderText("定义 Agent 的人格、行为规则...")
        self._e_prompt.setMaximumHeight(100)
        prompt_layout.addWidget(self._e_prompt)
        layout.addWidget(prompt_group)

        # LLM 配置
        llm_group = QWidget()
        llm_layout = QVBoxLayout(llm_group)
        llm_layout.setContentsMargins(0, 0, 0, 0)
        lbl3 = QLabel("🔌 LLM 配置")
        lbl3.setStyleSheet("font-size: 12px; font-weight: 600; color: var(--accent);")
        llm_layout.addWidget(lbl3)
        sep3 = QFrame()
        sep3.setFrameShape(QFrame.HLine)
        sep3.setStyleSheet("color: var(--border);")
        llm_layout.addWidget(sep3)

        fg2 = QWidget()
        fg2_layout = QFormLayout(fg2)
        fg2_layout.setContentsMargins(0, 0, 0, 0)
        self._e_provider = QComboBox()
        self._e_provider.addItem("使用全局", "")
        providers = api_get("/api/providers") or {}
        for k in providers:
            self._e_provider.addItem(k, k)
        self._e_provider.currentIndexChanged.connect(self._on_provider_change)
        fg2_layout.addRow("提供商", self._e_provider)

        self._e_model = QComboBox()
        self._e_model.addItem("使用全局", "")
        fg2_layout.addRow("模型", self._e_model)

        self._e_api_key = QLineEdit()
        self._e_api_key.setEchoMode(QLineEdit.Password)
        self._e_api_key.setPlaceholderText("留空用全局")
        fg2_layout.addRow("API Key", self._e_api_key)

        self._e_base_url = QLineEdit()
        self._e_base_url.setPlaceholderText("留空用默认")
        fg2_layout.addRow("API 地址", self._e_base_url)

        llm_layout.addWidget(fg2)
        layout.addWidget(llm_group)

        # 工具
        tool_group = QWidget()
        tool_layout = QVBoxLayout(tool_group)
        tool_layout.setContentsMargins(0, 0, 0, 0)
        lbl4 = QLabel("🔧 工具")
        lbl4.setStyleSheet("font-size: 12px; font-weight: 600; color: var(--accent);")
        tool_layout.addWidget(lbl4)
        sep4 = QFrame()
        sep4.setFrameShape(QFrame.HLine)
        sep4.setStyleSheet("color: var(--border);")
        tool_layout.addWidget(sep4)

        self._tool_grid = QWidget()
        self._tool_grid_layout = QHBoxLayout(self._tool_grid)
        self._tool_grid_layout.setContentsMargins(0, 0, 0, 0)
        self._tool_grid_layout.setSpacing(5)
        self._tool_grid_layout.addStretch()
        tool_layout.addWidget(self._tool_grid)
        layout.addWidget(tool_group)

        # 按钮
        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        self._btn_delete = QPushButton("🗑 删除")
        self._btn_delete.setObjectName("btnDanger")
        self._btn_delete.clicked.connect(self._on_delete)
        self._btn_save = QPushButton("💾 保存更改")
        self._btn_save.setObjectName("btnPrimary")
        self._btn_save.clicked.connect(self._on_save)
        btn_layout.addStretch()
        btn_layout.addWidget(self._btn_delete)
        btn_layout.addWidget(self._btn_save)
        layout.addWidget(btn_row)

        layout.addStretch()

    def load_agent(self, agent: dict):
        """加载 Agent 数据到表单"""
        if not agent:
            return
        self._agent_id = agent.get("id")
        self._e_name.setText(agent.get("name", ""))
        self._e_role.setText(agent.get("role", ""))
        self._e_prompt.setPlainText(agent.get("system_prompt", ""))
        self._e_api_key.setText(agent.get("api_key", ""))
        self._e_base_url.setText(agent.get("base_url", ""))

        prov = agent.get("provider", "")
        idx = self._e_provider.findData(prov)
        if idx >= 0:
            self._e_provider.setCurrentIndex(idx)
        else:
            self._e_provider.setCurrentIndex(0)

        # 工具复选框
        tools = agent.get("tools", [])
        all_tools = ["web_search", "web_extract", "file_read", "file_write", "code_exec"]
        self._tool_checks = {}
        while self._tool_grid_layout.count() > 1:
            item = self._tool_grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for t in all_tools:
            cb = QCheckBox(t)
            cb.setChecked(t in tools)
            cb.setStyleSheet(
                f"""
                QCheckBox {{
                    padding: 4px 10px;
                    border: 1px solid var(--border);
                    border-radius: 999px;
                    font-size: 11px;
                }}
                QCheckBox:checked {{
                    border-color: var(--accent);
                    background: var(--accent-subtle);
                    color: var(--accent);
                }}
                """
            )
            self._tool_checks[t] = cb
            self._tool_grid_layout.insertWidget(
                self._tool_grid_layout.count() - 1, cb
            )

    def _on_provider_change(self):
        self._e_model.clear()
        self._e_model.addItem("使用全局", "")
        p = self._e_provider.currentData()
        if p:
            providers = api_get("/api/providers") or {}
            models = providers.get(p, {}).get("models", [])
            for m in models:
                self._e_model.addItem(m, m)

    def _on_save(self):
        if not self._agent_id:
            return
        body = {}
        name = self._e_name.text().strip()
        if name:
            body["name"] = name
        role = self._e_role.text().strip()
        if role:
            body["role"] = role
        prompt = self._e_prompt.toPlainText().strip()
        if prompt:
            body["system_prompt"] = prompt
        tools = [k for k, cb in self._tool_checks.items() if cb.isChecked()]
        body["tools"] = tools
        body["provider"] = self._e_provider.currentData() or None
        body["model"] = self._e_model.currentData() or None
        body["api_key"] = self._e_api_key.text().strip() or None
        body["base_url"] = self._e_base_url.text().strip() or None

        res = api_patch(f"/api/agents/{self._agent_id}", body)
        if res.get("ok"):
            if self._parent_window:
                self._parent_window.set_status("✅ 已保存")
                self._parent_window.refresh_state()
        else:
            if self._parent_window:
                self._parent_window.set_status("❌ " + (res.get("error") or "保存失败"))

    def _on_delete(self):
        if not self._agent_id:
            return
        reply = QMessageBox.question(
            self, "确认删除", "确定删除这个 Agent？",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            res = api_delete(f"/api/agents/{self._agent_id}")
            if res.get("ok"):
                if self._parent_window:
                    self._parent_window.set_status("✅ Agent 已删除")
                    self._parent_window.refresh_state()
                    self._parent_window.clear_edit()
            else:
                if self._parent_window:
                    self._parent_window.set_status("❌ " + (res.get("error") or "删除失败"))

    _parent_window: "BaigongMainWindow" = None


class UpdateDialog(QDialog):
    """版本更新对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔄 版本与更新")
        self.setMinimumWidth(450)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 版本信息
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(0, 0, 0, 0)

        self._lbl_current = QLabel(f"当前版本: v{VERSION}")
        info_layout.addWidget(self._lbl_current)
        self._lbl_latest = QLabel("最新版本: -")
        info_layout.addWidget(self._lbl_latest)
        self._lbl_mode = QLabel("运行模式: -")
        info_layout.addWidget(self._lbl_mode)

        layout.addWidget(info_widget)

        # 状态
        self._status = QLabel("")
        self._status.setWordWrap(True)
        self._status.setStyleSheet(
            "padding: 10px 12px; background: var(--elevated);"
            "border-radius: 6px; min-height: 24px;"
        )
        layout.addWidget(self._status)

        # 按钮
        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        self._btn_check = QPushButton("🔍 检查更新")
        self._btn_check.setObjectName("btnSuccess")
        self._btn_check.clicked.connect(self._check)
        self._btn_download = QPushButton("⬇️ 下载更新")
        self._btn_download.setObjectName("btnPrimary")
        self._btn_download.clicked.connect(self._download)
        self._btn_download.setVisible(False)
        btn_layout.addWidget(self._btn_check)
        btn_layout.addWidget(self._btn_download)
        btn_layout.addStretch()
        layout.addWidget(btn_row)

        # 更新内容预览
        self._preview = QTextBrowser()
        self._preview.setMaximumHeight(120)
        self._preview.setObjectName("muted")
        layout.addWidget(self._preview)

        self.setStyleSheet(self.parent().styleSheet() if self.parent() else "")

    def _check(self):
        self._status.setText("⏳ 检查中...")
        self._btn_download.setVisible(False)
        res = api_get("/api/update/check")
        self._lbl_current.setText(f"当前版本: v{res.get('current', VERSION)}")
        self._lbl_latest.setText(f"最新版本: v{res.get('latest', '-')}")
        self._lbl_mode.setText(f"运行模式: {res.get('mode', '?')}")

        if res.get("has_update"):
            self._btn_download.setVisible(True)
            self._status.setText(f"✅ 有新版本 v{res.get('latest')} 可用！")
            body = res.get("body", "")
            if body:
                self._preview.setPlainText(body[:300])
        else:
            err = res.get("error")
            if err:
                self._status.setText(f"⚠️ {err}")
            else:
                self._status.setText("✅ 已是最新")

    def _download(self):
        self._btn_download.setEnabled(False)
        self._status.setText("⏳ 正在下载更新...")
        res = api_post("/api/update/apply")
        if res.get("ok"):
            self._status.setText(res.get("message", "下载完成"))
            if res.get("auto_install"):
                self._preview.setPlainText("⏳ 正在自动安装...新版将自动替换并重启应用")
                self._btn_download.setVisible(False)
        else:
            self._status.setText("❌ " + (res.get("error") or "下载失败"))
            self._btn_download.setEnabled(True)


class WorkflowBar(QWidget):
    """工作流状态条"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(12, 6, 12, 6)
        self._layout.setSpacing(4)

    def set_agents(self, agents: list):
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for a in agents:
            status = a.get("status", "idle")
            name = a.get("name", "?")
            action = a.get("action", "")
            current_task = a.get("current_task", "")

            bg = {
                "thinking": "var(--accent-subtle)",
                "acting": "var(--accent-subtle)",
                "done": "rgba(16,185,129,.12)",
            }.get(status, "var(--elevated)")

            border = {
                "thinking": "var(--accent)",
                "acting": "var(--accent)",
                "done": "rgba(16,185,129,.2)",
            }.get(status, "transparent")

            icon = {
                "thinking": "🤔",
                "acting": "🔧",
                "done": "✅",
                "idle": "⏳",
            }.get(status, "⏳")

            desc = current_task or action or ""
            if desc:
                text = f"{icon} {name} {desc[:20]}"
            else:
                text = f"{icon} {name}"

            lbl = QLabel(text)
            lbl.setStyleSheet(
                f"""
                background: {bg};
                border: 1px solid {border};
                border-radius: 999px;
                padding: 3px 10px;
                font-size: 10px;
                """
            )
            self._layout.addWidget(lbl)
        self._layout.addStretch()


class BaigongMainWindow(QMainWindow):
    """百工 Baigong 主窗口"""

    # 信号：用于 SSE 线程安全地传递数据到主线程
    state_updated = Signal(dict)
    start_result = Signal(object)  # start 结果，主线程处理 UI

    def __init__(self):
        super().__init__()
        self._state = {}
        self._current_theme = "indigo"
        self._editing_agent_id = None
        self._sse_thread: Optional[SSEThread] = None

        self.setWindowTitle(f"{APP_NAME} v{VERSION}")
        self.setMinimumSize(1024, 700)
        self.resize(1280, 800)

        self._setup_ui()
        self._apply_theme("indigo")
        # SSE 信号 → 主线程渲染
        self.state_updated.connect(self._render)
        self.start_result.connect(self._on_start_result)
        self._start_polling()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── 顶部栏 ──
        header = QWidget()
        header.setFixedHeight(48)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 0, 18, 0)
        header_layout.setSpacing(14)

        title = QLabel("🏮 百工")
        title.setStyleSheet("font-size: 16px; font-weight: 700;")
        ver = QLabel(f"<span style='font-weight:400;color:var(--dim);font-size:12px;'>Baigong</span>")
        ver.setTextFormat(Qt.RichText)
        header_layout.addWidget(title)
        header_layout.addWidget(ver)

        self._status_label = QLabel("⏳ 加载...")
        self._status_label.setObjectName("dim")
        self._status_label.setStyleSheet("font-size: 11px;")
        header_layout.addWidget(self._status_label)

        header_layout.addStretch()

        self._btn_start = QPushButton("▶ 启动")
        self._btn_start.setObjectName("btnPrimary")
        self._btn_start.clicked.connect(self._on_start)
        header_layout.addWidget(self._btn_start)

        self._btn_stop = QPushButton("⏹ 停止")
        self._btn_stop.setObjectName("btnDanger")
        self._btn_stop.setVisible(False)
        self._btn_stop.clicked.connect(self._on_stop)
        header_layout.addWidget(self._btn_stop)

        # 主题选择器
        self._theme_dots = []
        for tn in THEME_NAMES:
            dot = ThemeDot(tn)
            dot.clicked.connect(lambda checked, n=tn: self._set_theme(n))
            self._theme_dots.append(dot)
            header_layout.addWidget(dot)

        # 任务计数
        self._task_badge = QLabel("")
        self._task_badge.setObjectName("dim")
        self._task_badge.setStyleSheet("font-size: 11px;")
        header_layout.addWidget(self._task_badge)

        # 更新按钮
        btn_update = QPushButton("⚙️")
        btn_update.setFixedSize(36, 28)
        btn_update.clicked.connect(self._show_update)
        header_layout.addWidget(btn_update)

        main_layout.addWidget(header)

        # ── 任务输入栏 ──
        task_bar = QWidget()
        task_bar.setFixedHeight(44)
        task_layout = QHBoxLayout(task_bar)
        task_layout.setContentsMargins(18, 0, 18, 0)
        task_layout.setSpacing(8)

        self._task_input = QLineEdit()
        self._task_input.setPlaceholderText("给主管下发任务... 例如：收集10篇翡翠鉴别资料并入库")
        self._task_input.returnPressed.connect(self._submit_task)
        task_layout.addWidget(self._task_input, 1)

        self._btn_submit = QPushButton("📤 下发")
        self._btn_submit.setObjectName("btnPrimary")
        self._btn_submit.clicked.connect(self._submit_task)
        task_layout.addWidget(self._btn_submit)

        self._task_agent = QComboBox()
        self._task_agent.addItem("自动分配（主管）", "")
        self._task_agent.setMinimumWidth(180)
        task_layout.addWidget(self._task_agent)

        main_layout.addWidget(task_bar)

        # ── 三栏布局 ──
        splitter = QSplitter(Qt.Horizontal)

        # 左栏: Agent 列表
        self._agent_list = AgentListWidget()
        self._agent_list.agent_selected.connect(self._on_agent_selected)
        self._agent_list.setMinimumWidth(200)
        self._agent_list.setMaximumWidth(350)
        splitter.addWidget(self._agent_list)

        # 中栏: 看板 + 编辑
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)

        # 标签页
        self._tab_widget = QTabWidget()
        self._tab_widget.setDocumentMode(True)

        # 工作流条
        self._wf_bar = WorkflowBar()

        # 看板视图
        self._kanban = KanbanView()

        kanban_container = QWidget()
        kanban_layout = QVBoxLayout(kanban_container)
        kanban_layout.setContentsMargins(0, 0, 0, 0)
        kanban_layout.setSpacing(0)
        kanban_layout.addWidget(self._wf_bar)
        kanban_layout.addWidget(self._kanban, 1)
        self._tab_widget.addTab(kanban_container, "📋 任务看板")

        # 编辑视图
        self._edit_form = AgentEditForm()
        self._edit_form._parent_window = self
        self._tab_widget.addTab(self._edit_form, "✏️ 编辑 Agent")
        self._tab_widget.setTabVisible(1, False)

        self._tab_widget.currentChanged.connect(self._on_tab_changed)

        center_layout.addWidget(self._tab_widget)
        splitter.addWidget(center_widget)

        # 右栏: 日志
        self._log_viewer = LogViewer()
        self._log_viewer.setMinimumWidth(200)
        self._log_viewer.setMaximumWidth(350)
        splitter.addWidget(self._log_viewer)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([250, 700, 300])

        main_layout.addWidget(splitter, 1)

    # ── 主题 ──

    def _set_theme(self, name: str):
        self._current_theme = name
        self._apply_theme(name)
        for dot in self._theme_dots:
            dot.set_active(dot.theme_name == name)
        api_post("/api/theme", {"accent": name})

    def _apply_theme(self, name: str):
        theme = THEMES.get(name, THEMES["indigo"])
        qss = build_qss(theme["vars"])
        self.setStyleSheet(qss)

    # ── 控制 ──

    def _on_start(self):
        self._btn_start.setEnabled(False)
        self.set_status("⏳ 启动中...")
        # 后台线程启动，不阻塞 UI
        import threading as _t
        def _do_start():
            res = api_post("/api/start")
            self.start_result.emit(res)  # 信号 → 主线程处理 UI
        _t.Thread(target=_do_start, daemon=True).start()

    def _on_start_result(self, res):
        """主线程：处理启动结果"""
        if isinstance(res, dict) and res.get("ok"):
            self._btn_start.setVisible(False)
            self._btn_stop.setVisible(True)
            self.set_status("✅ 运行中")
            self._start_sse()
            self.refresh_state()
        else:
            err = (res or {}).get("error") or "启动失败"
            self.set_status("❌ " + err)
            self._btn_start.setEnabled(True)

    def _on_stop(self):
        api_post("/api/stop")
        self._btn_stop.setVisible(False)
        self._btn_start.setVisible(True)
        self._btn_start.setEnabled(True)
        self.set_status("⏹ 已停止")
        if self._sse_thread:
            self._sse_thread.stop()
            self._sse_thread = None

    def _submit_task(self):
        goal = self._task_input.text().strip()
        if not goal:
            return
        self._task_input.clear()
        agent_id = self._task_agent.currentData() or ""
        res = api_post("/api/task", {"goal": goal, "agent_id": agent_id})
        if res.get("ok"):
            self.set_status("✅ 任务已下发")
        else:
            self.set_status("❌ " + (res.get("error") or "提交失败"))

    # ── Agent ──

    def _on_agent_selected(self, agent_id: str):
        self._editing_agent_id = agent_id
        agent = api_get(f"/api/agents/{agent_id}")
        if agent and agent.get("id"):
            self._tab_widget.setTabVisible(1, True)
            tab_idx = self._tab_widget.indexOf(self._edit_form)
            self._tab_widget.setTabText(tab_idx, f"✏️ {agent.get('name', '?')}")
            self._edit_form.load_agent(agent)
            self._tab_widget.setCurrentWidget(self._edit_form)

    def clear_edit(self):
        self._editing_agent_id = None
        self._tab_widget.setTabVisible(1, False)
        self._tab_widget.setCurrentIndex(0)

    def _on_tab_changed(self, index: int):
        if index == 0:  # 切回看板
            self._editing_agent_id = None

    def refresh_state(self):
        state = api_get("/api/state")
        if state and state.get("agents"):
            self._render(state)

    # ── 更新 ──

    def _show_update(self):
        dlg = UpdateDialog(self)
        dlg.exec()

    # ── SSE ──

    def _start_sse(self):
        if self._sse_thread:
            self._sse_thread.stop()
        self._sse_thread = SSEThread(
            "/api/events", self._on_sse_data, interval=2.0
        )
        self._sse_thread.start()

    def _on_sse_data(self, data: dict):
        if data:
            self.state_updated.emit(data)  # 信号 → 主线程安全渲染

    # ── 轮询 ──

    def _start_polling(self):
        self._timer = QTimer()
        self._timer.timeout.connect(self._poll)
        self._timer.start(3000)

    def _poll(self):
        state = api_get("/api/state")
        if state and state.get("agents"):
            self._render(state)

    # ── 渲染 ──

    def _render(self, state: dict):
        self._state = state
        agents = state.get("agents", [])
        tasks = state.get("tasks", [])
        logs = state.get("logs", [])

        self._agent_list.set_agents(agents)
        self._log_viewer.set_logs(logs)
        self._kanban.set_tasks(tasks)
        self._wf_bar.set_agents(agents)

        self._task_badge.setText(f"📋 {len(tasks)}")

        # 更新 Agent 选择器
        current = self._task_agent.currentData()
        self._task_agent.blockSignals(True)
        self._task_agent.clear()
        self._task_agent.addItem("自动分配（主管）", "")
        for a in agents:
            if a.get("status") in ("idle", "done", None):
                self._task_agent.addItem(a.get("name", "?"), a.get("id", ""))
        idx = self._task_agent.findData(current)
        if idx >= 0:
            self._task_agent.setCurrentIndex(idx)
        self._task_agent.blockSignals(False)

        # 如果正在编辑某个 Agent，刷新表单
        if self._editing_agent_id and agents:
            agent = next(
                (a for a in agents if a.get("id") == self._editing_agent_id), None
            )
            if agent:
                self._edit_form.load_agent(agent)

    def set_status(self, text: str):
        self._status_label.setText(text)
