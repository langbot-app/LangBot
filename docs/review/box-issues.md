# Box 系统 — SaaS 发布前阻塞项

> 更新日期: 2026-06-02
> 分支: `feat/sandbox` (LangBot + langbot-plugin-sdk)
> 相关文档: [架构分析](./box-architecture.md) | [Session 作用域](./box-session-scope.md) | [Runtime 对比](./box-vs-plugin-runtime.md) | [测试覆盖](./box-test-coverage.md) | [toB 分析](./box-tob-analysis.md)

## 范围说明

**自部署社区版已具备发布条件**：默认 stdio 模式、box 为可选项；box 关闭 / 不可用时后端、前端、工具、skill、stdio-MCP 均能干净降级（清晰报错、不崩溃）；配置向后兼容（旧 `data/config.yaml` 可直接启动）；无新增 ORM 模型、无迁移欠债；市场安装失败不会破坏实例。CI 全绿。

本清单**只保留发布 SaaS / 多租户 / 公网暴露前必须处理的阻塞项**。社区版（可信、单运营者、内网）不受这些项阻塞——它们的风险面在"不可信调用方能直接触达 Box 控制面"或"多租户共享资源"的场景才成立。

## 已解决（社区版发布前）

| 项 | 处理 |
|----|------|
| 工具调用循环无上限 (原 #13) | `localagent.py` 增加 `MAX_TOOL_CALL_ROUNDS=128`，超限优雅终止（`cafef1a3`） |
| 配额校验同步遍历阻塞事件循环 (原 #10) | `_enforce_workspace_quota` 改 async，工作区遍历走 `asyncio.to_thread`（`cafef1a3`） |
| `host_path` 挂载白名单 (原 #3 的 LangBot 侧) | `pkg/box/service.py` `allowed_mount_roots` 白名单，空列表时拒绝一切宿主挂载 |
| 重复的 `_is_path_under` (原 #12) | 已去重，仅保留一处定义 |
| 重连 / 心跳 / Windows 兼容 / nsjail image 字段 / 前端 Box 状态接入 | 见上一轮 review 记录，均已合入 |

---

## SaaS 阻塞项

### S1. Box 控制面无认证 — Critical

- **位置**: SDK `box/server.py` — Action RPC WS (`/rpc/ws`) 与 managed-process relay (`/v1/sessions/{id}/managed-process/{pid}/ws`)
- **现状**: 两个 WS handler 在 `ws.prepare` 后直接服务，无任何 token / 鉴权；box 默认绑定 `0.0.0.0:5410`。任何能触达该端口者可发起 `EXEC`、创建 session、attach 任意 session 的 managed-process stdin/stdout、甚至 `SHUTDOWN`。LangBot→box 的 INIT 也未下发任何凭证。
- **缓解现状**: 默认 `docker-compose.yaml` 的 `langbot_box` 未把 5410 发布到宿主（爆炸半径限于内网 bridge）；但 box 挂载了 `/var/run/docker.sock`，同网络的任意服务（含被攻破的插件）→ 宿主 root。若运营者把 5410 发布到宿主或独立以 `0.0.0.0` 起 box，则完全裸奔。
- **要求**: INIT 时下发 token，两个 WS 路由按连接校验（query/header）。这是 SaaS 的**头号**阻塞项。

### S2. 无 exec 授权模型（policy.py 死代码） — High

- **位置**: LangBot `pkg/box/policy.py`（`SandboxPolicy` / `ToolPolicy` / `ElevatedPolicy` 全项目无引用）；`pkg/provider/tools/loaders/native.py`；`pkg/provider/tools/toolmgr.py`
- **现状**: 原生工具（`exec/read/write/edit/glob/grep`）按"box 是否可用"全有或全无地暴露，**无 per-pipeline 的 exec 网关 / 工具白名单 / 沙箱模式 / 权限提升控制**。只要 box 可用，任何使用 local-agent + 函数调用模型的 pipeline 都能跑任意 shell。
- **要求**: 接入 policy.py（或等价机制），按 pipeline 控制是否暴露 `exec`、可用工具白名单、沙箱网络/只读模式。

### S3. 会话资源无界（DoS） — High

- **#5 session 数量无上限**: SDK `box/runtime.py` `_get_or_create_session` 的 `_sessions` dict 无容量限制——可变 `session_id` 的恶意调用可无限创建容器，耗尽宿主 CPU/内存/PID/磁盘。
- **#8 无定时回收**: 过期 session 仅在 `_get_or_create_session` 时机会性清理，无独立周期任务；一波创建后转静默会永久泄漏容器。
- **要求**: `max_sessions` 上限（拒绝或 LRU），加独立周期 reaper（如 60s）。

### S4. 工作区配额无内核级限制（TOCTOU） — Med-High

- **位置**: LangBot `pkg/box/service.py` `_enforce_workspace_quota`（应用层 read-then-check）；SDK 侧 `workspace_quota_mb` 仅记录/透传，无 `--storage-opt size=` 等内核/FS 限额
- **现状**: 执行前后两次检查之间存在竞态窗口；单条命令（`dd`/`fallocate`）可在检查间隙撑爆磁盘，事后检查只能补救。
- **要求**: Docker `--storage-opt size=` 做内核级限制，或 Redis 原子计数预留式配额。

### S5. 挂载校验缺口 — Med-High

- **位置**: SDK `box/security.py` `_BLOCKED_HOST_PATHS_POSIX`；`box/backend.py` 的 `extra_mounts` 处理
- **现状**: ① SDK 黑名单仍不含 `/`（前缀匹配，`host_path="/"` 可通过，挂载整个宿主 fs）；用户 home、`/usr`、`/opt`、`/tmp` 也未拦截。② `validate_sandbox_security` 只校验 `spec.host_path`，**从不遍历 `spec.extra_mounts`**——LangBot 侧 `allowed_mount_roots` 也只校验 `host_path`。当前 `extra_mounts` 仅由 `build_skill_extra_mounts` 内部填充（agent 不可达），但缺乏纵深防御：一旦 S1 的无认证 RPC 被触达，extra_mounts 可挂任意宿主路径，两层都不拦。
- **要求**: SDK 黑名单加入 `/`（或改白名单）；`extra_mounts` 在 SDK 与 LangBot 两侧都纳入挂载校验。

### S6. 容器加固缺失 — Med

- **位置**: SDK `box/backend.py` 的 `docker run` 组装
- **现状**: 未设置 `--cap-drop=ALL`、`--security-opt=no-new-privileges`、非 root `--user`；叠加挂载 docker.sock，逃逸面偏大。
- **要求**: 默认加上上述加固 flag（需回归常用 skill 不被破坏）。

### S7. 全局锁内执行慢操作（扩展性） — Med

- **位置**: SDK `box/runtime.py` `_get_or_create_session`：`self._lock` 持有期间调用 `backend.start_session()`（`docker run` / nsjail 启动 / E2B `Sandbox.create`）
- **影响**: 冷启动（镜像拉取数秒、E2B >1s）期间串行阻塞所有并发请求——多租户负载下整个 Box runtime 停顿。降级表现是延迟而非失败。
- **要求**: 锁内只做状态检查与注册，容器创建移到锁外。

### S8. 其他硬化 / 跟进 — Low

- **#9** SDK `box/server.py` 直接读 `runtime._sessions` 私有字段、绕过锁，并发下可能读到不一致状态——应加公共访问方法。
- **#16** `pkg/provider/tools/toolmgr.py` `execute_func_call` 按优先级分发，plugin/MCP 若有同名 `exec/read/write/...` 工具会被静默遮蔽——应加命名空间或冲突告警。
- **#4** SDK `box/runtime.py` INIT/handshake 与 backend 实例化的残留竞态（仅"纯远程 WS box 先启动、LangBot 后连"场景成立；stdio/compose 路径下 config 经 env 在 spawn 时已就位，无竞态）——应在 INIT 完成前拒绝业务 action。
- **#11** `extra_mounts` 在容器创建时固定（SDK `runtime.py` 兼容性检查不含 extra_mounts）；长生命周期共享 session 后续新激活的 skill 不会挂上（当前缓解：创建时挂上 pipeline 绑定的全部 skill）——动态绑定场景需销毁重建或文档说明。
- **#21** 集成测试未进 CI：容器实际执行、E2B 真机、managed-process WS attach 仅本地可跑。安全关键路径缺自动化覆盖——SaaS 前建议加 Docker-in-Docker CI stage 或合并前手动 checklist。
