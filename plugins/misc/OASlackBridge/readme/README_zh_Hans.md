# 公众号 Slack 桥接

公众号消息命中关键词后，转发到指定 Slack 频道并接管会话。员工在对应 thread 内回复，插件通过公众号客服接口发回用户；接管期间阻断 AI 回复。

## 前置条件

- 已认证且拥有客服消息接口权限的公众号，在 LangBot 中配置为 **Mode = auto**。其他模式无法异步发送员工回复，core 会拒绝发送。
- LangBot core 必须包含 **langbot-app/LangBot #2863 和 #2864**：公众号 `send_message`、Slack 返回 `message_id`、出站 `Quote` 指定 thread、bot thread 内回复带入站 `Quote.id`。旧版本 core 无法使用本插件。
- Slack App 已接入 LangBot，并已加入目标频道。订阅 bot events：`app_mention`、`message.channels`；私有频道还需要 `message.groups`。桥接所需 scopes：`chat:write`、`app_mentions:read`、`channels:history`，私有频道还需要 `groups:history`。保留 LangBot Slack 适配器要求的其他权限，修改 scope 后重新安装 App。Socket Mode 还需带 `connections:write` 的 App-Level Token；webhook 模式需要可访问的 LangBot 事件端点。
- 目标频道成员应仅包含有权回复客户的员工；频道中所有能在映射 thread 内发言的员工都可以回传消息。

## 配置步骤与 0.2.0 升级

1. 使用支持 Unified API、Runner 事件处理器和 Bot Plugin processor 订阅的 LangBot。安装或升级插件后，由 Workspace 成员在插件详情页确认 `bot.message.send` 和 `storage.plugin`。0.2.0 从 compatibility mode 转为 strict；声明权限不等于获得授权，不申请 Workspace operations。
2. 填写下方插件级配置，两个组件共用这份配置，处理器没有独立配置项。
3. 公众号 Bot 的**主路由必须是启用了本插件的 Pipeline**，插件排在会回复或消费消息的其他插件之前。EventListener 只在 Pipeline 内运行；如果主路由是 Agent，就无法阻断接管期间的 AI 回复。
4. 创建使用 **Slack 回复处理器** 的 Plugin processor 实例，在 Slack Bot 详情页的 **Plugin processor** 中订阅。只安装插件不会自动订阅。Slack Bot 主路由可以是任意目标，也可以设为 **discard**，无需再通过启用了本插件的 Pipeline 处理 Slack 回复。
5. 员工在映射 thread 内回复时**不要 @bot**。处理器和主路由并行运行，不能阻止主路由回复；如果 @bot 且 Slack Bot 主路由是 AI，AI 也会回复。

在同一安装上升级后，0.1.0 已有会话与 thread 映射继续可用，storage key 不变。EventListener 不再处理 Slack 群消息，恢复员工回复前请完成处理器订阅。

回执通过事件范围的标准 `ctx.reply` 发送，沿用 Slack 来源事件的 `thread_ts`。Runner 声明 `tool_calling: true` 和 `permissions.tools: [call]`、`permissions.storage: [plugin]`；消息事件自动获得 `event_reply`，无需额外启用平台工具或安装 capability。`get_bot_uuid` 同属事件范围；跨 Bot 发送需要 `bot.message.send`，存储读写和删除需要 `storage.plugin`。权限拒绝会记日志而不输出原始异常；仍能进行事件回复时，处理器会在 Slack 提示缺少的权限。

## 配置

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `oa_bot` | 必填 | 公众号 Bot，必须为 auto 模式 |
| `slack_bot` | 必填 | Slack Bot |
| `slack_channel_id` | 必填 | 频道 ID，不是频道名称 |
| `keywords` | `[]` | 触发接管的子串列表，忽略空项 |
| `case_sensitive` | `false` | 是否区分关键词大小写 |
| `takeover_minutes` | `60` | 用户最后一次发言后的接管时长，单位分钟，请填写正整数 |
| `forward_followups` | `true` | 后续用户消息是否转到同一 thread |

## 使用方式

