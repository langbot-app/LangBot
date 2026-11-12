# ExecutionAPI 操作一览与作用域说明

LangBot Core 通过统一的 `ExecutionAPI` facade 暴露 80 项核心业务能力。插件与 Agent Runner 可以通过统一的授权契约与 SDK 入口调用这些能力。

## 作用域（Scopes）说明

ExecutionAPI 定义了严格的作用域划分，防止权限提升与越权访问：

| 作用域 | 标识 | 说明 |
| :--- | :--- | :--- |
| **Plugin** | `plugin` | 插件安装级别能力。仅在非 Run 上下文或具有插件完整 InstallationBinding 时可用。Run 上下文无法降级使用此类操作。 |
| **Run** | `run` | 单次 Agent Run 作用域。必须携带有效的 `run_id`，且按该 Run 的授权范围严格受限，调用时自动校验该 Run 的授权范围（如 Tool、Box 等资源）。 |
| **Runner Admin** | `runner_admin` | 运行器管理级别能力（如 Run 查询、状态恢复等）。需要特定的运行器管理权限，支持根据 AgentRun 授权快照恢复过期的 Run 上下文。 |
| **Plugin or Run** | `plugin_or_run` | 双模作用域能力（如 LLM 调用、存储操作等）。在 Run 上下文中调用时携带 Run 授权与审计标识；在普通插件事件上下文调用时使用插件安装级别凭证。 |

---

## SDK 调用方式

### 1. 通用 Execution 代理入口

SDK 在 `LangBotAPIProxy` 与 `RunnerAPIProxy`（即 `ctx.api`）上提供了通用的 `execution` 入口：

```python
# 1. 单目调用 (Unary)
version_info = await api.execution.invoke("execution.get_langbot_version")
# 也可以省略 "execution." 前缀
version_info = await api.execution.invoke("get_langbot_version")

# 2. 流式调用 (Streaming)
async for chunk in api.execution.stream(
    "execution.invoke_llm_stream",
    llm_model_uuid="your-model-uuid",
    messages=[{"role": "user", "content": "Hello"}],
):
    print(chunk)
```

在 Runner 上下文中（如 `ctx.api.execution.invoke(...)`），`run_id` 会由代理自动注入，确保上下文安全传递。

> **注意：存储类操作的调用限制**
> 
> `set_binary_storage`、`get_binary_storage`、`delete_binary_storage`、`get_binary_storage_keys` 这 4 个操作属于底层 Runtime 转 LangBot Core 的存储协议动作（属于 `RuntimeToLangBotAction`）。Runtime 侧并未暴露面向插件进程的直接同名 action 处理函数，因此通过 `api.execution.invoke('get_binary_storage', ...)` 直接调用会提示 `Action ... not found`。
> 
> 插件与 Runner 应对此使用 SDK 提供的专用存储代理方法：
> - 插件作用域存储：`api.set_plugin_storage` / `api.get_plugin_storage` / `api.delete_plugin_storage` / `api.get_plugin_storage_keys`
> - 工作区作用域存储：`api.set_workspace_storage` / `api.get_workspace_storage` / `api.delete_workspace_storage` / `api.get_workspace_storage_keys`
> 
> Runtime 在接收到上述方法调用后，会自动解析插件身份与租户边界，组装 `owner_type` 与 `owner` 后转发至 Core 的二进制存储 ExecutionAPI。

### 2. Box 专用代理方法

在 `LangBotAPIProxy` 上，新增了与 Runner 一致的 Box 沙箱绑定与文件流转方法（均具备 `@run_scoped` 保护）：

- `await api.bind_box(box_id: str) -> BoxBinding`: 绑定当前运行至指定 Box 沙箱。
- `await api.import_box_attachments(attachment_ids: list[str] | None = None) -> list[BoxFile]`: 将附件导入至绑定的 Box 沙箱。
- `await api.export_box_files(paths: list[str] | None = None) -> list[BoxFile]`: 从 Box 沙箱导出生成的文件。
- `await api.read_input_attachment(ref: str) -> InputAttachmentData`: 按 ref 读取当前事件输入附件的字节，无需绑定 Box。Runner 中优先使用 `await ctx.read_input_attachment(attachment)`：Host 不支持时返回 `None`，便于回退到旧逻辑。

---

## 80 项操作完整清单

本表与 `tests/data/execution_api_catalog.json`（由 LangBot Core 的 `scripts/export_execution_catalog.py` 导出）一致，由 `tests/api/test_execution_api_consistency.py` 校验。

