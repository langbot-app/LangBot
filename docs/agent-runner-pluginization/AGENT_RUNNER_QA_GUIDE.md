# Agent Runner QA 指南

本文档是 agent-runner 插件化下一轮测试的唯一 QA 入口。它合并并取代旧的 Phase 1 验收矩阵与 2026-05-18 / 2026-05-29 两份本地 QA 报告。

目标不是保留完整历史流水账，而是指导测试 agent 用最小但高价值的路径判断当前分支是否仍然健康。

## 1. 测试边界

当前主线验证的是 AgentRunner Protocol v1：

```text
event -> binding -> runner.run(ctx) -> result stream
```

本指南验证：

- Host 能通过当前 Query entry adapter 进入 event-first `run(event, binding)` 主链路。
- Runner 来自插件 registry，而不是旧内置 runner 分支。
- `local-agent` 能消费 Host 模型、工具、知识库、history、state、artifact 等基础设施。
- 外部 harness runner（当前为 LiteLLM Agent Platform 统一入口）能消费 event-first context，并把外部 session 指针写回 host-owned state。
- 错误、权限裁剪、无输出、timeout 等路径不会破坏主聊天流程。

本指南不验证：

- Runtime Control Plane v2。
- EventGateway / EventRouter 完整落地由外部 EBA 分支联调；本指南只验证本分支 Host 底座。
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
4. LiteLLM Agent Platform 外部 harness smoke。
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
- `runner_config` 表示 Agent/runner config，不表示插件实例状态。
- 不读取或回写旧 `ai.runner.runner` 字段。
- 不出现旧内置 runner stage 名（例如裸 `local-agent`）作为当前选中项或配置 surface。
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
| LA-02 | history API | 连续两轮对话，第二轮引用第一轮 marker。 | runner 通过 Host history API 或自管上下文读取历史，不依赖 inline history window。 |
| LA-03 | 流式 / 非流式 | 分别用支持流式和关闭流式的路径发送文本。 | 流式 UI 不重复、不空白；非流式只输出最终消息。 |
| LA-04 | 工具调用 | 绑定测试工具，发送会触发工具的 prompt。 | `ctx.resources.tools` 只包含授权工具；工具调用 started/completed；最终回复包含工具结果。 |
| LA-05 | RAG | 绑定测试知识库，发送命中文档的 prompt。 | `ctx.resources.knowledge_bases` 包含所选知识库；runner 通过授权 API 检索；回复使用检索内容。 |
| LA-06 | 多模态 | 发送图片输入。 | `ctx.input.contents` 保留图片；支持视觉模型时正常处理，不支持时受控失败。 |
| LA-07 | fallback / 错误 | 模拟 primary 模型失败或 runner 抛错。 | fallback 或 `run.failed` 行为受控；后续请求不受影响。 |
| LA-08 | 无输出保护 | 测试 runner 完成但不产出消息。 | 不产生空白成功回复；按受控失败或明确缺陷处理。 |
| LA-09 | steering / 运行中追加消息 | 使用支持 steering 的 runner，第一条消息触发长 run；run 未结束时在同 conversation 追加第二条消息。 | 第二条消息被 active run claim，不启动并发 run；runner 通过 `steering_pull` 看到追加输入；EventLog 有 `queued` -> `steering.injected`，若未消费则有 `steering.dropped` 终态；后续普通消息仍可处理。 |

Rerank、remove-think、文件输入等场景只在本次改动直接涉及时补测，不作为每轮必跑项。

## 7. LiteLLM Agent Platform Harness Smoke

这些测试用于验证 Claude Code / Codex 这类自管 runtime 经 LiteLLM Agent Platform 能走同一条 Host 协议路径。若 LiteLLM Agent Platform 服务不可用、目标 harness 没有 CLI/登录态/代理配置，标记 BLOCKED，不要伪造 PASS。

Smoke 前应优先保留一层轻量单测或 fixture 测试：LiteLLM Agent Platform HTTP session、消息发送、结果解析、`run_id` 提示词注入和 LangBot MCP gateway 必须有稳定测试覆盖。WebUI smoke 证明真实链路可用，但不能替代转换层和错误映射测试。

### 7.1 LiteLLM Agent Platform runner

步骤：

1. 确认 LiteLLM Agent Platform 服务可访问，目标 harness（例如 Claude Code 或 Codex）在该服务所在机器上可执行且已登录。
2. 绑定 `plugin:langbot/litellm-agent-platform-agent/default`。
3. 配置 `base-url`、`api-mode`、`agent-id` 或 `harness` 等必要字段。
4. 在 Debug Chat 执行一次确定性真实 smoke。
5. 检查 LangBot MCP gateway、`run_id` 回填和 host-owned state。

通过条件：

- WebUI 可见回复包含预期 sentinel。
- 发送给 LiteLLM 的消息包含当前 LangBot `run_id` 和可访问资源摘要。
- Harness 通过 gateway 调用 `langbot_history_page`、`langbot_retrieve_knowledge` 或 `langbot_call_tool` 时必须携带正确 `run_id`；错误 run id 被拒绝。
- `external.session_id` 写入 host-owned state。
- LiteLLM 服务错误、timeout、empty output 都转成受控 `run.failed`。
- resume 到同一 external session 时，全局锁边界符合 PROTOCOL_V1 §13。

### 7.2 API 型外部 runner

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
| 绑定插件身份的 run_id 省略 caller identity 被拒绝 | `_validate_run_authorization(..., caller_plugin_identity=None)` 返回错误。 |
| 未注册 Runtime 连接伪造插件身份被剥离 | SDK runtime forwarding 测试：请求自带 `caller_plugin_identity` 时，未注册连接转发前必须 `pop`，已注册连接必须覆盖为真实插件身份。 |
| storage/state scope 越权被拒绝 | state/storage proxy 单测。 |
| steering claim 异常不杀 consumer loop | controller 单测：无效 runner / registry 异常只让当前消息回到普通 session 槽位路径，消息消费循环继续。 |
| steering queue 未消费有终态 | session registry / orchestrator 单测：队列有上限；run unregister 时未 pull 项写 `steering.dropped` 审计。 |

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

历史高价值记录与当前 runner 验收状态见 [STATUS.md](./STATUS.md)。本指南只保留可重复执行的测试步骤和证据要求。
