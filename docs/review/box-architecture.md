# Box 系统架构深度分析

> 更新日期: 2026-05-19
> 分支: `feat/sandbox` (LangBot + langbot-plugin-sdk)
> 相关文档: [问题清单](./box-issues.md) | [Session 作用域](./box-session-scope.md) | [Runtime 对比](./box-vs-plugin-runtime.md) | [测试覆盖](./box-test-coverage.md) | [toB 分析](./box-tob-analysis.md)

---

## 1. 全局架构

```
┌──────────────────────────────────────────────────────────────────┐
│                       LangBot 主进程                              │
│                                                                   │
│  LocalAgentRunner ──> ToolManager ──> NativeToolLoader            │
│       │                    │              │                       │
│       │                    │      exec / read / write / edit      │
│       │                    │              glob / grep             │
│       │                    │                                      │
│       │                    ├──> MCPLoader ──> BoxStdioSession     │
│       │                    │       (shared 容器, 多 process)       │
│       │                    │                                      │
│       │                    ├──> SkillToolLoader (activate 工具)    │
│       │                    │                                      │
│       │                    ├──> SkillAuthoringToolLoader          │
│       │                    │                                      │
│       │                    └──> PluginToolLoader                  │
│       │                                                           │
│  BoxService (门面)                                                 │
│    ├─ Profile 管理 (locked 字段)                                   │
│    ├─ Host mount 校验 (allowed_mount_roots)                        │
│    ├─ Workspace quota 检查                                         │
│    ├─ 输出截断 (head+tail)                                         │
│    ├─ Session ID 模板解析 (resolve_box_session_id)                 │
│    ├─ 技能挂载组装 (build_skill_extra_mounts)                      │
│    ├─ 重连循环 (_reconnect_loop, 指数退避)                          │
│    └─ BoxRuntimeConnector                                          │
│         ├─ 心跳 loop (20s ping)                                    │
│         └─ ActionRPCBoxClient                                      │
│              │  Action RPC (stdio 或 WebSocket)                    │
│                                                                    │
│  SkillManager (skill_mgr)                                          │
│    └─ 从 Box runtime 拉取 skills, 不可用时回落 data/skills          │
└──────────────────────────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────────┐
│              Box Runtime 进程 (SDK 侧)                            │
│                                                                   │
│  BoxServerHandler (Action RPC 处理, INIT 配置注入)                  │
│       │                                                           │
│  BoxRuntime (session 管理 / 进程生命周期 / TTL reaper)              │
│       │       └─ session.managed_processes: dict[pid, _ManagedProcess]
│       │                                                           │
│  Backend (启动时根据 box.backend 配置选择):                          │
│    DockerBackend ──┐                                              │
│    PodmanBackend ──┤── CLISandboxBackend                          │
│    NsjailBackend ──┘  (本地 CLI 或 fallback 到容器内 CLI)            │
│    E2BBackend         (云沙箱, 需要 E2B_API_KEY)                    │
│                                                                   │
│  BoxSkillStore                                                    │
│    ├─ list / get / create / update / delete                       │
│    ├─ scan_skill_directory / read_skill_file / write_skill_file   │
│    └─ preview_skill_zip / install_skill_zip (zip 或 GitHub)        │
│                                                                   │
│  aiohttp 单端口服务 (默认 :5410):                                    │
│    /rpc/ws                                       — Action RPC      │
│    /v1/sessions/{id}/managed-process/ws          — 默认 process     │
│    /v1/sessions/{id}/managed-process/{pid}/ws    — 指定 process     │
└──────────────────────────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────────┐
│  容器 / 沙箱 (Docker/Podman 容器, nsjail sandbox, 或 E2B 远程沙箱)  │
│  - 隔离文件系统 / 网络 / PID 命名空间                                │
│  - 资源限制 (CPU, 内存, PID 数, 可选 workspace 配额)                 │
│  - 主挂载 (host_path → mount_path) + 任意条 extra_mounts             │
│      └─ Skills 通过 extra_mounts 挂在 /workspace/.skills/<name>     │
│  - exec: 用户命令在此执行                                            │
│  - managed process: 多个长驻进程并存 (MCP Server / 自定义服务)        │
└──────────────────────────────────────────────────────────────────┘
```

