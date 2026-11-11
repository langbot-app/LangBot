# Runner SDK / Runtime 实现说明

更新：2026-09-05，代码基线 `dev/4.11.x` / `f1da058`。源码版本为 `0.5.5`；版本字段不证明 registry 包包含本分支实现。Core 仍锁定 `langbot-plugin==0.5.3`，本机通过 editable 源码联调，发布前必须固定实际配套依赖。

本文档面向 SDK / Runtime 维护者。它不定义 Runner Protocol v1 的
schema；协议字段、结果类型、permissions 字面量和 Host API 语义以 LangBot 仓库的
`docs/agent-runner-pluginization/PROTOCOL_V1.md` 为准。

## SDK 负责的实现面

- `Runner` 组件基类和 runner-scoped API 入口。
- Runner Protocol v1 的 Pydantic 实体实现。
- `LIST_RUNNERS` / `RUN_RUNNER` runtime action 转发。
- component manifest 的 `spec.capabilities` / `spec.permissions` / `spec.config` 读取。
- runner 组件模板和 CLI 生成入口。
- run-scoped Host API helper，包括工具、知识库、历史等资源访问的权限边界。
- SDK 不内置 Claude Code、Codex、Kimi Code、Pi Agent 等具体 adapter；只保留 runner/plugin 可复用的低层 daemon relay primitives，不提供托管式通用远端 Runner 产品。外部 harness 执行策略应由 runner/plugin 包负责，优先复用 ACP 这类轻量 runtime 协议。
- SDK 侧单测和模板示例，保证 runner 作者只看到当前协议字段。

## 当前分支同步状态

`dev/4.11.x` 已同步 LangBot `dev/4.11.x` 的 Runner Protocol v1 与
EBA 基础实体。SDK 侧负责的当前闭环包括：

- Runner component discovery、manifest capabilities / permissions validation。
- `RUN_RUNNER` 转发、result sequence 注入、deadline / cancel 传播和异常到 `run.failed` 的转换。
- run-scoped Host API proxy，包括 history / event / state / resource / ledger / admin 边界。
- agent tools MCP bridge、asset gateway、skill-as-tool resource surface。
- runtime register / heartbeat、run claim / renew / release / reconcile 的基础实体与 proxy。

截至 2026-09-05，本分支仍不提供完整 Agent Platform、外部 harness daemon supervisor、runtime wakeup channel 或跨 Host 分布式管控。Plugin Runtime 自己的 installation worker 已有 supervisor、重启退避、并发协调与熔断；这两种进程管理不能混淆。

### 近期 Runtime 能力

- `runtime/plugin/runner_service.py` 承担 Runner discovery 与执行流转发；`mgr.py` 是插件生命周期和集成入口。
- `dependency_environment.py` 为已验证 artifact 准备独立依赖树，按 artifact、requirements、Python ABI、Runtime 版本与 profile 等计算复用键，原子发布；不把一个插件的依赖安装进另一个插件的环境。
- `worker_launcher.py` 管理进程与一次性注册凭据；Windows worker 使用 Runtime 管理的子进程和 loopback WebSocket 回连。
- shared profile 保留安装作用域、只读 artifact 和私有目录边界；硬 CPU/内存/PID 限制依赖部署的 nsjail/cgroup 条件。出站网络与硬磁盘配额仍有生产门禁。
- Plugin Runtime 和 Box 提供各自拥有目录的存储分析。扫描结果是观测，不代表 byte/inode 硬配额。

### 平台工具与未提交改动

Core 已把 `event_*` / `platform_*` 作为 `ToolResource(tool_type="platform")` 投射给 Runner，执行仍通过 run-scoped `call_tool`。Host 固定事件工具目标并检查 Runner 权限、适配器能力和运行身份；SDK 不持有平台 adapter。

2026-09-05 检视时，以下四个文件仍有未提交修改：

- `src/langbot_plugin/api/agent_tools/asset_gateway.py`
- `src/langbot_plugin/api/agent_tools/external_tools.py`
- `src/langbot_plugin/api/entities/builtin/runner/resources.py`
- `tests/api/test_agent_tools_mcp_bridge.py`

改动使 `langbot_list_assets` 可分别返回普通 `tools` 与 `platform_tools`，并按 `include_schemas` 返回平台工具 schema，更新 gateway 引导。下面本地测试包括这组改动，不能标记为已发布功能。配套授权规则见 LangBot `docs/agent-runner-pluginization/PLATFORM_ACTION_TOOLS.md`。

### 结构化交互

