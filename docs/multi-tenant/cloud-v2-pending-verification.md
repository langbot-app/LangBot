# Cloud v2 仍待验证事项

状态：`NOT APPROVED FOR SAAS ACTIVATION`

更新日期：2026-07-29

本文是 Cloud v2 首期上线前的剩余验证清单。它只记录尚不能由当前代码审查、
单元测试、集成测试、合成容量探针或短时 Linux 容器实验替代的证据。这里的项目
不属于 2026-07-29 代码与本地测试资源审查的完成条件，也不会让该审查持续保持未完成；
它们只在准备最终 SaaS 激活时重新进入验收范围。

相关文档：

- [多租户架构决策](./pending-architecture-decisions.md)
- [实现决策记录](./implementation-decisions.md)
- [Runtime 资源安全审查](./runtime-resource-audit-2026-07-28.md)
- [24 小时资源 Soak 门禁](./cloud-runtime-soak-gate.md)

## 1. 当前已形成的交付基线

- LangBot Core 全量 `2855 passed, 33 skipped`，Plugin SDK 全量
  `1328 passed`，闭源适配器 `40 passed`，Space Go 全量测试通过；三仓格式、
  静态检查和 `git diff --check` 已通过。
- Plugin Runtime 和 Box Runtime 的公开健康接口、event-loop lag 与有界
  blocking executor 指标已经过真实进程短时验证。
- 仓库 Dockerfile 构建的 Linux/cgroup v2 短时探针已证明 CPU、memory、
  swap 和 PID 限制代码路径可工作。
- PostgreSQL 16 + RLS 的 1,000 Workspace 真实启动测试，以及 5,000
  Workspace 三代替换合成探针已通过。
- Core 已精确钉住 Plugin SDK 提交
  `1d65ed301a6afc52150a998043f73cd6032c8162`。最终验证必须使用包含该提交的
  Core、Plugin Runtime 和 Box Runtime 镜像，不能混用旧 SDK。
- 独立资源复核已经移除 Cloud MCP 每会话 5 秒查询执行绑定的轮询，改由签名目录
  投影提交后向一个合并回收任务发布代次变化；工具与资源调用前后仍使用数据库
  execution fence。Plugin restart 冷却等待者、MCP 投影回收、消息聚合 buffer/scope
  均已纳入健康快照和 soak 归零门禁。
- 单实例目录现在有一致的操作容量契约：Space 在注册事务内通过 PostgreSQL
  advisory lock 串行执行 active Workspace check-and-create；Space 全量快照只返回
  active Workspace，并在查询阶段限制 Workspace/membership 数量；闭源适配器限制
  解压后的 HTTP 响应字节和签名目录基数；Core 在持有目录投影行锁的事务内再次
  COUNT active Workspace，超限时整批回滚且不推进 cursor。任何一层都不截断权威数据。
- Core Cloud PostgreSQL pool 的 `pool_size + max_overflow` 有绝对上限 100，
  Cloud runtime 连接默认强制 60 秒 statement/idle-transaction timeout 和 5 秒
  lock timeout；pool 使用量、超时累计数与目录 active/max 基数进入 `/healthz`。
  Box Runtime 的 session、process、admission record、RPC 文件和 completed retention
  配置也有不可被实例配置放大的绝对上限。
- Space 的 concurrent registration 容量准入已在一次性 PostgreSQL 16 上真实执行：
  两个 Account 同时争用最后一个 Workspace 槽位时，精确一个事务成功、一个事务
  得到 capacity error，最终 active Workspace 数为 1。active-only snapshot 与
  archived delta tombstone 的同一真实 PostgreSQL 集成流程也通过。
- Core Cloud manager 已连接一次性 PostgreSQL 16，并从 `pg_settings` 读回
  `statement_timeout=60000ms`、`lock_timeout=5000ms` 和
  `idle_in_transaction_session_timeout=60000ms`；测试结束后引擎已显式 dispose。
- 独立异常路径复核已补齐 HTTPX 超限/取消时的底层流关闭；Monitoring 查询、导出和
  detail 物化量均有实例上限与绝对上限，detail 统计使用数据库聚合。Token statistics
  不再拉取全部历史 LLM call 在 Python 中分桶，而由 PostgreSQL/SQLite 聚合并只返回
  有界的最新时间桶和模型分组，截断状态在响应中显式可见。邀请、Monitoring 和 Storage
  周期清理已合并为一个先等待首个 interval 的调度器，同一周期只进行一次 Workspace
  discovery；数据库删除批次和本地/S3 文件候选也有每轮硬上限。

