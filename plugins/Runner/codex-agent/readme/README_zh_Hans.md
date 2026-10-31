# Codex Agent

Codex Agent 通过 Codex app-server JSON-RPC 协议把 Codex CLI 接入 LangBot 运行器。它支持本机、SSH 和用户侧 daemon 三种运行位置，并通过受控 MCP 配置向 Codex 提供当前运行授权的 LangBot 工具与资源。

## 运行器 ID

`plugin:langbot-team/CodexAgent/default`

## 前置条件

- 运行位置已经安装 Codex CLI。
- Codex 已完成认证，用户的 `CODEX_HOME` 中存在有效认证状态。
- 配置的工作区存在且可写。
- 使用 SSH 或 daemon 时，网络和认证配置可用。

## 运行模式

- `local`：启动 `codex app-server --listen stdio://` 并通过 stdio JSON-RPC 通信。
- `remote-ssh`：在远端启动 app-server，并通过 SDK 反向隧道访问 LangBot MCP 资源。
- `daemon`：用户侧 daemon 主动连接 LangBot，在用户机器上启动 Codex app-server。

## 插件级 Daemon 配置

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `daemon-enabled` | `boolean` | `false` | 是否启动 daemon Hub |
| `daemon-host` | `string` | `127.0.0.1` | Hub 监听地址 |
| `daemon-port` | `integer` | `8768` | Hub 端口 |
| `daemon-token` | `secret` | 空 | daemon 共享令牌 |

## 运行器配置

| 字段 | 说明 |
| --- | --- |
| `location` | `local`、`remote-ssh` 或 `daemon` |
| `workspace` | Codex 工作目录 |
| `advanced-settings` | 展开命令、超时、会话和 LangBot 桥接调优选项 |
| `command` | Codex CLI 命令 |
| `args-json` | 追加的 app-server 参数 JSON |
| `env-json` | 追加的环境变量 JSON |
| `ssh-target` / `ssh-port` | SSH 目标和端口 |
| `daemon-id` | daemon 客户端 ID |
| `timeout` | 运行超时秒数 |
| `streaming` | 是否输出流式增量 |
| `reuse-session` | 是否恢复 Codex thread |
| `approval-policy` | Codex 原生命令和文件修改的审批策略 |
| `sandbox-mode` | Codex 沙箱模式 |
| `knowledge-bases` | 允许当前 runner 检索的 LangBot 知识库 |
| `langbot-assets-enabled` | 是否注入 LangBot 授权资源 |
| `mcp-bridge-transport` | MCP bridge 传输方式 |
| `mcp-servers-json` | 额外 MCP server 配置 |

## 隔离与配置管理

runner 会在工作区下准备隔离的每次运行 `CODEX_HOME`，链接用户已有的 Codex 认证与 session 状态，并把托管的 MCP server 配置写入 `config.toml`。敏感 MCP 信息不会通过命令行参数传递。

## Thread 与 Steering

启用 session 复用后，runner 使用 `thread/resume` 恢复 Codex thread。同一 LangBot 会话在运行期间收到新消息时，runner 会在 turn 边界拉取 steering 输入，并继续当前 thread。steering 不会在 token 输出中途插入，跟进消息附件目前不会转发。

## 安全说明

- 默认配置以 `approvalPolicy=never` 和 `sandbox=danger-full-access` 启动 Codex，不会等待交互式审批。只能在可信工作区和权限受限的操作系统账号下使用该默认配置。
- 不要把 Codex 认证信息放入普通配置或命令参数。
- 工作区和隔离 `CODEX_HOME` 必须限制为运行用户可访问。
- daemon Hub 对外暴露时必须配置共享 token 和 TLS。
- Codex 只能使用当前运行通过 MCP bridge 授权的 LangBot 能力。

## 开发检查

```bash
uv run --no-sync pytest -q
uv run --no-sync ruff check .
```


> Shared runtime / daemon upgrade: [required setup and safety contract](../README.md#shared-worker-candidate--daemon-upgrade). Shared 模式必须配置独立强 token 和端口；默认本地工作目录为 `/data/workspace`。请同时升级 daemon.py 与完整 pkg 目录；旧客户端不兼容。
