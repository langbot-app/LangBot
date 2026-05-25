# Agent Runner 插件化 Phase 1 QA 验收矩阵

本文档用于指导测试 agent 验收 Phase 1：Agent Runner 插件化是否已经达到旧内置 runner 的对外效果。

Phase 1 的目标是让当前聊天 Pipeline 在选择插件化 AgentRunner 后，用户可感知行为与旧内置 runner 保持一致。Phase 2/EBA 不纳入本轮验收。

本文档是当前分支兼容性验收矩阵，不代表目标架构边界。目标协议以 [PROTOCOL_V1.md](./PROTOCOL_V1.md) 为准：Pipeline 是兼容入口，`messages` 只是 optional bootstrap，LangBot 不默认 inline 全量历史。

## 1. 验收边界

本轮必须验收：

- Pipeline 仍按现有消息入口运行。
- Runner 由插件提供，并通过 `AgentRunOrchestrator` 调用。
- `local-agent` 插件达到旧内置 local-agent 的主要行为 parity。
- 官方外部 runner 插件至少完成 smoke 验收。
- 旧 Pipeline 配置兼容，新配置可保存并生效。
- 权限裁剪、错误隔离、运行状态更新不破坏主流程。

本轮不验收：

- EBA EventBus。
- EBA EventRouter。
- 消息撤回、群成员加入、好友申请等非消息事件的真实接入。
- `action.requested` 平台动作执行。
- 新平台 API 权限模型。

上述非目标只允许检查协议预留是否存在，不允许作为 Phase 1 阻塞项。

## 2. 状态定义

测试 agent 只能使用以下状态：

| 状态 | 含义 |
| --- | --- |
| PASS | 按本矩阵步骤执行，所有通过条件满足，并记录证据。 |
| FAIL | 环境可用，但功能行为不满足通过条件。 |
| BLOCKED | 因缺少密钥、外部服务不可用、账号/OAuth 未完成、测试数据缺失等环境问题无法执行。必须写清阻塞原因。 |
| N/A | 当前插件或平台明确不支持该能力。必须引用 manifest capability、文档或配置说明。 |

不能使用“看起来正常”“大概通过”“未完全测试”等模糊状态。

## 3. 总体验收条件

Phase 1 可以关闭的最低条件：

- 所有 P0 case 必须 PASS。
- `local-agent` 的 P1 parity case 必须 PASS，除非该能力旧内置 runner 也不支持，此时可标 N/A。
- 官方外部 runner smoke case 至少对已具备凭据和服务的插件 PASS；缺凭据的插件可标 BLOCKED，但必须保留配置页面截图或日志说明。
- 没有会导致主聊天路径不可用、插件 runtime 崩溃、Pipeline 配置丢失、权限绕过的未解决 FAIL。
- 所有 FAIL/BLOCKED 都必须记录复现步骤、日志位置、截图或请求/响应摘要。

推荐测试前先运行：

```bash
uv run --frozen pytest tests/unit_tests/agent
```

Host 侧 agent runner 单测不通过时，不应进入 UI parity QA。

## 4. 证据要求

每个 case 至少记录：

- LangBot commit、SDK commit、相关 runner 插件 commit。
- Pipeline UUID/name、runner id、runner config 摘要。
- WebUI 截图或浏览器操作记录。
- 后端日志中对应 query id/run id 的关键行。
- 对外部 runner，记录外部服务响应摘要或错误码。

用户可见流程必须通过 WebUI 或真实消息平台验证。API/curl 只能作为诊断证据，不能单独让 UI case PASS。

## 5. P0 环境与主链路

| ID | 场景 | 步骤 | 通过条件 |
| --- | --- | --- | --- |
| P0-ENV-01 | LangBot 服务可用 | 启动后端和前端，打开 WebUI。 | WebUI 可登录/访问；后端无启动异常；插件系统按配置启用。 |
| P0-ENV-02 | 插件 runtime 可用 | 查看插件列表或后端日志。 | runtime 已启动；官方 runner 插件处于可用状态；无循环重启。 |
| P0-ENV-03 | Runner registry 可发现插件 runner | 打开 Pipeline AI runner 配置。 | runner 下拉列表来自插件 registry；至少能看到 `plugin:langbot/local-agent/default`。 |
| P0-ENV-04 | 默认 Pipeline 可创建 | 新建 Pipeline 或读取默认 Pipeline。 | 默认配置使用 `ai.runner.id` 与 `ai.runner_config`；默认 runner 可保存。 |
| P0-ENV-05 | 主聊天路径调用插件 runner | 使用默认 `local-agent` Pipeline 发送一条普通消息。 | 后端日志显示走 `AgentRunOrchestrator` / `RUN_AGENT`；用户收到正常回复；旧内置 runner 不应作为主路径执行。 |
| P0-ENV-06 | 单测基线 | 运行 `uv run --frozen pytest tests/unit_tests/agent`。 | 全部通过；若失败，必须先修复或记录为 P0 FAIL。 |

