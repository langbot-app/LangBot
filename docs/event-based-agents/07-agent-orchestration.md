# Agent 与 Pipeline 统一编排（产品最终形态）

> **状态**：方向修订稿（2026-06-12），供「适配器改造 / Agent 插件化 / 工作流引擎」三条工作线评审。
>
> 本文档修订 [00-overview.md](./00-overview.md) §3.4 与 [04-event-routing.md](./04-event-routing.md) 中"四种 Handler"的编排模型：**所有编排目标统一进入处理器选择与事件绑定界面，但独立 Agent 与现有 Pipeline 保持不同类型**。事件路由的匹配机制、数据迁移策略、WebUI 交互骨架等内容仍以 04 为准，仅 handler 分类法被本文档取代。

## 1. 产品最终形态

**适配器接收各种事件 → 用户编排处理逻辑 → 处理器统一选择表面**，实现从 0 代码到低代码再到全代码的全层面支持：

```
消息平台 (Telegram / Discord / 企微 / ...)
  │ 各类平台事件
  ▼
平台适配器（EBA 新结构，已迁移 12 个）
  │ EBAEvent (message.* / group.* / friend.* / bot.* / feedback.* / platform.*)
  ▼
EventRouter（事件 → 处理器绑定）
  ├─→ 选中的处理器（响应者，单一仲裁）
  │     ├─ Pipeline：保留现有实体和执行链，仅处理消息事件
  │     └─ Agent：用户新建并选择 AgentRunner 插件，可接本地、低代码或外部 runtime
  │
  └─→ 插件 EventListener（观察者，N 个广播，可 prevent_default）
```

| 编写方式 | 处理器形态 | 代码化程度 |
|----------|-----------|-----------|
| WebUI 配置模型 + 提示词 + 工具 | 独立 Agent + LocalAgent 插件 | 0 代码 |
| 可视化消息编排 | Pipeline（`kind=pipeline`，完整多 Stage 链） | 0 代码 |
| 市场安装 | Agent 插件（市场分发） | 0 代码（使用者视角） |
| 可视化工作流 | 工作流引擎定义的 Agent | 低代码 |
| 对接外部平台 | dify / n8n / coze / webhook 外部 Agent | 集成 |
| SDK 编写 | Agent 插件组件 | 全代码 |

### 1.1 三条并行工作线与汇合点

| 工作线 | 范围 | 在本架构中的位置 |
|--------|------|------------------|
| 适配器改造（refactor/eba，本分支） | 事件体系、适配器结构、平台 API、EventRouter | 事件的**生产侧** + 路由层 |
| Agent 插件化 | Agent 抽象、Agent 组件类型、市场分发 | 事件的**消费侧**统一抽象 |
| 工作流引擎 | 内部低代码工作流 | Agent 的一种**编写方式** |

**汇合点是 SDK 的 Agent 组件契约（§4）与 event→处理器绑定模型（§3）**。这两个接口冻结后，三条线可彼此 mock 独立推进。契约由本分支（EBA）牵头起草，三线评审后在 langbot-plugin-sdk 落地（发布通道：0.5.0aX pre-release 已打通）。

## 2. 从四种 Handler 到统一处理器表面

### 2.1 演进理由

04 文档中的 pipeline / agent / webhook / plugin 四种 handler_type，本质上都是"对事件作出响应的逻辑"，差别只在编写和部署方式。产品层统一展示和绑定这些处理器，但不会把既有 Pipeline 持久化为 Agent：

- **产品**：用户只需理解"给 Bot 的事件绑定处理器"，处理器可以是 Pipeline 或 Agent；
- **工程**：路由层按 `target_type` 分发到 Pipeline 或 Agent，Agent 的扩展集中到 AgentRunner 抽象；
- **生态**：Agent 成为市场上可分发、可复用的一等公民。

### 2.2 收编映射

