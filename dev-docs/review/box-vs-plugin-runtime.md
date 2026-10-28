# Box Runtime vs Plugin Runtime: 连接架构对比

> 更新日期: 2026-06-02
> 状态更新: 自部署社区版已具备发布条件（box 可选、降级完善、无迁移欠债）；工具调用循环上限、配额遍历异步化、`host_path` 挂载白名单等已落地。剩余多租户 / 安全硬化项见 [SaaS 阻塞项清单](./box-issues.md)。
> 分支: `feat/sandbox` (LangBot + langbot-plugin-sdk)

---

## 1. 总体差异

| 维度 | Plugin Runtime | Box Runtime |
|------|---------------|-------------|
| **继承关系** | `PluginRuntimeConnector(ManagedRuntimeConnector)` | `BoxRuntimeConnector`（独立类） |
| **传输分支** | 3 条 (Docker/WS, Win32/subprocess+WS, Unix/stdio) | 3 条 (本地 stdio, Win32/subprocess+WS, 远程 WS) |
| **心跳** | 20s ping loop | 20s ping loop（`_heartbeat_loop`） |
| **重连** | WS 模式: sleep 3s → re-initialize | 由 BoxService `_reconnect_loop` 处理，指数退避 |
| **Handler 类型** | `RuntimeConnectionHandler` (1132 行, 25+ action) | 基础 `Handler` + `BoxServerHandler`（SDK 端 25 action） |
| **Client 抽象** | Handler 即 API | 独立 `ActionRPCBoxClient` 封装 Handler |
| **启用/禁用** | `is_enable_plugin` 开关 | 无开关（可用/不可用由初始化结果决定） |
| **初始化失败** | 异常上抛 | 静默降级 `_available=False` |
| **Shutdown** | 直接杀进程 | RPC SHUTDOWN → 清理容器 → 再杀进程 |

---

## 2. 传输决策

### Plugin: 3-路决策

```python
# pkg/plugin/connector.py:106-165
if get_platform() == 'docker' or use_websocket_to_connect_plugin_runtime():
    # Docker/WS → ws://langbot_plugin_runtime:5400/control/ws
elif get_platform() == 'win32':
    # Windows → 起子进程(无 pipe) + ws://localhost:5400/control/ws
else:
    # Unix/Mac → StdioClientController(python -m langbot_plugin.cli rt -s)
```

### Box: 3-路决策

```python
# pkg/box/connector.py
if self._uses_websocket():
    if platform.get_platform() == 'win32' and not self.configured_runtime_url:
        await self._start_subprocess_then_ws()  # subprocess + ws://localhost:5410/rpc/ws
    else:
        await self._connect_remote_ws()         # ws://{host}:5410/rpc/ws
else:
    await self._start_local_stdio()             # StdioClientController
```

> 历史：2026-04-16 版本本文档曾把 Box 描述为 2 路决策（缺 Windows 分支）。现已对齐 Plugin 的 3 路设计。

### 决策矩阵

| 环境 | Plugin | Box |
|------|--------|-----|
| Docker | WS → `:5400` | WS → `:5410/rpc/ws` |
| `--standalone-box` | N/A | WS → `localhost:5410/rpc/ws` |
| Windows 非 Docker | subprocess + WS (`:5400`) | subprocess + WS (`localhost:5410/rpc/ws`) |
| Unix/Mac 非 Docker | stdio | stdio |
| 手动配置 URL | 通过配置项 | WS → 用户配置的 URL |

---

## 3. 连接建立

### 同步模式差异

**Plugin**: `new_connection_callback` 内直接 ping + await handler_task，`initialize()` 通过 `create_task()` 异步启动，不阻塞等待连接。

**Box**: 使用 `asyncio.Event` + `wait_for(timeout=30s)` 模式，`initialize()` 同步等待连接成功或超时。

### Box stdio 路径

```
connector._start_local_stdio()
  ├─ connected = asyncio.Event()
  ├─ ctrl = StdioClientController(python, ['-m', 'langbot_plugin.cli.__init__', 'box', '-s', '--ws-control-port', N])
  ├─ _ctrl_task = create_task(ctrl.run(callback))
  │    callback:
  │      handler = Handler(connection)          ← 基础 Handler, 无 disconnect_callback
  │      client.set_handler(handler)
  │      _handler_task = create_task(handler.run())
  │      call_action(PING, {})                  ← 握手, timeout=15s
  │      connected.set()                        ← 通知外层
  │      await _handler_task                    ← 阻塞直到断开
  └─ await wait_for(connected.wait(), 30s)      ← 同步等待
```

### Plugin stdio 路径

```
connector.initialize()
  ├─ ctrl = StdioClientController(python, ['-m', 'langbot_plugin.cli', 'rt', '-s'])
  ├─ task = ctrl.run(callback)
  │    callback:
  │      disconnect_callback:
  │        [WS] → runtime_disconnect_callback → 重连
  │        [stdio] → 仅日志, 不重连
  │      handler = RuntimeConnectionHandler(conn, disconnect_cb, ap)
  │      create_task(handler.run())
  │      handler.ping()                         ← 握手, timeout=10s
  │      await handler_task                     ← 阻塞直到断开
  ├─ create_task(heartbeat_loop())              ← 20s ping loop
  └─ create_task(task)                          ← 不等待连接
```

