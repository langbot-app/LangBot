# Agent Runner QA 指南

本文档是 agent-runner 插件化下一轮测试的唯一 QA 入口。它合并并取代旧的 Phase 1 验收矩阵与 2026-05-18 / 2026-05-29 两份本地 QA 报告。

目标不是保留完整历史流水账，而是指导测试 agent 用最小但高价值的路径判断当前分支是否仍然健康。

## 1. 测试边界

当前主线验证的是 AgentRunner Protocol v1：

```text
event -> binding -> runner.run(ctx) -> result stream
```

本指南验证：

- Host 能通过当前 Pipeline adapter 进入 event-first `run(event, binding)` 主链路。
- Runner 来自插件 registry，而不是旧内置 runner 分支。
- `local-agent` 能消费 Host 模型、工具、知识库、history、state、artifact 等基础设施。
- 外部 harness runner（Claude Code / Codex）能消费 event-first context，并把 session / working directory 等指针写回 host-owned state。
- 错误、权限裁剪、无输出、timeout 等路径不会破坏主聊天流程。

本指南不验证：

- Runtime Control Plane v2。
- EventGateway / EventRouter 完整落地。
- 发布级 path isolation、secret filtering、MCP allowlist、资源配额和 workspace cleanup。
- 所有外部服务 runner 的真实凭据联调。

这些属于后续能力或发布门槛，分别见 [RUNTIME_CONTROL_PLANE_V2.md](./RUNTIME_CONTROL_PLANE_V2.md) 与 [SECURITY_HARDENING.md](./SECURITY_HARDENING.md)。

## 2. 状态定义

测试报告只使用以下状态：

| 状态 | 含义 |
| --- | --- |
| PASS | 按步骤执行，用户可见行为和日志证据都满足通过条件。 |
| FAIL | 环境可用，但行为不满足通过条件。 |
| BLOCKED | 凭据、CLI、外部服务、测试数据或本地配置缺失导致无法执行。必须写清阻塞原因。 |
| N/A | 当前 runner 或平台明确不支持该能力。必须引用 manifest、文档或配置说明。 |

不能使用“看起来正常”“大概通过”“基本没问题”等模糊状态。

## 3. 执行顺序

推荐按以下顺序执行，前一层失败时不要继续扩大测试面：

1. Host / SDK / runner 单测。
2. WebUI 登录与 Pipeline Debug Chat 基础 smoke。
3. `local-agent` 高价值场景。
4. Claude Code / Codex 外部 harness smoke。
5. 权限和错误路径补充检查。
6. 汇总 PASS / FAIL / BLOCKED，并给出下一步建议。

用户可见流程必须通过 WebUI 或真实消息平台验证。API / curl 只能作为诊断证据，不能单独让 UI case PASS。

## 4. 必跑基线

### 4.1 单测基线

在 LangBot 仓库运行：

```bash
uv run --frozen pytest tests/unit_tests/agent
```

如果本次改动只触及默认配置或 API service，也至少补跑相关目标测试，例如：

```bash
uv run pytest tests/unit_tests/api/test_pipeline_service_defaults.py
```

通过条件：

- agent 单测全 PASS，或失败项已确认与本次 agent-runner 路径无关。
- 若失败来自 `context_builder`、`orchestrator`、`session_registry`、`resource_builder`、`plugin/handler.py` 的 run action 权限路径，不应进入 UI smoke。

### 4.2 环境基线

用 `langbot-skills` 做环境检查：

```bash
cd "$LANGBOT_SKILLS_REPO"
bin/lbs env doctor
bin/lbs case list
```

`LANGBOT_SKILLS_REPO` 指向当前工作区里的 `langbot-skills` 仓库。优先使用已有 case，而不是临时发明测试路径。

推荐首批 case：

