# EBA 分阶段实施计划

> 更新：2026-07-12。文件名沿用早期设计，但这里的“迁移”仅指代码架构逐步接入 EBA，不代表 LangBot 3.x 数据库或配置升级。

## 1. 发布边界

EBA 跨越 SDK、平台适配器、LangBot Host、WebUI 与插件生态，按可验证阶段落地。当前发布遵守以下硬边界：

- LangBot 4.x 不支持从 3.x 数据库或配置升级；不保留 legacy migration chain、旧 JSON 模板或旧 Runner 字段读取。
- Pipeline 与 Agent 平级且长期并存，分别保留持久化模型与执行链。
- 现有 Pipeline 不迁移为 Agent，Pipeline 内的 runner config 不复制到 Agent。
- 用户需要 Agent 时新建独立 Agent并选择已安装的 AgentRunner。
- Host 不按 LocalAgent id 做运行时、Box 或 WebUI 特判。
- AgentRunner 的 SDK/Python 与 scoped MCP bridge 回调共享 Host 授权与事件 session 规则。

## 2. 阶段总览

| 阶段 | 目标 | 主要仓库 | 完成条件 |
| --- | --- | --- | --- |
| P0 | SDK 事件、能力与 AgentRunner 协议 | `langbot-plugin-sdk` | typed entities、manifest、proxy、runtime action 通过测试 |
| P1 | 平台适配器 EBA 化 | LangBot + SDK | 事件转换、能力声明、通用/透传 API 通过 adapter checklist |
| P2 | Host 观察者与响应者路由 | LangBot backend | observer 广播 + Pipeline/Agent/discard 单目标仲裁可运行 |
| P3 | 独立 Agent 与 Runner 注册 | LangBot backend + plugins | Agent CRUD、registry、run authorization、delivery 可运行 |
| P4 | WebUI 处理器与事件编排 | LangBot web | Agent/Pipeline 聚合入口和 Bot binding 编辑器可用 |
| P5 | 发布门禁与文档 | LangBot skills/docs + runner plugins | 单测、UI E2E、真实 adapter smoke 和插件预检通过 |

## 3. P0：SDK 契约

### 工作项

- 定义规范化平台事件、actor/subject/conversation/delivery context。
- 定义 adapter `supported_events`、`supported_apis` 与平台透传 API。
- 定义 AgentRunner manifest、run context/result、resource handles 和 pull/callback API。
- 提供 `AgentRunAPIProxy` 与 SDK-owned scoped MCP bridge。
- 保持协议传输与权限校验可测试，不把 Host 私有 Query 对象暴露给插件。

### 验收

- stdio/WebSocket runtime 对 typed action 的序列化一致。
- 无 `run_id` 或越权资源调用被拒绝。
- Python proxy 与 MCP bridge 对同一 Host tool 呈现一致结果/错误形状。

## 4. P1：平台适配器

每个适配器按自己的能力增量接入，而不是要求所有平台一次性支持全部事件。

### 单适配器步骤

1. 将原生 SDK callback 转换为规范化事件。
2. 声明实际支持的事件与 API，不把缺失能力伪装为成功。
3. 实现 send/reply/edit/delete/group/user 等适用 API 与平台透传。
4. 对消息链、媒体、reply target 和错误语义写单元测试。
5. 按 `adapters/acceptance-checklist.md` 记录真实平台 probe。

### 验收

- `message.received` 保持正常收发。
- 新事件不会重复转换或产生循环合成事件。
- `supported_apis` 与实际调用能力一致。

## 5. P2：Host 路由

### 执行顺序

```text
adapter event
  -> EventBus observer broadcast
  -> EventRouter match event_bindings
  -> one target: Pipeline | Agent | discard
  -> Host delivery
```

### 约束

- Plugin EventListener 是 observer，不作为 priority fallback。
- Pipeline 只处理消息事件并复用完整 Stage 链。
- Agent 使用独立 Agent 配置和 AgentRunner Host orchestrator。
- edit/reaction 等事件的 observer 副作用能力按事件和 adapter 能力过滤。
- dry-run 与合成派发必须使用同一匹配器，避免 UI 预览与真实路由漂移。

### 验收

- 精确、namespace wildcard、全局 wildcard、filters 与 priority 有单元覆盖。
- 同一事件最多一个响应目标，但 observer 仍能收到事件。
- Pipeline 与 Agent 可以在同一个 Bot 的不同 binding 中同时生效。

## 6. P3：独立 Agent 与 AgentRunner

### 工作项

- `agents` 只保存 Agent；Pipeline 继续使用自己的表和 API。
- Agent config 使用 `runner.id` 与 `runner_config[runner_id]`。
- registry 只展示已安装、有效的插件 AgentRunner。
- Host 构造 run-scoped resources、state、delivery 与 event log/transcript。
- SDK/Python `call_tool` 和 scoped MCP bridge 都回到同一个 Host ToolManager。
- Box session 由 Host 将 instance/workspace/bot/adapter/target/thread scope 规范化并哈希为固定长度 `lb-box-<sha256>`；同 scope 稳定、不同 scope 隔离、缺少 identity 时 fail closed。

### 验收

- 安装/卸载 Runner 后 metadata 与表单选项同步。
- Runner 无法调用未授权 model/tool/knowledge/state。
- 两种 Host callback transport 不能覆盖 sandbox session id。
- LocalAgent、ACP/ClaudeCode/Codex 与外部服务 Runner 不需要 Host id 特判。

## 7. P4：WebUI

### 工作项

- `/home/agents` 聚合显示 Agent 与 Pipeline，并明确类型。
- 创建时选择 Agent 或 Pipeline，编辑时进入各自表单。
- Agent 表单读取动态 Runner metadata，保存当前 `runner` / `runner_config` 形状。
- Bot 事件编排器编辑 `event_pattern`、target、filters、priority 与 enabled。
- 非消息事件过滤 Pipeline；Agent 按声明事件能力过滤。

### 验收

- 页面不出现 LocalAgent 专属 banner、变量隐藏或 Box/Pipeline 注入逻辑。
- 空 Runner 市场状态给出可安装 AgentRunner 的正常路径。
- Pipeline Debug Chat/Monitoring 与 Agent 运行日志分别可用。

## 8. P5：发布门禁

### 自动化

- LangBot backend unit/integration tests 与 Ruff。
- SDK AgentRunner/proxy/MCP bridge tests。
- Web lint/build 与关键 Playwright cases。
- `skills/bin/lbs validate`、`skills/bin/lbs index --check`。
- LocalAgent 与其他官方 Runner plugin package/test gate。

### 真实环境

- 至少一个消息事件走 Pipeline。
- 至少一个非消息事件走独立 Agent 并执行平台动作。
- SDK/Python 和 MCP bridge 各完成一次受权工具调用，并证明二者都进入同一个 `PluginToRuntimeAction.CALL_TOOL` Host handler。
- Box 可用/不可用的降级路径可观察且无 Runner 特判。

## 9. 非目标

- 不把 Pipeline 改名或包装成 Agent。
- 不自动把 Pipeline 内 runner 配置迁移成 Agent。
- 不为 3.x 保留数据库迁移、旧模板或配置 fallback。
- 不要求所有 Runner 经 MCP；本地 Python Runner 可以直接使用 SDK。
- 不允许 Runner 自定义 Box session scope。
- 不在首版实现多 Agent 串并联；多步骤编排留给后续 workflow。
