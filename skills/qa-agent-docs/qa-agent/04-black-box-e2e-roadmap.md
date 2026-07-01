# 黑盒 E2E QA 路线图

## 定位

LangBot 有大量外部依赖：模型供应商、plugin runtime、浏览器登录态、
marketplace/network、RAG engine、sandbox backend、平台适配器等。单测仍然有价值，
但这个 QA 方向当前不优先解决 LangBot core 的单测覆盖率问题，因为重 mock 往往不能
真实代表产品路径。

`langbot-skills` 当前目标是让黑盒 E2E 测试变得可执行、可沉淀、可复用：

```text
开发者测试意图
-> 复用或新增 case
-> agent 通过浏览器执行
-> UI + console + network + log 证据
-> report
-> 反哺 case / troubleshooting
```

这是面向开发者的 QA 资产库。开发者可以让 agent 测一个 feature；如果路径稳定，
就把路径正规化为 case，让下一个开发者或 QA agent 继续复用。

## 非目标

- 这一阶段不优先建设 LangBot core 单测覆盖率。
- 不把 API/curl 作为 WebUI 行为的通过标准。
- 不要求每个 case 都能进 CI。
- 不在 report 和日志守卫有用之前急着做完整 browser runner。
- 不把外部 provider、OAuth、marketplace 抖动直接判成产品失败，除非证据明确。

## 当前状态

仓库已经具备第一层基础设施：

- `skills/.env` 和 `skills/.env.local` 管理测试环境；
- `langbot-env-setup`、`langbot-testing`、`langbot-plugin-dev` 等 skill；
- `skills/langbot-testing/cases` 下的结构化 case；
- `skills/langbot-testing/troubleshooting` 下的结构化故障资产；
- RAG、多模态、plugin、MCP 等 fixture；
- `bin/lbs validate`、`bin/lbs index`、`bin/lbs case`、`bin/lbs trouble`、
  `bin/lbs test plan`、`bin/lbs test start`、`bin/lbs test report`。

所以当前已经不是“先把路径写进 Markdown”的阶段，而是进入“让每次运行有证据、
有报告、能沉淀”的阶段。

## 测试模型

UI case 只有在用户可见行为正确时才能通过。辅助证据必须解释同一次运行。

通过一个 UI case 的最低证据：

- 用户可见的成功信号，例如 bot 回复、provider 保存成功、文件上传完成、plugin 页面渲染；
- 没有意外 browser console error；
- 相关时间窗口内没有意外后端/runtime 错误；
- 有截图、DOM snapshot 或同等视觉/结构证据，如果当前 agent 能获取；
- API/curl 只在解释同一条 UI 路径时作为诊断证据。

失败报告需要保留足够信息，让开发者能复现或分流：

- case id 和实际测试 URL；
- 使用的 browser path；
- 最后可见 UI 状态；
- console/network 症状；
- 相关后端/前端日志；
- 匹配到的 troubleshooting id；
- 这是产品失败、环境问题、外部依赖抖动，还是证据不足。

## 结果词汇

统一使用这些结果：

- `pass`：UI 行为正确，辅助证据干净。
- `fail`：UI 行为错误，或同一次运行的 console/log 出现意外产品错误。
- `blocked`：缺登录、缺 provider credentials、服务未启动等原因导致目标路径没有跑起来。
- `env_issue`：失败在目标行为之外，例如 proxy、OAuth、provider quota、marketplace outage、
  本地服务启动问题。
- `flaky`：同一环境下结果不稳定，进入门禁前需要先稳定。

做 merge/release 判断时，`env_issue` 和 `blocked` 不能算产品通过。

## 路线图

### Phase 0：对齐文档

目标：明确当前黑盒 E2E 方向。

交付物：

- `docs/qa-agent/README.md` 文档状态导航；
- 本路线图；
- 给旧规划文档加状态说明。

完成标准：

- 新贡献者不用通读所有旧文档，也能知道当前重点。

### Phase 1：Test Report MVP

状态：已有第一版。

目标：让每次 agent browser 测试都有一致报告格式，即使 browser 执行还没自动化。

建议命令：

```bash
bin/lbs test start <case-id>
bin/lbs test report <case-id> --output reports/<timestamp>-<case-id>.md
```

MVP 行为：

