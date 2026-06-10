# Run Steering 与 Compaction Checkpoint（Future Design Note）

本文档描述两项尚未落地的 Host 能力缺口：**运行中消息注入（steering / follow-up）**和
**压缩摘要持久化（compaction checkpoint）**。两者来自官方 local-agent 对照
Pi agent harness（`pi-mono/packages/agent`，下称 pi-agent-core）的差距分析：
local-agent 已移植 Pi 的事件生命周期、并行工具语义、hook 扩展点和压缩预算模型，
但这两项无法由 runner 单方面闭环，需要 Host 协议或授权配合。

> 本文是设计备忘，不是 schema 事实源。涉及的数据结构最终落到
> [PROTOCOL_V1.md](./PROTOCOL_V1.md)；上下文边界语义以
> [AGENT_CONTEXT_PROTOCOL.md](./AGENT_CONTEXT_PROTOCOL.md) 为准；
> run 持久化与控制原语以 [RUNTIME_CONTROL_PLANE_V2.md](./RUNTIME_CONTROL_PLANE_V2.md) 为准。

## 1. Run Steering / Follow-up（运行中消息注入）

### 1.1 问题

IM 场景下用户在 agent 运行中追加消息非常常见（补充信息、纠正方向、"算了别查了"）。
当前主线是 `one event -> one AgentBinding -> one run_id -> one runner`
（PROTOCOL_V1 §13）：同会话的新消息要么等待当前 run 结束后触发新 run，
要么并发触发独立 run。两种行为都无法把新消息送进**正在执行的 tool loop**，
用户体验是"agent 自顾自跑完过期任务，然后才看到新消息"。

cancel（PROTOCOL_V1 §10）不解决这个问题：cancel 丢弃已完成的工作；
steering 是在保留当前进度的前提下改变后续方向。

### 1.2 Pi 的参考语义

pi-agent-core 区分两个队列，注入时机都在 turn 边界，不打断进行中的模型流或工具执行：

- **steering**：运行中插入。当前 assistant 消息的全部 tool call 完成后、
  下一次模型调用前，注入排队的用户消息；模型在下一 turn 看到它们。
- **follow-up**：排队后续工作。仅当没有 pending tool call 且没有 steering 消息、
  run 即将自然结束时检查；若有排队消息则注入并继续下一 turn，而不是结束 run。

两个队列各自支持 `one-at-a-time`（每次注入一条）和 `all`（一次注入全部）模式。

### 1.3 设计方向

职责划分遵循既有原则：Host 拥有事件路由和会话事实源，runner 拥有 turn 边界。

- **Host 侧**：BindingResolver / dispatch 层识别"同 conversation 存在 active run
  且 runner 声明支持 steering"的新消息事件，将其写入 run-scoped steering queue，
  并标记该事件已被在途 run 认领（不再触发新 run，避免破坏 §13 的基数约束）。
  事件仍照常进 EventLog / Transcript（事实源不变，改变的只是触发行为）。
- **Runner 侧**：在 turn 边界（tool batch 完成后、下一次模型调用前，以及 run
  即将自然结束前）通过 run-scoped pull API 拉取 pending steering 输入，
  注入 working context。local-agent 的 `AgentLoopHooks.prepare_next_turn` /
  `should_stop_after_turn` 已预留了对应的注入点。
- **能力协商**：runner manifest 声明 `steering` capability（参照 PROTOCOL_V1 §4.3）；
  未声明的 runner 保持现状（新消息按现有规则另起 run）。
- **回执**：被 steering 消费的事件需要可审计的归属记录（event 被哪个 run_id 认领、
  是否最终注入成功），形式可以是新的 result type 或 EventLog 记录，落协议时定。

需要新增的协议面（最终定义归 PROTOCOL_V1）：

1. `ContextAccess.available_apis` 增加 steering pull 能力位。
2. `AgentRunAPIProxy` 增加 steering 拉取 action（含 one-at-a-time / all 语义参数）。
3. dispatch 层的"认领"规则：什么事件类型可被 steering 吸收、超时未拉取如何回退
   （建议：run 结束或 deadline 到期时，未消费的排队事件按普通事件重新触发 run）。

### 1.4 边界

- 不引入 Host 替 runner 做 prompt 拼接：Host 只递队列，注入位置和格式由 runner 决定。
- 不与 observer / fan-out 混淆：steering 仍是单 run 内的输入补充，不产生第二个 runner。
- 远程 / 外部 harness runner（claude-code、codex 等）若其底层 session 自带
  steering 能力，adapter 可以直接转发；协议面保持一致。

## 2. Compaction Checkpoint 持久化

### 2.1 问题

local-agent 当前是无状态 runner：每次 run 重新拉取 transcript 尾部
（默认 50 条）、重新估算 token、重新生成压缩摘要。后果：

