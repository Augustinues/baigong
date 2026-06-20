# 百工 Baigong — 更新日志

## v0.3.0 (2026-06-20)

### New
- **三段式布局**：左栏 Agent 列表 / 中栏 Agent 编辑面板 / 右栏 日志+任务，告别标签页切换
- **Agent 编辑面板**：点击任意 Agent 卡片 → 中栏显示完整编辑界面
  - 名字、角色描述、人设 System Prompt（完整编辑，不截断）
  - 每个 Agent 可独立配置 LLM：提供商 / 模型 / API Key / API 地址
  - 工具勾选
  - 保存 / 删除
- **主题自定义**：顶部栏颜色圆点，7 种预设（琥珀/蓝/绿/紫/红/粉/青），点切换、自动保存
- **后端 API 扩展**：
  - `GET /api/agents/{id}` — 返回 Agent 完整详情
  - `GET /api/providers` — 返回所有提供商及可用模型
  - `POST /api/theme` — 保存主题设置
  - `PATCH /api/agents/{id}` — 支持更新 provider/api_key/base_url 等

### Bugfix
- JS 语法错误修复（PROVIDERS 对象多余 `}`）

## v0.2.3 (2026-06-20)

### Bugfix
- 修复打开后一直"加载中"：JS 语法错误（PROVIDERS 对象多余 `}`）导致整个脚本不执行
- pywebview create_window(debug=True) 参数无效导致窗口无法创建
- 修复 WKWebView 无法连接 localhost：Info.plist 添加 NSAllowsLocalNetworking
### Optimize
- 打包后自动修复 CFBundleIdentifier，启动台始终显示图标
- 增加详细日志 ~/Library/Logs/baigong.log

## v0.2.2 (2026-06-20)

### Bugfix
- 修复启动后一直卡死（exit code 137）的问题：去掉了 `psutil`/`httpx` 外部依赖
- 修复启动台看不到 app：CFBundleIdentifier 改为 `com.baigong.agent`
### New
- 支持 7 种 LLM Provider

## v0.2.1 (2026-06-20)

### Bugfix
- 修复打包版更新检测失效的问题

## v0.2.0 (2026-06-20)

### New
- 真实 Agent 管理工具：创建、配置、运行 Agent
- 配置向导 + 5 个管理面板
- 热更新

## v0.1.0 (2026-06-20)
首个版本（模拟演示）