**核心设计原则**:
- Box Runtime 作为独立进程运行，通过 Action RPC 与 LangBot 主进程通信，两者复用 SDK 的 IO 层（Handler → Connection → Controller）
- 一个 session_id 对应一个容器/沙箱实例。同一 session 内可并存多条 mount 与多个 managed process
- Skill / 默认 exec / MCP Server 共享同一个 session 容器（详见 [box-session-scope.md](./box-session-scope.md)）

---

## 2. LangBot 侧模块

### 2.1 BoxService (`pkg/box/service.py`, 722 行)

应用层门面，协调 Profile、安全校验、配额、连接、Skill 挂载与 Session 模板：

主要公开方法（按定义顺序）：

```
BoxService
  ├─ initialize()                              连接 Box Runtime + 默认 workspace 准备
  ├─ _on_runtime_disconnect(connector)         触发重连
  ├─ _reconnect_loop(connector)                指数退避重连
  ├─ available (property)                      连接状态
  │
  ├─ resolve_box_session_id(query)             从 pipeline 模板解析 session_id
  ├─ build_skill_extra_mounts(query)           组装 pipeline-bound skill 的挂载列表
  │
  ├─ execute_tool(parameters, query)           Agent 调用 exec 时的入口
  │    ├─ _apply_profile / build_spec
  │    ├─ _validate_host_mount
  │    ├─ _enforce_workspace_quota (phase=pre)
  │    ├─ client.execute(spec)
  │    ├─ _enforce_workspace_quota (phase=post)
  │    └─ _truncate (stdout/stderr)
  │
  ├─ execute_spec_payload(spec_payload, ...)   内部入口（其他 loader 调用）
  ├─ create_session(spec_payload, ...)         显式创建 session
  ├─ start_managed_process(session_id, ...)    启动 managed process
  ├─ get_managed_process(session_id, pid)      查询进程状态（pid 默认 'default'）
  ├─ stop_managed_process(session_id, pid)     单独停止某个 managed process
  ├─ get_managed_process_websocket_url(...)    返回 WS attach URL
  │
  ├─ list_skills() / get_skill(name)           Skill 元数据
  ├─ create_skill / update_skill / delete_skill  Skill CRUD
  ├─ scan_skill_directory(path)                扫描目录
  ├─ list_skill_files / read_skill_file / write_skill_file
  ├─ preview_skill_zip / install_skill_zip     zip / GitHub 安装
  │
  ├─ shutdown() / dispose()                    清理：RPC SHUTDOWN + 进程终止
  ├─ get_status() / get_sessions() / get_recent_errors()
  └─ get_system_guidance()                     LLM 系统提示
```

**Profile 系统**: 4 个内置 Profile（`default` / `offline_readonly` / `network_basic` / `network_extended`），`locked` frozenset 字段不可被 LLM 覆盖。参数合并顺序：Profile defaults → LLM 请求参数 → locked 强制值。

**输出截断**: 默认 4000 字符上限，保留前 60% + 后 40%，中间插入 `[...truncated...]`。

**Skill 挂载合并**: `execute_tool()` 调用时，`build_skill_extra_mounts(query)` 会把当前 pipeline-bound 的所有 skill 的 `package_root` 作为 `extra_mounts` 加入 BoxSpec，挂在 `/workspace/.skills/<name>`。LLM 通过 `activate` 工具显式激活某个 skill 后，工具调用才允许引用这个 skill 的虚拟路径。

### 2.2 BoxRuntimeConnector (`pkg/box/connector.py`, 357 行)

管理与 Box Runtime 的通信连接：

