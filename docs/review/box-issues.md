# Box 系统架构问题清单

> 更新日期: 2026-04-16
> 分支: `feat/sandbox` (LangBot + langbot-plugin-sdk)

---

## P0 — 合并前建议修复

### 1. policy.py 是死代码

- **位置**: `pkg/box/policy.py` (98 行)
- **现状**: `SandboxPolicy`、`ToolPolicy`、`ElevatedPolicy` 三个类已定义，但全项目无任何导入或调用
- **影响**: 三层安全策略（sandbox 模式/工具白名单/权限提升）完全未生效，当前的实际策略是 "Box 可用就暴露全部 4 个 native tool，不可用就全部隐藏"
- **建议**: 要么删除死代码，要么接入 NativeToolLoader 调用链

### 2. WebSocket relay 无认证

- **位置**: SDK `box/server.py` `create_ws_relay_app()` + `handle_managed_process_ws()`
- **现状**: 任何能访问 5410 端口的客户端都可以 attach managed process 的 stdin/stdout
- **影响**: 网络内的攻击者可直接向 MCP Server 发送任意指令
- **建议**: 至少加 token 认证（从 RPC 通道获取临时 token，WS 连接时验证）

### 3. Box 无重连机制

- **位置**: `pkg/box/connector.py` `_make_connection_callback()` — Handler 创建时未设置 `disconnect_callback`
- **现状**: 连接断开后 Handler loop 直接退出，Box 功能永久不可用直到应用重启
- **对比**: Plugin 在 WS 模式下有 `sleep(3) -> re-initialize` 自动重连
- **建议**: 参考 Plugin 的 `runtime_disconnect_callback`，至少 WS 模式加重连

### 4. Box 无心跳

- **位置**: `pkg/box/connector.py` — 无 `heartbeat_loop()` 方法
- **现状**: 初始握手后无定期探活，连接断开只能在下次 RPC 调用时被动发现
- **对比**: Plugin 有 20s 间隔的 ping loop
- **建议**: 加 30s 间隔心跳，失败时触发重连

### 5. security.py 根路径未拦截

- **位置**: SDK `box/security.py` `BLOCKED_HOST_PATHS_POSIX`
- **现状**: 黑名单中没有 `/`，`host_path="/"` 可通过校验并挂载整个主机文件系统
- **建议**: 将 `/` 加入黑名单，或改用白名单策略

---

## P1 — 合并后优先跟进

### 6. Session 数量无上限

- **位置**: SDK `box/runtime.py` `_get_or_create_session()`
- **现状**: `_sessions` dict 无容量限制，恶意或异常调用可创建无限 session
- **建议**: 加 `max_sessions` 配置项，达到上限时拒绝新建或清理最老 session

### 7. Quota 检查存在 TOCTOU

- **位置**: `pkg/box/service.py` `_enforce_workspace_quota()`
- **现状**: 应用层先读磁盘大小再执行命令，两步之间有竞态窗口
- **建议**: 短期用 Docker `--storage-opt size=` 做内核级限制；长期用 Redis 原子计数器做预留式配额

### 8. 全局锁持有期间执行慢操作

- **位置**: SDK `box/runtime.py` `_get_or_create_session()` — `self._lock` 下调用 `backend.start_session()` (即 `docker run`)
- **影响**: `docker run` 可能耗时数秒（含镜像拉取），期间阻塞所有并发请求
- **建议**: 在 `_lock` 下仅做状态检查和 session 注册，容器创建在锁外执行

### 9. Session 清理是机会性的

- **位置**: SDK `box/runtime.py` `_reap_expired_sessions_locked()` — 仅在 `_get_or_create_session()` 时调用
- **影响**: 如果长时间无新 session 请求，过期 session（含容器）不会被清理
- **建议**: 加一个独立的 `asyncio.create_task` 定时清理（如每 60s 一次）

### 10. 缺少 Windows 兼容处理

- **位置**: `pkg/box/connector.py` — 无 `win32` 分支
- **现状**: Windows 的 asyncio ProactorEventLoop 不支持 subprocess stdio pipe
- **对比**: Plugin 专门加了 Win32 分支（subprocess + WS 通信）
- **建议**: 加 Windows 分支，或在文档/代码中明确声明不支持