SDK 已有 typed interaction contract 和通用 Runner 脚手架支持；Host 执行 `action.requested` 中的 `interaction.requested` 白名单并校验回调。其它 result action 不自动执行平台动作。Provider 私有 continuation 由具体 Runner 处理，真实 Dify/CLI 验收与 SDK 合同测试分别记录。

## 源码入口

| 入口 | 责任 |
| --- | --- |
| `src/langbot_plugin/api/definition/components/runner/runner.py` | `Runner` 基类、`get_run_api(ctx)`、插件实例边界。 |
| `src/langbot_plugin/api/entities/builtin/runner/` | SDK Pydantic 实体实现。 |
| `src/langbot_plugin/api/proxies/agent_run/` | run-scoped Host API proxy，按 resource/context/state/ledger/admin 边界拆分。 |
| `src/langbot_plugin/runtime/plugin/mgr.py` | 插件生命周期、作用域与 Runner service 集成入口。 |
| `src/langbot_plugin/runtime/plugin/runner_service.py` | discovery / run 的实现、sequence、deadline 与失败结果转换。 |
| `src/langbot_plugin/runtime/io/handlers/control.py` | LangBot -> Runtime action handler。 |
| `src/langbot_plugin/assets/templates/components/runner/` | runner scaffold 模板。 |

## 同步流程

1. 协议合同变化先更新 LangBot canonical spec。
2. SDK 实体、Runtime、模板和测试按 canonical spec 同步。
3. runner 示例必须只引用 LangBot canonical spec 中的当前字段和稳定 result types。
4. SDK Runtime 把插件异常转换为 `run.failed`，不能把 generator 异常直接暴露给 Host。
5. 一个插件可以暴露多个 Runner component，Runtime discovery 不得限制为单 runner。

## Host action 兼容

`GET_TOOL_DETAIL` / `CALL_TOOL` 现在由 SDK Runtime 转发给 LangBot Host 处理，
不再只在 SDK Runtime 本地解析。Host 必须同时支持两种调用 envelope：

- 普通插件调用不带 `run_id`，继续使用 `tool_parameters` / `tool_response`。
- Runner 调用带 `run_id`，使用 `parameters` / `result`，并由 Host 按
  `caller_plugin_identity` 和 run resources 做权限校验。

发布 SDK Runtime 变更时必须确认配套 LangBot Host 已实现上述两个 shape；如果
SDK 与 Host 独立发版，先验证 Host action handler，再升级会转发 tool action 的 SDK。

## 高价值测试

2026-09-05 在现有 Windows venv 中以 `python -m pytest` 对以下范围执行定向验证：362 passed，10 warnings。使用当前 editable 源码及上述未提交改动，没有重新验证正式包安装或真实 provider。

```text
tests/api/entities/builtin/runner
tests/api/proxies
tests/api/test_agent_tools_mcp_bridge.py
tests/runtime/plugin/test_mgr_runner.py
tests/runtime/plugin/test_dependency_environment.py
tests/runtime/plugin/test_restart_coordinator.py
```

跨仓库测试前分别确认 Core 和 Runtime 的 `langbot_plugin.__file__` 与发行版元数据；两者都应指向预期版本。保留本地安装运行使用 `uv run --no-sync`。正式发布还需干净环境包安装验证，不能由 editable 测试替代。

- `RunnerContext` 最小字段 validate。
- `RunnerResult` 所有稳定 result type validate。
- manifest capabilities / permissions 和 context access 默认值。
- 单插件多 Runner discovery。
- `RUN_RUNNER` 成功流式输出。
- `RUN_RUNNER` 插件异常、runner 不存在、context schema 错误 -> `run.failed`。
- 模板和 README 示例不出现旧协议字段。
- run-scoped Host API helper 会携带调用方插件身份，并让 Host 进行资源授权校验。

历史 2026-06-23 验证（本轮未重跑以下整组命令）：

```bash
uv run pytest \
  tests/api/entities/test_events.py \
  tests/api/entities/builtin/runner \
  tests/api/proxies \
  tests/api/test_agent_tools_mcp_bridge.py \
  tests/runtime/plugin/test_mgr_runner.py \
  tests/runtime/test_pull_api_handlers.py \
  tests/runtime/io/handlers/test_plugin_handler.py \
  tests/test_message.py -q

uv run python scripts/check_action_consistency.py
```

结果：311 个相关测试通过；action consistency 通过，仅保留
`CommonAction.HEARTBEAT` 未在 SDK src 中注册/调用的既有警告。

## 不在本文维护

- Host 内部 `AgentBinding` / `AgentEventEnvelope` / Store 设计。
- Pipeline adapter 长期产品形态。
- 官方 runner 插件迁移计划。
- QA smoke 和实现进度。

这些内容在 LangBot 仓库的 agent-runner-pluginization 文档集中维护。
