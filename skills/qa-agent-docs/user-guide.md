# LangBot Skills 用户使用手册

## 这个仓库解决什么

`langbot-skills` 是给 agent 使用的 LangBot 测试资产库。开发者 clone 后，可以让 Codex、Claude Code、Computer Use 或 Playwright MCP 复用已有环境配置、测试路径和故障知识，像 QA 一样操作 LangBot WebUI。

核心目标：

- 不让下一个 agent 窗口从头探索登录、模型配置、pipeline 调试。
- 把稳定 UI 测试路径沉淀为 case。
- 把常见故障沉淀为 troubleshooting。
- 让 agent 优先通过浏览器点击验证产品行为。
- API/curl/log 只作为诊断手段，不作为 UI case 通过标准。

## 快速开始

1. Clone 仓库。

2. 检查本地默认变量：

```bash
bin/lbs env show
```

默认变量在：

```text
skills/.env
```

本机专用覆盖写到：

```text
skills/.env.local
```

它会覆盖 `skills/.env` 中的同名变量，并且不应该提交。
`skills/.env` 是共享默认值，不应写入本机绝对路径、浏览器 profile、provider key 或其他凭据。
新机器建议从模板开始：

```bash
cp skills/.env.example skills/.env.local
```

常用变量：

```text
LANGBOT_FRONTEND_URL
LANGBOT_BACKEND_URL
LANGBOT_DEV_FRONTEND_URL
LANGBOT_REPO
LANGBOT_WEB_REPO
LANGBOT_BROWSER_PROFILE
```

3. 检查环境是否就绪：

```bash
bin/lbs env doctor
bin/lbs fixture check
```

`env doctor` 会检查 URL、路径、代理变量等。代理变量是可选项；只有大小写代理变量互相冲突时才会报错。失败不一定代表仓库坏了，通常说明本地 LangBot 没启动、代理不一致或浏览器 profile 不存在。
`fixture check` 会检查仓库内测试 fixture 是否存在，例如 MCP stdio server、RAG 文档、多模态图片、qa-plugin-smoke 包和 QA AgentRunner 包。它也会校验 `.lbpkg` 是 zip 包，并检查 QA AgentRunner fixture 的入口文件未漂移。

4. 查看已有测试 case：

```bash
bin/lbs case list
bin/lbs case list --json --priority p0 --automation
bin/lbs case list --ready
bin/lbs case list --machine-ready
bin/lbs suite list
bin/lbs suite plan core-smoke
bin/lbs suite plan agent-runner-release-gate
bin/lbs suite start core-smoke
bin/lbs suite start core-smoke --run-id core-smoke-local --evidence-dir reports/evidence/core-smoke-local
```

`case list` 支持按 `--type`、`--area`、`--tag`、`--priority`、`--risk`、`--automation`
、`--ci`、`--ready` 和 `--machine-ready` 过滤。`--ready` 只显示没有缺机器输入且没有人工前置条件的 case；
`--machine-ready` 过滤掉缺机器输入的 case，但保留 `manual-check`，表示执行前还要确认前置条件。需要交给 agent 自动选择测试集时，优先使用 `--json`，
其中包含 `priority`、`risk`、`ci_eligible`、`automation`、`evidence_required` 以及
env/automation/fixture/manual readiness。
Case metadata 中的 `env` 和 `automation_env` 表示全部必填；URL 或 name 这类二选一输入会放在
`env_any` 或 `automation_env_any`，readiness 只要求组合里至少一个变量有值。

如果要跑一组已沉淀的测试路径，优先使用 suite。Suite 位于 `skills/<skill>/suites/*.yaml`，
只负责组织 case，不改变 UI/browser 作为通过标准的原则。
`suite plan` 会聚合 readiness：缺环境变量、缺自动化变量、缺 fixture 或需要
`manual_check` 时，会在执行前标出受影响的 case。`manual_check` 不是产品通过，
它表示机器配置已满足但 agent 必须先确认 case 里的 `preconditions` 或 `setup`。
Runner externalization 发布判断使用 `agent-runner-release-gate`。先跑
`agent-runner-release-preflight`，把缺 pipeline、runner id 错误、插件未安装这类
`blocked`，以及 provider key、Box、插件运行时这类 `env_issue` 分开，再执行较重的
浏览器 Debug Chat case。

5. 生成 agent 执行计划：

```bash
bin/lbs test plan pipeline-debug-chat
```