- 长会话中每 run 重复压缩计算，摘要每次重新生成，不同 run 之间措辞漂移，
  对 provider KV cache 不友好（AGENT_CONTEXT_PROTOCOL §"Summary checkpoint 稳定"
  已写明期望：只有压缩发生时才产生新 checkpoint）。
- 历史一旦超过 fetch limit，更早的内容永久不可见——没有 checkpoint 记录
  "已压缩到哪里、压缩出了什么"。

pi-agent-core 把 compaction 条目持久化进 session tree：摘要带
`tokensBefore` 和覆盖范围，后续 turn 直接复用，只在再次越过阈值时增量压缩。

### 2.2 现状盘点

协议面基本已备齐，缺的是消费约定和授权：

- State / Storage API 已定义（PROTOCOL_V1 §8 "State / Storage"），
  且 AGENT_CONTEXT_PROTOCOL 已点名 `summary.checkpoint` 是 state 的预期用法。
- `ContextAccess.available_apis.state` 默认 `false`（PROTOCOL_V1 §5.8）；
  Host 尚未对 local-agent binding 默认开启。
- local-agent 侧完全未消费：不读不写 checkpoint（其 README "Current Boundary"
  已声明这是预期的未来工作）。
- LLM 生成摘要**不依赖**本项 Host 能力——runner 用已授权的 `invoke_llm`
  即可生成，可以先行实现；本项只解决"存下来、下次复用"。

### 2.3 设计方向

- **存放位置**：state，scope=`conversation`（小 JSON，符合 PROTOCOL_V1 §8
  对 state/storage 的边界建议）。若未来摘要膨胀，超出部分放 storage 并在
  state 中留引用。
- **key 约定**：`runner.compaction.checkpoint`（runner 命名空间内）。
- **内容约定**（schema 落 PROTOCOL_V1 或 runner 文档，此处只列语义）：
  - `schema_version`
  - `summary`：压缩摘要文本（LLM 生成或确定性生成）
  - `covers_until`：已被摘要覆盖的 transcript 游标（seq / message id），
    是增量压缩和"从哪继续拉历史"的锚点
  - `tokens_before` / `created_at`：诊断与失效判断
- **消费流程**：run 开始时读 checkpoint → 只拉取 `covers_until` 之后的
  transcript → 压缩触发时基于旧摘要增量生成新摘要、写回新 checkpoint。
  checkpoint 缺失或解析失败时回退到现行为（全量拉尾部），保证向后兼容。
- **失效规则**：`covers_until` 在 Host transcript 中不存在（会话被清理 / 重置）
  即作废；runner 不得信任跨 conversation 的 checkpoint。
- **授权**：Host 对声明需要 state 的 runner binding 开启
  `available_apis.state`；校验沿用现有 run-scoped state 校验
  （scope、key、value 大小、JSON 可序列化，见 PROTOCOL_V1 §7.2 对
  `state.updated` 的要求）。

### 2.4 相关但独立的工作

- **tokenizer / usage metadata 透传**：runner 目前用 chars/4 启发式估 token，
  对 CJK 偏低 3-4 倍，压缩触发系统性偏晚。Host 应在模型响应或
  `ctx.runtime.metadata` 透传 provider usage（prompt/completion tokens）与
  model context window（LiteLLM model-info 工作）。该项不阻塞 checkpoint
  落地，但决定压缩触发的准确性。

## 3. 实施拆分

| 项 | 归属 | 依赖 |
| --- | --- | --- |
| steering queue、事件认领、超时回退 | LangBot Host（dispatch / binding 层） | 无 |
| steering pull API + capability 位 | PROTOCOL_V1 + SDK proxy | 上一项 |
| turn 边界拉取与注入 | langbot-local-agent（hooks 已预留） | 上两项 |
| local-agent 对 state API 的 checkpoint 读写 | langbot-local-agent | Host 开启 `available_apis.state` |
| checkpoint key / 内容 / 失效约定 | 本文档 → PROTOCOL_V1 | 无 |
| LLM 压缩摘要生成 | langbot-local-agent | 无（`invoke_llm` 已可用） |
| usage / context-window metadata 透传 | LangBot Host（model 层） | LiteLLM model-info |

建议顺序：checkpoint 先行（协议面现成，改动集中在授权和 runner 消费），
steering 后行（需要新协议面和 dispatch 行为变更）。

## 4. 开放问题

- steering 注入的消息在 Transcript 中如何与普通消息区分（审计需要区分
  "作为新 run 触发"与"被在途 run 吸收"）。
- 多条排队消息的合并语义由谁定：Host 全量递给 runner，还是支持
  one-at-a-time 协商；建议 Host 全量递、runner 自行决定消费节奏。
- streaming delivery 下 steering 注入后，前序 turn 已流出的内容与新 turn
  输出在 IM 消息编辑面的衔接（涉及 `ctx.delivery` 能力，待 delivery 演进定）。
- checkpoint 是否需要 Host 侧主动失效通知（如会话清空时删除对应 state key），
  还是仅靠 runner 读取时校验 `covers_until`。