以上结果是进入生产候选验证的前提，不是 SaaS 上线批准。

## 2. 尚有实现前置条件的阻断项

以下项目不是“再跑一次测试”即可关闭。必须先完成实现，再执行对应验收。

| 编号 | 阻断项 | 完成实现后的最低验收证据 |
| --- | --- | --- |
| B-01 | Cloud 插件缺少生产 egress policy | 证明插件只能访问允许的公网目标，不能访问 Core/Box/数据库、其他内部服务、loopback、link-local 或云 metadata endpoint |
| B-02 | Plugin installation 与 Box Workspace/Skill/root/tmp/home 缺少真实的 byte 和 inode 硬配额 provider | 在写入边界原子拒绝超额；并发写入、重启和配额耗尽后不能越界，也不能用目录扫描或事后清理冒充硬配额 |
| B-03 | 普通业务写入尚未具备贯穿 commit 的 generation-aware fence、同事务 business outbox，以及 generation cutover 后稳定的 durable-object 引用 | 在旧 generation 与新 generation 并发、事务提交竞态和重复投递下，旧 owner 不产生业务写入或外部副作用，outbox 可幂等恢复 |

任一 B 类项目未关闭时，不得把 24 小时 soak 的通过结果解释为可以上线。

## 3. 最终部署环境验证

### V-01：Plugin Runtime 与 Box 的 Linux 隔离

必须在最终 Cloud Pod security context、容器 runtime 和 cgroup 拓扑中验证，
不能使用开发机或权限不同的一次性容器替代。

验证内容：

1. nsjail 可以建立 mount、PID、IPC、UTS namespace 和 private `/proc`。
2. delegated cgroup v2 对每个插件进程和 sandbox 强制 CPU、memory、
   `memory.swap.max=0` 和 PID 上限。
3. open files、process 和单文件大小 rlimit 生效。
4. 插件不能枚举、读取或 signal Runtime 及其他 installation 的进程，
   不能读取其他 installation 的 home/tmp/data，也不能修改共享只读
   artifact/environment。
5. 超额只杀死或拒绝当前 installation/sandbox；Runtime、其他租户和健康接口
   继续工作。
6. 进程退出、取消、超时、generation 切换和 Pod SIGTERM 后，cgroup、nsjail
   目录、子进程和文件描述符均被回收。
7. 硬限制或 namespace 能力缺失时 readiness 失败关闭，不允许降级成普通进程。

通过证据必须包含实际容器安全配置、cgroup 文件值、探针原始输出和失败注入结果。

### V-02：Box 持久卷与硬存储配额

在 B-02 的 quota provider 实现后，必须验证：

1. Core 与 Box Runtime 通过随机 marker challenge 证明使用同一共享持久卷。
2. Workspace、Skill store、ephemeral root/tmp/home 的 byte 和 inode quota
   都在写入点生效。
3. 并发写、压缩包展开、文件同步、重启恢复和删除重建不能绕过配额。
4. 配额耗尽只影响目标 Workspace，其他 Workspace 仍能执行。
5. 任一硬存储能力缺失时 `/readyz` 返回非 2xx，Pod 不进入就绪流量。

### V-03：PostgreSQL 与 pgvector 生产边界

必须在最终 PostgreSQL endpoint、凭据和网络策略下验证：

1. migrator 与 runtime 使用不同 role；runtime role 无 superuser、
   `BYPASSRLS`、DDL、对象所有权、role membership 或额外 schema 权限。
2. runtime credential 只能连接目标 business database。需要专用
   cluster/endpoint，或经过测试的 HBA/proxy policy；database 内 catalog
   audit 本身不能证明这一点。
3. release migration Job 的 advisory lock、失败重试、回滚和精确 Alembic head
   校验有效；应用启动角色不能执行 migration 或其他 DDL。
4. 若使用 PgBouncer，transaction pooling、异常回滚和连接复用不会残留
   tenant context。
5. 故意遗漏应用层 Workspace filter 时，RLS 仍阻止跨租户读写。
6. 两个 Workspace 使用相同 `vector_id`、猜测其他 Workspace ID、后台任务和
   连接复用时，pgvector CRUD 均不能越权。
7. dimension mismatch、extension/schema/ACL drift 或 runtime audit 失败时，
   Core 启动失败且不回退到其他向量后端。