然后把计划交给当前 agent 执行。agent 应使用 Computer Use、Playwright MCP 或其他浏览器控制能力去操作 UI。
`test plan` 中的 Environment、Automation Readiness、Fixture Readiness 和 Manual
Readiness 是执行前门禁；如果 readiness 缺失，应先补配置或将本次 case 标记为
`blocked`。如果状态是 `manual_check`，先确认 `preconditions` 和 `setup`，再开始 UI
执行。不要把后续 curl/API 诊断当成 UI case 通过。

## 推荐使用方式

### 冒烟测试

你可以直接对 agent 说：

```text
帮我跑一下 LangBot 新前端 smoke test。
```

agent 应该：

- 读 `skills/.env`
- 优先查看 `bin/lbs suite plan core-smoke`，或查找 `type: smoke` 的 cases
- 生成 test plan
- 用浏览器执行 UI 操作
- 检查 console、截图、后端日志
- 输出简短 QA 报告

### Runner Externalization 发布门禁

你可以直接对 agent 说：

```text
按 agent-runner release gate 跑完整矩阵，先做 preflight，再跑浏览器 case，并把 blocked/env_issue/fail 分开。
```

agent 应该先查看 `skills/langbot-testing/references/agent-runner-release-gate.md`，
再执行：

```bash
bin/lbs test recommend
bin/lbs suite plan agent-runner-release-gate
bin/lbs test run agent-runner-release-preflight --dry-run
bin/lbs suite start agent-runner-release-gate --run-id agent-runner-release-local --evidence-dir reports/evidence/agent-runner-release-local
```

`test recommend` 输出的 run 命令默认带 `--dry-run`；确认 readiness 和 `manual_check` 前置条件后，再去掉 `--dry-run` 执行。

完成所有 case 后，用：

```bash
bin/lbs suite report agent-runner-release-gate --evidence-dir reports/evidence/agent-runner-release-local
```

没有最终 `result.json`、缺 required evidence、或把 `blocked`/`env_issue` 当成 pass，
都不能算发布门禁通过。

### 新 Feature 测试

你可以说：

```text
我改了 provider 页面，帮我测一下 DeepSeek provider 添加、测试、绑定 pipeline 是否正常。
```

agent 应该：

- 查找相关 case 和 reference
- 如果没有稳定路径，先探索 UI
- 用浏览器执行真实交互
- 失败时用日志/API 辅助定位
- 稳定后新增或更新 case/reference
- 新故障沉淀为 troubleshooting

### 定点排错

你可以说：

```text
Debug Chat 点了没回复，帮我查是前端问题还是后端问题。
```

agent 应该：

- 先通过 UI 复现
- 看 console/network
- 看后端日志
- 必要时用 API/curl 做诊断
- 匹配 troubleshooting
- 给出修复建议或直接修复

## 重要原则

这些原则固定在：

```text
docs/qa-agent/03-agent-browser-qa-principles.md
```

简化版：

- UI/browser 是测试主路径。
- API/curl/log 只做诊断。
- 后端接口成功不等于 UI case 通过。
- case 通过必须以用户可见 UI 结果为准。
- 有视觉能力时应检查截图。
- 没有视觉能力时用 DOM/accessibility snapshot 和 console。
- 不要打印 token、API key、OAuth secret 或 localStorage token 值。

## 规划文档

如果要判断下一步建设什么，先看：

```text
docs/qa-agent/README.md
docs/qa-agent/04-black-box-e2e-roadmap.md
```

`01-qa-agent-harness-plan.md` 是早期规划，部分内容已经被当前实现和路线图替代。

## 常用命令

### 环境

```bash
bin/lbs env show
bin/lbs env show --json
bin/lbs env doctor
bin/lbs fixture list
bin/lbs fixture check
bin/lbs fixture check --json
```

`env show` 和 `env doctor` 默认会对 token、API key、password、secret 以及 URL basic auth
做脱敏。不要把 `.env.local` 里的原始凭据复制进测试报告。

### Skill 和索引

```bash
bin/lbs list
bin/lbs validate
bin/lbs index --check
bin/lbs index
```

### Case

```bash
bin/lbs case list
bin/lbs case list --type smoke
bin/lbs case list --json --priority p1 --tag local-agent
bin/lbs case list --ready
bin/lbs case list --machine-ready
bin/lbs case show pipeline-debug-chat
bin/lbs case new my-feature --title "My Feature Works"
```

### Suite

