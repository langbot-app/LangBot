# Claude Code Agent

Claude Code Agent 将 Claude Code CLI 以非交互模式接入 LangBot 运行器。它可以在 LangBot 本机、SSH 远端或用户侧 daemon 上运行，并通过 SDK MCP bridge 向 Claude Code 提供本次运行授权的 LangBot 工具和资源。

## 运行器 ID

`plugin:langbot-team/ClaudeCodeAgent/default`

## 前置条件

- 运行位置已经安装 Claude Code CLI。
- Claude Code 已在对应机器完成认证。
- 配置的工作区存在且运行用户有访问权限。
- 使用 SSH 或 daemon 时，网络和认证配置可用。

## 运行模式

- `local`：运行 `claude -p --verbose --output-format stream-json`。
- `remote-ssh`：通过 SSH 在远端运行同一命令，并使用 SDK 反向隧道连接 LangBot MCP 资源。
- `daemon`：用户侧 daemon 主动连接 LangBot，在用户机器上启动 Claude Code。

## 插件级 Daemon 配置

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `daemon-enabled` | `boolean` | `false` | 是否启动 daemon Hub |
| `daemon-host` | `string` | `127.0.0.1` | Hub 监听地址 |
| `daemon-port` | `integer` | `8767` | Hub 端口 |
| `daemon-token` | `secret` | 空 | daemon 共享令牌 |

## 运行器配置

| 字段 | 说明 |
| --- | --- |
| `location` | `local`、`remote-ssh` 或 `daemon` |
| `workspace` | Claude Code 工作目录 |
| `advanced-settings` | 展开命令、超时、会话和 LangBot 桥接调优选项 |
| `command` | Claude CLI 命令；不在 `PATH` 时可填写绝对路径 |
| `args-json` | 追加的命令参数 JSON |
| `env-json` | 追加的环境变量 JSON |
| `ssh-target` / `ssh-port` | SSH 目标和端口 |
| `daemon-id` | daemon 客户端 ID |
| `timeout` | 运行超时秒数 |
| `streaming` | 是否输出流式增量 |
| `reuse-session` | 是否复用 Claude Code session |
| `dangerously-skip-permissions` | 是否传入 `--dangerously-skip-permissions` 跳过交互式权限审批；当前默认开启 |
| `knowledge-bases` | 允许当前 runner 检索的 LangBot 知识库 |
| `langbot-assets-enabled` | 是否注入 LangBot 授权资源 |
| `mcp-bridge-transport` | MCP bridge 传输方式 |
| `mcp-servers-json` | 额外 MCP server 配置 |

## Session 与 Steering

runner 首次运行使用 `--session-id` 创建 session，后续运行可通过 `claude --resume <session-id>` 恢复。同一 LangBot 会话在 Agent 仍运行时收到新消息，Host 会把消息吸收到当前运行；runner 在 turn 边界拉取 steering 输入，并以同一 Claude Code session 继续执行。

steering 当前只在 turn 之间注入，不会打断正在输出的 token；跟进消息中的附件暂不转发。没有会话范围时，runner 会退化为普通单轮执行。

## 安全说明

- 不要把 Claude 认证信息写入普通配置字段或命令参数。
- 当前 LangBot 尚未提供交互式审批流程，因此默认跳过 Claude Code 权限审批。只应在可信工作区和受约束的系统账号下使用；如需恢复 Claude Code 的正常权限检查，请关闭 `dangerously-skip-permissions`。
- SSH 私钥路径应限制文件权限。
- daemon Hub 对外暴露时必须使用 token，并建议通过 TLS 反向代理提供服务。
- Claude Code 获得的 LangBot 工具只限当前运行授权范围。

## 开发检查

```bash
uv run --no-sync pytest -q
uv run --no-sync ruff check .
```


> Shared runtime / daemon upgrade: [required setup and safety contract](../README.md#shared-worker-candidate--daemon-upgrade). Shared 模式必须配置独立强 token 和端口；默认本地工作目录为 `/data/workspace`。请同时升级 daemon.py 与完整 pkg 目录；旧客户端不兼容。
