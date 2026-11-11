<div align="center">

<h1>LangBot Plugin Infra</h1>

<p>为 <a href="https://github.com/langbot-app/LangBot">LangBot</a> 提供插件 SDK、CLI、插件运行时与 Box 代码沙箱运行时。</p>

[![PyPI](https://img.shields.io/pypi/v/langbot-plugin)](https://pypi.org/project/langbot-plugin/)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)

[English](README.md) / 简体中文

[文档](https://langbot.app/docs/zh/plugin/dev/tutor) ·
[插件市场](https://space.langbot.app) ·
[LangBot](https://github.com/langbot-app/LangBot)

</div>

## 简介

此仓库是支撑 LangBot **插件系统**与**代码沙箱**的共享基础设施，以单一的
[`langbot-plugin`](https://pypi.org/project/langbot-plugin/) 包发布到 PyPI，包含三部分：

- **插件 SDK 与 CLI**（`lbp`）—— 插件开发的 Python API、基类，以及用于脚手架、
  构建、调试和发布插件的 `lbp` 命令。
- **插件运行时**（`lbp rt`）—— 负责发现、安装并运行插件的宿主进程，通过 stdio
  或 WebSocket 与 LangBot 通信。
- **Box 运行时**（`lbp box`）—— 支撑 LangBot Box 子系统的代码沙箱服务，通过
  Docker / nsjail / E2B 后端执行不受信任的代码；另提供仅供可信本地开发显式启用、
  不具备沙箱隔离能力的 `host` 后端。

LangBot 通过 `pyproject.toml` 中固定的 `langbot-plugin==<x.y.z>` 依赖此包；
版本号以本仓库的 `pyproject.toml` 为准。

> **运行时**组件（`src/langbot_plugin/runtime/`）单独采用 **AGPL** 许可证，
> 本仓库其余部分采用 **Apache 2.0**，详见
> [`src/langbot_plugin/runtime/README.md`](src/langbot_plugin/runtime/README.md)。

## 安装

```bash
pip install langbot-plugin
# 或（推荐）
uv tool install langbot-plugin

lbp --help
```

## CLI 速览

| 命令 | 作用 |
| --- | --- |
| `lbp init <name>` | 初始化一个插件项目 |
| `lbp comp <Type>` | 生成组件（Command / Tool / EventListener / KnowledgeEngine / Parser / Page） |
| `lbp run` | 针对运行中的 LangBot 运行 / 远程调试插件 |
| `lbp build` | 将插件打包为可分发的 zip |
| `lbp publish` | 发布到 LangBot 插件市场 |
| `lbp login` / `lbp logout` | 登录 / 登出 LangBot 账号 |
| `lbp rt` | 启动独立的插件运行时（控制端口 `5400`，调试端口 `5401`） |
| `lbp box` | 启动独立的 Box 代码沙箱运行时（默认端口 `5410`） |
| `lbp ver` | 打印 CLI / 包版本 |

## 组件类型

插件通过六种组件类型扩展 LangBot，使用 `lbp comp <Type>` 生成：

- **Command** —— 用户触发的指令（如 `!weather tokyo`）
- **Tool** —— 供 AI Agent 调用的 LLM 工具函数
- **EventListener** —— 消息流水线事件的处理器
- **KnowledgeEngine** —— 用于 RAG 的自定义知识库检索
- **Parser** —— 自定义消息 / 内容解析
- **Page** —— 嵌入 LangBot 管理面板的自定义网页

## ExecutionAPI 操作一览与作用域说明

LangBot Core 通过统一的 `ExecutionAPI` facade 暴露 69 项核心业务能力。插件与 Agent Runner 统一经由该 facade 与 SDK 入口访问。

- **通用执行入口**: `api.execution.invoke(operation_id, **arguments)` 与 `api.execution.stream(...)`。
- **Box 沙箱代理扩展**: `LangBotAPIProxy` 现已提供 `@run_scoped` 的 `bind_box`, `import_box_attachments`, `export_box_files`。
- **完整清单与作用域契约**: 详见 [docs/execution_api.md](docs/execution_api.md)。

## 文档

- 插件开发教程 —— https://langbot.app/docs/zh/plugin/dev/tutor
- 调试运行时 / CLI / SDK —— https://langbot.app/docs/zh/develop/plugin-runtime
- 开发环境配置 —— https://langbot.app/docs/zh/develop/dev-config
- ExecutionAPI 操作一览与作用域说明 —— [docs/execution_api.md](docs/execution_api.md)

## 许可证

本仓库采用 Apache 2.0，但插件运行时（`src/langbot_plugin/runtime/`）单独采用
AGPL。详见 [LICENSE](LICENSE) 与
[运行时 README](src/langbot_plugin/runtime/README.md)。