- `webui-login-state`
- `pipeline-debug-chat`
- `local-agent-basic-debug-chat`
- `local-agent-rag-debug-chat`（改动涉及 RAG / knowledge）
- `local-agent-plugin-tool-call-debug-chat`（改动涉及 tool / resource policy）

## 5. WebUI 主链路 Smoke

### 5.1 Runner registry

步骤：

1. 打开 WebUI Pipeline 配置页。
2. 查看 AI runner 下拉列表。
3. 选择 `plugin:langbot/local-agent/default`。
4. 保存并刷新页面。

通过条件：

- runner 选项来自插件 registry。
- 保存后配置仍为 `ai.runner.id` + `ai.runner_config[id]`。
- `runner_config` 表示 binding config，不表示插件实例状态。
- 插件没有循环重启或 metadata 加载失败。

### 5.2 主聊天路径

步骤：

1. 使用绑定 `plugin:langbot/local-agent/default` 的 Pipeline。
2. 在 Debug Chat 发送确定性普通文本。
3. 查看 WebUI 回复和后端日志。

通过条件：

- 用户可见回复正常。
- 后端日志显示走 `AgentRunOrchestrator` / `RUN_AGENT`。
- 不走旧内置 local-agent 主执行分支。
- conversation transcript 写入用户消息和助手消息。

## 6. `local-agent` 高价值测试

只保留最能覆盖架构边界的场景。

| ID | 场景 | 操作 | 通过条件 |
| --- | --- | --- | --- |
| LA-01 | 绑定 prompt | 配置 system prompt 后发送文本。 | runner 使用 `ctx.config.prompt`，不读取 `ctx.adapter.extra["prompt"]`；回复体现绑定 prompt。 |
| LA-02 | history API | 连续两轮对话，第二轮引用第一轮 marker。 | runner 通过 Host history API 或自管上下文读取历史，不依赖 bootstrap window。 |
| LA-03 | 流式 / 非流式 | 分别用支持流式和关闭流式的路径发送文本。 | 流式 UI 不重复、不空白；非流式只输出最终消息。 |
| LA-04 | 工具调用 | 绑定测试工具，发送会触发工具的 prompt。 | `ctx.resources.tools` 只包含授权工具；工具调用 started/completed；最终回复包含工具结果。 |
| LA-05 | RAG | 绑定测试知识库，发送命中文档的 prompt。 | `ctx.resources.knowledge_bases` 包含所选知识库；runner 通过授权 API 检索；回复使用检索内容。 |
| LA-06 | 多模态 | 发送图片输入。 | `ctx.input.contents` 保留图片；支持视觉模型时正常处理，不支持时受控失败。 |
| LA-07 | fallback / 错误 | 模拟 primary 模型失败或 runner 抛错。 | fallback 或 `run.failed` 行为受控；后续请求不受影响。 |
| LA-08 | 无输出保护 | 测试 runner 完成但不产出消息。 | 不产生空白成功回复；按受控失败或明确缺陷处理。 |

Rerank、remove-think、文件输入等场景只在本次改动直接涉及时补测，不作为每轮必跑项。

## 7. 外部 Harness Runner Smoke

这些测试用于验证 Claude Code / Codex 这类自管 runtime 能走同一条 Host 协议路径。若本机没有 CLI、登录态或代理配置，标记 BLOCKED，不要伪造 PASS。

### 7.1 Claude Code runner

步骤：

1. 确认 `claude` CLI 在 LangBot runtime host 上可执行。
2. 绑定 `plugin:langbot/claude-code-agent/default`。
3. 使用保守权限模式和确定性 prompt。
4. 在 Debug Chat 执行一次真实 smoke。
5. 检查 context / skill / MCP projection 和 host-owned state。

通过条件：

- WebUI 可见回复包含预期 sentinel。
- context JSON schema 为 `langbot.agent_runner.external_harness_context.v1` 或当前文档声明的等价 schema。
- context 包含 event、input、delivery、resources、context、state。
- 如启用 skills / MCP，投影路径和配置可被 Claude Code 读取。
- `external.session_id` / `external.working_directory` 写入 host-owned state。
- CLI missing、nonzero exit、timeout、empty output 都转成受控 `run.failed`。

