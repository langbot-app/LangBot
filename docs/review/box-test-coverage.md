# Box 系统测试覆盖分析

> 更新日期: 2026-04-16
> 分支: `feat/sandbox` (LangBot + langbot-plugin-sdk)

---

## 1. 测试文件清单

### LangBot 仓库

| 文件 | 行数 | 测试数 | CI 运行 | 覆盖范围 |
|------|------|--------|---------|---------|
| `tests/unit_tests/box/test_box_connector.py` | 79 | 6 | 是 | Connector 传输决策、WS relay URL、dispose |
| `tests/unit_tests/box/test_box_service.py` | 1168 | 40+ | 是 | Service 核心逻辑（最全面） |
| `tests/unit_tests/box/test_workspace.py` | 144 | 7 | 是 | WorkspaceSession 路径重写、payload 构建 |
| `tests/unit_tests/provider/test_mcp_box_integration.py` | 642 | 22 | 是 | MCP Box 配置、路径重写、payload、runtime info |
| `tests/unit_tests/provider/test_localagent_sandbox_exec.py` | 444 | 5 | 是 | LocalAgent exec 流程、流式、Skill 激活 |
| `tests/unit_tests/provider/test_tool_manager_native.py` | 249 | 14 | 是 | ToolManager 路由、native tool CRUD、路径穿越 |
| `tests/unit_tests/provider/test_skill_tools.py` | 569 | 20 | 是 | Skill 管理、激活、路径、authoring CRUD |
| `tests/integration_tests/box/test_box_integration.py` | 324 | 6 | **否** | 真实容器执行、超时、网络隔离 |
| `tests/integration_tests/box/test_box_mcp_integration.py` | 361 | 6 | **否** | Managed process、WS attach、session 清理 |

### SDK 仓库

| 文件 | 行数 | 测试数 | CI 运行 | 覆盖范围 |
|------|------|--------|---------|---------|
| `tests/box/test_nsjail_backend.py` | 384 | 18 | 是 | nsjail 可用性、session、arg 构建、资源限制 |

**总计**: 10 个测试文件, ~4400 行, ~144 个测试; 其中 12 个集成测试在 CI 中不运行。

---

## 2. 覆盖良好的区域

| 区域 | 质量 | 说明 |
|------|------|------|
| BoxRuntime session 管理 | 优秀 | session 复用、冲突检测、TTL 配置 |
| BoxService Profile 系统 | 优秀 | 4 个内置 Profile、locked/unlocked 字段、timeout clamp |
| BoxService host mount 安全 | 优秀 | allowed_roots、disallowed_roots、shared_host_root |
| BoxService workspace quota | 优秀 | 前置/后置配额检查、超额清理 |
| BoxService 输出截断 | 优秀 | 短/精确边界/长输出、独立 stderr |
| BoxService 可观测性 | 优秀 | 状态报告、error ring buffer、buffer 上限 |
| RPC client/server 协议 | 优秀 | execute/get_sessions/delete/create/conflict error |
| BoxRuntimeConnector | 良好 | local/remote 模式、Docker 平台、relay URL、dispose |
| BoxWorkspaceSession | 良好 | payload 构建、managed process 路径重写 |
| BoxHostMountMode.NONE | 良好 | 枚举校验、workdir 约束 |
| NsjailBackend | 良好 | 可用性、session 生命周期、arg 构建、资源限制 |
| MCP Box 集成 | 良好 | config model、路径重写 (6 case)、payload |
| Native tool loader | 良好 | 文件 CRUD、目录列表、路径穿越拦截 |
| LocalAgent exec 流程 | 良好 | 完整 tool call 循环、流式、system prompt 注入 |
| Skill 系统 | 良好 | 加载、激活、marker、路径解析、authoring CRUD |

---

## 3. 覆盖缺失的区域

### 3.1 零测试 (Critical)

| 区域 | 源文件 | 影响 |
|------|--------|------|
| **`security.py`** | SDK `box/security.py` | `validate_sandbox_security()` 无任何测试。阻止 `/etc`/`/proc`/Docker socket 等危险挂载的安全函数从未被验证 |
| **`policy.py`** | `pkg/box/policy.py` | 三层安全策略（SandboxPolicy/ToolPolicy/ElevatedPolicy）无测试（也是死代码） |

### 3.2 未测试的关键路径

| 区域 | 说明 |
|------|------|
| **Session TTL 过期** | 测试配置了 `session_ttl_sec` 但从未推进时间验证过期清理 |
| **并发 session 访问** | 无并发 exec / 并发创建 / race condition 测试 |
| **Container backend (Podman/Docker)** | 仅通过集成测试覆盖（CI 不运行），单元测试全用 FakeBackend |
| **BoxRuntime shutdown()** | 在 test cleanup 中调用但未验证行为 |
| **BoxServerHandler 错误路径** | 畸形请求、未知 action 类型 |
| **WS relay** | 仅在集成测试中覆盖（CI 不运行） |
| **NsjailBackend _run_nsjail** | 总是被 mock，实际 subprocess 调用未验证 |
| **NsjailBackend managed process** | 完全未测试 |
| **MCP stdio 完整生命周期** | 依赖安装 → 进程启动 → 健康检查 → 重试 |
| **BoxService start_managed_process** | 仅集成测试覆盖 |

### 3.3 边缘情况缺失

| 区域 | 说明 |
|------|------|
| BoxSpec 校验 | 无效 session_id 格式、超长命令、env 特殊字符 |
| BoxExecutionResult | 仅 COMPLETED 和 TIMED_OUT，无 ERROR 状态测试 |
| 多后端 fallback | 仅单后端配置，无 Podman 不可用 → fallback Docker 测试 |
| Profile YAML 加载 | 测试用硬编码字符串，未从真实 config.yaml 加载 |

---

## 4. 集成测试 vs CI 的差距

CI 仅运行 `tests/unit_tests/`，以下场景**从未在自动化中验证**:

- 真实容器的创建/执行/销毁
- 容器网络隔离（`--network none`）
- 容器资源限制生效
- Managed process 的 WS 双向 I/O
- 孤儿容器清理
- Session 删除清理容器
- 进程退出检测

**建议**: 在 CI 中加一个可选的 Docker-in-Docker 集成测试 stage，至少覆盖核心执行路径。
