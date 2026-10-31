# ACP Runner

ACP Runner 用于把兼容 Agent Client Protocol（ACP）的编码 Agent 接入 LangBot。它支持在 LangBot 服务器本机、SSH 远端机器或用户侧 daemon 上启动 ACP 进程，并把 LangBot 本次运行授权的工具、知识库和历史能力通过 SDK MCP bridge 暴露给编码 Agent。

## 运行器 ID

`plugin:langbot-team/ACPAgentRunner/default`

## 主要能力

- 支持任意可通过 stdio 启动的 ACP 兼容 Agent。
- 支持 `local`、`remote-ssh`、`daemon` 三种运行位置。
- 支持 ACP session 恢复，并可在会话内复用外部 session。
- 支持流式文本、工具调用状态和 ACP plan 更新。
- 根据 ACP runtime 公告的能力转发图片或嵌入文本资源。
- 通过 SDK MCP bridge 提供授权的 LangBot 工具、知识库和历史。
- 支持运行中的 steering 跟进消息。
- `!new` 可在任意运行位置重置当前 ACP 绑定；daemon 模式下仅在客户端声明对应 session capability 时额外提供 `!list`、`!sessions`、`!switch` 和 `!delete`；`!stop` 使用 Host 的通用 Runner 取消契约。

## 支持的预设

`provider` 可选择预设 ACP 命令，也可选择 `custom` 并填写 `acp-command`。常见预设包括 Claude Code、Codex、Gemini、OpenCode、Qwen Code、Auggie、Kilo、Pi ACP 等。预设只负责提供默认启动命令，具体 CLI 仍需安装并完成认证。

## 运行位置

### 本机

在插件运行机器上启动 ACP 命令。`workspace` 必须是该机器上的可访问目录。

### SSH

通过 `ssh-target`、`ssh-port` 和可选的 `ssh-identity-file` 在远端启动 ACP 命令。LangBot MCP bridge 使用 SDK 反向隧道能力接入远端进程。

### Daemon

用户侧 daemon 主动连接插件提供的 WebSocket Hub，适合 Agent CLI 和工作区位于开发者电脑、LangBot 运行在服务器的情况。插件级 daemon Hub 配置如下：

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `daemon-enabled` | `boolean` | `false` | 是否启动 daemon WebSocket Hub |
| `daemon-host` | `string` | `127.0.0.1` | Hub 监听地址 |
| `daemon-port` | `integer` | `8766` | Hub 端口 |
| `daemon-token` | `secret` | 空 | daemon 连接共享令牌 |

只有在容器或反向代理明确暴露端口时才应使用 `0.0.0.0`，并应配置高强度 token 和 TLS 反向代理。

## 运行器配置

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `provider` | `select` | 预设值 | ACP provider 预设 |
| `location` | `select` | `local` | `local`、`remote-ssh` 或 `daemon` |
| `workspace` | `string` | 空 | Agent 工作目录 |
| `advanced-settings` | `boolean` | `false` | 展开桥接、超时、会话和进程调优选项；仅影响表单显示 |
| `ssh-target` | `string` | 空 | SSH 目标，如 `user@host` |
| `daemon-id` | `string` | 空 | daemon 模式下的客户端 ID |
| `acp-command` | `string` | 空 | 自定义 ACP 启动命令 |
| `timeout` | `integer` | `300` | 单次运行超时秒数 |
| `reuse-session` | `boolean` | `true` | 是否恢复并复用 ACP session |
| `streaming` | `boolean` | `true` | 是否输出流式增量 |
| `env-json` | `text` | `{}` | 传给 ACP 进程的环境变量 JSON |
| `mcp-servers-json` | `text` | `{}` | 额外 MCP server 配置 |
| `knowledge-bases` | `knowledge-base-multi-selector` | `[]` | 允许当前 runner 检索的 LangBot 知识库 |
| `langbot-assets-enabled` | `boolean` | `true` | 是否提供 LangBot 授权资产 |
| `langbot-assets-mode` | `select` | 自动 | 使用 stdio/代理或网关模式 |

其余 SSH、连接、启动和初始化超时字段用于慢网络或大型 CLI 启动场景，建议先保留默认值，再根据日志调整。

### 完整字段索引

除上表外，当前版本还提供以下高级字段：

