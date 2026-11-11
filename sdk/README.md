<div align="center">

<h1>LangBot Plugin Infra</h1>

<p>Plugin SDK, CLI, Plugin Runtime and Box sandbox runtime for <a href="https://github.com/langbot-app/LangBot">LangBot</a>.</p>

[![PyPI](https://img.shields.io/pypi/v/langbot-plugin)](https://pypi.org/project/langbot-plugin/)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)

English / [简体中文](README_CN.md)

[Documentation](https://langbot.app/docs/zh/plugin/dev/tutor) ·
[Plugin Market](https://space.langbot.app) ·
[LangBot](https://github.com/langbot-app/LangBot)

</div>

## Overview

This package is the shared infrastructure powering LangBot's plugin and
sandbox subsystems. Its source lives in
[`sdk/`](https://github.com/langbot-app/LangBot/tree/master/sdk) of the LangBot
repository. It is published to PyPI as the single
[`langbot-plugin`](https://pypi.org/project/langbot-plugin/) package and ships
three things:

- **Plugin SDK & CLI** (`lbp`) — Python APIs, base classes and the `lbp`
  command for scaffolding, building, debugging and publishing plugins.
- **Plugin Runtime** (`lbp rt`) — the host process that discovers, installs and
  runs plugins, bridging them to LangBot over stdio or WebSocket.
- **Box Runtime** (`lbp box`) — the code-sandbox service backing LangBot's Box
  subsystem, executing untrusted code via Docker / nsjail / E2B backends. An
  explicit, non-sandboxed `host` backend is available for trusted local
  development only.

LangBot depends on this package as the pinned `langbot-plugin==<x.y.z>` in its
`pyproject.toml`; the canonical version lives in `sdk/pyproject.toml`.

> The **Runtime** component (`src/langbot_plugin/runtime/`) is licensed
> separately under **AGPL**; everything else in this package is **Apache 2.0**.
> See [`src/langbot_plugin/runtime/README.md`](src/langbot_plugin/runtime/README.md).

## Install

```bash
pip install langbot-plugin
# or, recommended
uv tool install langbot-plugin

lbp --help
```

## CLI at a glance

| Command | Purpose |
| --- | --- |
| `lbp init <name>` | Scaffold a new plugin project |
| `lbp comp <Type>` | Generate a component (Command / Tool / EventListener / KnowledgeEngine / Parser / Page) |
| `lbp run` | Run / remote-debug a plugin against a running LangBot |
| `lbp build` | Package the plugin into a distributable zip |
| `lbp publish` | Publish to the LangBot Plugin Market |
| `lbp login` / `lbp logout` | Authenticate with your LangBot account |
| `lbp rt` | Launch a standalone Plugin Runtime (control `5400`, debug `5401`) |
| `lbp box` | Launch a standalone Box sandbox runtime (default port `5410`) |
| `lbp ver` | Print the CLI / package version |

## Component types

Plugins extend LangBot through six component types, scaffolded with
`lbp comp <Type>`:

- **Command** — user-triggered actions (e.g. `!weather tokyo`)
- **Tool** — LLM-callable functions for AI agents
- **EventListener** — handlers for message-pipeline events
- **KnowledgeEngine** — custom knowledge-base retrieval for RAG
- **Parser** — custom message / content parsing
- **Page** — custom web page embedded in the LangBot admin panel

## Runner Runtime

The SDK provides Runner component definitions, protocol entities, runtime
dispatch, run-scoped Host API helpers, and low-level daemon relay primitives
used by runner/plugin packages that need an outbound user-side runtime process.
This includes run-scoped pull APIs on `RunnerAPIProxy` (history, events, state,
run ledger) and `steering_pull` for absorbing follow-up user input into an
active run when the runner declares `capabilities.steering` in its manifest.
The SDK does not provide a managed, generic remote Runner product: external
harness execution policy, process launch details, authentication, workspace
selection, and provider-specific behavior belong to the runner/plugin package or
a deployment-owned remote daemon or managed agent platform.

## ExecutionAPI 操作一览与作用域说明

LangBot Core 通过统一的 `ExecutionAPI` facade 暴露 72 项核心业务能力。插件与 Agent Runner 统一经由该 facade 与 SDK 入口访问。

- **通用执行入口**: `api.execution.invoke(operation_id, **arguments)` 与 `api.execution.stream(...)`。
- **Box 沙箱代理扩展**: `LangBotAPIProxy` 现已提供 `@run_scoped` 的 `bind_box`, `import_box_attachments`, `export_box_files`。
- **完整清单与作用域契约**: 详见 [docs/execution_api.md](docs/execution_api.md)。

## Documentation

- Plugin development tutorial — https://langbot.app/docs/zh/plugin/dev/tutor
- Debugging the Runtime / CLI / SDK — https://langbot.app/docs/zh/develop/plugin-runtime
- Dev environment setup — https://langbot.app/docs/zh/develop/dev-config
- ExecutionAPI 操作一览与作用域说明 — [docs/execution_api.md](docs/execution_api.md)

## License

Apache 2.0, except the Plugin Runtime (`src/langbot_plugin/runtime/`) which is
AGPL. See [LICENSE](LICENSE) and the
[Runtime README](src/langbot_plugin/runtime/README.md).
