# Box Runtime vs Plugin Runtime: 连接架构对比

> 更新日期: 2026-04-16
> 分支: `feat/sandbox` (LangBot + langbot-plugin-sdk)

---

## 1. 总体差异

| 维度 | Plugin Runtime | Box Runtime |
|------|---------------|-------------|
| **继承关系** | `PluginRuntimeConnector(ManagedRuntimeConnector)` | `BoxRuntimeConnector`（独立类） |
| **传输分支** | 3 条 (Docker/WS, Win32/subprocess+WS, Unix/stdio) | 2 条 (本地 stdio, 远程 WS) |
| **心跳** | 20s ping loop | **无** |
| **重连** | WS 模式: sleep 3s → re-initialize | **无** |
| **Handler 类型** | `RuntimeConnectionHandler` (1132 行, 25+ action) | 基础 `Handler` (311 行, 0 自定义 action) |
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

### Box: 2-路决策

```python
# pkg/box/connector.py:56-60
if self.manages_local_runtime:   # = not configured_runtime_url
    await self._start_local_stdio()    # StdioClientController
else:
    await self._connect_remote_ws()    # ws://{host}:{port+1}
```

### 决策矩阵

| 环境 | Plugin | Box |
|------|--------|-----|
| Docker | WS → `:5400` | WS → `:{port+1}` (5411) |
| Windows 非 Docker | subprocess + WS (`:5400`) | **stdio (可能失败!)** |
| Unix/Mac 非 Docker | stdio | stdio |
| 手动配置 URL | 通过配置项 | WS → 用户配置的 URL |

**Box 的 Windows 问题**: 无 Win32 分支，asyncio ProactorEventLoop 不支持 subprocess stdio pipe。Plugin 为此专门做了处理。

---

## 3. 连接建立

### 同步模式差异

**Plugin**: `new_connection_callback` 内直接 ping + await handler_task，`initialize()` 通过 `create_task()` 异步启动，不阻塞等待连接。

**Box**: 使用 `asyncio.Event` + `wait_for(timeout=30s)` 模式，`initialize()` 同步等待连接成功或超时。

### Box stdio 路径

```
connector._start_local_stdio()
  ├─ connected = asyncio.Event()
  ├─ ctrl = StdioClientController(python, ['-m', 'langbot_plugin.box.server', '--port', N])
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
| 有心跳? | 是 (`connector.py:69-76`) | **否** |
| 间隔 | 20s | N/A |
| 失败处理 | 仅 DEBUG 日志，不触发重连 | N/A |
| 生命周期 | 整个应用生命周期，跨越重连 | N/A |

### 重连

| 维度 | Plugin | Box |
|------|--------|-----|
| Docker/WS 断开 | `runtime_disconnect_callback` → sleep 3s → re-initialize | Handler loop 退出，**永久不可用** |
| WS 连接失败 | 同上 | 存储错误 → `initialize()` 抛异常 → `_available=False` |
| stdio 断开 | 仅日志，不重连 | Handler loop 退出，永久不可用 |
| 重连退避 | 固定 3s，无 backoff | N/A |

**Box 断开后的效果链**:
1. `handler.run()` 捕获 `ConnectionClosedError`
2. `_disconnect_callback is None` → break
3. `_handler_task` 完成 → `_make_connection_callback` 返回
4. 后续 `client._call()` → `BoxRuntimeUnavailableError`
5. Box 功能永久不可用

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
| Action RPC (WS) | `:5400` | `:{port+1}` (默认 5411) |
| 辅助服务 | debug WS `:5401` | managed process WS relay `:5410` |

**Box 特点**: 即使在 stdio 模式，也额外在 `:5410` 启动 aiohttp WS 服务用于 managed process attach。Plugin 在 stdio 模式不开额外端口。

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

1. **Box 加重连**: 在 `_make_connection_callback` 中设置 `disconnect_callback`，WS 模式 sleep 3s → re-initialize
2. **Box 加心跳**: 30s 间隔 ping loop，参考 `PluginRuntimeConnector.heartbeat_loop()`

### P1

3. **Box 加 Windows 支持**: 像 Plugin 一样加 Win32 分支 (subprocess + WS)
4. **考虑 Box 继承 ManagedRuntimeConnector**: 复用 `_start_runtime_subprocess`/`_wait_until_ready`/`_dispose_subprocess`
5. **两者都加 WS 认证**: 至少 token 认证

### P2

6. **Plugin 重连加退避**: 固定 3s 无 backoff 可能造成日志洪水，建议指数退避
7. **统一连接管理模式**: Event-based (Box) vs direct-await (Plugin)，考虑收敛为一种