### 7.2 Codex runner

步骤：

1. 确认 `codex` CLI 在 LangBot runtime host 上可执行。
2. 绑定 `plugin:langbot/codex-agent/default`。
3. 如需要代理，使用 binding config 的 `environment-json` 显式传入。
4. 在 Debug Chat 执行一次真实 smoke。
5. 检查 JSONL 事件、last message、host-owned state。

通过条件：

- WebUI 可见回复包含预期 sentinel。
- Codex JSONL 至少包含 thread/session 起始事件、agent message、turn completed。
- `external.session_id` / `external.working_directory` 写入 host-owned state。
- timeout/cancel 不遗留 orphan CLI 子进程。
- CLI missing、nonzero exit、timeout、empty output 都转成受控 `run.failed`。

### 7.3 API 型外部 runner

Dify、n8n、Coze、DashScope、Langflow、Tbox 等外部服务 runner 不作为每轮必跑项。只有在本次改动触及对应 runner 或凭据已经可用时执行 smoke。

通过条件：

- runner 可选，配置可保存。
- 请求成功，或外部服务错误被清晰返回。
- 外部服务凭据缺失时标记 BLOCKED，并记录缺失项。

## 8. 权限与隔离补充

以下优先用单测 / targeted fixture 覆盖，不要求每次通过 UI 人工构造恶意 runner。

| 场景 | 推荐证据 |
| --- | --- |
| 未授权模型调用被拒绝 | `plugin/handler.py` run action 权限测试或目标单测。 |
| 未授权工具调用被拒绝 | `ctx.resources.tools` 与 host action 拒绝日志。 |
| 未授权知识库检索被拒绝 | `ctx.resources.knowledge_bases` 与 host action 拒绝日志。 |
| run_id 结束后复用被拒绝 | session registry 注销测试。 |
| 插件身份不匹配被拒绝 | `caller_plugin_identity` mismatch 测试。 |
| storage/state scope 越权被拒绝 | state/storage proxy 单测。 |

如果这些单测失败，不能用 WebUI 正常回复替代。

## 9. 证据要求

每轮测试报告至少记录：

- LangBot commit、SDK commit、相关 runner 插件 commit。
- Pipeline UUID/name、runner id、关键 runner config 摘要。
- WebUI 截图或 Playwright 操作记录。
- 后端日志中对应 query id / run id 的关键行。
- `langbot-skills` case/report 路径。
- 外部 harness runner 的 context 文件、session id、working directory、CLI 错误摘要。
- FAIL/BLOCKED 的复现步骤和归属仓库建议。

报告结论必须回答：

- 是否建议继续进入下一阶段测试。
- 是否存在主聊天路径阻塞。
- 是否只是凭据 / 外部服务 / 本机 CLI 缺失导致 BLOCKED。
- 是否需要进入 [SECURITY_HARDENING.md](./SECURITY_HARDENING.md) 的发布级验收。

## 10. 历史高价值记录

历史报告已合并为本指南，不再保留单独文档。后续若需要追溯，优先查看 `langbot-skills/reports/` 下的原始执行报告。

截至 2026-05-29，已有本地 smoke 证明：

- `local-agent` 可以通过 Pipeline Debug Chat 走插件化 `AgentRunOrchestrator` 主链路。
- Claude Code runner 可以通过同一条 `run(event, binding)` 路径执行。
- Claude Code runner 可以读取 LangBot event-first context / skill / MCP 投影，并写回 `external.session_id` / `external.working_directory`。
- Codex runner 可以通过同一条路径执行，并把 Codex `thread_id` 写回 host-owned state。

这些记录只证明本地协议闭环可用，不代表发布级 security hardening 已完成。
