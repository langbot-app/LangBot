# Local Agent

Local Agent 是 LangBot 官方的进程内运行器。它在 LangBot 插件进程中完成提示词组装、模型调用、工具循环、知识库检索、上下文压缩和技能调用，适合使用 LangBot 托管模型与工具的通用 Agent 场景。

## 运行器 ID

`plugin:langbot-team/LocalAgent/default`

## SDK 兼容性

LocalAgent 要求 `langbot-plugin>=0.7.18`，不设版本上限。插件包与项目声明保持一致；CI 每次安装 PyPI 最新稳定版 SDK，记录实际版本并验证契约和测试。`uv.lock` 保存最近一次解析结果，CI 会更新其中的 SDK 选择。

## 主要能力

- 支持主模型与 fallback 模型切换。
- 支持流式与非流式模型调用。
- 支持 LangBot 工具调用，并可选择同批工具并行或串行执行。
- 支持多知识库检索、重排和 Top-K 控制。
- 支持文本、图片、音频和文件等结构化输入。
- 支持基于模型上下文窗口的 token 预算与自动压缩。
- 支持 Host 管理的技能发现、激活和注册工具。
- 支持运行中断和同一会话内的 steering 跟进消息。

## 工作方式

LangBot 负责运行信封、资源授权与结果投递；Local Agent 负责 Agent 循环。每次运行会收到当前事件、输入、会话句柄、授权资源和运行时信息。需要历史、模型、工具、知识库或状态时，插件通过 `RunnerAPIProxy` 调用 Host API，不直接访问 LangBot 内部管理器。

典型流程如下：

1. 获取预处理后的有效提示词和授权的历史记录。
2. 组装当前输入、历史、RAG 结果、技能提示和工具定义。
3. 使用 Host token 计数 API计算上下文预算。
4. 必要时生成或复用会话级压缩摘要。
5. 调用模型并处理工具调用，直到得到最终回复或达到迭代上限。
6. 将流式增量、工具事件、状态更新和最终结果交给 LangBot 投递。

## 配置

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `model` | `model-fallback-selector` | 是 | 主模型为空，fallback 为空，reasoning 为 {} | 选择主模型及备用模型 |
| `timeout` | `integer` | 否 | `300` | 整次运行超时秒数；`0` 或 `null` 仅关闭插件本地超时，Host 截止时间仍有效 |
| `prompt` | `prompt-editor` | 是 | `You are a helpful assistant.` | 默认系统提示词；Host 提供有效提示词 API 时优先使用预处理后的结果 |
| `remove-think` | `boolean` | 否 | `false` | 请求模型适配器移除思考内容 |
| `knowledge-bases` | `knowledge-base-multi-selector` | 否 | `[]` | 用于 RAG 的知识库 |
| `box-enabled` | `boolean` | 否 | `true` | 启用沙箱执行和文件工具 |
| `box-session-id-template` | `string` | 是 | `{launcher_type}_{launcher_id}` | 预设下拉选择共享范围，支持自定义插值模板 |
| `advanced-settings` | `boolean` | 否 | `false` | 展开检索、工具、超时和上下文管理的高级参数；仅影响表单显示 |
| `date-grounding` | `boolean` | 否 | `true` | 注入当前 UTC 日期，并提醒核实时效信息 |
| `retrieval-top-k` | `integer` | 否 | `5` | 每个知识库请求的检索条数 |
| `rerank-model` | `rerank-model-selector` | 否 | 空 | 可选重排模型 |
| `rerank-top-k` | `integer` | 否 | `5` | 重排后保留的结果数 |
| `max-tool-iterations` | `integer` | 否 | `100` | 最大工具跟进轮数 |
| `tool-execution-mode` | `select` | 否 | `parallel` | 同批工具调用使用 `parallel` 或 `serial` |
| `max-tool-result-chars` | `integer` | 否 | `20000` | 注入下一次模型请求的工具结果字符上限 |
| `context-history-fetch-limit` | `integer` | 否 | `50` | 从 Host 历史 API 拉取的消息数 |
| `context-window-tokens` | `integer` | 否 | `200000` | 上下文窗口 fallback，同时作为 Host 模型元数据的上限 |
| `context-reserve-tokens` | `integer` | 否 | `16384` | 为模型输出和 provider 开销预留的 token |
| `context-keep-recent-tokens` | `integer` | 否 | `20000` | 压缩时保留的近期历史 token |
| `context-summary-tokens` | `integer` | 否 | `8000` | 压缩摘要的最大 token |

## 上下文管理

Local Agent 不按固定对话轮数截断历史，而是按最终 provider 消息和工具 schema 的 token 数进行预算。超过输入预算时，会通过授权模型生成结构化摘要，并保留近期历史。Host 支持状态 API 时，摘要会以会话级 checkpoint 持久化；下次运行可从 checkpoint 游标之后继续拉取历史。

如果 provider 在尚未输出内容前返回上下文溢出错误，Local Agent 会使用更激进的预算再压缩一次，并重试当前模型调用一次。Host 不提供 token 计数能力时，运行会失败关闭，不使用不可靠的字符估算替代。

## 工具与大结果

工具调用通过 Host 授权列表执行。过大的工具结果只向模型提供有界预览；工具明确返回的路径、URL 或其他外部引用会被保留。工具可返回顶层 `terminate: true`，当同批所有工具结果都请求终止时，Local Agent 会跳过额外模型调用并结束当前运行。

## 技能支持