---

## 4. 心跳与重连

### 心跳

| 维度 | Plugin | Box |
|------|--------|-----|
| 有心跳? | 是 | 是（`connector.py` `_heartbeat_loop`） |
| 间隔 | 20s | 20s |
| 失败处理 | 仅 DEBUG 日志，不触发重连 | 仅 DEBUG 日志，依赖 connection close 触发重连 |
| 生命周期 | 整个应用生命周期 | 连接建立后启动；`dispose()` 时 cancel |

### 重连

| 维度 | Plugin | Box |
|------|--------|-----|
| Docker/WS 断开 | `runtime_disconnect_callback` → sleep 3s → re-initialize | `runtime_disconnect_callback` → `BoxService._reconnect_loop()`（指数退避） |
| WS 连接失败 | 同上 | 同上；初次失败时 `_available=False`，重连成功后恢复 |
| stdio 断开 | 仅日志，不重连 | 接同样回调；stdio 重连需重新 fork 子进程 |
| 重连退避 | 固定 3s，无 backoff | 指数退避 |

> 历史：2026-04-16 版本本文档曾把心跳与重连标记为 Box 缺失。这两项已在 commit `2dfd9d5d` / `c6882cf` / `5029d9c` 等修复（详见 [box-issues.md 已解决](./box-issues.md)）。

---

## 5. 共享 IO 层

两者复用同一套 SDK IO 基础设施：

```
Handler ← ABC                              (runtime/io/handler.py)
  ├── RuntimeConnectionHandler              (Plugin 用, LangBot 侧)
  ├── ControlConnectionHandler              (Plugin 用, SDK 侧)
  ├── BoxServerHandler                      (Box 用, SDK 侧)
  └── 匿名 Handler 实例                     (Box 用, LangBot 侧)

Connection ← ABC
  ├── StdioConnection    (stdio: 16KB chunks, 应用层分帧协议)
  └── WebSocketConnection (WS: 64KB chunks, 原生 WS 分帧)

Controller ← ABC
  ├── StdioClientController    (fork 子进程, pipe stdin/stdout)
  ├── StdioServerController    (接管当前进程 stdin/stdout)
  ├── WebSocketClientController (连接 WS 服务端)
  └── WebSocketServerController (监听 WS 端口)
```

共享的核心机制：
- `call_action()` / `call_action_generator()` — RPC 调用/流式调用
- `ActionRequest` / `ActionResponse` — 请求/响应协议
- `seq_id` 关联 — 并发请求复用单连接
- `CommonAction.PING` — 两者都用于初始握手
- 文件传输 (`send_file`) — Plugin 用，Box 不用

---

## 6. 端口方案

| 服务 | Plugin | Box |
|------|--------|-----|
| Action RPC (stdio) | stdin/stdout | stdin/stdout |
| Action RPC (WS) | `:5400` | `:5410/rpc/ws` |
| 辅助服务 | debug WS `:5401` | managed process WS relay `:5410/v1/sessions/{id}/managed-process/ws` |

**Box 特点**: 单端口 aiohttp 服务（默认 5410），通过路径区分 Action RPC 和 managed process relay。即使在 stdio 模式，也在 `:5410` 启动 aiohttp 用于 managed process attach。Plugin 在 stdio 模式不开额外端口。

---

## 7. 销毁对比

### Plugin

```python
dispose():
  if stdio: ctrl.process.terminate()
  _dispose_subprocess()         # Windows 子进程
  heartbeat_task.cancel()
```

### Box

```python
connector.dispose():
  _handler_task.cancel()
  _ctrl_task.cancel()
  _subprocess.terminate()

service.dispose():
  connector.dispose()
  loop.create_task(client.shutdown())   # RPC SHUTDOWN → 清理所有容器
```

Box 的 RPC SHUTDOWN 确保容器被正确停止，不会成为孤儿。Plugin 直接杀进程。

---

## 8. 改进建议

### P0

1. **两者都加 WS 认证**: 至少 token 认证（INIT 时下发，连接时校验）

### P1

2. **考虑 Box 继承 ManagedRuntimeConnector**: 复用 `_start_runtime_subprocess` / `_wait_until_ready` / `_dispose_subprocess`，减少重复代码
3. **Plugin 重连加退避**: 固定 3s 无 backoff 可能造成日志洪水，建议向 Box 的指数退避看齐
4. **统一连接管理模式**: Event-based (Box) vs direct-await (Plugin)，考虑收敛为一种

### 已完成（自上一轮）

- ~~Box 加重连~~（commit `2dfd9d5d`）
- ~~Box 加心跳~~（20s loop 与 Plugin 一致）
- ~~Box 加 Windows 支持~~（commit `120817a` / `fafb7a4`）
