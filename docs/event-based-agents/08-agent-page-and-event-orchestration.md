# 处理器页面与事件编排产品设计

> 状态：实施稿（2026-06-23）
>
> 本文档修订 [07-agent-orchestration.md](./07-agent-orchestration.md) 中“Agent 替代 Pipeline”的表述。当前产品形态保留两种长期并存的同级处理器：**Agent** 与 **Pipeline**。处理器页面只是共享入口，不改变二者各自的持久化模型和执行语义。

## 1. 产品边界

LangBot 的处理逻辑分成两种同级形态：

| 形态 | 定位 | 可处理事件 | 典型用户 |
| --- | --- | --- | --- |
| Agent | runner 驱动的事件优先处理器，承载 AgentRunner / 外部 runner | `message.*`、`group.*`、`friend.*`、`bot.*`、`feedback.*`、`platform.*` 等声明范围 | 需要直接处理多类平台事件或接入外部 agent runtime 的用户 |
| Pipeline | 可视化、可控、可组合的消息处理流水线，执行完整 Stage 链 | 仅 `message.*`，首版等价于 `message.received` | 需要预处理、AI、后处理、扩展和输出控制的消息场景 |

处理器页面负责统一管理这两种处理单元：

- 创建时选择 **Agent** 或 **Pipeline**；
- 列表中清晰标注类型与事件能力；
- Pipeline 的编辑、调试、监控继续复用现有能力；
- Agent 保存 runner 配置与事件能力，并通过 Bot 事件绑定进入运行时执行。

## 2. 信息架构

### 2.1 处理器页面

路径：`/home/agents`

职责：

1. 展示所有可被事件绑定的处理单元，包括 Agent 与 Pipeline。
2. 创建时先选择类型：
   - Agent：创建一条独立 Agent 配置对象，默认支持其 runner 声明的事件范围；
   - Pipeline：创建一条独立 Pipeline，执行完整消息 Stage 链。
3. 编辑时按类型进入不同表单：
   - Pipeline：沿用原 Pipeline 配置页，包括 AI、触发、安全、输出、扩展、Debug、Monitoring；
   - Agent：配置基础信息、runner、runner config 和事件能力。

`/home/pipelines` 继续提供 Pipeline 直接编辑路径；共享处理器入口当前使用 `/home/agents`。URL 是实现路径，不代表 Agent 包含 Pipeline。

### 2.2 Bot 的事件编排

Bot 上维护“事件 -> 处理单元”的绑定规则：

```text
Bot
  └─ EventBinding[]
       ├─ event_pattern: message.received / group.member_joined / group.* / *
       ├─ target_type: agent / pipeline / discard
       ├─ target_uuid: Agent UUID 或 Pipeline UUID
       ├─ filters: 事件字段过滤条件
       ├─ priority: 数字越大越优先
       └─ enabled
```

Pipeline 只能被绑定到 `message.*`。如果用户选择非消息事件，目标选择器不展示 Pipeline。

## 3. 持久化模型

### 3.1 Agent 实例与 Pipeline 实例

`agents` 表只保存 Agent；Pipeline 继续保存在 Pipeline 表中。当前物理表名 `legacy_pipelines` 是既有存储名称，不代表 Pipeline 在产品架构中是遗留或过渡形态。

```python
class Agent(Base):
    uuid: str
    name: str
    description: str
    emoji: str
    kind: str               # 首版固定为 "agent"
    component_ref: str      # runner id / workflow id / future external ref
    config: dict            # runner 与 runner_config
    enabled: bool
    supported_event_patterns: list[str]
    created_at: datetime
    updated_at: datetime
```

处理器聚合服务把 `agents` 与 Pipeline 表投影成同一个前端列表：

```json
{
  "uuid": "...",
  "name": "...",
  "kind": "agent | pipeline",
  "capability": {
    "supported_event_patterns": ["*"],
    "message_only": false
  }
}
```

Pipeline 投影时固定：

```json
{
  "kind": "pipeline",
  "capability": {
    "supported_event_patterns": ["message.*"],
    "message_only": true
  }
}
```

### 3.2 Bot 事件绑定

Bot 新增 `event_bindings` JSON 字段，首版作为轻量配置面。后续当 EventRouter 查询、审计和多作用域规则稳定后，再拆成独立表。

```json
[
  {
    "id": "uuid",
    "event_pattern": "group.member_joined",
    "target_type": "agent",
    "target_uuid": "...",
    "filters": [],
    "priority": 100,
    "enabled": true,
    "description": "Welcome new group members"
  }
]
```

## 4. 匹配规则

事件模式支持三层：

1. 精确匹配：`group.member_joined`
2. 命名空间通配：`group.*`
3. 全局通配：`*`

优先级：

1. `enabled = true`
2. event pattern 命中
3. filters 全部命中
4. `priority` 数值高者优先
5. 同优先级按列表顺序

## 5. 并存策略

1. Pipeline 与 Agent 长期并存，各自保存配置并执行自己的运行链路。
2. 现有 Bot 的 `use_pipeline_uuid` 转换为仍指向原 Pipeline 的消息事件绑定。
3. 现有 `pipeline_routing_rules` 仍只作用于消息事件。
4. `event_bindings` 允许 `target_type=pipeline|agent|discard`；Pipeline 目标只限 `message.*`。
5. Pipeline 与 Agent 保留各自的持久化和编辑语义；处理器聚合入口只负责统一展示和选择。

## 6. 分阶段落地

### P0：处理器入口统一

- 新增 `/home/agents`。
- 侧边栏显示“处理器”，列表包含平级的 Agent 与 Pipeline。
- 创建时选择 Agent 或 Pipeline。
- `/home/pipelines` 继续作为 Pipeline 直接编辑路径。

### P1：配置模型落地

- 新增 `agents` 表与 `/api/v1/agents`。
- Agent 可保存 runner 与 runner_config。
- Pipeline 继续使用原 Pipeline 表单与 API。

### P2：事件编排配置面

- Bot 表单新增事件编排编辑器。
- 读取 adapter manifest 的 `supported_events` 生成事件选项。
- 根据事件类型过滤可选目标：Pipeline 仅在 `message.*` 可选。

### P3：EventRouter 执行接入

- EBA 事件先广播插件 observer。
- 然后按 `event_bindings` 的事件模式、filters、priority 和顺序选择一个处理器。
- Pipeline 目标通过 MessageAggregator 进入完整 Pipeline Stage 链；Agent 目标直接进入 AgentRunner 链路。
- 非消息事件只选择声明支持该事件的 Agent，不调用 Pipeline；AgentRunner 输出有平台 reply target 时会投递回平台。

## 7. 不做的事

- 不把 Pipeline 改名成 Agent，也不删除 Pipeline 的配置模型。
- 不把 Pipeline 降级为兼容层、Agent 子类型或临时运行入口。
- 不把非消息事件伪装成用户文本塞入 Pipeline。
- 不在首版做多 Agent 串并联；需要多步骤处理时留给后续 workflow。