```bash
bin/lbs suite list
bin/lbs suite list --json --priority p1
bin/lbs suite show local-agent-gate
bin/lbs suite plan core-smoke
bin/lbs suite plan local-agent-gate --json
bin/lbs suite start core-smoke
bin/lbs suite start core-smoke --run-id core-smoke-local --evidence-dir reports/evidence/core-smoke-local
bin/lbs suite run core-smoke --dry-run --json
bin/lbs suite run core-smoke --run-id core-smoke-local --evidence-dir reports/evidence/core-smoke-local
bin/lbs suite start core-smoke --json
bin/lbs suite report core-smoke --evidence-dir reports/evidence/<suite-run-id>
bin/lbs suite report core-smoke --evidence-dir reports/evidence/<suite-run-id> --json
bin/lbs suite new my-feature-gate --title "My Feature Gate"
```

`suite start` 不直接控制浏览器。它生成统一 run id、suite evidence root、每个 case 的 evidence
目录、`suite-start.json`/`suite-start.md` handoff 文件，以及每个 case 的 `test run`、`test report`
和 `test result` 命令模板。需要固定路径时，使用 `--run-id` 和 `--evidence-dir`。
`suite run --dry-run --json` 只预览 planned/skipped case，不创建 evidence，也不执行 automation。
`suite run` 会顺序执行 suite 中已有 automation、机器 readiness 已满足且不需要 `manual_check` 的 case，并在最后聚合 `suite report`。
缺 env、automation env 或 fixture 的 case 默认会跳过；确实要强制执行时，加 `--include-not-ready`。
确认前置条件后，才用 `--include-manual-check` 执行这类 case。
所有 case 执行完并写入最终 `result.json` 后，
`suite report` 会读取各 case evidence 目录并汇总为 `pass`、`fail`、`blocked`、`env_issue`、
`flaky`、`incomplete` 等状态。`pass` 必须声明已经收集 case 的全部 required evidence；
否则 suite 会保持 `incomplete`，避免把缺证据的运行误判成通过。

### Test Plan

```bash
bin/lbs test plan pipeline-debug-chat
bin/lbs test plan pipeline-debug-chat --json
```

### Test Start

```bash
bin/lbs test start pipeline-debug-chat
bin/lbs test start pipeline-debug-chat --json
```

`test start` 用于 agent 开始一次浏览器测试前记录 run id、开始时间和推荐 report 命令。
它会把 `--since "<started_at_local>"` 写进后续报告命令，减少历史日志污染本次判断。
如果 case 绑定了自动化脚本，输出里也会包含 `test run` 命令和 evidence 目录。

### Test Automation

```bash
bin/lbs test run webui-login-state --dry-run
bin/lbs test run pipeline-debug-chat --dry-run
bin/lbs test run webui-login-state --run-id login-smoke --output reports/evidence/login-smoke
bin/lbs test run pipeline-debug-chat --run-id pipeline-smoke --output reports/evidence/pipeline-smoke
```

查看当前所有带自动化脚本的 case：

```bash
bin/lbs case list --automation
bin/lbs case list --json --automation
```

当前自动化覆盖包括登录态、通用 Pipeline Debug Chat、local-agent runner 的基础回复、
PromptPreProcessing、RAG、plugin tool、MCP stdio tool、非流式、多模态和 RAG+多模态路径。
不要在文档里手工维护静态 case 清单；以 `case list --automation` 和 suite 定义为准。

自动化脚本位于 `scripts/e2e/`。它们会保存：

- `console.log`
- `network.log`
- `screenshot.png`
- `automation-result.json`

新增 Debug Chat 类自动化时，优先复用 `scripts/e2e/lib/debug-chat.mjs` 中的 pipeline 打开、
prompt 发送、visible response leaf 判断和失败信号分类，不要在新脚本里复制 DOM 扫描逻辑。

脚本需要本地安装 Playwright 后才能真正执行：

```bash
npm install
npx playwright install chromium
```

`pipeline-debug-chat` 通用自动化建议配置 `LANGBOT_PIPELINE_URL`。如果没有 direct URL，
脚本会尝试通过 `LANGBOT_PIPELINE_NAME` 从 Pipelines 页面进入目标 pipeline。两者都没有时，
该自动化会返回 `blocked`，不会伪造通过。