- **本地 stdio**: Unix/macOS 默认路径，fork `python -m langbot_plugin.cli.__init__ box -s --ws-control-port {port}` 子进程（与 plugin runtime 统一走 `lbp` CLI 入口）
- **本地 subprocess + WS**: Windows 本地（asyncio ProactorEventLoop 不支持 stdio pipe）
- **远程 WebSocket**: Docker 部署 / `box.runtime.endpoint` 显式配置时，连接 `ws://{host}:{port}/rpc/ws`
- **同步等待**: `asyncio.Event` + `wait_for(timeout=30s)` 模式确认连接
- **心跳**: `_heartbeat_loop()` 每 20s 调用 `ping()`，失败仅 DEBUG 日志（断开检测靠 connection close）
- **重连**: `runtime_disconnect_callback` 由 BoxService 提供，触发 `_reconnect_loop`
- **INIT 注入**: 连接建立后立即下发当前 `box.*` 配置子树（剔除 `runtime` 私有字段），Runtime 据此初始化 backend

> **历史改进**: 2026-04-16 版本本文档曾列 P0 「Box 无心跳 / 无重连」，已修复（commit `2dfd9d5d`、`c6882cf`、`5029d9c` 等）。

### 2.3 BoxWorkspaceSession 工具 (`pkg/box/workspace.py`, 413 行)

此文件目前提供两类能力：

1. **路径与命令重写工具函数** — `normalize_host_path` / `rewrite_mounted_path` / `unwrap_venv_path` / `rewrite_venv_command` / `infer_workspace_host_path`，被 MCP loader 与 Skill 路径解析共用。
2. **`BoxWorkspaceSession`** — 围绕 BoxService 的轻量包装，专供 MCP-in-Box 场景使用（管理一个共享 session 的 session_id、构建挂载 payload、stage host 文件到共享 workspace）。

**变化点**: 早期 Skill exec 会为每个 skill 创建独立 BoxWorkspaceSession（独占 session）；当前实现已转为 `extra_mounts` 模式，Skill 不再独占容器，只追加挂载。这部分 wrapping 逻辑已从 native loader 移除。

### 2.4 policy.py (`pkg/box/policy.py`, 98 行) — 仍是死代码

