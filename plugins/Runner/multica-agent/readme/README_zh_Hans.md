# Multica 智能体

在 LangBot 中直接与选定的 [Multica](https://github.com/multica-ai/multica) 智能体对话。

每个 LangBot 会话绑定一个 Multica 聊天会话。用户消息会发送到该会话并触发所选智能体运行，运行器等待智能体回复后把结果发回聊天。同一会话也能在 Multica 网页端的 **Chat** 中看到。

## 运行器标识

`plugin:langbot-team/MulticaAgent/default`

## 配置步骤

1. 在 Multica 中创建个人访问令牌（Settings → API tokens，形如 `mul_...`）。聊天以令牌所属用户身份创建，该用户需有权使用目标智能体。
2. 记下工作区 UUID（`multica workspace list --output json`）。智能体填名称即可，也可填 UUID。
3. 在 LangBot 流水线中选择 **Multica 智能体** 运行器并填写下列配置。智能体所在的运行时（Multica daemon）需在线才能回复。

## 插件设置

每个安装在插件设置页面配置一次。

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| language | select | 否 | en_US | 插件自身聊天输出的语言：`en_US`、`zh_Hans`、`zh_Hant`、`ja_JP`、`es_ES`、`ru_RU`、`th_TH`、`vi_VN` |

- 只影响插件自己写出的内容：进度行、命令回复和错误提示。智能体的回答正文和 Multica 返回的原始错误文本原样透传，不翻译。
- 不影响 LangBot 自身的界面语言（那是工作区设置）。
- 支持上面 8 个 locale，其他值回退英文。没有“跟随工作区语言”选项：那需要额外的工作区权限，每个安装都要成员确认授权。

## 运行器配置项

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| server-url | string | 是 | https://api.multica.ai | Multica API 地址，自托管时填写自己的服务端地址 |
| api-token | secret | 是 | '' | Multica 个人访问令牌（`mul_...`） |
| workspace-id | string | 是 | '' | Multica 工作区 UUID |
| agent | string | 否 | '' | 默认智能体，**名称或 UUID 均可**；未设置时用户需先用 `use` 选择（见下文） |
| agent-id | string | 否 | '' | 0.2.0 起**已废弃**。仅在 `agent` 为空时作为智能体 UUID 原样使用，0.1.x 的流水线无需修改 |
| allow-agent-switch | boolean | 否 | true | 允许用 `<前缀> use` 按会话切换智能体 |
| command-prefix | string | 否 | /multica | 运行器聊天命令前缀 |
| timeout | integer | 否 | 600 | 等待回复的秒数 |
| poll-interval | number | 否 | 2 | 查询回复的间隔秒数 |
| progress-mode | select | 否 | messages | `messages`：每条进度单独一条消息，最后一条是答案；`stream`：同一条消息持续更新；`off`：只发答案（0.1.x 行为） |
| progress-interval | number | 否 | 15 | “仍在执行”进度的最小间隔秒数（5-300） |

### 按名称选择智能体

填 UUID 时直接使用。否则运行器拉取令牌可见的未归档智能体，先按完整名称（忽略大小写）匹配，再按唯一包含该文本的名称匹配，结果在当前会话内记住。匹配到多个时本次运行失败并列出带序号的候选，可回复 `/multica use <序号>` 或改用完整 ID；一个都不匹配时列出前 10 个可见智能体名称。

## 聊天命令

| 命令 | 作用 |
| --- | --- |
| `/multica` | 查看当前智能体、会话和可用命令 |
| `/multica agents` | 列出令牌可见的智能体（带序号和 ID 前 8 位） |
| `/multica agents <关键词>` | 只列出名称包含关键词的智能体 |
| `/multica find <关键词>` | 同 `agents <关键词>`；不带关键词时显示用法 |
| `/multica use <名称或 ID>` | 为当前会话切换智能体（开启新的 Multica 会话）；名称有歧义时回复带序号的候选 |
| `/multica use <序号>` | 按最近一次 `agents` / `find` / 候选列表的序号选择（10 分钟内有效，回复会写明选中的智能体） |
| `/multica new` | 与当前智能体开启新的 Multica 聊天会话 |

`/multica` 还会显示当前的 `progress-mode` 和 `language`。`use` 的参数是纯数字时总是按序号处理。

## 进度输出

Multica 没有任务事件流：运行器只能观察到任务生命周期（排队、执行、结束）和已等待时长，看不到智能体正在调用哪些工具或执行哪一步，因此进度不会写出这些信息。

`progress-mode: messages`、`language: zh_Hans` 时的一次运行如下：

```
⏳ 已提交给 Coder（任务 3f2a9c1e）
▶️ Coder 开始执行
⏱ 仍在执行 · 已等待 45s
<智能体的答案，不带前缀>
```

任务排队时显示 `⏱ 排队中 · 已等待 Ns`。“仍在执行”每个 `progress-interval` 最多发一条，一次运行最多 `3 + timeout / progress-interval` 条消息。超时、取消或失败时，会先发一条 `⚠️ ...` 收尾，再结束本次运行。

`progress-mode: stream` 把同样的进度行写在同一条消息里，最后把答案接在末尾。不支持流式回复的平台会在运行结束时一次性收到这条消息，这类平台建议用 `messages`。

## 行为说明

- 智能体运行可能需要数分钟；超过 `timeout` 时本次运行失败，但任务仍在 Multica 中继续，回复可在 Multica 中查看。
- 若已保存的 Multica 会话被删除或归档，会自动新建会话并重发一次消息。
- Multica 中失败的智能体运行会以失败的 LangBot 运行返回，并附带 Multica 的失败信息；被取消的任务返回 `multica.no_reply`。
- 只转发文本输入，附件不会上传到 Multica。
