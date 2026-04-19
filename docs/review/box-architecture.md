# Box 系统架构深度分析

> 更新日期: 2026-04-16
> 分支: `feat/sandbox` (LangBot + langbot-plugin-sdk)
> 相关文档: [问题清单](./box-issues.md) | [Runtime 对比](./box-vs-plugin-runtime.md) | [测试覆盖](./box-test-coverage.md) | [toB 分析](./box-tob-analysis.md)

---

## 1. 全局架构

```
┌──────────────────────────────────────────────────────────────┐
│                       LangBot 主进程                          │
│                                                               │
│  LocalAgentRunner ──> ToolManager ──> NativeToolLoader        │
│       │                    │              │                    │
│       │                    │          exec/read/write/edit     │
│       │                    │              │                    │
│       │                    ├──> MCPLoader ──> BoxStdioSession  │
│       │                    │                                   │
│       │                    └──> PluginToolLoader               │
│       │                                                       │
│  BoxService (门面)                                             │
│    ├─ Profile 管理 (locked 字段)                               │
│    ├─ Host mount 校验 (allowed_roots)                          │
│    ├─ Workspace quota 检查                                     │
│    ├─ 输出截断 (head+tail)                                     │
│    └─ BoxRuntimeConnector                                      │
│         └─ ActionRPCBoxClient                                  │
│              │  Action RPC (stdio 或 WebSocket)                │
└──────────────┼─────────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────┐
│              Box Runtime 进程 (SDK 侧)                        │
│                                                               │
│  BoxServerHandler (Action RPC 处理)                            │
│       │                                                       │
│  BoxRuntime (session 管理/进程生命周期)                         │
│       │                                                       │
│  Backend (启动时选择一个):                                      │
│    DockerBackend ─┬── CLISandboxBackend                       │
│    NsjailBackend ─┘                                           │
│                                                               │
│  aiohttp WS Relay (:5410)                                     │
│    /v1/sessions/{id}/managed-process/ws                       │
│    (managed process stdin/stdout 双向中继)                      │
└──────────────────────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────┐
│  容器/沙箱 (Docker container 或 nsjail sandbox)               │
│  - 隔离文件系统、网络、PID 命名空间                              │
│  - 资源限制 (CPU, 内存, PID 数)                                │
│  - exec: 用户命令在此执行                                      │
│  - managed process: MCP Server 等长驻进程在此运行               │
└──────────────────────────────────────────────────────────────┘
```

**核心设计原则**: Box Runtime 作为独立进程运行，通过 Action RPC 与 LangBot 主进程通信。两者复用 SDK 的 IO 层（Handler → Connection → Controller）。

---

## 2. LangBot 侧模块

### 2.1 BoxService (`pkg/box/service.py`, 514 行)

应用层门面，协调 Profile、安全校验、配额、连接：

```
BoxService
  ├─ initialize()
  │    ├─ _ensure_default_host_workspace()   创建默认工作目录
  │    └─ connector.initialize()             连接 Box Runtime
  │
  ├─ execute_tool(parameters, query)         Agent 调用 exec 时的入口
  │    ├─ _build_spec(parameters, query)     合并 Profile + 参数 + locked 覆盖
  │    ├─ _validate_host_mount(spec)         校验 host_path 在 allowed_roots 内
  │    ├─ _enforce_workspace_quota(spec)     前置磁盘配额检查
  │    ├─ client.execute(spec)               RPC 调用
  │    ├─ _enforce_workspace_quota(spec)     后置检查（超额则销毁 session）
  │    └─ _truncate_output(result)           截断 stdout/stderr
  │
  ├─ execute_spec_payload(payload)           内部调用（BoxWorkspaceSession 用）
  ├─ create_session(payload)                 显式创建 session
  ├─ start_managed_process(session_id, payload)  启动长驻进程
  ├─ get_managed_process(session_id)         查询进程状态
  ├─ get_managed_process_websocket_url(sid)  获取 WS attach URL
  ├─ get_system_guidance()                   返回 LLM 系统提示词
  └─ get_status() / get_recent_errors()      可观测性
```