- 读取 case 和关联 troubleshooting；
- 生成 Markdown report 模板；
- 生成 run handoff，固定本次测试的 start timestamp 和推荐 report command；
- 写入脱敏后的环境摘要；
- 提供 `pass/fail/blocked/env_issue/flaky` 结果选项；
- 包含 UI result、console errors、network symptoms、logs、screenshots、
  diagnostics、matched troubleshooting、assets to update 等 section；
- 支持 `--json`，输出机器可读报告。

第一版已经是 report generator，不急着做自动判定。先把 evidence 收集格式统一起来，
再做自动化更稳。

完成标准：

- agent 可以先跑 `lbs test start <case-id>`，用它给出的时间窗口执行浏览器路径，
  然后按固定格式填写 report，不需要每次重新发明报告结构。

### Phase 2：日志守卫 MVP

状态：已有第一版文件扫描。

目标：捕获 UI 不一定明显展示的 runtime 问题。

日志守卫应集成进 `lbs test report`，不要发展成独立后端 API 测试框架。

建议命令形态：

```bash
bin/lbs test report <case-id> \
  --backend-log /path/to/backend.log \
  --frontend-log /path/to/frontend.log \
  --console-log /path/to/console.log \
  --evidence-dir reports/evidence/<run-id> \
  --since "2026-05-21T10:30:00+08:00" \
  --tail-lines 2000 \
  --output reports/<timestamp>-<case-id>.md
```

MVP 行为：

- 默认从 `LANGBOT_REPO/data/logs/` 扫描最新 `langbot-*.log`；
- 支持 agent 显式提供 backend、frontend、console 日志文件；
- 支持读取 evidence 目录下的 `automation-result.json`，把浏览器自动化脚本结论纳入报告；
- 支持 `lbs test result` 为人工/agent browser 运行写入标准 `result.json`，供 suite 聚合；
- 支持 `--since` 和 `--tail-lines`，避免历史日志污染本次报告；
- 检测默认非预期模式，例如 `Traceback`、未 await coroutine、unclosed client/connector、
  `KeyError`、`TypeError`、`AttributeError`、明显 secret 泄露；
- 匹配 case 声明的 `success_patterns` 和 `failure_patterns`；
- 匹配已知 troubleshooting，先支持 `plugin-runtime-timeout` 和 `proxy-env-mismatch`；
- 只有 case 明确声明时，才允许 expected failure；
- 将发现分类为 fail、warning、matched troubleshooting、ignored expected issue；
- 永远不打印 secret 值。

完成标准：

- 至少 `pipeline-debug-chat` 能生成包含日志摘要和 troubleshooting 匹配结果的 report。

### Phase 3：Case 元数据加固

状态：已有第一版。

目标：让 case 更容易选择、执行和晋级。

字段逐步补充，保持向后兼容：

```yaml
priority: p0 | p1 | p2
risk: low | medium | high
ci_eligible: false
preconditions:
  - "Authenticated browser profile is available."
setup:
  - "Start LangBot backend and frontend."
cleanup:
  - "Remove temporary provider, plugin, or knowledge base if created."
expected_failures: []
success_patterns:
  - "Conversation(0) Streaming completed"
failure_patterns:
  - "Action invoke_llm_stream call timed out"
evidence:
  required:
    - ui
    - console
    - backend_log
```

当前实现采用扁平字段 `evidence_required`，避免轻量 YAML 解析器在 case 文件里承载嵌套结构。
`bin/lbs validate` 会校验 `priority`、`risk`、`ci_eligible`、`evidence_required`、
`automation` 脚本路径、case 关联 skill 和 troubleshooting 交叉引用。`bin/lbs case list`
支持 `--json`、`--type`、`--area`、`--tag`、`--priority`、`--risk`、`--automation`、`--ci`
、`--ready` 和 `--machine-ready` 过滤，方便 agent 快速选择测试集。
`env_any` 和 `automation_env_any` 用于表达 URL-or-name 这类 one-of 输入，避免把可替代变量误判为全部必填。