三层安全策略设计（`SandboxPolicy` / `ToolPolicy` / `ElevatedPolicy`），全项目无任何导入或调用。详见 [问题清单 #1](./box-issues.md)。

### 2.5 SkillManager (`pkg/skill/manager.py`, 186 行)

```
SkillManager
  ├─ initialize()                  调用 reload_skills()
  ├─ reload_skills()               先从 Box runtime list_skills()，
  │                                 不可用则回落 data/skills/ 扫描
  ├─ refresh_skill_from_disk()     单 skill 重新加载
  ├─ get_skill_by_name(name)
  └─ get_managed_skills_root()     返回 Box 视角的 skills_root 路径
```

skill 元数据通过 `parse_frontmatter` 解析 `SKILL.md` 头部（`name` / `description` / `instructions`），不再做整体扫描的代价（典型 < 50 个）。

### 2.6 Skill activation (`pkg/skill/activation.py`, 33 行) + Skill loader 辅助

历史上 skill 通过 LLM 在文本中输出 `[ACTIVATE_SKILL:name]` 标记激活；当前已改为 **Tool Call 机制**：

- `SkillToolLoader` (`pkg/provider/tools/loaders/skill.py`, 157 行) 暴露 `activate` 工具，参数为 skill 名
- 工具实现调用 `register_activated_skill(query, skill_data)`，将激活态写入 `query.variables['_activated_skills']`
- 这种 KV-cache-friendly 模式对齐 Claude Code 设计；详见 [box-session-scope.md §4.3](./box-session-scope.md) 的 Tool Call 描述

`activation.py` 现仅保留对外辅助函数（pipeline 层调用 loader 的 `register_activated_skill`）。

---

## 3. SDK 侧模块

### 3.1 BoxRuntime (`box/runtime.py`, 599 行)

核心编排器，管理 session 生命周期与 backend 调度：

```
Session 生命周期:

  Client EXEC / CREATE_SESSION
       │
       ▼
  _get_or_create_session(spec)
    ├─ _reap_expired_sessions_locked()   清理 TTL 过期 session
    ├─ 已存在? → _assert_session_compatible() → 复用
    ├─ Backend session 失踪? → 重建 (commit c6882cf)
    └─ 新建? → backend.start_session(spec) → 创建容器
       │       └─ 应用 spec.extra_mounts （多挂载）
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
- 每 session 维护 `managed_processes: dict[process_id, _ManagedProcess]`，支持多个长驻进程并存（MCP / 自定义）
- 全局 `_lock` 保护 `_sessions` dict 的读写
- 兼容性检查：比较核心 spec 字段，`image` 字段对不支持自定义镜像的 backend（nsjail/E2B）会跳过

**Backend 选择 (`_select_backend`)**: 优先级
1. 显式 `box.backend` 配置（`docker` / `nsjail` / `e2b`）
2. `local` (默认) → Docker / Podman / nsjail CLI 顺序探测
3. `get_status` 调用时若当前 backend 不可用，会尝试重新选择 (commit `e5617c7`)

### 3.2 Backend 系统

#### CLISandboxBackend (`box/backend.py`, 411 行)

Docker / Podman 公共基类：

```
start_session(spec):
  1. validate_sandbox_security(spec)
  2. docker/podman run -d --rm --name <name>
     --network none (可选)
     --cpus/--memory/--pids-limit
     --read-only + --tmpfs /tmp
     -v <host>:<mount>:<mode>          主挂载
     -v <extra.host>:<extra.mount>:..  额外挂载 (extra_mounts)
     <image> sh -lc 'while true; do sleep 3600; done'
  3. 返回 BoxSessionInfo

exec(session, spec):
  docker/podman exec -e KEY=VAL <container>
    sh -lc 'mkdir -p <workdir> && cd <workdir> && <cmd>'

start_managed_process(session, spec):
  docker/podman exec -i <container>
    sh -lc 'mkdir -p <cwd> && cd <cwd> && exec <command> <args>'
  返回 asyncio.subprocess.Process (stdin/stdout PIPE)
```

容器以 idle 进程启动，实际命令通过 `docker exec` 执行。`--rm` 确保容器退出时自动清理。

**Windows 支持**: backend 内对 Windows 路径处理与 subprocess 调用做了适配（commit `120817a`）。

**孤儿清理**: 启动时枚举 `langbot.box=true` 标签的容器，instance_id 不匹配的强制删除。

#### NsjailBackend (`box/nsjail_backend.py`, 552 行)

轻量级 Linux 沙箱（无容器引擎依赖）：

- 使用 namespace 隔离（user/mount/pid/ipc/uts/cgroup/net）
- 挂载宿主 `/usr`/`/lib`/`/bin`/`/sbin` 只读 + 选定 `/etc` 条目
- 每 session 创建独立目录（workspace/tmp/home）
- 资源限制: cgroup v2 优先，fallback 到 rlimit
- **CLI 兼容**: 通过 `shutil.which(self._nsjail_bin)` 检测系统安装版 nsjail；不存在时再尝试容器内 nsjail（commit `686fcc0`、`feed530`）
- **无自定义镜像**: 使用宿主 OS，`image` 字段固定为 `'host'`，兼容性检查跳过 image

#### E2BBackend (`box/e2b_backend.py`, 429 行)

云沙箱后端（commit `75b547f` 引入）：

- 通过 `e2b` SDK 与 E2B 平台通信
- 配置：`box.e2b.api_key` / `api_url` / `template`
- 支持 `extra_mounts`（commit `0fea9b1` 同步上传文件）
- 无本地容器引擎依赖，适合无 Docker 的部署或 SaaS 多租户场景
- 不支持自定义 image 字段，由 template 控制

### 3.3 Server (`box/server.py`, 508 行)

单端口 aiohttp 服务（默认 5410），通过路径区分（commit `8c71ec5` 合并端口）：

1. **Action RPC** (`/rpc/ws`): `BoxServerHandler` 处理所有 action，包括 `INIT` 配置注入、skill store 操作等
2. **WS Relay** (`/v1/sessions/{id}/managed-process/ws` 与 `/v1/sessions/{id}/managed-process/{pid}/ws`): 双向桥接 WebSocket ↔ 指定 managed process stdin/stdout

stdio 模式同样会在 5410 启动 aiohttp，专门承担 managed process attach；Action RPC 走 stdin/stdout。

### 3.4 Client (`box/client.py`, 377 行)

`ActionRPCBoxClient` 封装 `Handler.call_action()` 调用：

- 25+ 方法对应 25+ 个 RPC action（exec / session / managed-process / skill / status / shutdown）
- 错误还原: `_translate_action_error()` 通过字符串前缀匹配还原 SDK 侧异常类型
- `execute()` timeout = 300s，其他默认 15s
- `BoxRuntimeClient` 是 ABC，供后续可能的非 RPC 实现复用

包级别 `__init__.py` 显式导出：`BoxRuntimeClient`、`ActionRPCBoxClient`（commit `df9c722`）。

### 3.5 Actions (`box/actions.py`, 34 行)

`LangBotToBoxAction` 枚举共定义 **25 个** action：

| 类别 | Actions |
|------|---------|
| 控制 | `INIT`、`HEALTH`、`STATUS`、`GET_BACKEND_INFO`、`SHUTDOWN` |
| 执行 | `EXEC` |
| Session | `CREATE_SESSION` / `GET_SESSION` / `GET_SESSIONS` / `DELETE_SESSION` |
| Managed Process | `START_MANAGED_PROCESS` / `GET_MANAGED_PROCESS` / `STOP_MANAGED_PROCESS` |
| Skill | `LIST_SKILLS` / `GET_SKILL` / `CREATE_SKILL` / `UPDATE_SKILL` / `DELETE_SKILL` / `SCAN_SKILL_DIRECTORY` / `LIST_SKILL_FILES` / `READ_SKILL_FILE` / `WRITE_SKILL_FILE` / `PREVIEW_SKILL_ZIP` / `INSTALL_SKILL_ZIP` |

### 3.6 Models (`box/models.py`, 331 行)

核心数据模型：

| 模型 | 用途 |
|------|------|
| `BoxNetworkMode` | `OFF` / `ON` |
| `BoxExecutionStatus` | `COMPLETED` / `TIMED_OUT` |
| `BoxHostMountMode` | `NONE` / `READ_ONLY` / `READ_WRITE` |
| `BoxManagedProcessStatus` | `RUNNING` / `EXITED` |
| `BoxMountSpec` | 单条挂载（host_path/mount_path/mode）— **新增** |
| `BoxSpec` | 执行请求；新增 `extra_mounts: list[BoxMountSpec]`、`persistent`、`workspace_quota_mb` |
| `BoxProfile` | 4 个内置 Profile + `locked` frozenset |
| `BoxSessionInfo` | Session 状态（含 backend_name/created_at/last_used_at） |
| `BoxManagedProcessSpec` | 长驻进程参数（process_id/command/args/env/cwd） |
| `BoxManagedProcessInfo` | 进程状态（status/exit_code/stderr_preview/attached） |
| `BoxExecutionResult` | 执行结果（status/exit_code/stdout/stderr/duration_ms） |

`BoxSpec` 校验器: `workdir` 默认继承 `mount_path`；`host_path` 支持 POSIX 和 Windows 路径；设置 `host_path` 时 `workdir` 必须在 `mount_path` 下。

### 3.7 BoxSkillStore (`box/skill_store.py`, 647 行)

新增模块（commit `4ab3502`），把 skill 持久化收归 Box runtime：

```
BoxSkillStore
  ├─ list_skills() / get_skill(name)
  ├─ create_skill(data) / update_skill(name, data) / delete_skill(name)
  ├─ scan_skill_directory(path)            扫描目录返回候选 skill 包列表
  ├─ list_skill_files(name, path)          浏览 skill 内文件树
  ├─ read_skill_file(name, path) / write_skill_file(name, path, content)
  ├─ preview_skill_zip(zip_bytes, ...)     不落盘预览 zip 内容
  └─ install_skill_zip(zip_bytes, ...)     解压、校验、复制到 skills_root
     └─ 支持 source_subdir / target_suffix（commit 1aa043f）
```

GitHub 安装路径：HTTP 层（`api/http/service/skill.py`）先 `git clone` 拉取，再走 `install_skill_zip` 或 directory 路径。Skill 文件存放于 `box.local.skills_root`（默认 `skills`，相对 `host_root`），容器内对应 `/workspace/.skills/`。

### 3.8 Security (`box/security.py`, 52 行)

`validate_sandbox_security()`: 黑名单校验 host_path，阻止挂载 `/etc`/`/proc`/`/sys`/`/dev`/`/root`/`/boot` 及 Docker/Podman socket。

**已知缺陷**: 根路径 `/` 未拦截，用户 home 目录未拦截，是 denylist 而非 allowlist 策略。详见 [问题清单 #5](./box-issues.md)。

### 3.9 Errors (`box/errors.py`, 33 行)

| 异常类型 | 含义 |
|----------|------|
| `BoxError` | 基类 |
| `BoxValidationError` | spec/参数校验失败 |
| `BoxBackendUnavailableError` | 无可用 backend |
| `BoxRuntimeUnavailableError` | Runtime 服务不可用 |
| `BoxSessionConflictError` | session 已存在但 spec 不兼容 |
| `BoxSessionNotFoundError` | session 不存在 |
| `BoxManagedProcessConflictError` | session 已有同名 process |
| `BoxManagedProcessNotFoundError` | process 不存在 |

---

## 4. 工具系统集成

### 4.1 ToolManager 编排 (`toolmgr.py`)

```
ToolManager.initialize()
  ├─ NativeToolLoader      (exec / read / write / edit / glob / grep)
  ├─ PluginToolLoader      (插件工具)
  ├─ MCPLoader             (MCP Server 工具)
  ├─ SkillToolLoader       (activate 工具 — Tool Call 激活)
  └─ SkillAuthoringToolLoader  (Skill CRUD)

工具调用优先级: native → plugin → mcp → skill → skill_authoring
```

### 4.2 Native Tools (`native.py`, 846 行)

| 工具 | 是否在 Box 中执行 | 是否访问宿主文件系统 |
|------|:---:|:---:|
| `exec`  | 是 | 否 |
| `read`  | **否** | **是** — 直接 `open()` 宿主文件 |
| `write` | **否** | **是** — 直接 `open()` 宿主文件 |
| `edit`  | **否** | **是** — 直接 `open()` 宿主文件 |
| `glob`  | **否** | **是** — 直接遍历宿主目录 |
| `grep`  | **否** | **是** — 直接读宿主文件 |

**沙箱边界不对称**: 这是刻意的设计权衡 — `read`/`write`/`edit`/`glob`/`grep` 绕过沙箱以获得性能（避免容器 I/O 开销与跨进程拷贝），但意味着 LLM 可以直接读写 `allowed_mount_roots` 下任何文件。Skill 路径经 `_resolve_host_path()` 重写，禁止穿越 `package_root`。

**exec 的 Skill 分支**: 命令中引用 `/workspace/.skills/<name>` 的 skill 时：
1. 验证 skill 已激活
2. 单次 exec 只能引用一个 skill 包
3. 若 skill 是 Python 项目（有 `requirements.txt` 或 `pyproject.toml`），命令会被 venv bootstrap 包裹（在 skill 挂载点内创建 `.venv`）
4. 调用 `box_service.execute_tool()` → 走默认 session_id 与已组装好的 `extra_mounts`，**不再为每 skill 起独立 session**

### 4.3 MCP-in-Box (`mcp_stdio.py`, 354 行)

`BoxStdioSessionRuntime` 让 MCP stdio 服务器在 Box 容器中运行，**共享 session、多 process**模式（commit `529088e`）：

```
initialize()
  1. 复用/创建共享 session (session_id = _build_box_session_id())
     - persistent=True，长期保持
  2. workspace.execute_raw(install_cmd) 安装依赖 (可选)
  3. 将每个 MCP server 文件 stage 到 /workspace/.mcp/<process_id>/
  4. workspace.start_managed_process(process_id=<server>)
  5. websocket_client(ws_url) 通过 WS relay 连接
  6. ClientSession.initialize() MCP 协议握手
```

配置 (`MCPServerBoxConfig`): `network='on'` (MCP 服务器通常需要网络)，`host_path_mode='ro'` (默认只读)，`startup_timeout_sec=120` (留时间给 pip install)。

每条 MCP server 是同一 session 中的一个 managed process，独立的 `process_id`、独立 attach URL，互不阻塞。

---

## 5. 启动与生命周期

### 5.1 启动顺序 (`build_app.py`)

```
BuildAppStage.run(ap)
  ├─ ... (persistence, models, sessions) ...
  │
  ├─ BoxService(ap)
  ├─ box_service.initialize()
  │    └─ connector.initialize()
  │         ├─ [stdio] fork box subprocess
  │         ├─ [subprocess+WS] Windows 本地
  │         └─ [remote WS] connect URL
  │    └─ 启动心跳 _heartbeat_task
  ├─ ap.box_service = box_service
  │
  ├─ ToolManager(ap)
  ├─ tool_mgr.initialize()
  │    ├─ NativeToolLoader   (检查 box_service.available)
  │    ├─ PluginToolLoader
  │    ├─ MCPLoader          (Box 可用时，stdio MCP 走沙箱)
  │    └─ SkillAuthoringToolLoader
  ├─ ap.tool_mgr = tool_mgr
  │
  ├─ ... (platform, pipeline) ...
  ├─ SkillManager.initialize()    (从 Box runtime 加载 skill 列表)
  └─ ... (RAG, HTTP, plugins) ...
```

BoxService 在 ToolManager **之前**初始化。ToolManager 创建 loader 时检查 `box_service.available`。

### 5.2 初始化失败处理

```python
try:
    await self._runtime_connector.initialize()
    self._available = True
except Exception as e:
    self._available = False
    logger.warning(f"Box runtime unavailable: {e}")
```

**静默降级**: Box 初始化失败不会阻止应用启动，仅导致 6 个 native tool、所有 Skill 工具和 MCP-in-Box 工具不暴露给 LLM。与 Plugin 的行为不同（Plugin 失败会抛异常）。

### 5.3 销毁流程

```
app.dispose()
  └─ box_service.dispose()
       ├─ connector.dispose()
       │    ├─ cancel _heartbeat_task
       │    ├─ cancel _handler_task / _ctrl_task
       │    └─ terminate subprocess (SIGTERM)
       └─ loop.create_task(client.shutdown())
            └─ RPC SHUTDOWN → Box Runtime 清理所有容器
```

Box 额外做了 RPC SHUTDOWN 通知 Runtime 主动清理容器，比 Plugin 的直接杀进程更安全。

---

## 6. 配置

### config.yaml (重构后)

```yaml
box:
    enabled: true         # 整个 Box 子系统的总开关。设为 false 时：
                          #  - 不连接远程 Box runtime，不 fork 本地 stdio 子进程
                          #  - sandbox 工具 (exec/read/write/edit/glob/grep) 不暴露给 LLM
                          #  - skill 添加/编辑 / GitHub 安装 / 文件写入全部拒绝
                          #  - stdio 模式的 MCP server 启动时报错（http/sse 模式不受影响）
                          #  - skill 列表/读取保持只读可用
                          # BOX__ENABLED 环境变量可覆盖（统一约定）
    backend: 'local'      # 'local' (探测) / 'docker' / 'nsjail' / 'e2b'
                          # 由 box.backend / BOX__BACKEND 选择后端
    runtime:
        endpoint: ''      # 外部 Runtime 的 WS 基地址 'ws://host:5410'
                          # 留空 = 本地自管 Runtime
    local:
        profile: 'default'
        image: ''                       # 覆盖 profile 默认 image
        host_root: './data/box'         # 工作区挂载根，Docker 部署需绝对路径
        default_workspace: ''           # 默认 '<host_root>/default'
        skills_root: 'skills'           # Box 管理的 skill 包目录（相对 host_root）
        allowed_mount_roots:            # 默认 ['<host_root>']
            - './data/box'
            - '/tmp'
        workspace_quota_mb: null        # 配额覆盖，null = 走 profile
    e2b:
        api_key: ''                     # 也可走 E2B_API_KEY 环境变量
        api_url: ''                     # 自托管 E2B 时填写
        template: ''                    # 默认 template ID
```

> **重大变更**: 较 2026-04-16 文档，配置结构完全重组（commit `eefdea4`）。原字段 `box.profile` / `box.runtime_url` / `box.shared_host_root` / `box.allowed_host_mount_roots` 全部迁入 `box.local.*` 子表，新增 `box.backend` 与 `box.e2b.*` 配置组。

### docker-compose.yaml

`langbot_box` 服务受 compose profile 控制,默认 `docker compose up` **不会**启动它。需要 sandbox 时:

```bash
docker compose --profile box up        # 启动 langbot + langbot_box + plugin runtime
docker compose --profile all up        # 同上
docker compose up                       # 只起 langbot + plugin runtime (box 关闭)
```

若不起 `langbot_box`,需要同步在 `data/config.yaml` 中设 `box.enabled: false`(或 langbot 容器 env 加 `BOX__ENABLED=false`),否则 LangBot 会一直尝试连接不存在的 Box runtime 并报错。

```yaml
# langbot_box 的关键 volume
volumes:
  - ${LANGBOT_BOX_ROOT}:${LANGBOT_BOX_ROOT}         # 工作区挂载(源/目标同路径)
  - /var/run/docker.sock:/var/run/docker.sock       # Docker backend 复用宿主 docker
```

### 关闭/连接失败时的行为矩阵

`box.enabled = false` 与"启用但连接失败"在用户可观察行为上**完全一致**——都通过 `BoxService.available = False` 表达,只是 `get_status` 多返回 `enabled` 字段供前端区分文案。

| 消费方 | Box 可用 | Box 不可用(disabled 或 failed) |
|---|---|---|
| native exec/read/write/edit/glob/grep 工具 | 暴露给 LLM | **不暴露** |
| `activate` / `register_skill` 工具 | 暴露给 LLM | **不暴露** |
| stdio MCP server | 在 Box 内启动 | **`_init_stdio_python_server` 抛 RuntimeError** 拒绝;不退化到宿主 stdio |
| http/sse MCP server | 正常 | 正常(不依赖 Box) |
| Skill 列表/读取 (`list_skills`/`get_skill`/`read_skill_file`) | 走 Box runtime | 走 LangBot 本地 `data/skills/` 只读 fallback |
| Skill 创建/编辑/安装/写文件 | 走 Box runtime | **HTTP 400** + 明确错误信息(`_require_box_for_write`) |
| Pipeline AI 配置中 `box-session-id-template` | 正常生效 | **前端 banner** 提示字段无效 |
| Pipeline 扩展页 `enable_all_skills` / 绑定 skill | 可编辑 | **前端禁用** + banner |
| 仪表盘 Box 状态卡片 | 绿点 / "已连接" | 灰点 / "已禁用"(disabled) 或 红点 / "已断开"(failed) |

> 后端拒写的边界条件:如果 `ap.box_service` **完全没装**(老式 dev mode,没经过 BuildAppStage),`_require_box_for_write` 视作 no-op,保留 `data/skills/` 本地路径——以兼容历史测试与最小化设置。生产环境总会装 `ap.box_service`,因此该 fallback 不会被触发。

### Pipeline 配置 (templates/metadata/pipeline/ai.yaml)

`local-agent.config.box-session-id-template` 控制 session 作用域，预设：

- `{launcher_type}_{launcher_id}` — 每个会话 (推荐，默认)
- `{launcher_type}_{launcher_id}_{sender_id}` — 群聊每个用户
- `{launcher_type}_{launcher_id}_{conversation_id}` — 每个对话上下文
- `{query_id}` — 每条消息（完全隔离）

详见 [box-session-scope.md](./box-session-scope.md)。

### REST API

| 端点 | 方法 | 说明 | 前端 |
|------|------|------|:---:|
| `/api/v1/box/status` | GET | 可用性、Profile、后端信息 | ✅ 监控页 |
| `/api/v1/box/sessions` | GET | 活跃 session 列表 | ❌ |
| `/api/v1/box/errors` | GET | 最近 50 条错误 | ❌ |
| `/api/v1/skills` 等 | GET/POST/PUT/DELETE | Skill CRUD、文件浏览、zip/GitHub 安装、preview | ✅ Skill 管理页 |

前端 `web/src/app/home/monitoring/components/overview-cards/SystemStatusCards.tsx` 已接入 `/api/v1/box/status`，展示 backend 名称、profile 与活跃 session 数。Sessions 与 errors API 仍未接入。