| 原 handler_type（04 文档） | 收编后 |
|---------------------------|--------|
| `pipeline` | 保留 Pipeline 实体；binding 使用 `target_type=pipeline` 和原 `pipeline_uuid`，进程内直接复用 MessageAggregator → QueryPool → Pipeline 机制 |
| `agent`（RequestRunner） | 用户新建独立 Agent，并选择对应 AgentRunner 插件；不读取或复制旧 Pipeline 内嵌 runner 配置 |
| `webhook` | 外部 Agent 的一种：事件 POST 出去、响应解析为动作（保留 04 §5.4 的请求/响应格式） |
| `plugin`（EventListener 分发） | **不收编**——角色不同，见 §2.3 |

### 2.3 响应者与观察者的角色切分

事件的消费方有两种角色，不应混为一谈：

- **响应者（Pipeline 或 Agent）**：路由选中**一个**，负责对事件作出回应（回复消息、执行动作）。多条绑定匹配同一事件时按 priority 仲裁，只取最高者。
- **观察者（插件 EventListener）**：**广播**给所有注册插件，做旁路逻辑（日志、审计、风控、统计）。沿用现有机制不变，包括 `prevent_default()`——观察者可拦截本次事件，使处理器不被调用（与现有"插件拦截流水线"行为完全兼容）。

执行顺序：事件到达 → 先广播观察者（按插件优先级）→ 若未被 prevent_default → 分发给选中的处理器。

## 3. 数据模型：event → 处理器绑定

### 3.1 独立 Agent 与现有 Pipeline

Agent 与 Pipeline 都是一等处理器。用户创建 Agent、选择已安装的 AgentRunner，再把适合的事件绑定到 Agent；Pipeline 继续保存在 Pipeline 表中，以完整 Stage 链处理消息事件。两者可在同一处理器列表中以不同 `kind` 展示和选择；这种聚合展示不会创建额外记录，也不会在两种模型之间复制配置。

```python
class Agent(Base):
    """Agent 实例：一个具体配置过的、可被事件绑定的响应者"""
    uuid: str                # 主键
    name: str
    kind: str                # 固定为 "agent"；Pipeline 使用自己的持久模型
    component_ref: str       # AgentRunner id，例如 plugin:<author>/<plugin>/<runner>
    config: dict             # JSON — runner id、runner config 与资源/状态/投递策略
    # 多租户预留：归属主体字段（tenant/workspace），首版可空
```

Bot 上的绑定配置（替代 04 §2.2 的 EventHandlerConfig，沿用其匹配语义）：

```python
class EventBinding(pydantic.BaseModel):
    event_pattern: str       # 精确 / "message.*" / "*"，匹配规则同 04 §4
    target_type: str         # "agent" | "pipeline" | "discard"
    target_uuid: str         # Agent 或 Pipeline 的原始 UUID；discard 时为空
    enabled: bool = True
    priority: int = 0        # 多条匹配时取最高者（单一仲裁）
    description: str = ''
```

`use_pipeline_uuid` 只迁移 Bot 的路由结构：写入 `{"event_pattern": "message.received", "target_type": "pipeline", "target_uuid": <原 pipeline uuid>}`，继续引用原 Pipeline。迁移不会创建独立 Agent，也不会复制 Pipeline 内嵌的 runner 配置；需要 Agent 的用户自行新增 Agent 并修改 binding。观察者广播不需要配置（始终发生），04 中"兜底 plugin 规则"不再需要。

## 4. SDK Agent 组件契约（草案）

Agent 成为插件系统的第七种组件（现有：Command / Tool / EventListener / KnowledgeEngine / Parser / Page）。

### 4.1 Manifest

```yaml
apiVersion: v1
kind: Agent
metadata:
  name: group-assistant
  label: { en_US: Group Assistant, zh_Hans: 群助理 }
spec:
  handled_events:            # 声明可处理的事件类型；绑定 UI 据此过滤
    - message.received
    - group.member_joined
  config:                    # 实例化配置 schema，复用现有组件配置体系
    - name: model
      type: llm-model-selector
    - name: persona
      type: prompt-editor
execution:
  python: { path: agent.py, attr: GroupAssistant }
```

### 4.2 运行时接口

