# Release Notes — v0.8.0

## 🎯 纯 Python 重写！不再依赖 HTML/JS/WKWebView

**这是百工历史上最大的架构变革。** 整个桌面 GUI 从 pywebview + HTML/CSS/JS 全面迁移到 **Pure Python PySide6**。

### 为什么这么做？
- 解决了**启动卡在加载界面**的顽疾（WKWebView 渲染 HTML 的兼容性问题）
- 不再需要嵌入式 Web 服务器来渲染 UI
- 原生 macOS 控件 = 更快的启动、更流畅的交互
- Python 开发者可以直接理解、修改全部 UI 代码

### 不变的
- 后端 FastAPI 服务器不变（所有 API 接口兼容）
- 功能一个不少：Agent 列表/编辑、任务看板、日志面板、7 套主题色、热更新
- 三栏布局保持一致的操作体验

### 变化了什么
| 方面 | 旧版 | v0.8.0 |
|------|------|--------|
| 前端技术 | HTML + CSS + JavaScript (482 行) | **纯 Python PySide6** (1743 行) |
| 窗口引擎 | pywebview (WKWebView) | **原生 Qt Widgets** |
| 渲染方式 | 浏览器渲染 HTML | Qt 引擎直接绘制控件 |
| 主题系统 | CSS 变量 + JS 切换 | **QSS 动态样式表** |
| 稳定性 | 受 WebView 兼容性影响 | **与系统 Qt 框架一致** |
| 启动问题 | 经常卡加载页面 | ✅ 已修复 |
| 构建体积 | 含浏览器引擎 | 稍大（含 Qt 库）|

### 更新方式
- **全新安装**：下载 DMG 安装到 /Applications
- **从旧版升级**：覆盖安装即可（注意：热更新路径已变更，建议直接下载新版 DMG）
- Windows / Linux 支持：框架层面兼容，后续通过社区 PR 适配

### 下载
[⬇️ Baigong-v0.8.0.dmg](https://github.com/Augustinues/baigong/releases/download/v0.8.0/Baigong-v0.8.0.dmg)

### 致谢
感谢所有用户反馈的启动卡死问题，这次直接换掉了整个前端架构。