### V-04：最终镜像和配置一致性

生产候选验证前必须固定：

- Core、Plugin Runtime、Box Runtime 的不可变镜像 digest；
- LangBot 与 SDK commit；
- `data/config.yaml` 的非敏感摘要和所有环境变量覆写；
- Space 的 `CLOUD_V2_MAX_DIRECTORY_WORKSPACES` 必须与 Core
  `cloud.directory.max_active_workspaces` 和
  `cloud.directory.max_snapshot_workspaces` 一致；Space 的 membership 上限必须与
  Core `cloud.directory.max_snapshot_memberships` 一致；
- Core 的 PostgreSQL pool、statement/lock/idle-transaction timeout，以及 Plugin
  Runtime/Box Runtime 的全部实例级资源上限；
- PostgreSQL migration revision；
- Cloud Adapter、Space control plane 和 workload 的版本。

滚动更新、节点迁移、配置变化或任一镜像 digest 变化后，旧验证报告失效。

## 4. 多租户行为与故障注入

### V-05：目录、entitlement 与 generation

在真实 Space control plane、闭源 Cloud Adapter 和 Core 之间验证：

1. 注册自动创建个人 Workspace、owner membership、Free subscription、
   entitlement snapshot 和 outbox 事件，且重试不重复创建。
2. 邀请、成员变更、套餐变更和 Workspace 撤销只影响目标 Workspace。
3. 全量快照与增量事件覆盖乱序、重复、断点续传、缺页、签名错误、
   high-water gap、snapshot coverage 和消费者重启。
4. Core、Plugin Runtime 或 Box 重启后，权威 desired state 可恢复；
   本地进程表和缓存不是唯一真相。
5. generation/revision 切换期间，旧 callback、RPC、WebSocket、Box relay、
   plugin worker 和缓存写入全部失败关闭。
6. 为未来多副本预留的 replica-local cursor 语义通过故障注入：
   一个副本追平不能使另一个副本跳过本地 cache 刷新。
7. 同时使大量 plugin worker 因系统性故障退出，证明 restart launch 全局并发受限、
   失败阈值触发 Runtime circuit、冷却后只有一个 half-open probe，且 probe 未稳定前
   其他 installation 不会继续重启；冷却计时器/状态等待者数量不得超过全局 restart
   并发，取消 probe 不得把 circuit 永久卡在 half-open；24 小时门禁必须把 circuit
   打开或 `gate_waiters` 未归零判为失败。
8. 使用大量空闲 remote MCP session 做 generation 切换，证明目录投影只创建一个
   合并回收任务，不产生每 session 周期数据库查询、计时器或同时唤醒；旧 session
   最终关闭，`mcp_projection_retirements` 和
   `mcp_projection_reconcile_active` 在冷却期归零。

### V-06：套餐、Box 与 stdio MCP

1. Free/非 Pro Workspace 不会自动获得 managed sandbox。
2. 合资格 Workspace 最多只有一个持久 `global` sandbox，且新增 Workspace
   不创建专属 Runtime、Pod、PVC、database、schema、role 或连接池。
3. Cloud 即使 `box.enabled=true`，也不能 create/update/test/start stdio MCP；
   旧记录和直接 API 调用同样失败关闭，且不创建 `mcp-shared` session。
4. OSS 默认仍是单 Workspace、多用户，stdio MCP 保持兼容，多租户能力不会被
   未签名配置或普通环境变量开启。

### V-07：跨租户安全回归

至少使用两个恶意测试 Workspace 验证：

- 同 digest 插件只共享只读代码和依赖；进程、secret、日志及所有可写目录隔离。
- 同 author/name/version 但 digest 不同的 artifact 不共享目录。
- Plugin Host API、Box RPC、对象 key、WebSocket、RAG、storage、model/session
  cache 和平台回调不能接受调用方伪造的 Workspace scope。
- 撤销 entitlement、删除 installation 或 generation 切换后，已有长连接和
  in-flight 请求不能继续访问旧权限。

## 5. 生产候选容量与 24 小时门禁

### V-08：真实容量曲线

现有 fake adapter/requester/Plugin handler 探针不能替代真实容量数据。必须使用
计划上线的平台 SDK、外部 HTTP/WebSocket 连接池、真实插件进程、真实
PostgreSQL/pgvector 和代表性 Workspace 配置分布，测量：