**Profile 系统**: 4 个内置 Profile（`default`/`offline_readonly`/`network_basic`/`network_extended`），`locked` frozenset 字段不可被 LLM 覆盖。参数合并顺序：Profile defaults → LLM 请求参数 → locked 强制值。

**输出截断**: 默认 4000 字符上限，保留前 60% + 后 40%，中间插入 `[...truncated...]`。

### 2.2 BoxRuntimeConnector (`pkg/box/connector.py`, 160 行)

管理与 Box Runtime 的通信连接：

- **本地 stdio**: Unix/macOS 无特殊配置时，fork `python -m langbot_plugin.box.server --port {port}` 子进程
- **远程 WebSocket**: Docker / `--standalone-box` / 显式 `runtime_url` 时，连接 `ws://{host}:{port}/rpc/ws`（同一端口，路径区分）
- **Windows**: subprocess + WebSocket（Windows 不支持 async stdio pipe）
- **同步等待**: 使用 `asyncio.Event` + `wait_for(timeout=30s)` 模式确认连接

### 2.3 BoxWorkspaceSession (`pkg/box/workspace.py`, 404 行)

在 BoxService 上的高级抽象，用于 Skill 和 MCP 场景：

- **路径重写**: `host_path → /workspace` 映射
- **Venv 重写**: `.venv/bin/python → python`
- **Python 环境自举**: 检测 `requirements.txt`/`pyproject.toml`，生成 shell 脚本自动创建 venv 并安装依赖
- **Session 作用域**: 每个 Skill/MCP Server 有独立 session_id

### 2.4 policy.py (`pkg/box/policy.py`, 98 行) — 死代码

