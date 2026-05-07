# Box 系统 toB 商业化分析

> 更新日期: 2026-04-16
> 分支: `feat/sandbox` (LangBot + langbot-plugin-sdk)

---

## 1. 现有优势

| 能力 | toB 价值 | 代码位置 |
|------|---------|---------|
| **沙箱隔离执行** | 企业安全运行不受信代码的基础能力 | SDK `box/backend.py` |
| **多后端支持** | 适配不同企业容器基础设施 (Podman/Docker/nsjail) | SDK `box/runtime.py` `_select_backend()` |
| **Profile + locked 字段** | 运维锁定安全边界，LLM/用户无法绕过 | `pkg/box/service.py`, SDK `box/models.py` |
| **资源限制** | CPU/内存/PID 数限制防止资源滥用 | SDK `backend.py` `--cpus/--memory/--pids-limit` |
| **Workspace quota** | 磁盘用量控制 | `pkg/box/service.py` `_enforce_workspace_quota` |
| **静默降级** | Box 不可用不影响其他功能，降低部署门槛 | `pkg/box/service.py:78` `_available=False` |
| **孤儿容器清理** | 防止泄漏的容器持续占用资源 | SDK `backend.py` `cleanup_orphaned_containers` |
| **网络隔离** | `--network none` 防止数据外泄 | SDK `backend.py` start_session |
| **只读根文件系统** | `--read-only` 防止容器被持久篡改 | SDK `backend.py` start_session |
| **Host path 白名单** | `allowed_host_mount_roots` 限制可挂载目录 | `pkg/box/service.py` `_validate_host_mount` |

---

## 2. toB 差距分析

### 2.1 安全与合规

| 维度 | 现状 | toB 要求 | 优先级 |
|------|------|---------|--------|
| **WS relay 认证** | 无认证，任何人可 attach | 至少 token 认证 | **P0** |
| **安全策略** | policy.py 是死代码，实际无细粒度控制 | 工具级 allow/deny、沙箱模式控制 | **P0** |
| **审计日志** | 仅内存中 50 条 `_recent_errors` | 持久化审计：谁何时执行了什么、结果如何 | **P0** |
| **Host path 校验** | 黑名单策略，`/` 未拦截 | 白名单策略，默认拒绝 | **P1** |
| **数据驻留** | 无控制 | GDPR / 等保要求的数据隔离 | **P2** |

### 2.2 多租户

| 维度 | 现状 | toB 要求 | 优先级 |
|------|------|---------|--------|
| **租户隔离** | 无租户概念 | BoxSpec/Profile 绑定 tenant_id | **P0** |
| **RBAC** | 仅 token 认证 | admin/operator/viewer 角色权限 | **P0** |
| **资源配额** | 单一 workspace quota | 每租户 CPU 时间/内存/并发/执行次数配额 | **P1** |
| **Session 隔离** | 所有 session 共享 dict | 按租户分区，互不可见 | **P1** |

### 2.3 可靠性

| 维度 | 现状 | toB 要求 | 优先级 |
|------|------|---------|--------|
| **连接恢复** | 无重连、无心跳 | 自动重连 + 健康检查 | **P0** |
| **Session 清理** | 机会性（仅新建时触发） | 定时清理 + 独立 reaper | **P1** |
| **水平扩展** | 单 Box Runtime 实例 | 多实例负载均衡 | **P1** |
| **优雅降级** | 已有（_available=False） | 已满足基本要求 | 已有 |

### 2.4 可观测性

| 维度 | 现状 | toB 要求 | 优先级 |
|------|------|---------|--------|
| **监控指标** | 无 Prometheus metrics | session 数/执行延迟/资源用量/错误率 | **P1** |
| **结构化日志** | Python logging, 无结构化 | JSON 格式日志，含 trace_id/tenant_id | **P1** |
| **前端面板** | 无 Box UI | 状态面板：可用性/活跃 session/错误/资源用量 | **P2** |

---

## 3. SaaS 部署架构建议

### 3.1 方案 A: 共享 Box Runtime Pool (快速上线)

```
LangBot Instance ──> Box Runtime (共享)
                       ├─ tenant_id 标签隔离
                       ├─ Redis 配额计数器
                       └─ Container labels: langbot.tenant_id=xxx
```

- **优点**: 改动最小，加 tenant_id 到 BoxSpec/labels 即可
- **缺点**: 容器引擎共享，安全隔离弱

### 3.2 方案 B: 每租户 K8s Namespace + gVisor (推荐中期)

```
LangBot ──> K8s API
              ├─ namespace: tenant-xxx
              │    ├─ RuntimeClass: gVisor (runsc)
              │    ├─ ResourceQuota
              │    └─ NetworkPolicy
              └─ namespace: tenant-yyy
                   └─ ...
```

- **优点**: 强隔离（namespace + gVisor），原生 K8s 配额
- **缺点**: 需要重写 backend 为 K8s Job，部署复杂度高

### 3.3 方案 C: K8s Job 直接编排 (长期)

```
LangBot ──> K8s Job per execution
              ├─ 每次执行创建 Job
              ├─ Pod Security Standards
              ├─ 自动调度和资源分配
              └─ Job TTL Controller 自动清理
```

- **优点**: 最强隔离，天然水平扩展
- **缺点**: 冷启动延迟，架构重写

**推荐演进路径**: A → B → C

---

## 4. 配额体系建议

### 三层配额

| 层 | 实现 | 作用 |
|----|------|------|
| **内核层** | Docker `--cpus`/`--memory`/`--storage-opt` | 硬性资源上限，不可绕过 |
| **应用层** | Redis 原子计数器 | 并发 session 数/执行次数/CPU 时间预算 |
| **计费层** | 月度聚合 | 按租户计费（session-hours/execution-count） |

### Profile 与套餐映射

| 套餐 | Profile | locked 字段 | 配额 |
|------|---------|------------|------|
| Free | `offline_readonly` | network, host_path_mode, rootfs | 10 exec/天, 0.5 CPU, 256MB |
| Pro | `default` | (无) | 100 exec/天, 1 CPU, 512MB |
| Enterprise | `network_extended` | (按需) | 无限, 2 CPU, 1GB, 自定义镜像 |

### TOCTOU 配额修复

当前 `_enforce_workspace_quota` 的 TOCTOU 问题可通过两种方式解决:

1. **预留式配额** (应用层): Redis `INCRBY` 预扣额度 → 执行 → 成功则扣减，失败则回滚
2. **内核级限制** (Docker): `--storage-opt size=500m` 直接限制容器可写层大小

---

## 5. 优先实施路线

### Phase 1 (2-4 周): 安全基线

- [ ] WS relay 加 token 认证
- [ ] 接入或删除 policy.py
- [ ] Box 加重连和心跳
- [ ] 审计日志持久化（至少写文件/数据库）
- [ ] `security.py` 加 `/` 拦截，考虑白名单

### Phase 2 (4-8 周): 多租户基础

- [ ] BoxSpec 加 `tenant_id` 字段
- [ ] 容器 labels 加 tenant 标识
- [ ] Redis 配额计数器（并发/执行次数/时间）
- [ ] RBAC 基础框架
- [ ] 定时 session reaper

### Phase 3 (8-16 周): 生产就绪

- [ ] Prometheus metrics exporter
- [ ] 前端 Box 状态面板
- [ ] K8s backend 支持 (方案 B)
- [ ] 结构化日志 (JSON, trace_id)
- [ ] 水平扩展支持