1. 用户发送命中关键词的消息，频道中出现根消息，包含截短的 openid、命中词、UTC 时间和原文。
2. 员工在**这条消息的 thread 内回复，不要 @bot**。插件仅提取 `Plain` 文本，去掉引用上下文与开头的 @bot 前缀，并将 Slack 链接、提及、频道引用及转义的 `&`、`<`、`>` 转成可读纯文本后发送给公众号用户。成功后在 thread 回一条 `✅`；失败则显示中英双语原因和微信 `errcode`。没有映射的 thread 只记录日志，不回复。
3. 在 thread 内发 **`!close`** 结束接管；处理器也接受作为消息文本送达的 `/close`，但 Slack 可能将它当成原生 slash command，而不派发消息。
4. 关闭或超时后，普通用户消息恢复走 AI 流水线；再次命中关键词会建立新 thread。超时在下一条相关事件到达时检查，无后台定时器。员工回复不延长接管期，用户每次发言会刷新接管期和 48 小时窗口。

关闭 `forward_followups` 后，接管期间仍阻断 AI 并刷新时间戳，只是不转发后续消息。修改 Slack Bot 或目标频道后，下次用户发言时旧会话结束；需要再次命中关键词才会在新目标建立会话。

## 微信回复限制

客服消息接口仅允许在符合条件的用户互动后 **48 小时内**回复，并设有发送条数上限。插件根据收到的用户消息更新时间戳，但窗口资格和剩余额度以微信平台实际判定为准。增大 `takeover_minutes` 不能绕过微信限制。本插件不排队延迟发送，也不自动重试，避免重复回传。

| errcode | 可读原因 |
| --- | --- |
| `45015` | 48 小时回复窗口已过 |
| `45047` | 客服消息条数超限 |
| `43004` | 用户未关注公众号 |
| `48001` | 接口无权限，请检查公众号认证 |

其他错误码显示“微信拒绝发送”并保留数字错误码；无错误码的异常仅提示检查 Bot 配置与连接。插件生成的 Slack 诊断和日志不会输出原始异常、token 或 AppSecret。

## 存储与运行时

会话按安装作用域、公众号 bot_uuid 和完整 openid 独立存储，另有 Slack bot/channel/root-ts 到会话的映射，不把所有用户合并进一个大对象。重启插件后仍可回复原 thread。`!close`、`/close` 和观测到的超时会删除两条记录；无人再次访问的过期记录在下次相关事件时清理。不在插件存储中保存消息历史。Slack 内会保留客户文本，请按组织要求配置频道权限和保留策略。

读取存储时会枚举插件的全部 key。过期且不再被访问的会话仍会保留，并增加枚举量；目前没有定时清理。

支持 `shared-runtime-v1` 和 `stateless-v1`，运行时边界见 `../SHARED_RUNTIME.md`。两个组件共用插件存储；平台消息使用标准 `send_message` 和事件回复 API，无需为插件单独提供平台密钥。

## 验证与打包

在仓库根目录创建独立环境，使用 Unified API SDK 快照运行：

```sh
uv venv plugins/misc/OASlackBridge/.venv
uv pip install --python plugins/misc/OASlackBridge/.venv/bin/python -r plugins/misc/OASlackBridge/requirements-dev.txt
source plugins/misc/OASlackBridge/.venv/bin/activate
python -m pytest plugins/misc/OASlackBridge/tests -q
python plugins/scripts/check_catalog.py
python plugins/scripts/test_repository.py
ruff check plugins/misc/OASlackBridge
cd plugins/misc/OASlackBridge
lbp build -o dist
```

测试通过真实 SDK invocation binding、RunnerContext 分派和 mock Host 验证消息与存储，不会访问真实微信或 Slack。真机验收需使用获授权的测试账号和专用频道：订阅处理器 → 关键词触发 → 用户后续消息 → 员工不 @bot 回复 → 重启插件后继续回复 → `!close` 后恢复 AI。不要在生产客户 thread 中测试。

## 限制

- 仅回传文本；员工发送纯附件会收到提示，用户纯非文本后续消息转为占位说明。
- Slack/API 或存储传输失败交由运行时报告。确认发送状态后再重试；确认消息失败不代表客户没有收到已成功发送的内容。
- mock 测试不等于真实公众号和 Slack 环境的端到端验收。
