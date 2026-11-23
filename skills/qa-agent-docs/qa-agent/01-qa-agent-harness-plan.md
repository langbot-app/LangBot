# LangBot Skills 测试资产库规划

## 状态

这是早期测试资产库规划文档，保留用于解释 `langbot-skills` 的分层来源。

当前路线已经收敛为黑盒 E2E QA：开发者用 agent 通过浏览器测试 LangBot，
稳定路径沉淀为 case，失败知识沉淀为 troubleshooting。`lbs test report` 和
日志守卫已有 MVP，后续重点是报告证据、case 元数据和少量稳定路径自动化。当前优先级见：

```text
docs/qa-agent/04-black-box-e2e-roadmap.md
```

本文中关于 `case list/show`、`trouble show/search`、`test plan` 的“计划实现”
内容已经部分过时，因为这些能力已经落地。

## 目标

让开发者 clone `langbot-skills` 后，可以把测试意图交给 agent，由 agent 复用已有环境配置、测试路径和故障知识完成 LangBot 功能验证。

典型场景：

- 冒烟测试：验证 pipeline Debug Chat、provider、常见页面是否正常。
- Provider 测试：添加 DeepSeek/OpenAI/Claude 等供应商并验证模型可用。
- 新 feature 测试：探索新 UI 路径，并在稳定后沉淀成 case/reference。
- 回归测试：复用旧路径，避免每个窗口重新探索登录、模型配置、pipeline 调试。
- 故障沉淀：把 runtime 超时、代理不一致、WebSocket 问题记录为可搜索资产。

核心方向见 `03-agent-browser-qa-principles.md`：agent 必须以浏览器/UI 为主路径，API/curl 只能作为诊断手段。

## 当前仓库结构

```text
skills/
  .env                         # 共享默认变量
  langbot-env-setup/           # 环境准备、浏览器控制路径、代理、登录态
  langbot-testing/             # WebUI / provider / pipeline 测试入口
  langbot-plugin-dev/          # 插件开发测试
  langbot-eba-adapter-dev/     # 平台适配器开发测试
src/
  lbs.ts                       # CLI 源码
bin/
  lbs                          # CLI 入口
docs/
  qa-agent/                    # 规划文档，历史目录名保留
```

## 设计分层

### 1. Skill 层

`SKILL.md` 只做触发和路由，不承载大段流程。

例子：

```text
langbot-env-setup -> 选择 Computer Use / Playwright MCP / OAuth profile / proxy
langbot-testing -> 选择 WebUI / pipeline / provider / troubleshooting
```

### 2. Reference 层

Markdown 记录人和 agent 都能读的流程说明。

适合内容：

- 如何选择浏览器控制方式
- 如何启动/检查服务
- 如何执行 pipeline Debug Chat
- 如何处理 OAuth 登录态

### 3. Case 层

使用 YAML 记录可重复测试路径。

建议结构：

```text
skills/langbot-testing/cases/
  pipeline-debug-chat.yaml
  provider-deepseek.yaml
```

建议格式：

```yaml
id: pipeline-debug-chat
title: Pipeline Debug Chat returns a bot response
mode: agent-browser
area: pipeline
type: smoke
skills:
  - langbot-env-setup
  - langbot-testing
env:
  - LANGBOT_FRONTEND_URL
  - LANGBOT_BACKEND_URL
steps:
  - Open LANGBOT_FRONTEND_URL
  - Navigate to Pipelines
  - Open target pipeline
  - Select Debug Chat
  - Send deterministic prompt
checks:
  - "UI: User message appears"
  - "UI: Bot message appears"
  - "Console: No unexpected frontend errors"
  - "Logs: Backend log includes Conversation(0) Streaming completed"
diagnostics:
  - "Use API/curl only after the UI path is attempted, to distinguish frontend display failure from backend/runtime failure."
troubleshooting:
  - plugin-runtime-timeout
  - proxy-env-mismatch
```

### 4. Troubleshooting 层

故障资产会逐渐变大，适合结构化记录。

历史 Markdown 入口保留在：

```text
skills/langbot-testing/references/troubleshooting.md
```

当前 canonical 结构化故障资产在：

```text
skills/langbot-testing/troubleshooting/
  plugin-runtime-timeout.yaml
  proxy-env-mismatch.yaml
```

### 5. CLI 层

`lbs` 是统一入口，不再引入独立 `qa` 命令。

已实现或当前可用：

```bash
bin/lbs list
bin/lbs validate
bin/lbs index
bin/lbs new-skill <name>
bin/lbs new-ref <skill> <name>
bin/lbs case new pipeline-debug-chat --title "Pipeline Debug Chat"
bin/lbs case list
bin/lbs case show pipeline-debug-chat
bin/lbs trouble list <skill>
bin/lbs trouble show plugin-runtime-timeout
bin/lbs trouble search runtime
bin/lbs trouble add <skill> --title ... --symptom ... --cause ... --fix ...
bin/lbs test plan pipeline-debug-chat
bin/lbs test start pipeline-debug-chat
bin/lbs test run pipeline-debug-chat --dry-run
bin/lbs test report pipeline-debug-chat
bin/lbs test report pipeline-debug-chat --backend-log /path/to/backend.log
```

## 测试库位置

不要使用隐藏 `.qa/` 作为主测试库。测试资产应该和 skill 放在一起，便于触发和维护：

```text
skills/langbot-testing/
  references/
  cases/
  troubleshooting/
  reports/          # 可选，本地运行产物可按需忽略或输出到外部目录
```

如果未来需要项目本地测试库，可以允许 `lbs` 支持 `--workspace` 或项目根目录配置，但 canonical 资产仍保存在 `langbot-skills`。

## 阶段规划

### 阶段一：环境和测试路径沉淀

状态：基本完成，持续维护。

- `skills/.env` 管共享默认变量。
- `langbot-env-setup` 拆出 Computer Use、Playwright MCP、OAuth profile、proxy、service startup。
- `langbot-testing` 记录 WebUI、pipeline、provider 测试路径。
- `lbs validate/index` 维护结构。

完成标准：

- agent 可以从 `skills/.env` 和 references 中找到当前测试入口。
- pipeline Debug Chat 这类路径不再需要从头探索。

### 阶段二：结构化 case/troubleshooting

状态：主体已完成，继续补齐元数据和资产质量。

目标：

- `lbs case new/list/show`
- `lbs trouble show/search`
- case id 去重、字段校验、索引生成

完成标准：

- 冒烟测试路径可以用结构化 case 表示。
- 下一个 agent 窗口可以直接读取 case 执行。

### 阶段三：计划和报告

状态：已有 MVP，继续完善。

目标：

- `lbs test plan <case>`
- agent 按 plan 使用浏览器执行 UI QA
- `lbs test report`
- 日志守卫集成
- 报告产物和 evidence 约定

完成标准：

- agent 可以按 case plan 执行浏览器测试。
- 结果报告包含 UI 结果、后端日志、console 错误和 troubleshooting 建议。

## 执行规则

- agent 可以直接编辑 Markdown reference。
- 新增结构化 case/troubleshooting 时，优先使用 `lbs`。
- 每次结构变更后运行 `bin/lbs validate`。
- 每次索引相关变更后运行 `bin/lbs index`。
- 测试文档不写死端口，使用 `skills/.env` 中的 URL 变量。
- 测试 case 的 `mode` 固定为 `agent-browser`。
- API/curl 只能写入 `diagnostics`，不能替代 UI 步骤和 UI 检查。
