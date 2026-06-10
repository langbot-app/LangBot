# Box 系统测试覆盖分析

> 更新日期: 2026-06-02
> 状态更新: 自部署社区版已具备发布条件（box 可选、降级完善、无迁移欠债）；工具调用循环上限、配额遍历异步化、`host_path` 挂载白名单等已落地。剩余多租户 / 安全硬化项见 [SaaS 阻塞项清单](./box-issues.md)。
> 分支: `feat/sandbox` (LangBot + langbot-plugin-sdk)

---

## 1. 测试文件清单

### LangBot 仓库

| 文件 | 行数 | CI 运行 | 覆盖范围 |
|------|------|---------|---------|
| `tests/unit_tests/box/test_box_connector.py` | 106 | 是 | Connector 传输决策、WS relay URL、dispose、心跳/重连 |
| `tests/unit_tests/box/test_box_service.py` | 1224 | 是 | Service 核心逻辑（最全面） |
| `tests/unit_tests/box/test_workspace.py` | 147 | 是 | WorkspaceSession 路径重写、payload 构建 |
| `tests/unit_tests/provider/test_mcp_box_integration.py` | 707 | 是 | MCP Box 配置、路径重写、payload、shared-session/multi-process、runtime info |
| `tests/unit_tests/provider/test_localagent_sandbox_exec.py` | 444 | 是 | LocalAgent exec 流程、流式、Skill 激活 (Tool Call) |
| `tests/unit_tests/provider/test_tool_manager_native.py` | 249 | 是 | ToolManager 路由、native tool CRUD、路径穿越、6 工具暴露 |
| `tests/unit_tests/provider/test_skill_tools.py` | 582 | 是 | Skill 管理、Tool Call 激活、路径、authoring CRUD |
| `tests/unit_tests/test_skill_service.py` | 396 | 是 | HTTP service：skill CRUD、zip/GitHub install、文件浏览 |
| `tests/unit_tests/test_paths.py` | 23 | 是 | paths 工具 |
| `tests/unit_tests/test_preproc.py` | 134 | 是 | PreProcessor 注入 session 变量、bound skill 解析 |
| `tests/unit_tests/pipeline/test_chat_handler_logging.py` | 78 | 是 | Chat handler 日志相关回归 |
| `tests/integration_tests/box/test_box_integration.py` | 329 | **否** | 真实容器执行、超时、网络隔离 |
| `tests/integration_tests/box/test_box_mcp_integration.py` | 368 | **否** | Managed process、WS attach、shared-session 清理 |

### SDK 仓库

| 文件 | 行数 | CI 运行 | 覆盖范围 |
|------|------|---------|---------|
| `tests/box/test_backend_selection.py` | 255 | 是 | 显式 backend / local 模式探测顺序 / 配置变更触发 reselect |
| `tests/box/test_nsjail_backend.py` | 452 | 是 | nsjail 可用性、安装版 CLI vs 容器内 CLI、session、arg 构建、资源限制 |
| `tests/box/test_e2b_backend.py` | 482 | 是 | E2B SDK mock、session 生命周期、extra_mounts 同步 |
| `tests/box/test_skill_store.py` | 88 | 是 | zip preview/install、基础 file CRUD |

**总计**: 17 个测试文件, ~6,500 行测试代码; 其中 2 个集成测试（约 700 行）在 CI 中不运行。

> 较 2026-04-16 版增加：`test_skill_service.py`、`test_paths.py`、`test_preproc.py`、`test_chat_handler_logging.py` (LangBot)，`test_backend_selection.py`、`test_e2b_backend.py`、`test_skill_store.py` (SDK)。`test_nsjail_backend.py` 增加 CLI 兼容性 case (commit `feed530`)。

---

## 2. 覆盖良好的区域

