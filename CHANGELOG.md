# 百工 Baigong — 更新日志

## v0.2.3 (2026-06-20)

### Bugfix
- 替换 pywebview（WKWebView）为默认浏览器打开，彻底解决启动后一直"加载中"的卡死问题
- 移除 webview 依赖，减小打包体积
### Optimize
- 不再需要内嵌 WebView，启动更稳定

## v0.2.2 (2026-06-20)

### Bugfix
- 修复启动后一直卡死（exit code 137）的问题：去掉了 `psutil`/`httpx` 外部依赖
- 修复启动台看不到 app：`CFBundleIdentifier` 改为 `com.baigong.agent`
### New
- 支持 7 种 LLM Provider：DeepSeek / OpenAI / Anthropic / DashScope / Ollama / OpenRouter / 自定义

## v0.2.1 (2026-06-20)

### Bugfix
- 修复打包版更新检测失效的问题

## v0.2.0 (2026-06-20)

### New
- 真实 Agent 管理工具：创建、配置、运行 Agent
- 配置向导：首次启动选择 API Key / 模型 / 创建首个 Agent
- 5 个管理面板：Agent / 任务 / 工具 / 日志 / 配置
- 热更新：打包版从 GitHub Release 下载 DMG，源码版 git pull
- 支持 7 种 LLM Provider

## v0.1.0 (2026-06-20)

### New
- 首个版本（模拟演示）
- macOS 原生 .app
- 游戏风格 Agent 模拟面板