| 操作 ID (Operation ID) | 作用域 (Scope) | 副作用 (Side Effect) | 流式 (Streaming) | 描述 |
| :--- | :--- | :--- | :--- | :--- |
| `execution.reply_message` | `plugin` | 是 | 否 | 回复消息到当前查询来源 |
| `execution.get_bot_uuid` | `plugin` | 否 | 否 | 获取当前查询关联的机器人 UUID |
| `execution.set_query_var` | `plugin` | 是 | 否 | 设置当前查询变量 |
| `execution.get_query_var` | `plugin` | 否 | 否 | 获取当前查询变量 |
| `execution.get_query_vars` | `plugin` | 否 | 否 | 获取当前查询的所有变量 |
| `execution.create_new_conversation` | `plugin` | 是 | 否 | 为当前查询创建新会话 |
| `execution.get_langbot_version` | `plugin_or_run` | 否 | 否 | 获取 LangBot Core 版本与 API 特性 |
| `execution.list_tools` | `plugin` | 否 | 否 | 列出插件可访问的工具 |
| `execution.list_commands` | `plugin` | 否 | 否 | 列出插件可访问的命令 |
| `execution.list_plugins_manifest` | `plugin` | 否 | 否 | 列出插件 manifest |
| `execution.get_bots` | `plugin` | 否 | 否 | 获取已配置的机器人列表 |
| `execution.get_bot_info` | `plugin` | 否 | 否 | 获取指定机器人的详细信息 |
| `execution.send_message` | `plugin_or_run` | 是 | 否 | 向目标实体主动发送消息 |
| `execution.call_platform_api` | `plugin_or_run` | 是 | 否 | 调用底层平台通信 API |
| `execution.reply_stream` | `run` | 是 | 否 | 更新、结束或中止当前运行的增量回复流 |
| `execution.request_interaction` | `run` | 是 | 否 | 向用户发起阻塞式人工交互（表单 / 确认 / 选择），等待提交或超时 |
| `execution.get_llm_models` | `plugin` | 否 | 否 | 列出可用 LLM 模型 UUID 列表 |
| `execution.count_tokens` | `plugin_or_run` | 否 | 否 | 计算指定消息链的 Token 数量 |
| `execution.invoke_llm` | `plugin_or_run` | 是 | 否 | 单目同步调用大语言模型 |
| `execution.invoke_llm_stream` | `plugin_or_run` | 是 | 是 | 流式调用大语言模型 |
| `execution.call_tool` | `plugin_or_run` | 是 | 否 | 调用工具（Tool）执行能力 |
| `execution.get_tool_detail` | `plugin_or_run` | 否 | 否 | 获取工具定义及参数模式 |
| `execution.set_binary_storage` | `plugin_or_run` | 是 | 否 | 设置二进制键值存储 |
| `execution.get_binary_storage` | `plugin_or_run` | 否 | 否 | 读取二进制键值存储 |
| `execution.delete_binary_storage` | `plugin_or_run` | 是 | 否 | 删除指定键的二进制存储 |
| `execution.get_binary_storage_keys` | `plugin_or_run` | 否 | 否 | 列出二进制存储键名 |
| `execution.get_config_file` | `plugin` | 否 | 否 | 读取插件配置文件 |
| `execution.invoke_embedding` | `plugin_or_run` | 是 | 否 | 调用文本向量嵌入模型 |
| `execution.invoke_rerank` | `plugin_or_run` | 是 | 否 | 调用重排（Rerank）模型 |
| `execution.vector_upsert` | `plugin` | 是 | 否 | 插入或更新向量数据 |
| `execution.vector_search` | `plugin` | 否 | 否 | 执行向量相似度检索 |
| `execution.vector_delete` | `plugin` | 是 | 否 | 删除特定向量数据 |
| `execution.vector_list` | `plugin` | 否 | 否 | 列出向量集合中的条目 |
| `execution.get_knowledge_file_stream` | `plugin` | 是 | 否 | 流式读取知识库文件内容 |
| `execution.list_parsers` | `plugin` | 否 | 否 | 列出可用的解析器 |
| `execution.invoke_parser` | `plugin` | 是 | 否 | 调用解析器插件解析文件 |
| `execution.list_knowledge_bases` | `plugin` | 否 | 否 | 列出插件可访问的知识库 |
| `execution.retrieve_knowledge` | `plugin_or_run` | 否 | 否 | 检索指定知识库中的切片内容 |
| `execution.list_pipeline_knowledge_bases` | `plugin` | 否 | 否 | 列出当前查询所属流水线绑定的知识库 |
| `execution.retrieve_knowledge_base` | `plugin_or_run` | 否 | 否 | 检索指定知识库切片（兼容入口） |
| `execution.get_prompt` | `run` | 否 | 否 | 获取当前运行预处理后的有效 Prompt |
| `execution.history_page` | `run` | 否 | 否 | 分页获取当前会话的历史交互记录 |
| `execution.history_search` | `run` | 否 | 否 | 在当前会话历史中搜索消息 |
| `execution.event_get` | `run` | 否 | 否 | 获取特定历史事件的详情 |
| `execution.event_page` | `run` | 否 | 否 | 分页读取当前会话的事件记录 |
| `execution.steering_pull` | `run` | 是 | 否 | 拉取用户在运行中追加的引导消息 |
| `execution.steering_ack` | `run` | 是 | 否 | 确认已领取的引导消息；校验当前或持久化 Run 授权 |
| `execution.state_get` | `run` | 否 | 否 | 获取 Agent 作用域状态值 |
| `execution.state_set` | `run` | 是 | 否 | 设置 Agent 作用域状态值 |
| `execution.state_delete` | `run` | 是 | 否 | 删除 Agent 状态值 |
| `execution.state_list` | `run` | 否 | 否 | 列出指定作用域下的运行状态键 |
| `execution.get_box_status` | `plugin_or_run` | 否 | 否 | 获取 Box 沙箱服务运行状态 |
| `execution.list_boxes` | `plugin_or_run` | 否 | 否 | 列出当前工作区中可用的 Box 沙箱 |
| `execution.acquire_box` | `plugin_or_run` | 是 | 否 | 申请或复用 Box 沙箱实例 |
| `execution.bind_box` | `run` | 是 | 否 | 将特定 Box 实例与当前运行绑定 |
| `execution.import_box_attachments` | `run` | 是 | 否 | 导入附件至绑定的 Box 沙箱 |
| `execution.read_input_attachment` | `run` | 否 | 否 | 按 ref 读取当前事件输入附件的字节 |
| `execution.export_box_files` | `run` | 是 | 否 | 导出 Box 沙箱生成的文件 |
| `execution.run_get` | `runner_admin` | 否 | 否 | 管理员查询指定 Agent Run 状态 |
| `execution.run_list` | `runner_admin` | 否 | 否 | 管理员分页查询历史 Agent Run 列表 |
| `execution.run_events_page` | `runner_admin` | 否 | 否 | 分页读取指定运行的事件 |
| `execution.run_cancel` | `runner_admin` | 是 | 否 | 取消指定运行（Runner 管理） |
| `execution.run_retry` | `runner_admin` | 是 | 否 | 按当前授权创建重试 Run，或重新入队外部任务 |
| `execution.run_resume` | `runner_admin` | 是 | 否 | 从已提交检查点创建恢复 Run |
| `execution.run_cancel_ack` | `runner_admin` | 是 | 否 | 确认运行取消后的资源清理 |
| `execution.run_append_result` | `runner_admin` | 是 | 否 | 向指定运行追加结果（Runner 管理） |
| `execution.run_finalize` | `runner_admin` | 是 | 否 | 结束指定运行并写入最终状态 |
| `execution.runner_list` | `runner_admin` | 否 | 否 | 列出已注册的 Runner |
| `execution.runtime_register` | `runner_admin` | 是 | 否 | 注册外部 Runtime |
| `execution.runtime_heartbeat` | `runner_admin` | 是 | 否 | 外部 Runtime 心跳上报 |
| `execution.runtime_list` | `runner_admin` | 否 | 否 | 列出已注册的外部 Runtime |
| `execution.runtime_reconcile` | `runner_admin` | 是 | 否 | 清理心跳超时的外部 Runtime |
| `execution.run_stats` | `runner_admin` | 否 | 否 | 查询工作区内 Agent Run 运行统计 |
| `execution.runtime_stats` | `runner_admin` | 否 | 否 | 获取外部 Runtime 统计信息 |
| `execution.runner_stats` | `runner_admin` | 否 | 否 | 获取 Runner 统计信息 |
| `execution.run_claim` | `runner_admin` | 是 | 否 | 为外部 Runtime 认领待执行的运行 |
| `execution.run_renew_claim` | `runner_admin` | 是 | 否 | 续期对运行的认领 |
| `execution.run_release_claim` | `runner_admin` | 是 | 否 | 释放对运行的认领 |
| `execution.list_application_operations` | `plugin_or_run` | 否 | 否 | 列出本次运行被授权的 ApplicationAPI 工作区操作及其 schema |
| `execution.call_application_operation` | `plugin_or_run` | 是 | 否 | 以处理器身份调用本次运行被授权的 ApplicationAPI 工作区操作 |

---

## 内部通信/传输动作审计说明

以下 6 个底层动作属于运行时传输控制与引导动作，不对外作为业务能力暴露在 `ExecutionAPI` 中：

1. `__ping`: WebSocket 心跳保活动作。
2. `__file_chunk`: 底层文件传输协议分块帧。
3. `__stream_ack`: 流式背压确认帧。
4. `__cancel_action`: 底层通信动作取消信号。
5. `initialize_plugin_settings`: 插件安装初始配置引导。
6. `get_plugin_settings`: 插件运行时启动配置拉取。
