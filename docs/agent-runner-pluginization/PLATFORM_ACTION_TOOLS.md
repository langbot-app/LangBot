# Agent 工具权限

Agent 配置页展示同一次运行中可能投射给 AgentRunner 的完整工具目录：

- 事件级工具由 Agent 选择的事件范围自动启用。
- `allowed_platform_tools` 管理需要 Agent 自行指定目标的平台级动作。
- `allowed_tools` 管理沙盒内置工具、MCP 工具、插件工具和技能工具。

Host 会按当前 Workspace 实时解析工具来源。未安装的插件、未连接的 MCP、不可用的 Box
沙盒以及名称存在歧义的工具不会进入可选目录。旧 Agent 若尚未保存 `allowed_tools`，继续
沿用运行器原有的工具策略；一旦在配置页保存，就转为明确的顶层白名单。

Agent 不直接持有平台适配器，也不能调用任意原始平台接口。每次运行时，Host 根据当前
事件自动加入兼容的事件级工具，并加入 `allowed_platform_tools` 中选择的平台级工具，
再与 AgentRunner 权限、当前适配器声明的 API、当前事件能够安全绑定的目标取交集，
得到 `ctx.resources.tools` 中 `tool_type=platform` 的最终工具集合。

## 两类工具

- 事件级工具以 `event_` 开头。用户、群组、消息或请求标识由 Host 从当前事件冻结，
  Agent 只能填写回复文本、审核结果、禁言时长等动作参数。
- 平台级工具以 `platform_` 开头。Agent 可以填写目标用户、群组或消息标识，因此权限
  更宽，配置页将其与事件级工具分开展示。

当前事件级工具包括：回复当前会话、删除当前消息、查询事件发起者或相关群组/成员、
禁言/解除禁言/移出相关成员、同意或拒绝好友请求、同意或拒绝入群邀请。

当前平台级工具包括：发送/查询/删除消息，查询群组、群列表、群成员，修改群名称，
禁言/解除禁言/移出成员、退出群组，以及查询用户和好友列表。

`call_platform_api` 不在 Agent 工具目录中。平台私有透传接口必须先在 Host 中定义为
具有固定名称、JSON Schema、风险级别和授权规则的语义工具，不能让 Agent 自行传入
原始 action 名称。

## 运行时投射

```text
current event type ── compatible event tools
Agent.allowed_platform_tools ── selected platform tools
        │
        ├─ AgentRunner capability tool_calling is enabled
        ├─ AgentRunner manifest permissions.tools contains call
        ├─ current adapter.get_supported_apis()
        └─ current event type and frozen target are compatible
        │
        ▼
ctx.resources.tools[tool_type=platform]
        │
        ├─ Local Agent: AgentRunAPIProxy.call_tool
        └─ External AgentRunner: langbot_list_assets / langbot_get_tool_detail /
                                langbot_call_tool (MCP Asset Gateway)
        │
        ▼
Host revalidates run_id, runner plugin identity, operation and frozen source
        │
        ▼
current bot adapter semantic API
```

本地和外部 AgentRunner 因此使用同一个工具名、参数 Schema 和 Host 授权快照。外部
平台不会获得适配器对象或长期凭据；MCP 网关中的 run token 和 Host 中的 run session
都只对应当前运行。

## 失败语义

- Agent 未选择当前事件：不会触发运行，也不会生成事件级工具。
- 平台级工具未在 Agent 配置中选择：不进入运行资源。
- Runner 未启用 `tool_calling` 或没有 `tools.call` 权限：所有平台动作均不可用。
- 当前适配器不声明对应 API：该工具记入 `platform_capabilities.unavailable_tools`，不投射。
- 事件类型不匹配或缺少可冻结目标：事件级工具不投射。
- 调用期间机器人下线或适配器能力变化：Host 拒绝执行并返回具体错误。
- 参数包含 Schema 之外的字段：Host 拒绝执行。

这些规则保证配置白名单不是唯一防线；真正的执行授权始终由单次运行快照和执行时检查
共同决定。
