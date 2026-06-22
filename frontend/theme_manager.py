"""百工主题系统 — 7 套完整 QSS 主题"""

THEMES = {
    "indigo": {
        "name": "靛蓝",
        "dot": "#4f5bf5",
        "vars": {
            "--canvas": "#0d1230",
            "--surface": "#161b3d",
            "--elevated": "#1e2550",
            "--border": "#2a3270",
            "--ink": "#e0e6ff",
            "--dim": "#8890c0",
            "--muted": "#5a6390",
            "--accent": "#4f5bf5",
            "--accent-hover": "#3f4ae0",
            "--accent-subtle": "rgba(79,91,245,.15)",
            "--green": "#10b981",
            "--red": "#ef4444",
            "--amber": "#f59e0b",
            "--purple": "#8b5cf6",
            "--radius": "6px",
            "--radius-card": "10px",
        },
    },
    "amber": {
        "name": "琥珀",
        "dot": "#f59e0b",
        "vars": {
            "--canvas": "#1a1108",
            "--surface": "#2a1c0e",
            "--elevated": "#3d2916",
            "--border": "#54381e",
            "--ink": "#f5e6d0",
            "--dim": "#b8956a",
            "--muted": "#8a6d48",
            "--accent": "#f59e0b",
            "--accent-hover": "#d48a08",
            "--accent-subtle": "rgba(245,158,11,.18)",
            "--green": "#10b981",
            "--red": "#ef4444",
            "--amber": "#f59e0b",
            "--purple": "#8b5cf6",
            "--radius": "6px",
            "--radius-card": "10px",
        },
    },
    "jade": {
        "name": "翡翠",
        "dot": "#10b981",
        "vars": {
            "--canvas": "#0a1a12",
            "--surface": "#10281c",
            "--elevated": "#193a28",
            "--border": "#234d37",
            "--ink": "#d4f0e0",
            "--dim": "#7ab894",
            "--muted": "#55906e",
            "--accent": "#10b981",
            "--accent-hover": "#059669",
            "--accent-subtle": "rgba(16,185,129,.18)",
            "--green": "#10b981",
            "--red": "#ef4444",
            "--amber": "#f59e0b",
            "--purple": "#8b5cf6",
            "--radius": "6px",
            "--radius-card": "10px",
        },
    },
    "twilight": {
        "name": "暮紫",
        "dot": "#a855f7",
        "vars": {
            "--canvas": "#140d22",
            "--surface": "#1f1535",
            "--elevated": "#2c1f47",
            "--border": "#3c2a5c",
            "--ink": "#e8ddf5",
            "--dim": "#b095d0",
            "--muted": "#8870a8",
            "--accent": "#a855f7",
            "--accent-hover": "#9333ea",
            "--accent-subtle": "rgba(168,85,247,.18)",
            "--green": "#10b981",
            "--red": "#ef4444",
            "--amber": "#f59e0b",
            "--purple": "#8b5cf6",
            "--radius": "6px",
            "--radius-card": "10px",
        },
    },
    "rose": {
        "name": "玫瑰",
        "dot": "#ec4899",
        "vars": {
            "--canvas": "#1a0a10",
            "--surface": "#2a101e",
            "--elevated": "#3d192c",
            "--border": "#54233c",
            "--ink": "#f5e0ea",
            "--dim": "#c088a8",
            "--muted": "#a06888",
            "--accent": "#ec4899",
            "--accent-hover": "#db2777",
            "--accent-subtle": "rgba(236,72,153,.18)",
            "--green": "#10b981",
            "--red": "#ef4444",
            "--amber": "#f59e0b",
            "--purple": "#8b5cf6",
            "--radius": "6px",
            "--radius-card": "10px",
        },
    },
    "midnight": {
        "name": "极夜",
        "dot": "#38bdf8",
        "vars": {
            "--canvas": "#050610",
            "--surface": "#0a0c1a",
            "--elevated": "#101226",
            "--border": "#181b36",
            "--ink": "#c8ccd8",
            "--dim": "#5a5e78",
            "--muted": "#3d4158",
            "--accent": "#38bdf8",
            "--accent-hover": "#0ea5e9",
            "--accent-subtle": "rgba(56,189,248,.18)",
            "--green": "#10b981",
            "--red": "#ef4444",
            "--amber": "#f59e0b",
            "--purple": "#8b5cf6",
            "--radius": "6px",
            "--radius-card": "10px",
        },
    },
    "daylight": {
        "name": "白昼",
        "dot": "#4f5bf5",
        "vars": {
            "--canvas": "#f0f4ff",
            "--surface": "#ffffff",
            "--elevated": "#e6edf8",
            "--border": "#cdd9e8",
            "--ink": "#0a1028",
            "--dim": "#5a6890",
            "--muted": "#8895b8",
            "--accent": "#4f5bf5",
            "--accent-hover": "#3f4ae0",
            "--accent-subtle": "rgba(79,91,245,.1)",
            "--green": "#10b981",
            "--red": "#ef4444",
            "--amber": "#f59e0b",
            "--purple": "#8b5cf6",
            "--radius": "6px",
            "--radius-card": "10px",
        },
    },
}

THEME_NAMES = list(THEMES.keys())