Runner 专用 case 不应复用通用 pipeline 变量。Local Agent、Codex AgentRunner 和
Claude Code AgentRunner 这类 case 会通过 `automation_pipeline_url_env` /
`automation_pipeline_name_env` 映射到 case-specific env，例如
`LANGBOT_LOCAL_AGENT_PIPELINE_URL`。这些 case 如果缺少专用变量，会返回 `blocked`，
不会退回到 `LANGBOT_PIPELINE_URL`，避免跑错 pipeline 后产生假阳性。
如果 case 声明了 `setup_automation`，只有 `bin/lbs test run <case-id>` 的真实执行路径会先运行这些 setup；
`test plan`、`suite plan`、`case list` 和 `--dry-run` 只展示它们，不会修改本地环境。
setup 可以是 `case:<case-id>` 或仓库内 `node:scripts/... --flag`，每一步证据会写到主 evidence 目录下的
`setup/` 子目录。setup 失败时主 automation 不会继续执行；setup 写入 `.env.local` 后，主 automation
会重新读取环境。用 `setup_provides_env` 声明 setup 会生成的变量，可以让 readiness 正确显示机器可准备状态。
如果 Debug Chat case 需要固定流式/非流式路径，可以在 case 中设置
`automation_stream_output: "1"` 或 `"0"`，脚本会在发送消息前切换 Debug Chat 的 Stream 控件。
如果 case 需要上传图片，可以设置 `automation_image_base64_fixture` 指向仓库内的 base64 PNG fixture，
脚本会在 evidence 目录写出临时 PNG 并通过 Debug Chat 上传控件发送。
`bin/lbs test plan <case-id> --json` 和 `bin/lbs suite plan <suite-id> --json`
都会显示这些专用变量是否已配置。

### Test Report 和日志守卫

```bash
bin/lbs test report pipeline-debug-chat
bin/lbs test report pipeline-debug-chat --output reports/pipeline-debug-chat.md
bin/lbs test report pipeline-debug-chat \
  --backend-log /path/to/backend.log \
  --frontend-log /path/to/frontend.log \
  --console-log /path/to/console.log
bin/lbs test report pipeline-debug-chat --evidence-dir reports/evidence/pipeline-smoke
bin/lbs test report pipeline-debug-chat --backend-log /path/to/backend.log --json
bin/lbs test report pipeline-debug-chat --since "2026-05-21T10:30:00+08:00"
bin/lbs test report pipeline-debug-chat --tail-lines 2000
bin/lbs test report pipeline-debug-chat --since "2026-05-21T10:30:00+08:00" --tail-lines 2000
```

`test report` 会生成报告模板，并默认从 `LANGBOT_REPO/data/logs/` 自动选择最新的
`langbot-*.log` 作为 LangBot 后端日志扫描。也可以用 `--backend-log` 覆盖，或用
`--no-auto-log` 只生成模板。

如果提供 `--evidence-dir`，或 `--console-log` 指向 `reports/evidence/<run-id>/console.log`，
报告会优先读取同目录的 `automation-result.json`，并展示自动化脚本的 `status`、`reason`、
起止时间和目标 URL。

日志守卫会扫描常见错误、secret 泄露风险、case 声明的 success/failure patterns，以及已知
troubleshooting pattern。它不控制浏览器，也不替代 UI 通过判断。`success_patterns`
命中会作为通过证据写入 `success_signals`；声明了 success pattern 但本次扫描窗口没有命中，
会给 warning；`failure_patterns` 命中会让本次日志守卫 fail。

建议在执行浏览器 case 前记录当前时间，然后在报告阶段使用 `--since`。如果只想快速看
最近日志，可以使用 `--tail-lines`。

### Runtime Log Guard

如果还没有进入某个具体 UI case，只是想观察 LangBot 后端日志，可以直接使用 `log`
命令。它和 `test report` 使用同一套扫描器、secret 脱敏、troubleshooting pattern 和
case success/failure pattern。

```bash
bin/lbs log scan --tail-lines 300
bin/lbs log scan --case pipeline-debug-chat --since "2026-05-21T10:30:00+08:00"
bin/lbs log scan --backend-log /path/to/langbot.log --json
bin/lbs log scan --failure-pattern "runner.tool_loop_error|Action invoke_llm_stream call timed out" --strict
```

`log scan` 默认从 `LANGBOT_REPO/data/logs/` 自动选择最新的 `langbot-*.log`。传入
`--case <case-id>` 后，会额外应用该 case 声明的 `success_patterns`、`failure_patterns`
和 related troubleshooting。默认用于观察，返回码保持 0；加 `--strict` 后，`fail` 或
`env_issue` 会返回非 0，适合脚本门禁。

运行期观察可以用 `watch`：

