# LangBot Cloud 24 小时资源 Soak 门禁

`scripts/cloud_runtime_soak.py` 是生产候选拓扑的最终资源稳定性门禁。它不替代单元测试、历史 churn 探针或 nsjail 隔离测试；它把以下三类证据按同一时间轴采集并给出可机读的 pass/fail：

- Core、Plugin Runtime 和 Box Runtime 的 HTTP liveness/readiness。
- 三个 Python 进程的 event-loop recent max/p95 调度延迟。
- Linux `/proc` 进程树的 current RSS、累计 CPU、线程、文件描述符和子进程数。
- cgroup v2 的 `memory.current/peak/events`、swap、CPU usage/throttling、PID current/events 和实际硬限制。

生产批准必须使用 cgroup 证据。`--pid` 只适合本地诊断，因为进程指标无法证明 OOM kill、PID limit 或 CPU throttling。

## 运行位置

建议把采集器放在独立的 node agent 或监控 sidecar 中，并只读挂载三个目标容器的 cgroup 路径。不要把采集器和样本文件放进被测容器自己的 cgroup/数据卷，否则采集器的 CPU、内存和 page cache 会污染目标数据。

Kubernetes/containerd 生成的 cgroup 路径不是稳定 API。每次生产候选部署都必须从实际 pod/container ID 解析，不能从 pod 名猜路径。传入的每个目录都必须至少可读：

- `memory.current`、`memory.events`
- `cpu.stat`、`cpu.max`
- `pids.current`、`pids.events`

最终门禁应加 `--require-hard-limits`。该选项要求每个目标 cgroup 都能观察到有限的 CPU quota、memory、swap 和 PID 上限；任一值为 `max` 都失败。

## 标准 24 小时命令

```bash
uv run python scripts/cloud_runtime_soak.py \
  --duration 24h \
  --startup-grace 5m \
  --sample-interval 15s \
  --cooldown 30m \
  --analysis-window 30m \
  --http-timeout 5s \
  --max-memory-growth-mib 64 \
  --max-memory-slope-mib-per-hour 32 \
  --max-tail-cpu-cores 0.5 \
  --max-throttled-period-ratio 0.25 \
  --max-event-loop-lag-ms 1000 \
  --max-event-loop-p95-lag-ms 250 \
  --require-hard-limits \
  --endpoint core=http://langbot:5300/healthz \
  --endpoint plugin=http://langbot-plugin-runtime:5400/healthz \
  --endpoint box=http://langbot-box:5410/readyz \
  --cgroup core=/host-cgroup/CURRENT_CORE_CONTAINER \
  --cgroup plugin=/host-cgroup/CURRENT_PLUGIN_RUNTIME_CONTAINER \
  --cgroup box=/host-cgroup/CURRENT_BOX_RUNTIME_CONTAINER \
  --samples-file artifacts/cloud-soak-samples.jsonl \
  --report-file artifacts/cloud-soak-report.json \
  --workload uv run python tests/load/cloud_candidate_workload.py
```

`--duration` 是包含启动观察、负载和冷却期的最大墙钟时间。工作负载必须在截止时间前退出并至少留出 30 分钟冷却；否则门禁会终止负载并失败。若负载由外部系统控制，可以省略 `--workload`，但必须保证最后 `--analysis-window` 完全无测试流量，该窗口才可解释为空闲尾段。

工作负载命令的 stdout/stderr 会转发到采集器 stderr，不会混入 stdout 的最终 JSON 报告。命令以独立 process group 启动；超时或中断时整组收到 TERM，10 秒后仍未退出则收到 KILL。

凭据只能通过 workload 进程环境或 secret mount 注入，不能放在命令参数中。最终报告只记录可执行文件名和参数个数，不保存参数正文；采集器也拒绝带 userinfo、query 或 fragment 的健康 URL。

## 必须覆盖的负载

同一候选版本至少要覆盖：

1. 大批 Workspace 注册、成员邀请、登录和 entitlement 刷新。
2. Plugin installation reconcile、依赖准备、正常调用、进程崩溃与重启。
3. Dashboard/Embed/平台 WebSocket 建连、突发消息和批量断连。
4. Box session、文件同步、并发 exec、managed-process 输出和清理。
5. PostgreSQL pool 接近容量、事务超时和恢复。
6. Core、Plugin Runtime、Box 分别收到 SIGTERM 后的优雅重启。

工作负载不能把 API 过载拒绝当作成功吞掉。默认情况下，Core health 中 blocking executor 的 global/scope rejection counter 只要增长，门禁即失败；只有专门验证“过载会正确返回 429”的独立测试才可以使用 `--allow-rejections`，该次运行不能作为生产批准证据。

## 判定规则

整个有效观察期内出现以下任一情况即失败：

- 健康接口请求失败、非 2xx、Core `code != 0`，或 Box `ready=false`。
- `memory.events.high/max/oom/oom_kill/oom_group_kill` 增长。
- `pids.events.max` 增长。
- cgroup 单调计数器回退，表示目标很可能发生了未记录的重启或 cgroup 替换。
- CPU throttled-period ratio 超过配置阈值。
- 任一健康采样窗口的 event-loop recent max 超过 1 秒，或冷却尾段 recent p95 超过 250 ms。
- 健康接口缺少 event-loop monitor、monitor 未持续运行，或其 sample counter 回退。
- blocking executor rejection counter 增长。
- Plugin Runtime restart circuit 的累计打开次数增长。
- Core 目录 active Workspace、最近 snapshot/delta Workspace 或 membership 基数
  超过各自配置上限，或 PostgreSQL `checked_out` 超过配置 pool 容量；相关 current/max
  指标只出现一半或 max 非法也失败。

负载结束后的冷却尾段还必须满足：

- `memory.current`/RSS 的稳健首尾增长和线性斜率不能同时超过阈值。
- 平均 CPU 核数不超过 `--max-tail-cpu-cores`。
- event-loop recent p95 不超过 `--max-event-loop-p95-lag-ms`。
- blocking executor `pending` 至少回到过零；不能整个尾段持续积压。
- Plugin Runtime restart coordinator 的 active launch、half-open probe 和
  circuit open remaining time 必须回到零，`gate_waiters` 必须至少归零一次。
- Core 的 MCP projection retirement queue/worker 和 message aggregation
  buffer/scope 必须至少归零一次。
- telemetry、QueryPool、MCP host/dispatch、Box creating/closing/background 等临时 gauge 不能继续增长。

内存判定要求“增长量”和“斜率”同时越界，避免几 MiB allocator/page-cache 噪声在短窗口被外推成很大的每小时斜率。最终报告仍保留实际增长与斜率，人工审查时不能只看 verdict。

## 产物与退出码

- `--samples-file`：逐样本 JSONL，写入后立即 flush，供时序图和故障定位。
- `--report-file`：最终汇总、阈值、资源硬限制、OOM/PID/throttle delta、尾段斜率和 workload 状态。
- stdout：与 report 文件相同的最终 JSON；workload 日志只写 stderr。

退出码：

- `0`：全部门禁通过。
- `1`：采样完成但资源门禁失败。
- `2`：CLI 参数或目标配置错误。

必须保存原始 JSONL、最终报告、三个镜像 digest、LangBot/SDK commit、生产配置摘要和工作负载版本。滚动更新、节点迁移或镜像变化后，旧报告不能继续作为新候选版本的批准证据。