## 6. P1 local-agent parity

`local-agent` 是 Phase 1 的主验收对象。以下 case 需要和旧内置 local-agent 的用户可见行为对齐。

| ID | 场景 | 步骤 | 通过条件 |
| --- | --- | --- | --- |
| P1-LA-01 | 普通文本对话 | 绑定 `plugin:langbot/local-agent/default`，发送普通文本。 | 回复正常生成；conversation history 写入用户消息和助手消息。 |
| P1-LA-02 | 有效 prompt | 配置 system prompt，并通过 PromptPreProcessing 插件或现有预处理改变 prompt。 | runner 使用 host 处理后的 `ctx.adapter.extra["prompt"]`，不是只读取静态 `ctx.config.prompt`；回复体现有效 prompt。 |
| P1-LA-03 | 历史消息 | 连续多轮对话，第二轮引用第一轮内容。 | 当前兼容路径下 runner 能读到 host 下发的 bootstrap/history；目标协议下应通过 history API 或插件自管上下文实现。第二轮能基于上下文回答。 |
| P1-LA-04 | 流式输出 | 使用支持流式的 adapter/WebUI，开启流式模型或流式 runner。 | UI 逐步更新；后端接收 `message.delta`；最终没有重复消息或空白卡片。 |
| P1-LA-05 | 非流式输出 | 使用不支持流式或关闭流式的路径。 | 只输出最终消息；不会创建异常流式卡片。 |
| P1-LA-06 | 工具调用 | 绑定一个可调用工具，提问触发工具。 | `ctx.resources.tools` 只包含授权工具；runner 能获取工具详情并调用；最终回复包含工具结果。 |
| P1-LA-07 | 工具权限裁剪 | 不绑定某工具，但让 runner 尝试调用。 | 调用被拒绝；错误不泄露未授权工具详情；Pipeline 不崩溃。 |
| P1-LA-08 | RAG 检索 | 绑定知识库并提问命中文档。 | `ctx.resources.knowledge_bases` 包含所选知识库；runner 可检索；回复引用或使用检索内容。 |
| P1-LA-09 | RAG 权限裁剪 | 不绑定知识库或绑定另一个知识库。 | 未授权知识库不可检索；错误可控。 |
| P1-LA-10 | rerank | 绑定 rerank 模型并启用知识库检索排序。 | runner 可通过授权 rerank 模型排序；无权限时不允许调用。 |
| P1-LA-11 | fallback model | 配置 primary 和 fallback，模拟 primary 失败。 | fallback 被调用；用户得到可用回复或明确失败提示；日志能区分 primary/fallback。 |
| P1-LA-12 | remove-think | 开启输出 `remove-think`，使用会产生 think 内容的模型。 | 用户最终回复不包含被移除的 think 内容；插件 runner 走 runtime metadata 或 API 参数保持旧行为。 |
| P1-LA-13 | 多模态图片 | 发送图片输入。 | `ctx.input.contents` / `ctx.input.attachments` 保留图片；支持视觉模型时可正常处理；不支持时错误提示可控。 |
| P1-LA-14 | 文件输入 | 发送文件或文件 URL。 | runner 可看到文件 attachment 摘要；支持文件处理时正常处理；不支持时不崩溃。 |
| P1-LA-15 | 会话状态 | runner 返回 `state.updated`，下一轮继续对话。 | state 被 host 接收并作用于下一轮；conversation id 等兼容旧行为。 |
| P1-LA-16 | 异常处理 | 让 runner 返回 `run.failed` 或抛异常。 | ChatMessageHandler 使用 Pipeline 的异常策略；用户提示符合配置；runtime 和后续请求不受影响。 |
| P1-LA-17 | 无输出保护 | runner 完成但不返回消息。 | 不产生空白成功回复；应按受控失败处理或明确记录缺陷。 |

## 7. P1 配置兼容与迁移

| ID | 场景 | 步骤 | 通过条件 |
| --- | --- | --- | --- |
| P1-CFG-01 | 读取旧配置 | 使用只包含 `ai.runner.runner = local-agent` 和旧 `ai.local-agent` 配置的 Pipeline。 | 能解析为 `plugin:langbot/local-agent/default`；旧配置值生效。 |
| P1-CFG-02 | 保存新配置 | 在 WebUI 修改 runner 和 runner config 后保存。 | 数据库存储 `ai.runner.id` 和 `ai.runner_config[id]`；刷新页面后不丢失。 |
| P1-CFG-03 | runner 切换 | 同一 Pipeline 从 local-agent 切到另一个官方 runner，再切回。 | 每个 runner 的绑定配置独立保存；切换不污染其它 runner config。 |
| P1-CFG-04 | 插件缺失 | 配置引用一个未安装或未启动的 runner。 | WebUI/后端给出可理解错误；Pipeline 不因 metadata 加载失败整体不可用。 |
| P1-CFG-05 | bound plugin 授权 | Pipeline 只绑定部分插件。 | 未绑定插件的 runner 不能执行；已绑定插件正常执行。 |