当 Host 提供技能资源并允许 `activate` 或 `register_skill` 工具时，Local Agent 会将可见技能事实加入模型上下文。技能包、挂载路径和可见性策略由 LangBot 与 Box 管理，Local Agent 只负责把授权能力呈现给模型并转发工具调用。

## 权限与安全边界

插件声明并使用以下 Host 权限：

- 模型：`count_tokens`、`invoke`、`stream`、`rerank`
- 工具：`detail`、`call`
- 知识库：`list`、`retrieve`
- 历史：`page`

“Local”表示 Agent 循环运行在本地插件进程中，并不表示模型可以访问运行机器的任意文件。文件和沙箱操作必须通过本次运行授权的 Host 或 Box 工具完成。

## 开发与测试

```bash
uv sync --extra dev --upgrade-package langbot-plugin
uv run --no-sync pytest -q
uv run --no-sync ruff check .
```

测试使用已发布的 SDK。若导入或契约检查失败，先核对实际安装版本和 PyPI 发布内容；不要用本地 SDK 源码替代发布包掩盖兼容问题。

## 文件交付

文件写入 sandbox 后不会自动交付。模型需要显式调用 `export_box_files(paths)`，传入要交付的绝对路径；建议把生成物放在本次 run 的 outbox 中。Core 会先完整校验所选文件，成功后登记附件并仅清理所选文件，其他文件保持不变。导出错误通过对应的工具结果返回同一上下文，重试沿用原来的工具、上下文和时间预算，没有独立的两次自动修复循环。

清理警告不代表导出失败，不应因此重复交付。Core 接收后的平台发送失败会终止运行，避免重新生成或重发可能已经送达的文件。流式文字已发出时不会被撤回。

最低 SDK 版本已包含显式路径导出 API。Core 和 Plugin Runtime 也须提供配套契约；缺少 `export_box_files(paths)` 时，插件会明确拒绝准备文件工具。

## 当前边界

- 不负责 EventGateway、事件订阅、调度器或事件广播。
- 不绕过 `ctx.resources` 访问未授权模型、工具、知识库或平台 API。
- 不在插件实例上保存可变的跨会话状态；需要持久化时使用 Host 管理的状态或存储接口。

## 原生运行器迁移说明

以上字段属于**每条流水线的 Runner 绑定配置**（`ai.runner_config[plugin:langbot-team/LocalAgent/default]` / 解析后的
`binding.runner_config`），不是插件全局配置。`model.reasoning` 默认 `{}`，按模型 UUID
保存 provider-neutral 等级：`provider_default`、`disabled`、`enabled`、`minimal`、`low`、
`medium`、`high`、`xhigh`、`max`。Host 必须从描述符声明的模型选择器读取配置，在运行开始时
冻结到授权快照，并对主模型、fallback、工具跟进与摘要请求使用请求级模型副本。插件不生成
供应商参数，也不扩展 SDK/wire；需要支持该桥接的 Host，单纯保存配置不代表推理等级已生效。
`remove-think` 只控制思考输出过滤，不代表推理强度。

`date-grounding=true` 默认在 token 预算计算前注入当前 UTC 日期与时效信息核实提示，
并保留静态或 Host 有效提示词。UTC 不等于推测用户时区；已有独立日期提示时可设为 `false`。
SDK 支持的结构化提示词内容与消息元数据会保留；无效内容显式报错，不再静默丢弃。

迁移采用新默认：token 预算与 checkpoint 压缩替代 `max-round`，不做轮数到 token 的伪换算；
工具结果上限 20000 字符、总运行超时 300 秒、工具跟进上限 100 轮；保留有界且独立的 RAG 上下文。
`timeout=0`/`null` 只关闭插件本地超时，不能取消 Host 截止时间。`retrieval-top-k=5` 为每个知识库
请求 5 条，无重排时合并后也最多保留 5 条；有重排时使用 `rerank-top-k=5`。

保留 `tool-execution-mode=parallel` 默认以并发执行独立工具，结果仍按源顺序返回。
**结果排列不代表执行顺序**，有副作用或依赖顺序的操作可能竞争，应选择 `serial`；
两种模式均不能扩大 Host 授权范围。工具、MCP 附件/可见性、技能授权由 Host 管理，Box 复用由运行器配置控制，
不可移到插件全局配置。旧 `knowledge-base` 和字符串 `model` 分别需要显式迁移为
`knowledge-bases` 与模型选择器；旧历史与 Box 文件共享范围必须另行分析，压缩不等于数据导入。

### Box 沙箱

沙箱开关和复用范围在运行器配置中设置。默认 `{launcher_type}_{launcher_id}` 按聊天复用；
`{global}` 在当前工作区共享，也可用 `{sender_id}`、`{bot_id}`、`{run_id}`、`{event_type}`
和当前请求变量组合模板。变量不存在时会明确报错，不会悄悄把不同会话合并。
托管环境要求固定共享范围时，运行器采用 Host 返回的范围限制。

LocalAgent 在执行前获取并绑定 Box，再导入当前附件。生成的文件须放到提示词指定的
本次运行 outbox 中。成功完成后，流水线把导出的文件作为回复附件发送；Agent 通过
当前事件的回复 API 发送，仍遵守该事件允许调用的工具范围。关闭沙箱后不提供原生文件和执行工具。

Box 复用不等于文件发送范围复用：每次运行的收件与发件目录独立。Box 空闲回收后会重新创建，
工作区文件保留，容器内部进程不会保留。
