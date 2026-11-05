# Multica 智能体

在 LangBot 中直接与选定的 [Multica](https://github.com/multica-ai/multica) 智能体对话。

每个 LangBot 会话绑定一个 Multica 聊天会话。用户消息会发送到该会话并触发所选智能体运行，运行器等待智能体回复后把结果发回聊天。同一会话也能在 Multica 网页端的 **Chat** 中看到。

## 运行器标识

`plugin:langbot-team/MulticaAgent/default`

## 配置步骤

1. 在 Multica 中创建个人访问令牌（Settings → API tokens，形如 `mul_...`）。聊天以令牌所属用户身份创建，该用户需有权使用目标智能体。
2. 记下工作区 UUID 和智能体 UUID（`multica agent list --output json` 可同时查看）。
3. 在 LangBot 流水线中选择 **Multica 智能体** 运行器并填写下列配置。智能体所在的运行时（Multica daemon）需在线才能回复。

## 配置项

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| server-url | string | 是 | https://api.multica.ai | Multica API 地址，自托管时填写自己的服务端地址 |
| api-token | secret | 是 | '' | Multica 个人访问令牌（`mul_...`） |
| workspace-id | string | 是 | '' | Multica 工作区 UUID |
| agent-id | string | 否 | '' | 默认智能体 UUID；未设置时用户需先用 `use` 选择 |
| allow-agent-switch | boolean | 否 | true | 允许用 `<前缀> use` 按会话切换智能体 |
| command-prefix | string | 否 | /multica | 运行器聊天命令前缀 |
| timeout | integer | 否 | 600 | 等待回复的秒数 |
| poll-interval | number | 否 | 2 | 查询回复的间隔秒数 |

## 聊天命令

| 命令 | 作用 |
| --- | --- |
| `/multica` | 查看当前智能体、会话和可用命令 |
| `/multica agents` | 列出令牌可见的智能体 |
| `/multica use <名称或 ID>` | 为当前会话切换智能体（开启新的 Multica 会话） |
| `/multica new` | 与当前智能体开启新的 Multica 聊天会话 |

## 行为说明

- 智能体完成后一次性回复（不流式）。智能体运行可能需要数分钟；超过 `timeout` 时本次运行失败，但任务仍在 Multica 中继续，回复可在 Multica 中查看。
- 若已保存的 Multica 会话被删除或归档，会自动新建会话并重发一次消息。
- Multica 中失败的智能体运行会以失败的 LangBot 运行返回，并附带 Multica 的失败信息；被取消的任务返回 `multica.no_reply`。
- 只转发文本输入，附件不会上传到 Multica。