三层安全策略设计（SandboxPolicy/ToolPolicy/ElevatedPolicy），但**全项目无任何调用**。详见 [问题清单 #1](./box-issues.md)。

---

## 3. SDK 侧模块

### 3.1 BoxRuntime (`box/runtime.py`, 388 行)

核心编排器，管理 session 生命周期：

```
Session 生命周期:

  Client EXEC/CREATE_SESSION
       │
       ▼
  _get_or_create_session(spec)
    ├─ _reap_expired_sessions_locked()   清理 TTL 过期 session
    ├─ 已存在? → _assert_session_compatible() → 复用
    └─ 新建? → backend.start_session(spec) → 创建容器
       │
       ▼
  execute(spec)
    ├─ 获取 session lock (每 session 独立)
    ├─ backend.exec(session, spec)       在容器中执行命令
    ├─ 更新 last_used_at
    └─ 超时? → 销毁 session
       │
       ▼
  Session 保持存活直到:
    ├─ TTL 过期 (默认 300s，下次操作时清理)
    ├─ 执行超时 (自动销毁)
    ├─ 客户端 DELETE_SESSION
    └─ SHUTDOWN
```

**关键设计**:
- 每 session 有独立 `asyncio.Lock`，同一 session 内的命令串行执行
- 全局 `_lock` 保护 `_sessions` dict 的读写
- 兼容性检查：比较 10 个字段（network/image/host_path/mount_path/cpus/memory_mb/pids_limit/read_only_rootfs/host_path_mode/workspace_quota_mb）

### 3.2 Backend 系统

#### CLISandboxBackend (`box/backend.py`)

Docker 的基类：

```
start_session(spec):
  1. validate_sandbox_security(spec)     安全校验
  2. docker run -d --rm --name <name>
     --network none (可选)
     --cpus/--memory/--pids-limit        资源限制
     --read-only + --tmpfs /tmp          只读根文件系统
     -v <host>:<mount>:<mode>            工作区挂载
     <image> sh -lc 'while true; do sleep 3600; done'   保活进程
  3. 返回 BoxSessionInfo

exec(session, spec):
  docker exec -e KEY=VAL <container>
    sh -lc 'mkdir -p <workdir> && cd <workdir> && <cmd>'

start_managed_process(session, spec):
  docker exec -i <container>
    sh -lc 'mkdir -p <cwd> && cd <cwd> && exec <command> <args>'
  返回 asyncio.subprocess.Process (stdin/stdout PIPE)
```

容器以 idle 进程启动（`while true; do sleep 3600; done`），实际命令通过 `docker exec` 执行。`--rm` 确保容器退出时自动清理。

**孤儿清理**: 启动时枚举 `langbot.box=true` 标签的容器，instance_id 不匹配的强制删除。

#### NsjailBackend (`box/nsjail_backend.py`, 510 行)

轻量级 Linux 沙箱（无容器引擎依赖）：

- 使用 namespace 隔离（user/mount/pid/ipc/uts/cgroup/net）
- 挂载宿主 `/usr`/`/lib`/`/bin`/`/sbin` 只读 + 选定 `/etc` 条目
- 每 session 创建独立目录（workspace/tmp/home）
- 资源限制: cgroup v2 优先，fallback 到 rlimit
- **无自定义镜像**: 使用宿主 OS，`image` 字段固定为 `'host'`

**后端选择优先级**: Docker → nsjail（启动时逐个探测，首个可用的胜出，不做运行时 failover）

### 3.3 Server (`box/server.py`, 268 行)

单端口 aiohttp 服务（默认 5410），通过路径区分：

1. **Action RPC** (`/rpc/ws`): `BoxServerHandler` 处理 11 种 action（HEALTH/STATUS/EXEC/CREATE_SESSION/...），通过 stdio 或 WS 传输。WS 模式使用 `AiohttpWSConnection` 适配层。
2. **WS Relay** (`/v1/sessions/{id}/managed-process/ws`): 双向桥接 WebSocket ↔ managed process stdin/stdout

端口分配:
- Port N (默认 5410): 所有 WebSocket 端点（Action RPC + managed process relay）

### 3.4 Client (`box/client.py`, 177 行)

`ActionRPCBoxClient` 封装 `Handler.call_action()` 调用：

- 每个方法对应一个 RPC action
- 错误还原: `_translate_action_error()` 通过字符串前缀匹配还原 SDK 侧异常类型
- `execute()` timeout = 300s，其他默认 15s

### 3.5 Models (`box/models.py`, 302 行)

核心数据模型：

| 模型 | 用途 |
|------|------|
| `BoxSpec` | 执行请求（cmd/workdir/timeout/network/session_id/image/host_path/资源限制） |
| `BoxProfile` | 预设配置 + `locked` frozenset |
| `BoxSessionInfo` | Session 状态（含 backend_name/backend_session_id/created_at/last_used_at） |
| `BoxManagedProcessSpec` | 长驻进程启动参数（command/args/env/cwd） |
| `BoxManagedProcessInfo` | 进程状态（status/exit_code/stderr_preview/attached） |
| `BoxExecutionResult` | 执行结果（status/exit_code/stdout/stderr/duration_ms） |

`BoxSpec` 校验器:
- `workdir` 默认继承 `mount_path`
- `host_path` 支持 POSIX 和 Windows 路径
- 设置了 `host_path` 时，`workdir` 必须在 `mount_path` 下

### 3.6 Security (`box/security.py`, 54 行)

`validate_sandbox_security()`: 黑名单校验 host_path，阻止挂载 `/etc`/`/proc`/`/sys`/`/dev`/`/root`/`/boot` 及 Docker socket。

**已知缺陷**: 根路径 `/` 未拦截，用户 home 目录未拦截，是 denylist 而非 allowlist 策略。详见 [问题清单 #5](./box-issues.md)。

---

## 4. 工具系统集成

### 4.1 ToolManager 编排 (`toolmgr.py`)

```
ToolManager.initialize()
  ├─ NativeToolLoader      (exec/read/write/edit)
  ├─ PluginToolLoader      (插件工具)
  ├─ MCPLoader             (MCP Server 工具)
  └─ SkillAuthoringToolLoader  (Skill CRUD)

工具调用优先级: native → plugin → mcp → skill_authoring
```

### 4.2 Native Tools (`native.py`)

| 工具 | 是否在 Box 中执行 | 是否访问宿主文件系统 |
|------|:---:|:---:|
| `exec` | 是 | 否 |
| `read` | **否** | **是** — 直接 `open()` 宿主文件 |
| `write` | **否** | **是** — 直接 `open()` 宿主文件 |
| `edit` | **否** | **是** — 直接 `open()` 宿主文件 |

**沙箱边界不对称**: 这是刻意的设计权衡 — `read`/`write`/`edit` 绕过沙箱以获得性能（避免容器 I/O 开销），但意味着 LLM 可以直接读写 allowed_roots 下的任何文件。

exec 对 Skill 的特殊处理: 如果 `workdir` 引用 `/workspace/.skills/<name>`，会创建 `BoxWorkspaceSession`，将 Skill 的 `package_root` 作为 `host_path`，并可选做 Python 环境自举。

### 4.3 MCP-in-Box (`mcp_stdio.py`)

`BoxStdioSessionRuntime` 让 MCP stdio 服务器在 Box 容器中运行：

```
initialize()
  1. 创建 BoxWorkspaceSession
  2. workspace.create_session()              创建容器
  3. workspace.execute_raw(install_cmd)       安装依赖 (可选)
  4. workspace.start_managed_process(...)     启动 MCP Server
  5. websocket_client(ws_url)                通过 WS relay 连接
  6. ClientSession.initialize()              MCP 协议握手
```

配置 (`MCPServerBoxConfig`): `network='on'`（MCP 服务器通常需要网络），`host_path_mode='ro'`（默认只读），`startup_timeout_sec=120`（留时间给 pip install）。

---

## 5. 启动与生命周期

### 5.1 启动顺序 (`build_app.py`)

```
BuildAppStage.run(ap)
  ├─ ... (persistence, models, sessions) ...
  │
  ├─ BoxService(ap)                       line 134
  ├─ box_service.initialize()             line 135
  │    └─ connector.initialize()
  │         ├─ [local] fork box.server subprocess
  │         └─ [remote] connect WS
  ├─ ap.box_service = box_service         line 136
  │
  ├─ ToolManager(ap)                      line 138
  ├─ tool_mgr.initialize()               line 139
  │    ├─ NativeToolLoader   (检查 box_service.available)
  │    ├─ PluginToolLoader
  │    ├─ MCPLoader          (Box 可用时，stdio MCP 走沙箱)
  │    └─ SkillAuthoringToolLoader
  ├─ ap.tool_mgr = tool_mgr              line 140
  │
  ├─ ... (platform, pipeline) ...
  ├─ SkillManager.initialize()            line 160
  └─ ... (RAG, HTTP, plugins) ...
```

BoxService 在 ToolManager **之前**初始化。ToolManager 创建 loader 时检查 `box_service.available`。

### 5.2 初始化失败处理

```python
# service.py:68-81
try:
    await self._runtime_connector.initialize()
    self._available = True
except Exception as e:
    self._available = False
    logger.warning(f"Box runtime unavailable: {e}")
```

**静默降级**: Box 初始化失败不会阻止应用启动，仅导致 4 个 native tool 不暴露给 LLM。与 Plugin 的行为不同（Plugin 失败会抛异常）。

### 5.3 销毁流程

```
app.dispose()
  └─ box_service.dispose()
       ├─ connector.dispose()
       │    ├─ cancel _handler_task
       │    ├─ cancel _ctrl_task
       │    └─ terminate subprocess (SIGTERM)
       └─ loop.create_task(client.shutdown())
            └─ RPC SHUTDOWN → Box Runtime 清理所有容器
```

Box 额外做了 RPC SHUTDOWN 通知 Runtime 主动清理容器，比 Plugin 的直接杀进程更安全。

---

## 6. 配置

### config.yaml

```yaml
box:
    profile: 'default'              # 内置 Profile 名
    runtime_url: ''                 # 空 = 自动 fork 子进程
    shared_host_root: './data/box'  # Docker 部署时用 '/workspaces'
    default_host_workspace: ''      # 默认为 <shared_host_root>/default
    allowed_host_mount_roots:       # 安全白名单
        - './data/box'
        - '/tmp'
```

### docker-compose.yaml

```yaml
volumes:
  - ./data/box:/workspaces                          # 工作区挂载
  - /var/run/docker.sock:/var/run/docker.sock       # Docker backend
```

### REST API (3 个端点)

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/box/status` | GET | 可用性、Profile、后端信息 |
| `/api/v1/box/sessions` | GET | 活跃 session 列表 |
| `/api/v1/box/errors` | GET | 最近 50 条错误 |

**注意**: 前端目前未接入这 3 个 API。