```bash
bin/lbs log watch --case pipeline-debug-chat
bin/lbs log watch --backend-log /path/to/langbot.log --interval-ms 500
bin/lbs log watch --duration-ms 30000 --strict --json
```

`log watch` 默认从启动时的文件末尾开始，只观察新追加的日志；加 `--from-start` 可从文件开头扫。
它会实时打印新命中的 findings 和 success signals。为了避免当前历史日志噪声影响观察，默认不因
异常返回非 0；加 `--strict` 后，退出时如果看到 `fail` 或 `env_issue` 会返回非 0。

给一次 QA 运行包日志窗口时，用 `guard start/stop`：

```bash
bin/lbs log guard start --run-id local-debug --case pipeline-debug-chat
# 执行浏览器或手工测试
bin/lbs log guard stop --run-id local-debug
```

`start` 会在 `reports/log-guards/<run-id>.json` 记录起始时间、case 和当前后端日志路径；
`stop` 会用 start/stop 时间作为扫描窗口，生成 `reports/log-guards/<run-id>.md`，并默认按
strict guard 返回码处理。临时只想收集报告、不想让命令失败，可以加 `--no-strict`。

当前 LangBot core 日志还不是完全结构化日志，runtime guard 主要依赖时间窗口和文本 pattern。
已支持 ISO 时间戳和 LangBot 当前的 `[MM-DD HH:mm:ss.SSS]` 前缀；没有时间戳的连续行会跟随上一条
带时间戳的日志块。如果后续 core 能提供稳定 request id、conversation id、plugin action id 或
JSON log field，guard 可以从“时间窗口 + 文本匹配”升级为更精确的关联分析。

### Test Result

```bash
bin/lbs test result pipeline-debug-chat \
  --result pass \
  --reason "Debug Chat returned OK and the report log guard was clean." \
  --evidence-dir reports/evidence/pipeline-smoke \
  --started-at "2026-05-21T10:30:00+08:00" \
  --evidence ui,screenshot,console,backend_log
```

`test result` 用于把一次人工/agent browser 运行的最终判断写成标准 `result.json`，
供 `suite report` 聚合。它不会替代 UI 测试：如果写 `--result pass`，`--evidence`
必须覆盖该 case 的 `evidence_required`，否则命令会失败。自动化脚本写
`automation-result.json`；如果 case 还要求 backend log、API diagnostic 或 filesystem
evidence，agent 需要在报告和诊断完成后再用 `test result` 写最终 `result.json`。

### Troubleshooting

```bash
bin/lbs trouble list langbot-testing
bin/lbs trouble show plugin-runtime-timeout
bin/lbs trouble search runtime
bin/lbs trouble add langbot-testing --title "..." --symptom "..." --cause "..." --fix "..."
```

## 目录说明

```text
skills/
  .env                         # 共享默认变量
  langbot-env-setup/           # 环境、浏览器、登录态、代理
  langbot-testing/             # WebUI / provider / pipeline 测试
schemas/                       # 结构化资产 schema
src/                           # lbs TypeScript 源码
bin/                           # lbs 入口
docs/                          # 设计文档和用户手册
AGENTS.md                      # agent 维护协议
```

## 添加一个新测试路径

1. 先让 agent 通过浏览器探索并执行路径。
2. 稳定后创建 case：

```bash
bin/lbs case new provider-xxx --title "Provider XXX can be configured" --area provider --type provider
```

3. 编辑生成的 `cases/*.yaml`，补充真实步骤、检查点和 troubleshooting。

4. 校验：

```bash
bin/lbs validate
bin/lbs index --check
bin/lbs index
```

## 添加一个新故障

```bash
bin/lbs trouble add langbot-testing \
  --title "Plugin runtime actions time out" \
  --symptom "Debug Chat shows Agent runner temporarily unavailable" \
  --cause "Old plugin runtime survived backend restart" \
  --fix "Stop old runtime processes and restart LangBot"
```

然后编辑生成的 YAML，补充 `patterns`、`related_cases` 和验证方式。

## 当前边界

- `lbs test plan` 只生成测试计划，不直接控制浏览器。
- `lbs test report` 生成报告，默认扫描最新 LangBot 后端日志；也可扫描显式提供的
  backend/frontend/console 日志文件。
- 真正的 UI 操作由当前 agent 的浏览器能力执行。
- `env doctor` 是 readiness check，不是产品测试。
- `curl/API` 是诊断工具，不是主要测试路径。