def build_qss(theme_vars: dict) -> str:
    """根据主题变量生成 QSS 样式表"""
    v = theme_vars
    return f"""
    /* ── 全局 ── */
    QMainWindow, QDialog {{
        background: {v["--canvas"]};
        color: {v["--ink"]};
        font-family: -apple-system, "PingFang SC", "SF Pro Text", Helvetica, sans-serif;
        font-size: 13px;
    }}
    QWidget {{
        background: transparent;
        color: {v["--ink"]};
        font-family: -apple-system, "PingFang SC", "SF Pro Text", Helvetica, sans-serif;
        font-size: 13px;
    }}

    /* ── 按钮 ── */
    QPushButton {{
        padding: 6px 16px;
        border: none;
        border-radius: {v["--radius"]};
        font-size: 11px;
        font-weight: 600;
        background: {v["--elevated"]};
        color: {v["--ink"]};
        border: 1px solid {v["--border"]};
    }}
    QPushButton:hover {{
        background: {v["--surface"]};
        border-color: {v["--accent"]};
    }}
    QPushButton:pressed {{
        background: {v["--elevated"]};
    }}
    QPushButton:disabled {{
        opacity: 0.35;
    }}
    QPushButton#btnPrimary {{
        background: {v["--accent"]};
        color: #fff;
        border: none;
    }}
    QPushButton#btnPrimary:hover {{
        background: {v["--accent-hover"]};
    }}
    QPushButton#btnDanger {{
        background: {v["--red"]};
        color: #fff;
        border: none;
    }}
    QPushButton#btnSuccess {{
        background: {v["--green"]};
        color: #fff;
        border: none;
    }}
    QPushButton#btnGhost {{
        background: transparent;
        color: {v["--dim"]};
        border: 1px solid {v["--border"]};
    }}
    QPushButton#btnGhost:hover {{
        color: {v["--ink"]};
        border-color: {v["--accent"]};
    }}

    /* ── 输入框 ── */
    QLineEdit, QTextEdit, QPlainTextEdit {{
        padding: 7px 10px;
        background: {v["--elevated"]};
        border: 1px solid {v["--border"]};
        border-radius: {v["--radius"]};
        color: {v["--ink"]};
        font-size: 13px;
        selection-background-color: {v["--accent"]};
        selection-color: #fff;
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
        border-color: {v["--accent"]};
    }}
    QComboBox {{
        padding: 6px 10px;
        background: {v["--elevated"]};
        border: 1px solid {v["--border"]};
        border-radius: {v["--radius"]};
        color: {v["--ink"]};
        font-size: 12px;
        min-height: 20px;
    }}
    QComboBox:hover {{
        border-color: {v["--accent"]};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}
    QComboBox QAbstractItemView {{
        background: {v["--surface"]};
        color: {v["--ink"]};
        border: 1px solid {v["--border"]};
        selection-background-color: {v["--accent-subtle"]};
        selection-color: {v["--ink"]};
        outline: none;
    }}

    /* ── 列表 ── */
    QListWidget {{
        background: transparent;
        border: none;
        outline: none;
        font-size: 12px;
    }}
    QListWidget::item {{
        padding: 8px 10px;
        border-radius: {v["--radius-card"]};
        margin: 2px 6px;
    }}
    QListWidget::item:hover {{
        background: {v["--elevated"]};
    }}
    QListWidget::item:selected {{
        background: {v["--accent-subtle"]};
        border: 1px solid {v["--accent"]};
    }}

    /* ── 标签页 ── */
    QTabWidget::pane {{
        background: {v["--surface"]};
        border: none;
        border-top: 1px solid {v["--border"]};
    }}
    QTabBar::tab {{
        padding: 9px 18px;
        font-size: 12px;
        font-weight: 500;
        color: {v["--dim"]};
        border-bottom: 2px solid transparent;
        background: transparent;
    }}
    QTabBar::tab:hover {{
        color: {v["--ink"]};
    }}
    QTabBar::tab:selected {{
        color: {v["--accent"]};
        border-bottom: 2px solid {v["--accent"]};
    }}

    /* ── 进度条 ── */
    QProgressBar {{
        background: {v["--elevated"]};
        border: none;
        border-radius: 3px;
        height: 4px;
        text-align: center;
        font-size: 9px;
    }}
    QProgressBar::chunk {{
        background: {v["--accent"]};
        border-radius: 3px;
    }}

    /* ── 滚动条 ── */
    QScrollBar:vertical {{
        width: 6px;
        background: transparent;
    }}
    QScrollBar::handle:vertical {{
        background: {v["--border"]};
        border-radius: 3px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {v["--accent"]};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QScrollBar:horizontal {{
        height: 6px;
        background: transparent;
    }}
    QScrollBar::handle:horizontal {{
        background: {v["--border"]};
        border-radius: 3px;
        min-width: 30px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {v["--accent"]};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0;
    }}

    /* ── 标签 ── */
    QLabel {{
        color: {v["--ink"]};
        background: transparent;
    }}
    QLabel#dim {{
        color: {v["--dim"]};
        font-size: 11px;
    }}
    QLabel#muted {{
        color: {v["--muted"]};
        font-size: 10px;
    }}
    QLabel#accent {{
        color: {v["--accent"]};
        font-weight: 600;
    }}

    /* ── 分组框 ── */
    QGroupBox {{
        font-size: 12px;
        font-weight: 600;
        color: {v["--accent"]};
        border: none;
        padding-top: 16px;
        margin-top: 8px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 0px;
        padding: 0 4px;
    }}

    /* ── 分割器 ── */
    QSplitter::handle {{
        background: {v["--border"]};
        width: 1px;
    }}

    /* ── 文本浏览 ── */
    QTextBrowser {{
        background: transparent;
        color: {v["--ink"]};
        border: none;
        font-size: 11px;
        font-family: "SF Mono", Menlo, Monaco, Consolas, monospace;
        selection-background-color: {v["--accent"]};
        selection-color: #fff;
    }}

    QScrollArea {{
        border: none;
        background: transparent;
    }}
    """
