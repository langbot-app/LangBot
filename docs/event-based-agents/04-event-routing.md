# 事件路由与编排

> 状态：当前实施模型（2026-07-12）。本文以 Pipeline / Agent 平级并存为准，不再保留早期 `pipeline / agent / webhook / plugin` 四种 Handler 草案。

## 1. 路由边界

EBA 将事件处理拆成两个互不替代的阶段：

1. **观察者广播**：EventBus 把事件广播给有权限的插件 EventListener。观察者可记录、同步或执行受控副作用，但不占用响应目标。
2. **响应者仲裁**：EventRouter 按 Bot 的 `event_bindings` 选择一个 Pipeline、独立 Agent 或 `discard`。

Pipeline 与 Agent 是平级处理器：

| 处理器 | 配置事实源 | 执行路径 | 事件范围 |
| --- | --- | --- | --- |
| Pipeline | Pipeline 表与完整 Stage 配置 | MessageAggregator -> QueryPool -> RuntimePipeline | 消息事件，首版为 `message.received` |
| Agent | Agent 表中的 runner 与 runner config | AgentRunner Host orchestrator -> plugin AgentRunner | Agent/Runner 声明支持的消息或非消息事件 |
| discard | 无处理器配置 | 明确结束路由 | 任意事件 |

插件 EventListener 不是第三种响应目标。Webhook、Dify、n8n、Coze 等外部系统需要响应事件时，由对应 AgentRunner 插件承接。

## 2. 数据模型

### 2.1 独立 Agent

Agent 保存自己的 Runner 选择与配置，不嵌入 Pipeline，也不复制 Pipeline 的 AI stage：

```python
class Agent(Base):
    uuid: str
    name: str
    description: str
    emoji: str
    kind: str                         # 固定为 "agent"
    component_ref: str                # AgentRunner id
    config: dict                      # runner + runner_config
    enabled: bool
    supported_event_patterns: list[str]
```

当前配置形状：

```json
{
  "runner": {
    "id": "plugin:langbot-team/LocalAgent/default"
  },
  "runner_config": {
    "plugin:langbot-team/LocalAgent/default": {
      "model": {
        "primary": "model-uuid",
        "fallbacks": []
      }
    }
  }
}
```

Runner id 来自已安装插件的 AgentRunner manifest。Host 不维护 LocalAgent、Dify 或其他具体实现的内置分支。

### 2.2 EventBinding

Bot 维护事件到处理器的引用：

```python
class EventBinding(BaseModel):
    id: str
    event_pattern: str                # 精确、namespace.* 或 *
    target_type: str                  # agent | pipeline | discard
    target_uuid: str | None           # Agent/Pipeline 原始 UUID
    filters: list[dict]
    priority: int
    enabled: bool
    description: str
```

示例：

```json
[
  {
    "id": "binding-message",
    "event_pattern": "message.received",
    "target_type": "pipeline",
    "target_uuid": "pipeline-uuid",
    "filters": [],
    "priority": 100,
    "enabled": true
  },
  {
    "id": "binding-member-joined",
    "event_pattern": "group.member_joined",
    "target_type": "agent",
    "target_uuid": "agent-uuid",
    "filters": [],
    "priority": 50,
    "enabled": true
  }
]
```

Binding 只保存引用与路由条件。它不复制 Pipeline 或 Agent 配置。

## 3. 匹配与仲裁

事件模式支持：

- 精确匹配：`group.member_joined`
- 命名空间通配：`group.*`
- 全局通配：`*`

路由按以下顺序处理：

1. 忽略 `enabled = false` 的 binding。
2. 检查 `event_pattern` 与结构化 filters。
3. 校验目标存在、启用且声明支持该事件。
4. 按 `priority` 从高到低选择；同优先级按稳定列表顺序。
5. 只执行一个响应目标。

Pipeline 目标只能匹配消息事件。非消息事件不得伪装成用户文本塞进 Pipeline。

## 4. 执行流程

```text
Platform adapter
  -> normalized event
  -> EventBus
       -> authorized Plugin EventListener observers
  -> EventRouter
       -> Pipeline target -> full Pipeline stage chain
       -> Agent target    -> AgentRunner Host orchestrator
       -> discard         -> stop
  -> Host delivery/platform API
```

### 4.1 Pipeline target

消息事件按原有方式构造 Query，经 MessageAggregator、QueryPool 和完整 Pipeline Stage 链执行。Pipeline 可以继续使用 AgentRunner 作为 AI stage 的实现，但 Pipeline 本身不会因此变成 Agent。

### 4.2 Agent target

Host 读取独立 Agent 的 Runner id/config，构造 event-first context、run-scoped resources 与 delivery policy，再调用插件 AgentRunner。Runner 输出由 Host 统一归一化、记录和投递。

AgentRunner 可通过 SDK/Python `AgentRunAPIProxy.call_tool` 或 SDK-owned scoped MCP bridge 回调 Host 能力。两条路径都映射到 `PluginToRuntimeAction.CALL_TOOL`，使用相同的 run authorization、Host execution Query、ToolManager 和 Box session 规则。Box session 是 Host canonical scope 的固定长度安全哈希；同一平台会话稳定、不同 scope 隔离、缺少 identity 时 fail closed，Runner 不配置 sandbox scope。

### 4.3 Observer side effects

观察者与响应者可以同时工作。为避免编辑、reaction 等合成事件重复触发不可逆操作，Host 应按事件能力和授权过滤观察者可用 API，并记录副作用结果。Observer 广播不作为 fallback 响应。

## 5. Pipeline 与 Agent 的并存规则

1. Pipeline 与 Agent 保留各自的持久化、编辑和执行语义。
2. 处理器聚合页面可以统一展示二者，但不会创建第三份处理器记录。
3. 旧 Pipeline 仍是 Pipeline；其 runner config 不迁移、不复制为独立 Agent。
4. 需要 Agent 的用户新建 Agent、选择已安装 AgentRunner，再建立 event binding。
5. 一个 Bot 可按不同事件同时绑定 Pipeline 与 Agent。

## 6. WebUI 约束

处理器入口展示带类型标识的 Agent 与 Pipeline。Bot 事件编排器应：

- 按 adapter manifest 展示可用事件；
- 非消息事件不提供 Pipeline 目标；
- Agent 目标按 `supported_event_patterns` 过滤；
- 展示 priority、filters、enabled 与 discard；
- 保存前校验目标 UUID 与 `target_type` 一致。

Pipeline 的配置、Debug Chat 和 Monitoring 继续使用 Pipeline 页面；Agent 使用独立表单配置 Runner 与事件能力。

## 7. 版本与迁移边界

此功能按当前 4.x schema 直接实现，不提供 LangBot 3.x 数据库或配置升级路径，也不读取旧 Runner 字段作为 fallback。旧 Pipeline 中的 runner 配置不会生成独立 Agent；用户按新产品模型添加 Agent 即可。

详见 [07-agent-orchestration.md](./07-agent-orchestration.md) 与 [08-agent-page-and-event-orchestration.md](./08-agent-page-and-event-orchestration.md)。