## 8. P1 权限与隔离

| ID | 场景 | 步骤 | 通过条件 |
| --- | --- | --- | --- |
| P1-AUTH-01 | 模型权限 | runner 尝试调用不在 `ctx.resources.models` 的模型。 | Host action 拒绝；错误包含 run/session 维度信息；不会调用实际模型。 |
| P1-AUTH-02 | 工具权限 | runner 尝试调用不在 `ctx.resources.tools` 的工具。 | Host action 拒绝；不会越权执行工具。 |
| P1-AUTH-03 | 知识库权限 | runner 尝试检索不在 `ctx.resources.knowledge_bases` 的知识库。 | Host action 拒绝；不会返回未授权知识库内容。 |
| P1-AUTH-04 | 存储权限 | manifest 未声明 storage 权限时访问 plugin/workspace storage。 | 访问被拒绝；普通插件非 AgentRunner 的兼容路径不受影响。 |
| P1-AUTH-05 | run_id 生命周期 | runner 结束后继续使用旧 run_id 调 host action。 | session 已注销；请求被拒绝。 |
| P1-AUTH-06 | 插件身份隔离 | A 插件 runner 的 run_id 被 B 插件使用。 | Host 拒绝 identity mismatch。 |

## 9. P2 官方外部 runner smoke

以下 case 是 smoke，不要求和 local-agent 一样覆盖全部能力。若缺少外部服务凭据，状态标 BLOCKED，并记录缺失项。

| ID | Runner | 步骤 | 通过条件 |
| --- | --- | --- | --- |
| P2-EXT-01 | `dify-agent` | 配置 chat/agent/workflow 中至少一种可用应用并发送消息。 | runner 可选、配置可保存、请求成功或外部服务错误被清晰返回。 |
| P2-EXT-02 | `n8n-agent` | 配置 webhook 和认证方式并发送消息。 | webhook 被调用；返回内容进入 LangBot 回复；认证失败时提示明确。 |
| P2-EXT-03 | `coze-agent` | 配置 Coze 应用并发送文本，若可用再测图片。 | 文本回复正常；多模态能力按 manifest/配置表现；思维链处理不污染最终回复。 |
| P2-EXT-04 | `dashscope-agent` | 配置 agent 或 workflow 并发送消息。 | 调用成功；失败时错误可控且不影响后续请求。 |
| P2-EXT-05 | `langflow-agent` | 配置 flow endpoint 并发送消息。 | 普通或 SSE 流式响应能归一为 LangBot 消息。 |
| P2-EXT-06 | `tbox-agent` | 配置 Tbox 应用并发送消息。 | 回复正常；多模态输入按插件能力处理。 |

## 10. P2 事件预留检查

这些只检查协议预留，不要求真实平台事件接入。

| ID | 场景 | 步骤 | 通过条件 |
| --- | --- | --- | --- |
| P2-EVT-01 | 消息事件名稳定 | 触发普通消息 runner。 | `ctx.trigger.type` 和 `ctx.event.event_type` 为 `message.received`；平台原始类型保存在 `ctx.event.event_data.source_event_type`。 |
| P2-EVT-02 | 非消息事件名预留 | 检查 host 侧保留事件名。 | `message.recalled`、`group.member_joined`、`friend.request_received` 作为稳定协议名存在。 |
| P2-EVT-03 | action.requested 预留 | 让测试 runner 返回 `action.requested`。 | Host 只记录日志，不执行平台动作，不影响主流程。 |

## 11. 退出标准

QA agent 完成后应输出一份报告，至少包含：

- 总状态：PASS / FAIL / BLOCKED。
- 每个 case 的状态表。
- 所有 FAIL 的复现步骤和建议归属仓库。
- 所有 BLOCKED 的环境缺口。
- 是否建议关闭 Phase 1，进入 Phase 2/EBA。

建议关闭 Phase 1 的条件：

- P0 全 PASS。
- P1 全 PASS，或只有旧内置 runner 同样不支持的 N/A。
- P2 外部 runner smoke 对可用凭据全部 PASS。
- 剩余问题均为 EBA 预留、外部服务凭据、或非阻塞体验问题。
