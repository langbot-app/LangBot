# Runner Protocol v1 Reference

SDK 仓库不维护 Runner Protocol v1 的 schema 副本。

协议合同的唯一事实源在 LangBot 仓库：

- `docs/agent-runner-pluginization/PROTOCOL_V1.md`

本文件只作为 SDK 侧跳转页，避免 SDK 与 LangBot 同时维护两份
`RunnerManifest`、`RunnerContext`、`RunnerResult`、
`RunnerAPIProxy` 定义。

## SDK 实现入口

- `src/langbot_plugin/api/definition/components/runner/runner.py`
- `src/langbot_plugin/api/entities/builtin/runner/`
- `src/langbot_plugin/api/proxies/agent_run/`
- `src/langbot_plugin/runtime/plugin/mgr.py`
- `src/langbot_plugin/runtime/io/handlers/control.py`
- `src/langbot_plugin/assets/templates/components/runner/`

## 维护规则

- 协议字段、结果类型、权限字面量和 Host API 语义以 LangBot canonical spec 为准。
- SDK 代码、模板或测试与 canonical spec 冲突时，先确认是否要修改协议合同；如果合同不变，修 SDK。
- 本目录的其他文档不得重抄协议 schema，只能引用 canonical spec 或 SDK 源码入口。