```python
class Agent(BaseComponent):
    async def handle(self, ctx: AgentContext) -> typing.AsyncGenerator[AgentChunk, None]:
        """处理一次事件，流式产出回复与动作。每次事件调用一次。"""
        ...

class AgentContext:
    event: EBAEvent              # 触发事件（统一事件体系）
    bot: BotHandle               # 来源 Bot 信息
    session: SessionHandle       # 会话句柄：历史消息、会话变量（LangBot 侧管理，Agent 保持无状态）
    config: dict                 # 该 Agent 实例的配置

    # 能力面（经 runtime RPC 回 LangBot 执行）：
    async def reply(self, chain: MessageChain, quote: bool = False): ...
    async def send_message(self, target_type: str, target_id: str, chain: MessageChain): ...
    async def call_platform_api(self, action: str, params: dict) -> dict: ...
    async def invoke_llm(self, model_uuid: str, messages: list, funcs: list = None) -> dict: ...
    # + 工具调用 / KB 检索 / 插件存储（沿用 LangBotAPIProxy 既有方法）

class AgentChunk:
    delta_message: MessageChain | None = None   # 增量回复（流式）
    actions: list[dict] | None = None           # 平台动作（同 webhook response_actions 格式）
    final: bool = False
```

**流式**：复用 SDK 通信协议既有的 `chunk_status: continue/end` 机制，`handle()` 的每次 yield 对应一个 chunk。
**Pipeline 与 Agent 分流**：Pipeline target 继续走 LangBot 进程内的 Pipeline 执行链；独立 Agent 经 AgentRunner 插件 runtime 分发。路由层通过 binding 的 `target_type` 明确区分二者。

### 4.3 执行语义与可靠性

| 关注点 | 约定 |
|--------|------|
| 仲裁 | 单响应者：priority 最高的匹配绑定生效，其余忽略 |
| 性能 | Pipeline 继续走进程内链路；插件 Agent 每事件过一次 RPC 边界，消息场景需设延迟预算（评审项：目标 P95 附加延迟） |
| 会话状态 | 归 LangBot 侧（SessionHandle），插件 Agent 原则上无状态，崩溃重启不丢会话 |
| 降级 | Agent 调用失败/超时：可配置 fallback（回错误提示，或指定备用处理器）；不会隐式回退到旧 Pipeline 配置 |
| 多租户预留 | AgentContext / SessionHandle / 存储接口显式携带归属主体标识，禁止新增全局单例状态——为后续轻量 SaaS 多租户铺路 |

## 5. 发布火车

| 版本 | 内容 | 备注 |
|------|------|------|
| 4.11（可选） | 现状成果：12 个 EBA 适配器、插件全事件订阅、`call_platform_api` | 对用户不可见的管道工程 + 插件新能力，不动产品概念 |
| **5.0** | 产品形态首发：EventRouter + event→处理器绑定 + WebUI 编排 + 旧 Bot 路由迁移 + 独立 Agent / AgentRunner 插件 + SDK Agent 组件契约（可标 experimental） | `use_pipeline_uuid` 仅改写为指向原 Pipeline 的 binding，不生成 Agent；配 SDK 0.5.0 正式版；走 beta 周期 |
| 5.x | 工作流 Agent（工作流引擎线挂入）、Agent 市场生态、剩余适配器（satori 等）、Agent 插件化收尾 | 验证开放注册机制 |
| 多租户 | 独立评估：仅数据隔离 → 5.x 部署选项；伴随权限/计费/产品定位变化 → 6.0 | 前置条件是 §4.3 的归属主体预留已落实 |

## 6. 开放问题（评审清单）

1. **webhook 的最终定位**：作为外部 Agent（响应者，现方案）之外，是否还需要"纯通知观察者"形态（现 WebhookPusher 的角色）？
2. **多 Agent 协作**：单一仲裁之外，是否需要"串联/并联多个 Agent"的场景？（建议 5.0 不做，留给工作流引擎表达）
3. **工作流引擎的宿主**：核心内置，还是自身也作为一个插件交付（解释工作流定义的 Agent 插件）？
4. **插件 Agent 的延迟预算**：消息主链路过 RPC 的 P95 目标值与压测方案。
5. **Workflow 的处理器边界**：未来 Workflow 应作为与 Pipeline、Agent 平级的处理器，还是作为其中一种处理器的内部编排实现。
6. **SDK 1.0 时机**：Agent 契约稳定后是否随 LangBot 5.x 给插件生态一个 API 稳定承诺。