- 空 Workspace、活跃 Workspace、每个启用插件和每个 Pro sandbox 的边际
  RSS、线程、文件描述符、连接和 PostgreSQL pool 成本；
- 启动、目录重放、批量 reconcile 和故障恢复的耗时与峰值；
- remote MCP 数量增加及目录 generation 批量切换时的数据库 QPS、回收队列和
  event-loop lag，确认不存在与 session 数量成比例的空闲轮询；
- 在最大 retention/backlog 和并发 Dashboard 请求下执行不带时间范围的 Monitoring
  overview/token statistics，验证 SQL 分桶、statement timeout、响应截断和 cleanup
  追赶不会形成 PostgreSQL CPU 尖峰或 Core RSS 增长；
- 单实例可批准的 Workspace、活跃 Bot、plugin worker 和 sandbox 上限。

容量上限必须写入生产配置与告警，不能只保留在测试报告中。
代码中的默认值和绝对上限只是失控配置的最后防线，不等于生产容量结论。V-08 必须
根据最终镜像的真实曲线把 Space 与 Core 的匹配上限调到已验证容量以内；如果最终
批准值高于当前默认 1,000 active Workspace，必须重新执行目录启动、故障恢复和
24 小时门禁。

### V-09：24 小时资源 soak

使用 [标准 24 小时命令](./cloud-runtime-soak-gate.md#标准-24-小时命令)，并强制
`--require-hard-limits`。工作负载至少覆盖：

1. 注册、邀请、登录和 entitlement 刷新；
2. plugin reconcile、依赖准备、调用、崩溃与重启；
3. Dashboard/Embed/平台 WebSocket 建连、突发消息和断连；HTTP Bot 覆盖
   高基数 session/idempotency、硬容量拒绝、空闲回收及 callback 堵塞；
   remote MCP 覆盖大量空闲连接、批量 generation 切换和合并回收；
4. Box session、文件同步、并发 exec、输出与清理；
5. PostgreSQL pool 接近容量、事务超时和恢复；
6. Core、Plugin Runtime、Box 分别 SIGTERM 和恢复。

最后至少保留 30 分钟无测试流量冷却。任一健康失败、OOM/memory pressure、
PID limit、blocking executor rejection、超阈值 CPU throttling/event-loop lag、
目录 `active_workspaces > max_active_workspaces`、数据库 pool 使用量超过配置容量、
冷却尾段内存持续增长，或 Plugin restart `gate_waiters`、MCP 投影回收、
消息聚合 buffer/scope 等临时 gauge 不回落都判为失败。
标准 soak 工具已自动比较目录 active/最近批次与各自配置上限，并比较 PostgreSQL
`checked_out` 与配置 pool 容量；名为 `core` 的标准 endpoint 缺少任一容量指标、
current/max 只出现一半、数值非法或任一样本越界都会直接失败。

必须归档：

- 原始 `cloud-soak-samples.jsonl`；
- 最终 `cloud-soak-report.json`；
- 三个镜像 digest、Core/SDK commit；
- 生产配置摘要、数据库 migration revision 和 workload 版本；
- 故障注入时间线及关联日志/trace。

## 6. 本轮不作为验收条件的后续事项

以下能力已明确暂缓，不能混入当前验证结果，也不能以“尚未验证”为理由临时发明方案：

- Workspace export、释放、delete、单 Workspace restore 和在线迁移；
- Workspace 级 BYOK E2B WebUI 配置；
- 多 Core/Plugin Runtime/Box replica 的 lease store 与调度实现；
- PostgreSQL 多 shard、dedicated shard 和跨地域部署；
- 多 CloudInstance、Cell Router 或 Workspace Placement。

这些事项需要后续单独决策。首期实现仍需保留稳定 UUID、generation fence、
幂等事件和无副本地址泄漏的协议边界。

## 7. 关闭规则

每个 B/V 项只能通过以下方式关闭：

1. 记录被测 commit、镜像 digest、配置摘要和环境拓扑；
2. 保存可复现命令、原始输出和失败注入证据；
3. 由报告明确给出 pass/fail，不能只依赖日志中“看起来正常”；
4. 任一生产候选输入变化后，重跑受影响的验证。

在 B-01 至 B-03 全部实现，且 V-01 至 V-09 均有当前生产候选版本的通过证据前，
Cloud v2 状态保持 `NOT APPROVED FOR SAAS ACTIVATION`。
