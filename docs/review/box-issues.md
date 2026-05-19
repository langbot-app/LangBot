# Box 系统架构问题清单

> 更新日期: 2026-05-19
> 分支: `feat/sandbox` (LangBot + langbot-plugin-sdk)

---

## 已解决（自上一轮 review）

下列原 P0/P1 项在最新分支已被修复，仅作记录：

| 原编号 | 问题 | 处理 commit / 说明 |
|--------|------|---------------------|
| #3 | Box 无重连机制 | `_make_connection_callback` 已接入 `runtime_disconnect_callback`；`BoxService._reconnect_loop()` 实现指数退避重连 (`2dfd9d5d`、`c6882cf`) |
| #4 | Box 无心跳 | `BoxRuntimeConnector._heartbeat_loop()`，间隔 20s（沿用 Plugin 模式） |
| #10 | Windows 兼容 | connector 增加 Windows 分支 (subprocess + WS)，backend 适配 Windows Docker (`120817a`、`fafb7a4`) |
| #12 | nsjail image 字段冲突 | `_assert_session_compatible()` 在不支持自定义镜像的 backend 跳过 image 字段 |
| #22 | 前端无 Box UI | 监控页 `SystemStatusCards.tsx` 已接入 `/api/v1/box/status`；Skill 管理页接入了全部 skill API（sessions/errors API 仍未接入） |

---

## P0 — 合并前建议修复

### 1. policy.py 是死代码

- **位置**: `pkg/box/policy.py` (98 行)
- **现状**: `SandboxPolicy`、`ToolPolicy`、`ElevatedPolicy` 三个类已定义，但全项目无任何导入或调用
- **影响**: 三层安全策略（沙箱模式 / 工具白名单 / 权限提升）完全未生效。当前实际策略仍是"Box 可用就暴露全部 6 个 native tool，不可用就全部隐藏"
- **建议**: 要么删除死代码，要么接入 NativeToolLoader 的工具暴露 / exec 调用链。如果短期不会接入，至少在 `pkg/box/__init__.py` 显式标注其状态

### 2. WebSocket relay 无认证

- **位置**: SDK `box/server.py` — Action RPC 路径 `/rpc/ws` 与 managed-process relay `/v1/sessions/{id}/managed-process/{pid}/ws`
- **现状**: 任何能访问 5410 端口的客户端都可以连接，attach 任意 session 的 managed process stdin/stdout，或直接发起 EXEC
- **影响**: 容器化 / Docker compose 部署中，若 Box runtime 端口外暴露，网络内的攻击者可直接控制沙箱
- **建议**: 至少加 token 认证（INIT 时下发，WS 连接 query string 或 header 校验）；多 process 后 attach 面更大，更不能裸奔

### 3. security.py 根路径未拦截

- **位置**: SDK `box/security.py` `BLOCKED_HOST_PATHS_POSIX`
- **现状**: 黑名单中没有 `/`，`host_path="/"` 可通过校验并挂载整个主机文件系统；用户 home 目录、`/var` 等也未拦截
- **建议**: 将 `/` 加入黑名单，或改用白名单策略与 LangBot 侧 `allowed_mount_roots` 二次拦截

### 4. INIT 与 backend 初始化的竞态

- **位置**: SDK `box/runtime.py` `init()` 在握手后才下发实际配置；`backend` 在 INIT 之前可能已经按默认值实例化
- **现状**: commit `5029d9c` 修复了 "init config before backend reuse" 的部分场景，但 backend 重新实例化时若有正在执行的 session，可能命中旧 backend
- **建议**: 整理 init/handshake 顺序——要么 INIT 完成前不接受任何业务 action，要么允许 backend 配置变更时显式清理现有 session

---

## P1 — 合并后优先跟进

### 5. Session 数量无上限

- **位置**: SDK `box/runtime.py` `_get_or_create_session()`
- **现状**: `_sessions` dict 无容量限制，恶意或异常调用可创建无限 session
- **建议**: 加 `max_sessions` 配置项，达到上限时拒绝新建或按 LRU 清理

### 6. Quota 检查存在 TOCTOU

- **位置**: `pkg/box/service.py` `_enforce_workspace_quota()`
- **现状**: 应用层先读磁盘大小再执行命令，两步之间有竞态窗口
- **建议**: 短期用 Docker `--storage-opt size=` 做内核级限制；长期用 Redis 原子计数器做预留式配额

### 7. 全局锁持有期间执行慢操作

- **位置**: SDK `box/runtime.py` `_get_or_create_session()` — `self._lock` 下调用 `backend.start_session()` (即 `docker run` / `nsjail` 进程启动 / E2B `Sandbox.create`)
- **影响**: `docker run` 可能耗时数秒（含镜像拉取）、E2B 冷启动通常 > 1s，期间阻塞所有并发请求
- **建议**: 在 `_lock` 下仅做状态检查和 session 注册，容器创建在锁外执行

### 8. Session 清理是机会性的

- **位置**: SDK `box/runtime.py` `_reap_expired_sessions_locked()` — 仅在 `_get_or_create_session()` 时调用
- **影响**: 如果长时间无新 session 请求，过期 session（含容器）不会被清理
- **建议**: 加一个独立的 `asyncio.create_task` 定时清理（如每 60s 一次）