- `daemon-connect-timeout`：等待目标 daemon 上线的最长时间。
- `ssh-identity-file`、`ssh-connect-timeout`、`ssh-extra-options`：SSH 私钥、连接超时和额外参数。
- `langbot-assets-gateway-host`、`langbot-assets-gateway-port`、`langbot-assets-gateway-public-url`、`langbot-assets-token-ttl`：Asset Gateway 地址、端口、公开 URL 和 token TTL。
- `startup-timeout`、`initialize-timeout`：ACP 进程启动与 initialize 握手超时。
- `create-session-if-missing`：session 恢复失败时是否自动创建新 session。
- `append-run-scope-prompt`：是否追加本次 LangBot 运行范围说明。
- `mcp-servers-json`：额外 MCP server JSON 配置。

## 会话恢复

启用 `reuse-session` 后，runner 会保存 ACP session ID，并在后续 LangBot 会话运行中优先调用 ACP session load/resume 能力。若 provider 声称支持恢复但实际恢复失败，runner 会创建新 session，并记录可诊断错误。不同 ACP provider 的恢复质量取决于其自身实现。

## 会话管理命令

`!list`、`!sessions`、`!switch` 和 `!delete` 用于 `location=daemon`，需要 daemon 端 ACP runtime 支持相应的 session capability；`!new` 只重置 ACPAgentRunner 绑定，可用于任意运行位置。它们属于 ACPAgentRunner 专属能力，不是通用 Runner Command 契约。命令状态使用可跨 Host context reset 保持稳定的 IM session identity，群聊和私聊不会共享当前会话指针。若 ACP 进程依赖 `env-json`，请改为在 daemon 进程环境中配置；daemon 会话控制命令不会把环境变量值持久化到插件存储。

| 命令 | 说明 |
| --- | --- |
| `!new` | 清除当前绑定；下一条普通消息创建新 ACP 会话。旧会话保留，可稍后切回 |
| `!list` / `!sessions` | 列出当前 daemon 工作目录中的 ACP 会话 |
| `!switch <序号或 session ID>` | 切换到已有 ACP 会话，下一条消息通过 `session/load` 或 `session/resume` 继续 |
| `!delete` | 调用 ACP `session/delete` 删除当前会话；成功后再清理 LangBot 绑定和可见上下文 |
| `!stop` | 停止当前正在运行的任务，但保留 ACP 会话 |

`!delete` 不会物理删除 LangBot 的运行审计记录；它删除 ACP 会话并创建新的 LangBot context generation，因此旧 transcript 不再进入后续上下文。若 ACP 删除失败，当前绑定会保留，避免 LangBot 与 ACP 状态不一致。

`!stop` 的即时取消需要 LangBot Host 在 session 并发槽之前识别控制命令。较旧的 Host 会把它作为普通命令排队，不能立即停止运行中的任务。

群聊中，`!new`、`!switch` 和 `!delete` 仅允许机器人管理员执行；普通成员只能停止自己发起的活动任务，机器人管理员可以停止群内任意活动任务。

## 多模态输入

runner 会根据 ACP 初始化响应中声明的 prompt capability 决定如何发送输入：

- 支持 image 时，data URL 图片转换为 ACP image block。
- 支持 embedded context 时，文本文件可作为 resource block 发送。
- URL 资源可作为 resource link 发送。
- provider 不支持相应能力时，runner 会向 Agent 注入明确说明，而不是静默丢弃。

## 权限与安全

插件只通过当前运行授权访问 LangBot 工具、知识库、历史和插件存储。远程命令、SSH 目标和工作区路径属于高权限配置，应由管理员控制。不要把长期凭据直接写入命令参数；优先使用受保护的环境变量或 daemon 所在机器的原生认证。

## Daemon 示例

```text
# 插件配置
daemon-enabled = true
daemon-host = 0.0.0.0
daemon-port = 8766
daemon-token = <shared-token>
```

```bash
python daemon.py \
  --url wss://your-domain.example/daemon \
  --daemon-id developer-laptop \
  --token '<shared-token>'
```

## 开发检查

```bash
uv run --no-sync pytest -q
uv run --no-sync ruff check .
```

使用本地 SDK 联调时应保留 editable 安装，并避免 `uv sync` 将其替换成缺少 Runner/daemon/MCP bridge API 的旧版 wheel。


> Shared runtime / daemon upgrade: [required setup and safety contract](../README.md#shared-worker-candidate--daemon-upgrade). Shared 模式必须配置独立强 token 和端口；默认本地工作目录为 `/data/workspace`。请同时升级 daemon.py 与完整 pkg 目录；旧客户端不兼容。