### 11. server.py 直接访问 runtime 私有字段

- **位置**: SDK `box/server.py:139` — `handle_managed_process_ws` 直接读 `runtime._sessions`
- **影响**: 绕过锁和封装，在并发场景下可能读到不一致状态
- **建议**: 在 BoxRuntime 上增加公共方法（如 `get_session_managed_process(session_id)`）

### 12. nsjail image 字段与兼容性检查冲突

- **位置**: SDK `box/nsjail_backend.py:148` 设 `image='host'`；`runtime.py:284` 检查 `image` 字段一致性
- **影响**: 用 nsjail 后端时，如果调用方 BoxSpec 指定了 `image='python:3.11-slim'`（默认值），存储的 `image='host'` 与后续请求的默认值不匹配，永远冲突
- **建议**: nsjail 后端的兼容性检查应跳过 `image` 字段，或统一忽略 image 当 backend 不支持自定义镜像时

---

## P2 — 后续迭代

### 13. 重复的 `_is_path_under` 函数

- **位置**: `pkg/box/service.py` 行 30 和行 36 — 同名函数定义两次
- **建议**: 删除重复定义

### 14. Skill 激活协议无递归保护

- **位置**: `pkg/skill/activation.py`
- **影响**: LLM 在第二次调用中可再次输出 `[ACTIVATE_SKILL:]` 标记，触发无限循环
- **建议**: 加 `max_activation_depth` 检查

### 15. localagent.py 工具循环无迭代上限

- **位置**: `pkg/provider/runners/localagent.py` `while pending_tool_calls` 循环
- **影响**: 恶意或混乱的 LLM 可无限产生 tool call，消耗资源
- **建议**: 加 `max_tool_iterations` 配置项（如默认 50 次）

### 16. localagent.py 中的死代码

- **位置**: `pkg/provider/runners/localagent.py:29-35` — `SANDBOX_EXEC_TOOL_NAME` 和 `SANDBOX_EXEC_SYSTEM_GUIDANCE`
- **现状**: 旧命名方案的遗留常量，从未被引用（实际使用 `EXEC_TOOL_NAME` from native.py）
- **建议**: 删除

### 17. @loader_class 装饰器未使用

- **位置**: `pkg/provider/tools/loader.py` — `preregistered_loaders` 列表和 `@loader_class` 装饰器
- **现状**: MCPLoader 和 PluginToolLoader 的 `@loader_class` 被注释掉，ToolManager 手动实例化所有 loader
- **建议**: 要么启用装饰器自动注册，要么删除未用的机制

### 18. 工具名冲突风险

- **位置**: `pkg/provider/tools/toolmgr.py` `execute_func_call()` — 按优先级 native -> plugin -> mcp -> skill_authoring 分发
- **影响**: 如果 plugin 或 MCP 有名为 `exec`/`read`/`write`/`edit` 的工具，会被 native loader 静默遮蔽
- **建议**: 加命名空间前缀或冲突检测告警

### 19. workspace quota 检查阻塞事件循环

- **位置**: `pkg/box/service.py` `_get_workspace_size_bytes()` — 使用同步 `os.scandir` 递归遍历
- **影响**: 大工作区可能阻塞 asyncio event loop
- **建议**: 用 `asyncio.to_thread()` 包装，或用 `aiofiles` 异步扫描

### 20. client.py 反序列化不一致

- **位置**: SDK `box/client.py:118-126` — `execute()` 手动逐字段构建 `BoxExecutionResult`
- **对比**: `start_managed_process()` 使用 `model_validate(data)` 自动反序列化
- **建议**: 统一使用 `model_validate`

### 21. 错误类型还原基于字符串前缀匹配

- **位置**: SDK `box/client.py:59-82` `_translate_action_error()`
- **影响**: 如果 server 端错误消息格式变化，client 会回退到通用 `BoxError`
- **建议**: 在 ActionResponse 中增加结构化的错误类型字段

### 22. 前端无 Box 相关 UI

- **位置**: `web/src/` — 无任何 Box 组件、类型定义或 API 调用
- **现状**: 后端有 3 个 REST API（`/api/v1/box/{status,sessions,errors}`）但前端未接入
- **建议**: 后续迭代加 Box 状态面板（至少展示可用性、活跃 session、最近错误）
