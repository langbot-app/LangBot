# Agent 页面与事件编排产品设计

> 状态：实施稿（2026-06-23）
>
> 本文档修订 [07-agent-orchestration.md](./07-agent-orchestration.md) 中“Agent 替代 Pipeline”的表述。当前产品形态应保留两种同级处理单元：**Agent 编排**与**Pipeline**。Agent 页面是统一入口，但不是把 Pipeline 消除。

## 1. 产品边界

LangBot 的处理逻辑分成两种同级形态：

| 形态 | 定位 | 可处理事件 | 典型用户 |
| --- | --- | --- | --- |
| Agent 编排 | 面向 EBA 的事件优先处理单元，承载 AgentRunner / 外部 runner / 后续工作流 | `message.*`、`group.*`、`friend.*`、`bot.*`、`feedback.*`、`platform.*` 等 | 希望按事件类型配置不同智能处理逻辑的用户 |
| Pipeline | 现有无代码消息流水线与向后兼容形态 | 仅 `message.*`，首版等价于 `message.received` | 已有 Pipeline 用户、只需要消息处理的用户 |

Agent 页面负责统一管理这两种处理单元：

- 创建时选择 **Agent 编排** 或 **Pipeline**；
- 列表中清晰标注类型与事件能力；
- Pipeline 的编辑、调试、监控继续复用现有能力；
- Agent 编排保存 runner 配置与事件能力，并通过 Bot 事件绑定进入运行时执行。

## 2. 信息架构

### 2.1 Agent 页面

路径：`/home/agents`

职责：

1. 展示所有可被事件绑定的处理单元，包括 Agent 编排与 Pipeline。
2. 创建时先选择类型：
   - Agent 编排：创建一条 Agent 配置对象，默认支持所有 EBA 事件；
   - Pipeline：创建现有 legacy pipeline，只能处理消息事件。
3. 编辑时按类型进入不同表单：
   - Pipeline：沿用原 Pipeline 配置页，包括 AI、触发、安全、输出、扩展、Debug、Monitoring；
   - Agent 编排：配置基础信息、runner、runner config 和事件能力。

`/home/pipelines` 保留为兼容路由，但新导航入口使用 `/home/agents`。

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

### 3.1 Agent 编排实例

新增 `agents` 表，只保存 Agent 编排形态。Pipeline 继续保存在 `legacy_pipelines`。

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

Agent 聚合 API 把 `agents` 与 `legacy_pipelines` 投影成同一个前端列表：

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

## 5. 兼容策略

1. 现有 `legacy_pipelines` 不迁移、不改语义。
2. 现有 Bot 的 `use_pipeline_uuid` 仍作为消息事件默认 Pipeline。
3. 现有 `pipeline_routing_rules` 仍只作用于消息事件。
4. 新增 `event_bindings` 是 EBA 事件编排配置，允许 Pipeline 目标但只限 `message.*`。
5. `/api/v1/pipelines` 继续存在；新增 `/api/v1/agents` 作为聚合入口。

## 6. 分阶段落地

### P0：产品入口统一

- 新增 `/home/agents`。
- 侧边栏显示“Agent”，但列表包含 Agent 编排与 Pipeline。
- 创建时选择 Agent 编排或 Pipeline。
- `/home/pipelines` 保留兼容。

### P1：配置模型落地

- 新增 `agents` 表与 `/api/v1/agents`。
- Agent 编排可保存 runner 与 runner_config。
- Pipeline 继续使用原 Pipeline 表单与 API。

### P2：事件编排配置面

- Bot 表单新增事件编排编辑器。
- 读取 adapter manifest 的 `supported_events` 生成事件选项。
- 根据事件类型过滤可选目标：Pipeline 仅在 `message.*` 可选。

### P3：EventRouter 执行接入

- EBA 事件先广播插件 observer。
- 然后按 `event_bindings` 的事件模式、filters、priority 和顺序选择 Agent 编排。
- 消息事件继续优先保留现有 Pipeline / MessageAggregator 兼容路径。
- 非消息事件只调用 Agent 编排，不调用 Pipeline；AgentRunner 输出有平台 reply target 时会投递回平台。

## 7. 不做的事

- 不把 Pipeline 改名成 Agent，也不删除 Pipeline 的配置模型。
- 不把非消息事件伪装成用户文本塞入 Pipeline。
- 不在首版做多 Agent 串并联；需要多步骤处理时留给后续 workflow。