当前也有 `skills/<skill>/suites/*.yaml` 和 `bin/lbs suite plan <suite-id>`，用于组织常跑测试集，
例如 `core-smoke`、`local-agent-gate` 和
`agent-runner-release-gate`。发布门禁使用 `agent-runner-release-preflight`
先分类配置 blockers 和 runtime env issues，再运行较重的浏览器 Debug Chat case。
依赖 fixture 的 case 可以在浏览器执行前先跑 `bin/lbs fixture check`，检查
`fixtures/fixtures.json` 登记的 deterministic 文件、plugin 包和本地测试 server 是否存在。
`bin/lbs suite start <suite-id>` 会生成 suite run id、suite evidence root、per-case evidence 目录、
`suite-start.json`/`suite-start.md` handoff 文件和 per-case evidence 命令；
浏览器自动化脚本会写入 `automation-result.json`，供 `bin/lbs test report` 展示原始自动化结论；
`bin/lbs test result <case-id>` 会在人工/agent browser case 完成后写入最终 `result.json`；
`bin/lbs suite report <suite-id> --evidence-dir <dir>` 会聚合各 case 的 `result.json`，并且
不会把缺少 required evidence 的 `pass` 当作 suite 通过。
Runner 专用 Debug Chat case 通过 `automation_pipeline_url_env` 和
`automation_pipeline_name_env` 绑定专用 pipeline 变量，避免 local-agent、Codex 或
Claude Code case 误用通用 `LANGBOT_PIPELINE_URL` 后产生假阳性。
Debug Chat case 还可以通过 `automation_stream_output` 固定流式或非流式发送路径。
多模态 Debug Chat case 可以通过 `automation_image_base64_fixture` 复用 deterministic 图片 fixture。
`test plan` 和 `suite plan` 会输出 readiness，让 agent 在执行浏览器前就看到缺失的 env、
自动化变量、fixture，以及需要人工确认的 `manual_check` 前置条件。

完成标准：

- `lbs case list` 或后续 filter 能回答“smoke 跑哪些”、“哪些适合 CI”、
  “哪些需要真实 provider credentials”。

### Phase 4：开发者沉淀流程

目标：开发者让 agent 测新 feature 后，稳定路径不会丢在聊天记录里。

流程：

1. 开发者要求 agent 通过浏览器测试某个 feature。
2. agent 先按 UI 主路径探索。
3. agent 用 `lbs test start` 固定运行窗口，再用 `lbs test report` 写报告。
4. 如果路径稳定，agent 新增或更新 case。
5. 如果出现可复用故障，agent 新增或更新 troubleshooting。
6. agent 跑 `bin/lbs validate` 和 `bin/lbs index`。

完成标准：

- feature QA 的结果能进入资产库，而不是只留在一次对话里。

### Phase 5：选择性浏览器自动化

状态：已有第一版 `test run` 入口和两个 Playwright 脚本。

目标：只自动化少量稳定、值得重复跑的黑盒路径。

建议顺序：

1. `webui-login-state`
2. `pipeline-debug-chat`
3. `local-agent-basic-debug-chat`
4. `local-agent-rag-debug-chat`
5. 一个基于 deterministic fixture 的 plugin 或 MCP smoke path

执行策略：

- 继续把 Computer Use 或 Playwright MCP 作为默认交互路径；
- 只给稳定、确定性的路径补直接 Playwright script；
- 保存 screenshots、console logs、trace/video；
- flaky 或强依赖真实 credentials 的 provider case 暂时不要进 CI。

当前已经绑定：

- `webui-login-state` -> `scripts/e2e/webui-login-state.mjs`
- `pipeline-debug-chat` -> `scripts/e2e/pipeline-debug-chat.mjs`

第一版自动化先产出 `reports/evidence/<run-id>/` 下的 console、network、screenshot 和
result JSON。真实执行后仍要用 `lbs test report --since ... --console-log ...` 做日志守卫和
最终报告。开发期间可以先用 `bin/lbs test run <case-id> --dry-run` 检查命令和 evidence 路径。
Debug Chat 类脚本应复用 `scripts/e2e/lib/debug-chat.mjs`，避免重复实现 visible response leaf
判断和已知失败信号分类。

完成标准：

- 小规模 smoke subset 可以不靠人工决定每一步点击；更大的资产库仍然服务于人工/agent
  驱动的探索式 E2E。

## 下一批动工切片

在做 browser runner 之前，继续做这些：

1. 等 LangBot 当前开发状态稳定后，用一次真实 `pipeline-debug-chat` 跑通
   `test start -> test run -> test report -> test result -> suite report`，产出 sample report。
2. 只给 smoke/local-agent 首批 case 补必要元数据。
3. 继续补日志守卫规则，尤其是 WebSocket、plugin runtime、provider streaming、前端
   chunk/rendering failure。
4. 约定 report 产物目录、截图和 console/network 导出的命名方式。
5. 再评估是否开始给 `webui-login-state` 和 `pipeline-debug-chat` 做直接 Playwright
   自动化。

这样 infra 会立刻有用，同时保留后续自动化 browser execution 的空间。
