# 事件处理器示例工坊

[English](README.md)

一个完整、可重复测试的 **Runner** 示例插件。适用于 LangBot 4.11
 `dev/4.11.x` 主程序和配套 SDK；旧版 SDK 没有此组件，不能运行。
无需配置模型，也不依赖任何付费 API。

## 两个组件

- **社区助手**：使用类型化的 `@self.handler(...)` 处理入群、退群、消息、表态、反馈和好友申请。
  展示查询资料、回复、配置分支、进度日志、可恢复错误及主动失败。
- **事件观察员**：使用 `EBAEvent` 通用处理函数处理绑定机器人的事件，支持输出结构化摘要和事件载荷。
  不调用工具，不发送消息。

安装插件不代表启用监听。请先创建插件处理器配置，再到详情页选择组件并保存。
两份配置相互独立。在机器人详情页的「插件处理器」中添加配置并保存，即可自动处理组件声明的事件；也可以在这里直接创建配置。
插件处理器与 Agent／流水线路由独立执行，同一事件可按多份配置分别处理，某次处理失败不会阻止其他处理。
观察员的 `*` 只接收已绑定机器人的事件，**不是安装后全局广播监听**。
旧版 Pipeline 的 EventListener 语义保持不变。

## 安装与页面调试

1. 使用配套 SDK 在此目录执行 `lbp build`。
2. 在 LangBot「添加扩展」中选择本地安装，上传
   `dist/langbot-team-RunnerDemo-0.2.1.lbpkg`。
3. 分别创建「社区助手」「事件观察员」两个插件处理器配置。
4. 在详情页顶部选择对应组件，在右侧「配置」标签中设置参数并保存。
5. 在左侧事件调试中选择样例的 `event_type`；切换到「完整 JSON」，仅粘贴样例中的 **`data` 对象**。
   样例外层的 `event_type`、`data` 是直接调用 HTTP 调试接口的请求格式。
6. 点击运行测试，在右侧点选运行记录，查看日志、动作参数、结果、状态和耗时。

插件代码和工具调用链会实际运行；页面调试中的平台动作使用 Mock，不发真实消息。
绑定真实机器人后，社区助手的回复会实际发送。好友申请只记录人工审核提示，绝不自动批准。

## 推荐演示顺序

| 样例 | 展示内容 |
|---|---|
| `01-member-joined.json` | 读取成员和群资料，再回复欢迎消息，完整展示 3 次动作 |
| `02-member-left.json` | 默认只记录警告；打开「发送退群通知」后再执行可比较配置分支 |
| `03-help.json` | 查看 `/demo` 指令帮助 |
| `04-profile.json` | 通过指令触发多步资料查询 |
| `05-slow.json` | 3 条进度日志、模拟任务耗时和最终回复 |
| `06-failure.json` | 默认仅提示；开启「允许触发演示错误」后，产生有错误日志的失败记录 |
| `07-feedback.json` | 差评分类、反馈内容和原因记录，不发送回复 |
| `08-reaction.json` | 记录消息表态；修改 `is_add` 可演示撤销 |
| `09-friend-request.json` | 记录好友申请与人工审核提示，不执行批准 |
| `10-observer-custom.json` | 选择观察员，观察自定义平台事件；打开载荷记录可查看自定义字段 |
| `11-echo-with-image.json` | 保留中文和混合消息链，回显文字并记录图片类型；不下载图片 |
| `12-ignored-message.json` | 非演示指令正常结束，不发送回复 |

演示 `fail` 后建议关掉失败开关。它是明确的测试指令，不会随机失败。
若平台不支持可选资料查询，插件保留失败动作和警告，随后使用事件资料继续欢迎流程；
回复动作自身失败则传播异常，保留已有日志并将运行标记失败。

## 配置说明

社区助手可配置输出语言、欢迎文案、指令前缀、退群通知、演示任务时长和失败开关。
延时默认 600 毫秒，代码限制为 0–2000 毫秒。欢迎文案按输入原样使用，切换语言不会自动翻译它。
观察员可配置输出语言和是否记录事件载荷，后者默认关闭；不会记录原始平台对象。

## 共享运行时认证配置

RunnerDemo 声明了 `execution.sharedRuntime: shared-runtime-v1`，并保持运行时代码
不使用进程级或可变模块状态；配置和单次运行数据仅通过 `RunnerContext` 传递。
`tests/test_shared_runtime.py` 用已发布 SDK 复现了双绑定证据：同一个真实 Worker
（`PluginRuntimeController`、一份 `RunnerDemo` 实例、每个组件一份实例）分别以
workspace-A/installation-A 与 workspace-B/installation-B 挂载两次，两个安装并发驱动同一个
`community` 组件，各自使用独立配置、事件和结果；同一测试还会摘除其中一个安装，验证
另一个安装的对象图不受影响。只有 Host/后端 RPC 响应是固定桩。本地
`lbp build` 生成的归档仍未签名，ZIP 注释中不含认证信息。Space 审批是独立的
签发和签名关卡；本仓库不声称已经获得审批或证书。

## 开发测试

```bash
# 先准备支持 Runner 的配套 SDK 环境
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
lbp build

# 可选：在已授权实例上安装插件并自动执行全部样例
export LANGBOT_API_KEY='your-key'
python scripts/smoke.py --base-url http://127.0.0.1:5399
```

也支持 `LANGBOT_TOKEN`，多工作空间可设置 `LANGBOT_WORKSPACE_ID`。
脚本创建或复用「示例工坊 · 社区助手」「示例工坊 · 事件观察员」，运行全部 12 个样例，
验证回复使用 Mock，并在最后关闭故障演示开关。它会为示例配置开启退群通知和观察员载荷记录，
不会创建机器人绑定。重复执行会增加一组运行记录。
测试结果保存在不入库的 `data/smoke-results.json`，其中不包含凭据。

## 阅读源码

`community.py` 演示类型化事件，`observer.py` 演示通用事件回退。
同名 YAML 定义组件名称、独立配置、支持事件与权限。`ctx.event` 是平台事件；
`ctx.config` 是当前处理器的配置；`ctx.log()` 记录日志，`ctx.reply()` 调用平台回复动作。
`ctx.get_available_tools()` 查询本次可调用的工具。平台和 LangBot API 通过 `self.plugin` 调用，并自动使用当前运行的授权。无需伪造 Pipeline Query，也没有 Agent loop；处理函数返回即结束本次调用。

## 完整事件矩阵

创建一个独立的「事件观察员」配置，开启事件载荷日志，不绑定机器人。
沿用上面的认证环境变量，执行：

```bash
python scripts/event_matrix.py --base-url http://127.0.0.1:5399 --processor-id YOUR_PROCESSOR_UUID
```

`examples/event-matrix.json` 覆盖全部 17 种标准事件的最小和完整载荷，
另有空消息、纯图片、反馈类型、临时禁言等 8 个变体，以及 6 个非法输入，共 48 项。
脚本检查类型化字段保留、合法输入只完成一次运行、持久化状态、无动作调用，
以及非法输入被拒绝。运行会增加调试记录，结果保存在被 Git 忽略的
`data/event-matrix-results.json`，不会安装插件或修改机器人绑定。
这些检查覆盖 Host 与运行时的处理链路；各平台的事件支持和实际投递仍需单独验证。

观察员声明 `usages: [agent, event]`，可由 Agent 或插件处理器选择；社区助手声明 `usages: [event]`。两者共用 Runner 上下文和事件处理函数。
