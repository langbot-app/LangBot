# Agent 统一编排（产品最终形态）

> **状态**：方向修订稿（2026-06-12），供「适配器改造 / Agent 插件化 / 工作流引擎」三条工作线评审。
>
> 本文档修订 [00-overview.md](./00-overview.md) §3.4 与 [04-event-routing.md](./04-event-routing.md) 中"四种 Handler"的编排模型：**所有编排目标统一收编为 Agent 抽象**。事件路由的匹配机制、数据迁移策略、WebUI 交互骨架等内容仍以 04 为准，仅 handler 分类法被本文档取代。

## 1. 产品最终形态

**适配器接收各种事件 → 用户编排处理逻辑 → Agent 统一抽象**，实现从 0 代码到低代码再到全代码的全层面支持：

```
消息平台 (Telegram / Discord / 企微 / ...)
  │ 各类平台事件
  ▼
平台适配器（EBA 新结构，已迁移 12 个）
  │ EBAEvent (message.* / group.* / friend.* / bot.* / feedback.* / platform.*)
  ▼
EventRouter（事件 → Agent 绑定）
  ├─→ 选中的 Agent（响应者，单一仲裁）
  │     ├─ 内置：pipeline-wrapper（旧流水线收编）/ local-agent
  │     ├─ 插件：SDK Agent 组件（全代码）
  │     ├─ 低代码：工作流定义的 Agent（内部工作流引擎）
  │     └─ 外部：dify / n8n / coze / dashscope / webhook（RequestRunner 体系收编）
  │
  └─→ 插件 EventListener（观察者，N 个广播，可 prevent_default）
```

| 编写方式 | Agent 形态 | 代码化程度 |
|----------|-----------|-----------|
| WebUI 配置模型 + 提示词 + 工具 | 内置 local-agent | 0 代码 |
| 沿用现有流水线 | pipeline-wrapper 内置 Agent | 0 代码（兼容） |
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

**汇合点是 SDK 的 Agent 组件契约（§4）与 event→agent 绑定模型（§3）**。这两个接口冻结后，三条线可彼此 mock 独立推进。契约由本分支（EBA）牵头起草，三线评审后在 langbot-plugin-sdk 落地（发布通道：0.5.0aX pre-release 已打通）。

## 2. 从四种 Handler 到 Agent 统一抽象

### 2.1 演进理由

04 文档中的 pipeline / agent / webhook / plugin 四种 handler_type，本质上都是"对事件作出响应的逻辑"，差别只在编写和部署方式。为四种类型分别设计配置表单、执行语义和扩展机制，等于把同一个概念做四遍。统一为 Agent 后：

- **产品**：用户只学一个概念——"给 Bot 的事件绑 Agent"；
- **工程**：路由层退化为很薄的 event → agent 分发，所有扩展集中到 Agent 抽象；
- **生态**：Agent 成为市场上可分发、可复用的一等公民。

### 2.2 收编映射

| 原 handler_type（04 文档） | 收编后 |
|---------------------------|--------|
| `pipeline` | 内置 `pipeline-wrapper` Agent：实例配置为 `pipeline_uuid`，进程内直接复用 MessageAggregator → QueryPool → Pipeline 机制 |
| `agent`（RequestRunner） | 现有 Runner 体系（local-agent / dify / n8n / coze / dashscope / langflow / tbox）整体收编为内置 Agent 家族——Runner 本来就是"Agent 抽象"的前身 |
| `webhook` | 外部 Agent 的一种：事件 POST 出去、响应解析为动作（保留 04 §5.4 的请求/响应格式） |
| `plugin`（EventListener 分发） | **不收编**——角色不同，见 §2.3 |

### 2.3 响应者与观察者的角色切分

事件的消费方有两种角色，不应混为一谈：

- **响应者（Agent）**：路由选中**一个**，负责对事件作出回应（回复消息、执行动作）。多条绑定匹配同一事件时按 priority 仲裁，只取最高者。
- **观察者（插件 EventListener）**：**广播**给所有注册插件，做旁路逻辑（日志、审计、风控、统计）。沿用现有机制不变，包括 `prevent_default()`——观察者可拦截本次事件，使 Agent 不被调用（与现有"插件拦截流水线"行为完全兼容）。

执行顺序：事件到达 → 先广播观察者（按插件优先级）→ 若未被 prevent_default → 分发给选中的 Agent。

## 3. 数据模型：event → agent 绑定

### 3.1 Agent 实体化（推荐）

Agent 作为一等实体（独立表），用户先创建/安装 Agent，再在 Bot 上把事件绑定到 Agent。好处：跨 Bot 复用、市场分发、独立的配置页面。