| 区域 | 质量 | 说明 |
|------|------|------|
| BoxRuntime session 管理 | 优秀 | session 复用、冲突检测、TTL 配置、消失 session 重建 |
| BoxService Profile 系统 | 优秀 | 4 个内置 Profile、locked/unlocked 字段、timeout clamp |
| BoxService host mount 安全 | 优秀 | allowed_mount_roots、disallowed_roots、shared host root |
| BoxService workspace quota | 优秀 | 前置/后置配额检查、超额清理 |
| BoxService 输出截断 | 优秀 | 短/精确边界/长输出、独立 stderr |
| BoxService 可观测性 | 优秀 | 状态报告、error ring buffer、buffer 上限 |
| BoxService session 模板 | 良好 | `resolve_box_session_id` + `build_skill_extra_mounts` 在 service / native / mcp 三处都有覆盖 |
| RPC client/server 协议 | 优秀 | execute/get_sessions/delete/create/conflict error |
| BoxRuntimeConnector | 良好 | local/remote 模式、Docker 平台、relay URL、心跳与重连回调 |
| BoxWorkspaceSession | 良好 | payload 构建、managed process 路径重写、stage host file |
| BoxHostMountMode.NONE | 良好 | 枚举校验、workdir 约束 |
| NsjailBackend | 良好 | 可用性、安装版 vs 容器内、session 生命周期、arg 构建、资源限制 |
| E2BBackend | 良好 | mock SDK、session/extra_mounts 同步 |
| Backend selection | 良好 | 显式 backend 优先级、local 探测顺序、配置变更触发 reselect |
| MCP Box 集成 | 良好 | config model、路径重写、payload、shared-session 多 process |
| Native tool loader | 良好 | 6 工具（exec/read/write/edit/glob/grep）、路径穿越拦截 |
| LocalAgent exec 流程 | 良好 | 完整 tool call 循环、流式、system prompt 注入、Tool Call 激活 |
| Skill 系统 | 良好 | 加载、Tool Call 激活、marker、路径解析、authoring CRUD、HTTP service |

---

## 3. 覆盖缺失的区域

### 3.1 零测试 / 严重不足

| 区域 | 源文件 | 影响 |
|------|--------|------|
| **`security.py`** | SDK `box/security.py` (52 行) | `validate_sandbox_security()` 无任何测试。阻止 `/etc`/`/proc`/Docker socket 等危险挂载的安全函数从未被验证 |
| **`policy.py`** | `pkg/box/policy.py` (98 行) | 三层安全策略无测试（也是死代码） |
| **`skill_store.py` 边缘场景** | SDK `box/skill_store.py` (647 行) vs 测试 88 行 | GitHub 安装路径、`source_subdir` / `target_suffix` 组合、损坏 zip、文件冲突等场景未覆盖 |

### 3.2 未测试的关键路径

| 区域 | 说明 |
|------|------|
| **Session TTL 过期** | 测试配置了 `session_ttl_sec` 但从未推进时间验证过期清理 |
| **并发 session 访问** | 无并发 exec / 并发创建 / race condition 测试 |
| **Container backend (Docker)** | 仅通过集成测试覆盖（CI 不运行），单元测试全用 FakeBackend |
| **E2B 真实 sandbox** | 单测全是 mock，未对接真实 E2B API |
| **BoxRuntime shutdown()** | 在 test cleanup 中调用但未验证行为 |
| **BoxServerHandler 错误路径** | 畸形请求、未知 action 类型 |
| **WS relay** | 仅在集成测试中覆盖（CI 不运行） |
| **NsjailBackend managed process** | 完全未测试 |
| **MCP stdio 完整生命周期** | 依赖安装 → 进程启动 → 健康检查 → 多 process 并发 → 重试 |
| **BoxService start/stop_managed_process** | 单 process 流转有单测，多 process 互不阻塞主要靠集成测试 |
| **重连指数退避** | connector 单测覆盖回调接线，未实际跑完整重连周期 |

### 3.3 边缘情况缺失

| 区域 | 说明 |
|------|------|
| BoxSpec 校验 | 无效 session_id 格式、超长命令、env 特殊字符 |
| BoxSpec.extra_mounts | 重复 mount_path、与 host_path 冲突、绝对 vs 相对路径 |
| BoxExecutionResult | 仅 COMPLETED 和 TIMED_OUT，无 ERROR 状态测试 |
| 多后端 fallback | local 模式探测顺序仅靠 mock，无真实 Docker 不可用 → nsjail 真机 fallback 测试 |
| Profile YAML 加载 | 测试用硬编码字符串，未从真实 config.yaml 加载 |
| INIT 配置变更触发 backend 重建 | 单测仅在初始化场景验证 |

---

## 4. 集成测试 vs CI 的差距

CI 仅运行 `tests/unit_tests/`，以下场景**从未在自动化中验证**:

- 真实容器的创建/执行/销毁
- 容器网络隔离（`--network none`）
- 容器资源限制生效（cpus/memory/pids_limit）
- Managed process 的 WS 双向 I/O
- 多 process 同 session 并发 I/O
- 孤儿容器清理
- Session 删除清理容器
- 进程退出检测
- E2B 真实 sandbox 行为

**建议**: 在 CI 中加一个可选的 Docker-in-Docker 集成测试 stage，至少覆盖核心执行路径（exec / MCP attach / session 销毁）。
