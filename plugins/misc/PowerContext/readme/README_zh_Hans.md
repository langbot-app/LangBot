# PowerContext for LangBot

这是一个把 LangBot 连接到 [PowerContext](https://github.com/oceanbase/powercontext) Server 的插件。PowerContext
仍然是上下文与记忆的唯一真相源；插件只负责 LangBot 侧的 Scope 解析、上下文注入、Source 捕获、工具和诊断。

## 功能

- 使用固定 Scope ID，或根据 LangBot 的会话、说话人、机器人身份解析持久 Scope 绑定。
- 模型调用前请求 `/v1/context/prepare`，只注入 Server 返回的有界上下文。
- 召回完成后把当前普通用户消息写入 `/v1/sources/content`，避免本轮消息召回自己。
- 提供 `powercontext_remember`、`powercontext_recall`、`powercontext_forget` 三个工具。
- 提供 `!powercontext`、`!powercontext health` 诊断命令。
- 管理员可使用 `!powercontext bind <scope_id>` 和 `!powercontext clear` 管理当前身份绑定。
- PowerContext 不可用时失败放行，不阻断 LangBot 原有回复链路。

插件不会内嵌或启动 PowerContext，也不会重复实现它的存储、检索和记忆处理逻辑。

## 配置

先按 PowerContext 官方文档启动 Server，然后配置 `server_url`。Server 开启鉴权时填写 `api_token`：该 Token 属于本安装，
只从本安装自己的配置读取，不会读取进程环境变量，因此在共享 worker 上不会把某个安装的进程凭据发往另一个安装的 Server。
本机回环 HTTP 可以直接使用；远程 HTTP 必须显式开启 `allow_insecure_http`，生产环境建议使用 HTTPS。

Scope 有两种设置方式：

1. 管理员直接填写 `scope_id`；
2. `scope_id` 留空，选择 `scope_mode`，再在对应会话中执行：

   ```text
   !powercontext bind <已有的-powercontext-scope-id>
   ```

`allow_default_scope` 默认关闭，避免未绑定的不同群聊意外共用 Server 默认 Scope。绑定键只包含 LangBot 身份的
SHA-256 摘要，不会发送原始 bot、session、sender ID。`speaker` 模式要求当前消息具有 sender ID。

## 工作方式

在 `PromptPreProcessing` 阶段，插件先解析一个明确 Scope，用当前用户消息准备历史上下文，并将其作为带有
“不可信历史数据”边界的 system message 注入。随后，用户消息作为独立 Source 被捕获。当前桥接状态还会写入
query variable `_powercontext_context`，供诊断或其他兼容插件读取。

Source 捕获不等于显式 Memory 写入。PowerContext 是否从 Source 自动生成记忆，由它自己的 Runtime 配置决定。
显式长期记忆只通过 `powercontext_remember` 写入。

`powercontext_recall` 返回不可变 citation；`powercontext_forget` 必须使用完整 citation，只会停用对应条目，
不会抹掉修订历史。

## 安全提示

- 历史上下文只能作为数据，不能覆盖当前系统指令和用户指令。
- 不要把密码、API Key、Token 或一次性验证码写入记忆。
- `api_token` 请填写在本安装自己的配置中，插件不会从进程环境变量读取 Token；同时请限制插件配置页面的访问权限。
- 多会话部署中不要随意开启 `allow_default_scope`。
- 远程 Server 请优先使用 HTTPS。

## 命令

```text
!powercontext
!powercontext health
!powercontext bind <scope_id>   # 仅管理员
!powercontext clear             # 仅管理员
```