```python
class Agent(Base):
    """Agent 实例：一个具体配置过的、可被事件绑定的响应者"""
    uuid: str                # 主键
    name: str
    kind: str                # "builtin" | "plugin"
    component_ref: str       # 内置: "pipeline-wrapper" / "local-agent" / "dify" / "webhook" / ...
                             # 插件: "<plugin_author>/<plugin_name>/<agent_component_name>"
    config: dict             # JSON — 实例配置（pipeline_uuid / 模型与提示词 / 外部平台凭据 / 工作流 id ...）
    # 多租户预留：归属主体字段（tenant/workspace），首版可空
```

Bot 上的绑定配置（替代 04 §2.2 的 EventHandlerConfig，沿用其匹配语义）：

```python
class EventBinding(pydantic.BaseModel):
    event_type: str          # 精确 / "message.*" / "*"，匹配规则同 04 §4
    agent_uuid: str          # 绑定的 Agent 实例
    enabled: bool = True
    priority: int = 0        # 多条匹配时取最高者（单一仲裁）
    description: str = ''
```

`use_pipeline_uuid` 自动迁移：为每个被引用的 pipeline 生成一个 `pipeline-wrapper` Agent 实例，并写入 `{"event_type": "message.received", "agent_uuid": <wrapper>}` 绑定。观察者广播不需要配置（始终发生），04 中"兜底 plugin 规则"不再需要。

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
**内置与插件同构**：内置 Agent（pipeline-wrapper、local-agent、各外部平台）在 LangBot 进程内实现同一接口注册，不过 RPC；插件 Agent 经 plugin runtime 分发。对路由层二者不可区分。

### 4.3 执行语义与可靠性

| 关注点 | 约定 |
|--------|------|
| 仲裁 | 单响应者：priority 最高的匹配绑定生效，其余忽略 |
| 性能 | 内置 Agent 进程内零额外开销；插件 Agent 每事件过一次 RPC 边界，消息场景需设延迟预算（评审项：目标 P95 附加延迟） |
| 会话状态 | 归 LangBot 侧（SessionHandle），插件 Agent 原则上无状态，崩溃重启不丢会话 |
| 降级 | Agent 调用失败/超时：可配置 fallback（回错误提示，或指定备用 Agent）；pipeline-wrapper 作为进程内兜底与性能对照组 |
| 多租户预留 | AgentContext / SessionHandle / 存储接口显式携带归属主体标识，禁止新增全局单例状态——为后续轻量 SaaS 多租户铺路 |

## 5. 发布火车

| 版本 | 内容 | 备注 |
|------|------|------|
| 4.11（可选） | 现状成果：12 个 EBA 适配器、插件全事件订阅、`call_platform_api` | 对用户不可见的管道工程 + 插件新能力，不动产品概念 |
| **5.0** | 产品形态首发：EventRouter + event→agent 绑定 + WebUI 编排 + 数据迁移 + 内置 Agent（pipeline-wrapper、local-agent、外部平台家族）+ SDK Agent 组件契约（可标 experimental） | 资格线不依赖其他两线交付；配 SDK 0.5.0 正式版；走 beta 周期；deprecation（旧 sources 适配器、legacy/*、use_pipeline_uuid）集中在此窗口处理 |
| 5.x | 工作流 Agent（工作流引擎线挂入）、Agent 市场生态、剩余适配器（satori 等）、Agent 插件化收尾 | 验证开放注册机制 |
| 多租户 | 独立评估：仅数据隔离 → 5.x 部署选项；伴随权限/计费/产品定位变化 → 6.0 | 前置条件是 §4.3 的归属主体预留已落实 |

## 6. 开放问题（评审清单）

1. **webhook 的最终定位**：作为外部 Agent（响应者，现方案）之外，是否还需要"纯通知观察者"形态（现 WebhookPusher 的角色）？
2. **多 Agent 协作**：单一仲裁之外，是否需要"串联/并联多个 Agent"的场景？（建议 5.0 不做，留给工作流引擎表达）
3. **工作流引擎的宿主**：核心内置，还是自身也作为一个插件交付（解释工作流定义的 Agent 插件）？
4. **插件 Agent 的延迟预算**：消息主链路过 RPC 的 P95 目标值与压测方案。
5. **Pipeline 的长期命运**：pipeline-wrapper 兼容期多长，Stage 体系是否在 6.0 退役或被工作流引擎吸收。
6. **SDK 1.0 时机**：Agent 契约稳定后是否随 LangBot 5.x 给插件生态一个 API 稳定承诺。