### 9. server.py 直接访问 runtime 私有字段

- **位置**: SDK `box/server.py` — managed-process WS handler 直接读 `runtime._sessions`
- **影响**: 绕过锁和封装，在并发场景下可能读到不一致状态
- **建议**: 在 BoxRuntime 上增加公共方法（如 `get_session_managed_process(session_id, process_id)`）

### 10. workspace quota 检查阻塞事件循环

- **位置**: `pkg/box/service.py` `_get_workspace_size_bytes()` — 使用同步 `os.scandir` 递归遍历
- **影响**: 大工作区可能阻塞 asyncio event loop
- **建议**: 用 `asyncio.to_thread()` 包装，或用 `aiofiles` 异步扫描

### 11. extra_mounts 一旦容器创建即固定

- **位置**: SDK `box/runtime.py` 的兼容性检查；`pkg/box/service.py:build_skill_extra_mounts()`
- **现状**: Skill 挂载在容器创建时一次性写入；同一 session 后续 pipeline 切换 skill 列表时，新挂载不会生效（除非销毁重建）
- **影响**: 用户长时间共享 session 的场景下，新激活的 skill 可能挂不上
- **建议**: 要么在创建时把 pipeline 绑定的所有 skill 都挂上（实际现状）+ 写入文档；要么变更挂载时强制销毁 session 重建（已被 commit `5029d9c` 部分覆盖，需校验）

---

## P2 — 后续迭代

### 12. 重复的 `_is_path_under` 函数

- **位置**: `pkg/box/service.py` 行 30 附近 — 同名函数定义两次
- **建议**: 删除重复定义

### 13. localagent.py 工具循环无迭代上限

- **位置**: `pkg/provider/runners/localagent.py` `while pending_tool_calls` 循环
- **影响**: 恶意或混乱的 LLM 可无限产生 tool call，消耗资源
- **建议**: 加 `max_tool_iterations` 配置项（如默认 50 次）

### 14. localagent.py 中的死代码

- **位置**: `pkg/provider/runners/localagent.py:29-35` 附近 — 旧命名 `SANDBOX_EXEC_TOOL_NAME` 和 `SANDBOX_EXEC_SYSTEM_GUIDANCE`
- **现状**: 旧命名方案的遗留常量，从未被引用（实际使用 `EXEC_TOOL_NAME` from native.py）
- **建议**: 删除

### 15. @loader_class 装饰器未使用

- **位置**: `pkg/provider/tools/loader.py` — `preregistered_loaders` 列表和 `@loader_class` 装饰器
- **现状**: 各 loader 的 `@loader_class` 多数被注释掉，ToolManager 手动实例化所有 loader
- **建议**: 要么启用装饰器自动注册，要么删除未用的机制

### 16. 工具名冲突风险

- **位置**: `pkg/provider/tools/toolmgr.py` `execute_func_call()` — 按优先级 native → plugin → mcp → skill → skill_authoring 分发
- **影响**: 如果 plugin 或 MCP 有名为 `exec`/`read`/`write`/`edit`/`glob`/`grep`/`activate` 的工具，会被前序 loader 静默遮蔽
- **建议**: 加命名空间前缀或冲突检测告警

### 17. client.py 反序列化不一致

- **位置**: SDK `box/client.py` — `execute()` 与其他方法对返回值的反序列化方式不统一（部分手动构造 model，部分用 `model_validate`）
- **建议**: 统一使用 `model_validate`

### 18. 错误类型还原基于字符串前缀匹配

- **位置**: SDK `box/client.py` `_translate_action_error()`
- **影响**: 如果 server 端错误消息格式变化，client 会回退到通用 `BoxError`，丢失类型信息
- **建议**: 在 ActionResponse 中增加结构化的错误类型字段（如 `error_code` 枚举）

### 19. 前端只用到了 status

- **位置**: `web/src/app/home/monitoring/...` 已接入 `/api/v1/box/status`
- **现状**: `/api/v1/box/sessions` 与 `/api/v1/box/errors` 后端可用、前端未消费
- **建议**: 在监控页或独立 Box 详情页展示活跃 session 列表与最近错误，提升运维体感

### 20. skill_store 测试覆盖偏薄

- **位置**: SDK `tests/box/test_skill_store.py` 仅 88 行
- **现状**: 相对 `skill_store.py` 的 647 行实现，单测覆盖度不够；GitHub 安装路径、`source_subdir` / `target_suffix` 组合、损坏 zip 的错误处理等场景未覆盖
- **建议**: 至少补到核心 path 覆盖（preview/install/list/file CRUD 各 2~3 个 case）

### 21. 集成测试未进 CI

- **位置**: LangBot `tests/integration_tests/box/test_box_integration.py`、`test_box_mcp_integration.py`，SDK 端的 E2B 真机测试
- **现状**: 容器实际执行、E2B 真实 sandbox、Managed process WS attach 均仅本地能跑
- **建议**: 加一个可选的 Docker-in-Docker CI stage，或在合并前手动跑 checklist
