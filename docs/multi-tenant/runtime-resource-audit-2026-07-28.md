# LangBot Cloud Runtime 资源安全审查

日期：2026-07-28 至 2026-07-29

审查分支：

- LangBot：`feat/multi-tenants`，审查起点 `32abbb636f4455e965141d8d209b359dbfbb5aae`
- Plugin SDK：`feat/multi-tenants`，审查起点 `0cddf3c2bea5939c67b71e488a719e9903c28d17`

## 结论

本轮已覆盖 LangBot Core、Plugin Runtime 和 Box Runtime 的主要常驻对象、后台任务、队列、网络客户端、进程生命周期及数据库连接池。本轮定位到的攻击者可控或历史累积状态均已补充容量、超时、淘汰或确定性清理边界；修正后的高基数探针没有观察到随历史请求继续增长的活跃缓存。按本轮“代码审查 + 本地可重复测试”的验收口径，审查已经完成，未发现仍未处理的严重内存泄漏或 CPU 抢占路径。该结论不等于证明任意生产负载下不存在资源问题。

最终 Cloud 拓扑和生产环境不是本轮完成条件。代码级审查、跨仓全量测试和仓库 Dockerfile 构建的 Linux/cgroup v2 探针已经通过，但当前状态仍不能单独作为 Cloud 生产激活批准。完整的环境侧剩余清单见
[Cloud v2 仍待验证事项](./cloud-v2-pending-verification.md)。其中与本轮资源审查直接相关、上线前还必须完成的项目包括：

1. 在最终 Cloud 部署权限和 cgroup 拓扑下重复 nsjail、namespace 和 delegated cgroup v2 的 CPU、内存、swap、PID、文件句柄验证。本轮一次性 Linux 容器已经证明代码路径可工作，但普通容器和仅 `--privileged` 的 private cgroup namespace 都不满足条件。
2. 为 Cloud Box 提供并验证硬文件系统 quota provider。普通 nsjail bind mount 不能证明总字节数和 inode 硬配额，当前严格 readiness 按设计会失败关闭。
3. 使用最终生产配置分布继续做容量测试，并据此确定单实例 Workspace placement 上限。本轮真实 PostgreSQL 16 + RLS 启动测试已经覆盖 1,000 个各带 Provider、三类 Model、Bot、Pipeline、KnowledgeBase、MCP 和 Plugin setting 的 Workspace，启动加载耗时和 SQL 次数保持线性；5,000 Workspace 的合成三代替换探针也证明旧运行时会释放。仓库已新增可同时采集 Core/Plugin/Box HTTP、进程树和 cgroup v2 的 24 小时门禁工具，并在受 CPU、memory、swap、PID 硬限制的 Linux 容器中完成短时自检；但最终生产候选拓扑的 24 小时运行仍未执行。测试中的 fake adapter/requester/Plugin handler 仍不能替代真实平台 SDK、外部连接池和插件进程的容量数据；合法活跃租户本身仍会线性占用内存。
SDK 已先行发布到分支提交 `1d65ed301a6afc52150a998043f73cd6032c8162`，本提交集中的 LangBot
`pyproject.toml` 和 `uv.lock` 已精确钉住该提交。最终镜像仍需按待验证清单记录并核对实际安装版本。

## 覆盖范围

### LangBot

- 启动、停机、全局任务管理和运行时配置。
- PostgreSQL、Tenant UoW、RLS、迁移和共享 pgvector。
- HTTP、MCP、WebSocket、上传下载、S3/本地存储、维护任务和异步用户任务。
- QueryPool、Pipeline Controller、会话/对话、限流、第三方 Agent/LLM runner 和同步 SDK 桥接。
- PlatformManager 以及 DingTalk、QQ、Lark、WeCom、WeComCS、WeChatPad、LINE、Kook、Satori、OpenClaw Weixin、Telegram、Discord、Matrix、HTTP/WebSocket 等适配器。
- Plugin Runtime connector、插件包校验、Marketplace 下载、pip 安装输出和 desired-state reconcile。
- Box connector、admission、session/process 生命周期和 RPC 文件。
- RAG、向量后端、Skill、Storage、Telemetry 和日志缓存。

### Plugin SDK

- stdio/WebSocket transport、请求 waiter、action task 和文件传输。
- Runtime control handler、Workspace/generation fence 和 EventContext。
- 插件 artifact、Marketplace、pip 依赖安装、共享依赖环境、installation desired state、Supervisor 和 worker launcher。
- nsjail 参数、cgroup/rlimit、进程注册 capability 和 Runtime shutdown。
- Box admission、generation fence、session/process/reaper、RPC/relay WebSocket 和 nsjail backend。

## 主要修复

### 确定性生命周期

- 修复 `Application.shutdown()` 使用 `contextlib.suppress` 却未导入 `contextlib` 的问题。原行为会在实际资源关闭分支直接 `NameError`，阻断后续 Plugin、Box、HTTP 和数据库释放。
- `make_app()` 在任一启动 stage 或初始化失败时会关闭尚未返回给 `main()` 的半构建 Application；Telemetry、Box、Tool、Platform、Vector 和 HTTP manager 在初始化前即挂到 Application，避免初始化中途失败后清理器无法发现已经创建的连接、会话、子进程或后台任务。
- MCP streamable-HTTP session manager 现在随 Application shutdown 显式退出。
- MCP loader 按 `(instance, workspace, generation)` 管理 host task 和 session；任务完成会从注册表移除，代次推进会取消旧 host task 并关闭旧 session，reload/shutdown 会先清空现有运行时，避免 completed task 和旧代连接永久驻留。
- Platform bot reload/remove/shutdown 统一串行化，旧 bot、代理、adapter 任务和进程会先停止再从注册表移除。
- Model provider requester 新增异步关闭契约；provider reload/remove、Workspace generation 替换、全量 reload 和 Application shutdown 都会确定性关闭旧 requester，允许第三方 requester 安全持有自己的 HTTP client 或连接池。
- Plugin Runtime、Box Runtime、stdio transport、adapter 连接和共享 HTTP client 均补齐 close/cancel/await。
- HTTPX 有界流在超限异常或消费者取消时会立即关闭底层响应流；原来的 response hook
  只在正常读完后由 HTTPX 自动关闭，持久客户端反复收到超大响应时可能积累未释放连接。
  已消费响应在超限分支也会先 `aclose()` 再传播错误。
- `Application.dispose()` 只允许一个可追踪 shutdown task；重复的信号、窗口关闭或调用方清理不会铺开多个并行停机流程。
- Lark、微信、钉钉、企业微信和 QQ Official 的凭证交换后台任务统一进入 Application TaskManager，受全局/单 Workspace admission 约束并随应用停机取消；容量满时关闭尚未调度的 coroutine 并返回 429，不留下游离 task。
- `TaskCapacityError` 已下沉到无 Application/controller 依赖的纯错误模块。原来的 HTTP 过载异常路径会在特定冷启动导入顺序下触发 TaskManager/controller 循环导入，把应返回的 429 变成框架 500。
- S3 storage provider 在初始化失败或 Application shutdown 时关闭 botocore HTTP connection pool；Storage manager 在 provider 初始化前即挂到 Application，避免 bucket probe 失败后遗留 client。
- 修复 Coze runner 每次请求创建 `aiohttp.ClientSession` 却不关闭的问题；现在 runner 的 `aclose()` 会确定性关闭底层 API client。
- LINE SDK client 现在随 adapter 停止关闭；Plugin Runtime shutdown 回调只创建一个可追踪、可等待的后台任务，重复回调不会累积清理 task。
- SDK `lbp publish` 现在用上下文管理器关闭插件包上传文件；原实现的成功、API 错误和 HTTP 错误返回路径都会遗留文件句柄。
- Plugin worker、Box Docker/CLI backend、Box nsjail backend 和 nsjail 依赖安装在调用方取消时会 terminate/kill、读取管道并 `wait()` 回收子进程；Windows worker 的原生进程路径也进入相同的 `finally` 清理契约，避免取消安装、停机或超时后留下孤儿进程。
- Box 服务入口现在从 Runtime initialize、aiohttp app/runner setup、端口 bind 到主循环共用一个外层清理边界；建站期间的非 `OSError` 也会关闭 Runtime 和 reaper。WebSocket 控制模式端口绑定失败会退出并交给编排器重启，不再在没有任何可用 RPC/health 端口时永久等待；stdio 模式仍允许仅 relay 绑定失败后继续控制通道。
- Plugin artifact 解压、installation staging/activation/rollback/delete、共享依赖环境和 nsjail session 目录的关键文件系统变更均移出事件循环。已经开始的原子变更在取消时会先等待线程结束，再回滚临时目录、目标目录或旧 supervisor，不会让后台线程继续修改一个调用方已经认为清理完毕的路径。
- Core 和 SDK 的阻塞 executor 新增独立的有界清理入口。普通工作在容量耗尽时仍快速拒绝；已经拥有资源的 close/unlink/rmtree/进程回收则等待有限 worker 槽位并保证原子操作结束后再传播取消，避免过载恰好导致清理任务被拒绝。SeekDB、Milvus、S3、LINE、WeChatPad、MCP staging 和 TBox 临时文件等关键路径已接入。

### 有界队列、缓存和历史状态

- QueryPool 同时限制全局与单 Workspace 的 queued/running query；调度后不再被过载淘汰；历史 scope counter 有上限。
- Session、Conversation、WebSocket connection/proxy/message、rate-limit identity、task record/log、telemetry task、vector handle 和 adapter 私有队列均有容量或 LRU/TTL。
- SessionManager 现在维护 Workspace 二级索引和带 revision 校验的最小过期堆。新会话只扫描目标 Workspace 的有界会话集，TTL 回收只消费已过期堆前缀，全局 idle 淘汰使用最小堆；高频命中产生的旧堆项按活跃会话的有界倍数压缩。原实现会在每个攻击者可制造的新 launcher id 上扫描并排序实例全部会话。
- SDK 的 EventContext 和依赖准备锁使用 weak reference；generation、admission、installation、capability 和 completed-process 状态有上限。
- Plugin restart circuit 打开期间只有 `max_concurrent_restarts` 个 supervisor
  能持有冷却计时器/状态等待，其他 installation 睡眠在同一个 semaphore FIFO；
  probe 状态变更在调用者取消时仍会完成，避免 half-open 永久占用。
- Box nsjail 启动时只扫描一次 `/proc`，并流式删除遗留 session 目录；不再为每个
  遗留目录重复扫描全部进程或先把全部目录物化到内存。
- Box Skill discovery、目录列表和列表正文分别限制扫描 entry、package、返回 entry
  与累计文本字节；BFS 使用 deque，拒绝 inode 洪泛导致的 O(N²) 或无界列表。
- Core message aggregation 使用 `(instance, workspace, generation)` O(1) scope
  counter 做准入，不再为每个新 launcher 扫描全实例 buffer。
- Cloud remote MCP 的 idle execution fence 不再由每个 session 每 5 秒查询
  Workspace/ExecutionState；签名目录投影事务提交后将失效 scope 合并进一个有界
  cleanup worker。实际工具/资源调用前后仍保留数据库强校验。
- 空 Workspace 不再预分配 Model generation scope、Plugin installation set 或 Box generation event；只有 Workspace 实际拥有对应运行时资源或等待任务时才创建这些对象。
- Runtime RPC 文件同时限制单文件字节数和单连接未消费文件数量，连接关闭时清理连接拥有的临时文件。
- Box Runtime 维护实例与 Workspace 到活跃 session 的二级索引；创建、删除、过期、撤销和 shutdown 共用同一清理路径，避免每个租户 RPC 都扫描实例中的全部 session。
- Box Runtime 另外只索引“可过期 session”和“持有 managed process 的 session”。Cloud 的持久 `global` sandbox 不进入 TTL 索引，managed process 被禁用时进程索引为空；session 创建、周期 reaper、状态和 `/healthz` 因此不会随全部持久租户数线性扫描。测试把总 session 字典替换为禁止迭代的映射，仍能完成第二个持久 session 创建、reap、status 和 health。
- Core MCP loader 同样维护 Workspace/generation 到 session、host task 的二级索引；请求、代次回收和动态配置不再扫描实例中的全部租户 MCP session，已完成 task 的 done callback 会同步移除所有索引。
- Box admission 过期回收使用带 revision/generation 校验的最小堆，只访问已到期记录；重复续期产生的旧堆项会被忽略，堆大小超过活跃 grant 的有界倍数时压缩，不再在每次 RPC 上全表扫描所有租户 grant。
- 旧 QQ message ID/object cache 和 stdio MCP Workspace copy lock 不再随历史请求无限增长。
- LLM/Agent runner 的单次生成结果默认限制为 1 MiB，流式传输限制单事件 1 MiB、单请求累计 16 MiB，并限制最多 100,000 个流式事件，避免上游异常响应无限占用内存或 CPU。
- Marketplace JSON 限制为 1 MiB、插件包限制为 64 MiB；pip stdout/stderr 各最多保留 1 MiB，超出部分继续 drain 但不驻留内存。
- Plugin Runtime stdio/WebSocket 协议除 16 MiB 消息字节上限外，新增最多 4,096 个入站和出站碎片的对象数量上限；大消息的 UTF-8 编码、分片、拼接、JSON 编解码和 Pydantic 验证均在线程执行。WebSocket receive 异常使用稳定的 `ConnectionClosed` 类型，不再因库顶层未导出 `exceptions` 属性而在错误路径二次失败。
- HTTPX response hook 和 aiohttp 有界读取统一把第三方响应限制为 10 MiB；JSON 解析及诊断文本转换在线程执行，错误正文最多保留 4 KiB，避免大 JSON 在共享事件循环集中解析。
- 图片、data URI 和平台媒体默认限制为 10 MiB，Base64 在解码前先校验编码长度；Plugin binary storage 默认单值 10 MiB，并设置不可由错误配置绕过的 64 MiB 绝对上限。
- Skill 文本单文件限制为 1 MiB，Plugin UI 文件限制为 4 MiB，host edit 文件限制为 1 MiB；Box Skill ZIP、插件 artifact 和 GitHub Skill archive 同时限制条目数、单文件、解压总量和压缩比。
- SDK E2B 文件同步限制为最多 2,048 个目录项、1,024 个文件、单文件 10 MiB、总计 50 MiB；同步文件 IO 从事件循环移到线程。
- Dify 待提交表单、用户 Space OAuth state 和 Cloud launch JTI replay cache 改为带 revision 校验的最小过期堆；Space credits 使用按时间有序的 LRU/TTL 队列。原实现会在每次攻击者可触发的请求上扫描整个历史缓存并在满容量时再次线性寻找最旧项；现在过期回收为摊销 `O(log N)` 或仅消费已过期前缀，旧堆项会忽略并按活跃状态的有界倍数压缩。
- Cloud launch JTI cache 达到 4,096 个仍有效 token 时失败关闭，不再为了接纳新 token 淘汰仍有效的 replay 记录；否则攻击者可以在容量满后重放被提前遗忘的合法签名。
- Entitlement resolver 现在跟随 Cloud directory 的权威 Workspace 活跃集合。全量目录投影会丢弃已 fenced/removed Workspace 的历史 entitlement snapshot，delta 批量更新不会对每个变化重复扫描；provider 请求进行中发生目录撤销时，返回前的第二次 active fence 会阻止旧结果重新写回缓存。
- Cloud directory 的签名响应、Workspace、membership 和实例 active Workspace
  均新增可配置操作上限与绝对上限。闭源适配器按流读取响应并在 JSON/JWS 解析前
  拒绝超过 32 MiB 默认值的解压后正文；Manifest/entitlement/event endpoint 再
  分别限制为 256 KiB、256 KiB 和 2 MiB。entitlement 刷新最多并发并驻留 16 个
  原始响应，逐批验证成小型 snapshot 后释放；Core 在目录投影行锁保护的事务内检查最终
  active 数量，超限时回滚 Workspace、Account、membership、inbox 和 cursor，不会
  截断权威数据或让并发副本各自越过最后一个容量槽。
- Space 全量目录只投影 active Workspace，历史 archived Workspace 只在最多 100 个
  目标的签名 delta 中作为 tombstone 返回。注册创建新个人 Workspace 前通过
  PostgreSQL transaction advisory lock 串行执行全局 active 数量准入；达到上限
  返回 503，避免多个 Space 副本同时观察到最后一个空位。
- Monitoring 分页、offset、CSV export 和 session/message detail 均在 service
  边界执行实例配置上限与不可放大的绝对上限；detail 的完整统计改为 SQL aggregate，
  只物化有界的 tool/LLM/error 明细并显式返回 `detail_truncated`。默认分页 1,000、
  export 10,000、detail 2,000，绝对上限分别为 5,000、50,000、10,000。
- Token statistics 的时间序列不再把筛选范围内的全部 LLM call 拉回 Python 分桶；
  PostgreSQL 使用 `date_trunc`、SQLite 使用 `strftime` 在数据库中聚合，并只返回
  最近 1,000 个时间桶（绝对上限 10,000）。模型分组复用分页上限并在 SQL 中按 token
  排序、限制；两类结果都返回显式的 `*_truncated` 标志。
- Monitoring 过期数据每表每轮默认最多删除 4 个批次、绝对最多 100 个批次；本地/S3
  过期上传文件候选和每轮删除默认最多 1,000、绝对最多 10,000。单个历史数据量异常的
  Workspace 不再能让一次维护循环无限物化候选或持续清空全部 backlog。
- Workspace webhook 数量默认限制为 16、绝对限制为 64；管理查询和运行时 fan-out
  都只物化有界结果。实例同时发送的 webhook 请求默认限制为 16、绝对限制为 128；
  满载时直接跳过未获准目的地，不创建一批等待 semaphore 的 task。取消调用时会取消并
  await 已创建的所有请求任务，归还实例槽位。
- Local/S3 Storage 的对象读取在实际 IO 中只读取 `limit + 1` 字节，S3 body 在成功、
  超限和异常分支都会关闭；默认单对象 10 MiB、绝对上限 64 MiB。所有 scoped load
  以及 WebSocket attachment 都经过同一边界，写入也不能产生当前实例无法安全读取的对象。
- Valkey Search 的批量删除改为固定页流式搜索、删除并累计计数，不再把全部匹配 key
  保留在 Python 列表；每次删除后从 offset 0 继续，避免结果集缩短造成跳项，并设置
  1,000 轮绝对终止条件。

### CPU 和事件循环保护

- 修复旧 QQ `repeat_seed('')` 空输入无限循环。
- ZIP 校验/重打包、PIL、Base64、AES、JSON 解析、fsync probe、插件 artifact/依赖文件、Skill、S3、本地存储和维护目录扫描从事件循环移到线程。
- 公开 Slack、QQ Official、HTTP Bot、公众号、WeCom/WeComCS 回调体显式限制为 1 MiB；JSON/XML 解码移出共享事件循环。QQ、DingTalk、Satori、WeCom AI 和 WeChatPad 网关帧同样设置 1 MiB 上限或在解码前拒绝超限消息；KOOK zlib 数据使用 10 MiB 解压后硬上限，阻断小压缩包制造的大内存解压。
- HTTP Bot 的幂等键和 outbound session 现在均在写入前执行硬容量 admission；满额时只按固定 64 项预算检查最旧记录，不能先超限后整体清空，也不再在每条回复上扫描和排序全部 session。已有 session 继续 O(1) 访问，新 session 在没有可安全回收的空闲记录时失败关闭。
- Dashboard、Embed 和 Plugin Runtime 的协议 JSON 编解码在线程执行；Dashboard/Embed 在接收端提交 terminal error 后为发送端保留有界 drain 窗口并使用内部 sentinel 唤醒，不会因“任一方向结束即取消”在撤权错误帧发出前关闭连接。
- 租户配置的敏感词、内容忽略和群响应正则统一使用声明为直接依赖的 `regex` 引擎：最多 64 个 pattern、单 pattern 1,024 字符、输入 1 MiB、单次总匹配 CPU 预算 50 ms，并在线程中执行。超时、非法正则和替换放大均失败关闭；灾难性 `(a+)+$` 回归在 1 ms 测试预算内被中断。
- 原生 `read/write/edit/glob/grep` 文件工具移出事件循环并继承 Workspace 阻塞预算。目录列举、递归 walk、grep 文件/总字符、单行、pattern、结果和 regex CPU 均有硬上限；glob 只用固定大小最小堆保留最新 100 项，不再先把全部命中路径驻留内存。Box 内执行的 glob/grep 脚本同样限制命中集合、扫描量和正则时间。
- Dify、DingTalk、QQ、WeCom 等客户端复用连接并在生命周期结束时关闭，响应体和下载有字节上限。
- DashScope、TBox 等同步第三方 SDK 的调用和生成器迭代改为在线程执行；单个同步生成器最多消费 100,000 个事件。
- Dashboard 和 Embed WebSocket 改为任一收发 task 结束即取消并等待另一方向，避免发送端退出后接收 task 永久阻塞；两方向 task 同时继承从认证结果或 RuntimeBot 得到的可信 Workspace 阻塞预算。
- Plugin installation 生命周期全局串行化；不同租户的依赖 pip/nsjail 准备不会在安装高峰并发抢占 CPU。
- Plugin installation 的意外退出除了每 installation 的 jittered exponential backoff，还经过 Runtime 全局 restart launch 并发槽和失败窗口熔断。
  熔断冷却后只允许一个 half-open probe；probe 必须完成初始化并持续稳定后才恢复其他 installation。未在 30 秒内 ready 的 worker
  会被取消回收。健康指标输出 active launch、窗口失败数、circuit 状态和累计打开次数，24 小时门禁把 circuit 打开或尾段启动槽不归零判为失败。
- S3 同步 SDK 使用线程执行，并通过实例级 semaphore 限制并发；默认 `storage.s3.max_concurrency=16`，可通过实例配置和环境变量覆写。
- Box 子进程 stderr 以 64 KiB 块读取，日志最多每秒输出 4 个摘录并汇总抑制数量，避免无换行或刷屏输出制造无界缓冲与日志放大。
- Plugin worker 日志单行最多保留 64 KiB；Box managed-process stdout relay 以固定 64 KiB 块读取，不再依赖换行符，避免超长无换行输出触发 `StreamReader` limit 或堵塞子进程。
- Box generation fence 的代次更新改为只访问目标 Workspace 的 event 和 active-task 二级索引。原实现每次更新都会遍历全部 Workspace 的 fence/task 记录，10,000 个 Workspace 的第二阶段更新会退化为 O(N²) 并在 40 秒后仍未完成；修正后包括其他 SDK 高基数负载和本轮协议 offload 在内的当前完整双阶段探针耗时 `11.270s`。
- Box session 枚举、旧 generation 回收和 admission 计数均通过 Workspace 索引执行；admission 过期回收通过最小堆执行，不再在每次 RPC 上产生 O(实例总 session/grant 数) 的扫描。
- Model、Pipeline、RAG 和 Platform manager 均维护 Workspace 到运行时 key 的二级索引。Workspace generation 更新只清理目标 Workspace 的缓存和运行时，不再扫描实例内所有租户的 provider/model、pipeline、knowledge runtime 或 bot；回归测试使用禁止全局迭代的映射验证该边界。
- Cloud heartbeat 直接读取已加载且有容量边界的 Pipeline、MCP、KnowledgeBase 和 Bot registry 计数，不再为每个活跃 Workspace 依次打开 Tenant UoW、执行四类 COUNT 查询；这消除了租户数增长后每日周期性形成的串行 SQL/CPU 尖峰。OSS 模式仍保留数据库统计语义。
- 邀请、Monitoring 和 Storage 的三个周期清理 task 合并为一个
  `resource-maintenance` 调度器。调度器先等待首个 interval，不与启动加载争抢资源；
  同一到期周期只执行一次 active Workspace discovery，然后按 Workspace 串行运行
  有界 job，单 Workspace 失败不跳过其他 Workspace。默认相同的一小时周期由此从
  三次全租户发现和三个同时唤醒的任务收敛为一次发现和一个任务。
- Cloud 启动阶段先生成一份经过部署适配器和目录投影校验的 Workspace binding 快照，Model、Platform、Pipeline、RAG 和 Plugin 初始化共用该快照，初始化完成后立即释放；避免启动期间为每个 manager 重复执行整批租户发现和投影校验。
- Platform、Pipeline 和 RAG 的资源加载在使用已验证启动快照时不再为每个 Bot/Pipeline/KnowledgeBase 重新查询同一个 execution binding；常规请求和动态更新路径仍保留数据库 generation fence。
- MCP 初始 host 和 shutdown burst 由实例级 semaphore/批次限制；默认 `mcp.lifecycle_concurrency=16`，支持 `MCP__LIFECYCLE_CONCURRENCY` 覆写并硬性限制最大 128。初始加载不再先为每个 server 创建一个等待 semaphore 的 task，而是由一个可取消 dispatcher 每批最多物化 `lifecycle_concurrency` 个子 task；同时去掉了 ORM server/config 的双份临时列表，避免大量租户启动时集中占用 CPU、内存、socket 和文件句柄。
- Core、Plugin Runtime、Box Runtime 和独立 Plugin worker 的默认 `asyncio.to_thread()` executor 统一改为硬有界线程池。默认最多同时运行 8 个阻塞调用、排队 128 个，达到容量后立即抛出 admission 错误，不再使用 Python 默认 `ThreadPoolExecutor` 的无界工作队列保留任意数量的请求对象、Future 和闭包。每个可信 Workspace 的 running + queued 默认再限制为 4，并强制配置值不超过 worker 数的一半，避免单个租户先提交一整批同步工作占满全部 worker/FIFO 队列。Core 使用 `system.blocking_executor.max_workers/max_pending/max_inflight_per_scope`，原生支持对应的 `SYSTEM__BLOCKING_EXECUTOR__*` 覆写；SDK 进程使用 `LANGBOT_BLOCKING_EXECUTOR_MAX_*`，并分别限制全局最大值为 64/4096。
- Core、Plugin Runtime 和 Box Runtime 各自运行固定 1 秒间隔、仅保留最近 120 个样本的 event-loop lag monitor；健康快照输出 current/recent max/recent p95/进程期最大延迟和累计样本数。Plugin Runtime 的两个 WebSocket 端口现在都在免认证 `/healthz` 返回同一份无凭据、无租户标识的聚合 JSON，Box `/readyz` 同时附带资源快照。24 小时门禁默认拒绝缺失或停止的 monitor、超过 1 秒的 recent max、超过 250 ms 的尾段 recent p95 及 sample counter 回退。
- Workspace 阻塞预算由服务端认证后的 `RequestContext`、公开 bot 的 RuntimeBot、公开对象 key 中经 binding fence 验证的 Workspace、Platform/TaskManager 的 ExecutionContext，以及 SDK 入站 ActionContext 建立，不接受调用方伪造的租户 header。公开 webhook、公开对象下载、Dashboard/Embed WebSocket、普通 HTTP handler、Platform adapter 和 detached tenant task 均已覆盖。容量拒绝在 Core HTTP 路径返回稳定的 429，health/debug counter 分开报告 global 与 scope rejection。
- Argon2 密码 hash/verify 只允许一个实例级在途操作，额外并发立即返回容量错误而不是在 asyncio semaphore 中无限积累等待请求；该 CPU/内存密集工作同时使用独立的 `system:authentication` 阻塞作用域。Cloud 本身仍禁用本地密码登录。
- WeCom 扩展 API 的无限客户端超时改为 120 秒；平台 webhook 的 AES、媒体 Base64 与同步 SDK 调用均移出共享事件循环。
- 长文本转图片限制为 100,000 字符、256 行、800 万 RGBA 像素和 10 MiB 输出；
  超限时回退到 forward message。数字边界查找从重复 `count/find/sort` 改成线性扫描，
  PIL image 使用显式关闭，压缩步长为零时也能终止。
- Core 在每次 quota-enforced Box exec 前后遍历 Workspace 时使用非递归 DFS，并在
  超过字节 quota 或默认 100,000/绝对 1,000,000 个目录项后立即停止；目录项洪泛
  失败关闭，不再重复完整扫描 inode bomb。远程 outbox fallback 同时限制扫描项、
  文件数、单文件和总字节，Python project manifest 使用分块 hash 并限制单文件 10 MiB。

### 插件和 Box 资源隔离

- Plugin worker 数量受 `max_workers`、`max_total_cpus / max_cpus` 和 `max_total_memory_mb / max_memory_mb` 的最小值约束。
- Shared profile 强制 Linux 和 nsjail；Cloud 强制 `plugin.worker.require_hard_limits=true`；cgroup v2 delegation 不可用时拒绝启动。
- 每个 worker 下发 CPU、memory、swap、PID cgroup 限制，以及 process、open-file、file-size rlimit；插件 manifest 不能提高限制。
- Box nsjail 的 cgroup v2 路径现在同时设置 `memory.max` 和 `memory.swap.max=0`。修复前，48 MiB 沙盒可以把强制提交的 128 MiB 页面换出并正常退出，形成宿主 swap 抢占；修复后同一探针以 exit 137 被 cgroup 杀死。
- 仓库 Docker Compose/Kubernetes 示例显式下发 Core、Plugin Runtime 和 Box Runtime 的 blocking executor 上限；Kubernetes Box readiness probe 从仅报告进程存活的 `/healthz` 改为 `/readyz`，使 backend 或 managed-mode 隔离检查失败时不会把 Pod 加入就绪流量。
- 相同 digest 的已验证代码和依赖环境可只读共享，每个 installation 的 home/tmp/data 和进程独立。
- SDK 在发布共享依赖环境前最多校验 100,000 个目录项和 2 GiB 常规文件元数据总量；
  超限的 staging tree 会被原子清理而不会进入 worker。`requirements.txt` 和插件
  `manifest.yaml` 都使用 `limit + 1` 有界读取，manifest 额外限制为 1 MiB。
- Box session、managed process、completed process、admission record 和 RPC 文件均有实例级上限；Cloud entitlement 仍限制每个合资格 Workspace 一个 `global` session、零 managed process。
- Box Runtime 对上述实例级配置再增加不可放大的硬上限：session 5,000、managed
  process 1,024、completed process 10,000、admission record 250,000、RPC 单文件
  100 MiB、completed retention 86,400 秒。初始化与远程 INIT 对错误类型、负数和
  超上限均失败关闭，错误动态更新不会留下部分生效的 limit。

### PostgreSQL

- Cloud 强制 PostgreSQL 业务库、共享 pgvector 和允许的固定向量维度。
- pgvector Cloud 模式复用业务数据库的同一个 AsyncEngine，不创建第二个连接池。
- `database.postgresql` 新增并校验 `pool_size`、`max_overflow`、`pool_timeout_seconds`、`pool_recycle_seconds`；默认最大连接数为 `10 + 10`。
- `pool_size + max_overflow` 的绝对上限为 100，timeout/recycle 也有绝对上限；
  Cloud runtime 的 asyncpg 连接默认设置 60 秒 statement timeout、5 秒 lock
  timeout 和 60 秒 idle-in-transaction timeout，并分别限制最大 300/60/300 秒。
  一次性 release migration 不继承这些短 runtime timeout。
- `/healthz` 输出 pool 配置容量、checked-in/out、overflow、pool admission timeout
  累计数和 SQL timeout 配置；目录同时输出 active/max 与最近批次
  Workspace/membership 数，供生产 soak 和告警核对。
- Application shutdown 显式 dispose 业务引擎；standalone pgvector 仅关闭自己拥有的引擎。
- PersistenceManager 提供统一异步 shutdown；Cloud 常驻进程的启动失败、正常停机和一次性 release migration 的成功/异常路径都会释放数据库引擎。真实 PG catalog 测试还覆盖了“入口已经关闭后测试再次复用 manager 会重开 pool”的第二生命周期，严格资源告警模式下无 asyncpg socket/transport 遗留。

## 本轮采用的默认决策

- 优先 fail closed 或淘汰最老的 idle cache，不允许攻击者控制的历史 key 无限驻留。
- 插件依赖准备选择实例级串行化，以稳定 CPU/磁盘峰值；代价是批量安装耗时增加。
- PostgreSQL 使用一个显式有界共享连接池；未拆分 pgvector pool。
- 单实例目录的默认 active/full-snapshot Workspace 上限均为 1,000，membership
  上限为 20,000，签名响应上限为 32 MiB；绝对上限分别为 5,000、100,000 和
  64 MiB。Space 和 Core 必须配置为同一操作上限，生产值只能根据 V-08 容量曲线
  向下调整或在重跑全部门禁后提高。
- 第三方 runner 采用 1 MiB 单结果、16 MiB 单流总量和 100,000 个同步/异步事件的统一实例级安全上限；超限请求失败关闭。
- S3 默认允许 16 个并发阻塞调用，最大配置值 128；在没有独立 worker service 的前提下限制线程池排队和上游连接压力。
- MCP 生命周期默认并发 16、最大 128；该限制统一约束实例启动时的 session host 峰值和 shutdown 批次，不允许租户配置单独放大。
- Core 与 SDK 各进程的通用阻塞 executor 默认使用 8 个 worker、128 个 pending 槽位、每 Workspace 4 个在途槽位；它是实例/进程级共享背压，不由 Workspace 或插件 manifest 调高，单 Workspace 配置硬性不得超过 worker 的一半。生产值应按容器 CPU 和上游阻塞时延校准，不能把 pending 当吞吐配置无限放大。
- 插件包下载上限 64 MiB，pip stdout/stderr 保留上限各 1 MiB；这不会限制安装进程实际输出，只限制父进程内存中的诊断副本。
- 通用远程响应和媒体默认上限 10 MiB；错误诊断正文只保留 4 KiB。Plugin binary storage 默认 10 MiB、绝对上限 64 MiB；Skill 文本、Plugin UI 和 host edit 分别限制为 1 MiB、4 MiB 和 1 MiB。
- Storage scoped object 默认读写上限 10 MiB、代码绝对上限 64 MiB；Webhook 默认每
  Workspace 16 个、实例 16 个同时出站请求，代码绝对上限分别为 64 和 128。Box
  Workspace quota 扫描默认最多访问 100,000 个目录项、绝对最多 1,000,000 个。
- SDK 共享依赖环境在发布前最多接受 100,000 个条目、2 GiB 常规文件元数据总量；
  artifact manifest 与 requirements 各最多 1 MiB。这些是 Runtime 控制面在启动
  worker 前的保护，不替代最终文件系统的 byte/inode 硬配额。
- Monitoring 查询上限由 `monitoring.query_limits` 配置并支持原生环境变量覆写，但始终
  受代码绝对上限约束；cleanup 的每表批次数和 Storage 每轮文件数同样采用实例配置加
  绝对上限。时间序列默认/绝对上限为 1,000/10,000 个数据库聚合桶，模型分组复用分页
  上限。提高这些值必须计入 V-08/V-09 的数据库 CPU 与 Core RSS 容量曲线。
- Managed-process relay 保留 stdout 的原始换行，并按 64 KiB WebSocket frame 分块；不再承诺“一行对应一个 frame”。这是为无换行输出提供确定内存边界所需的协议收敛。
- 本轮没有把 Pipeline、Model、KnowledgeBase 等合法租户资源改成 lazy runtime。该改动会改变启动和请求语义，留到 Workspace placement/释放机制一起设计。
- 本轮没有为普通 nsjail 声称伪硬盘配额；严格 Cloud readiness 保持失败关闭。

## 验证结果

| 验证项 | 结果 |
| --- | --- |
| LangBot Ruff + `git diff --check` | 通过 |
| Plugin SDK Ruff + `git diff --check` | 通过 |
| LangBot 全量测试（含 unit/integration/Box/E2E） | `2855 passed, 33 skipped` |
| Plugin SDK 全量测试 | `1328 passed` |
| Space Go 全量测试与闭源 Cloud Adapter 测试 | Go `go test ./...` 通过；Adapter `40 passed` |
| Space PostgreSQL 16 Cloud v2 目录与并发容量准入 | 通过；两个注册并发争用最后一个槽位时 `1 success / 1 capacity rejection / 1 active Workspace` |
| Core PostgreSQL 16 Cloud runtime server timeout | 真实连接从 `pg_settings` 读回 `60000ms / 5000ms / 60000ms` 的 statement/lock/idle-transaction timeout，并显式 dispose |
| 真实 PostgreSQL 16 + pgvector 迁移/RLS/发布测试（严格资源告警） | `22 passed` |
| 真实 PostgreSQL 16 + RLS populated Cloud 启动容量 | 500 Workspace `6.178s / CPU 3.026s`；当前 1,000 Workspace 复跑 `12.109s / CPU 5.967s` |
| 较早 Core Dockerfile Linux 镜像构建与 `regex` 导入 | 通过，image SHA `8893a14053df`；该镜像使用旧 SDK pin，已失效，最终候选必须重建 |
| `ResourceWarning` + `PytestUnraisableExceptionWarning` 全量门禁 | Core 与 SDK 均通过，并已固化到 pytest 配置 |
| Plugin SDK Box 专项测试（含全局扫描回归保护） | `669 passed` |
| Docker Compose 渲染、Compose/Kubernetes YAML 解析与 diff 检查 | 通过 |
| Cloud soak 门禁解析/采样/判定单元测试 | `27 passed` |
| Core/Plugin SDK event-loop monitor 专项测试 | 两仓各 `7 passed`，包含真实 50 ms scheduler stall |
| Cloud soak Linux 硬限制短时自检 | 通过；CPU `0.5`、memory+swap `256 MiB`、PID `128` 均从 cgroup v2 读回，冷却尾段 verdict `pass` |
| Core 双阶段历史 churn 资源探针（使用当前本地 SDK 分支） | audit 通过，`12.559s` |
| Core 5,000 个 populated Workspace 三代容量探针（使用当前本地 SDK 分支） | 当前复跑通过，最大替换耗时比 `1.405` |
| Plugin SDK 双阶段资源探针 | audit 通过，`11.270s` |

两个仓库新增了可重复执行的历史 churn 探针，Core 另有 populated Workspace 三代替换探针：

```bash
# LangBot Core
PYTHONPATH=../langbot-plugin-sdk/src uv run python scripts/runtime_resource_probe.py --scale audit --json

# LangBot Core：5,000 个带代表性资源的 Workspace
PYTHONPATH=../langbot-plugin-sdk/src uv run python scripts/workspace_runtime_capacity_probe.py --scale audit --json

# LangBot Core：真实 PostgreSQL 16 + RLS populated Workspace 启动
TEST_POSTGRES_URL=postgresql+asyncpg://... \
LANGBOT_PG_CAPACITY_WORKSPACES=1000 \
uv run pytest \
  tests/integration/persistence/test_migrations_postgres.py::TestPostgreSQLTenantRuntime::test_populated_cloud_startup_is_linear_and_task_bounded \
  -q -W error::ResourceWarning --log-cli-level=INFO

# langbot-plugin-sdk
uv run python scripts/runtime_resource_probe.py --scale audit --json
```

Core audit 每个阶段执行 10,000 个空 Workspace 的真实 Model/Plugin manager 加载与 reconcile、25,000 次 Query、2,500 次 session churn、10,000 个限流身份、5,000 个 task 和 2,500 次 WebSocket churn。第一、第二阶段的保留状态完全一致：

- 20,000 个历史空 Workspace：Model scope/provider/LLM、Plugin Workspace set/installation 均为 `0`。
- 50,000 个历史 Query：活跃 query cache `0`，历史 scope counter `100`。
- 5,000 个会话身份：session cache `200`。
- 20,000 个限流身份：rate-limit container `10,000`。
- 10,000 个历史 task：task record `200`。
- 5,000 次 WebSocket churn：conversation 与 stream index 均为 `200`。
- event-loop task、线程和文件描述符保持 `1 / 1 / 6`；使用当前本地 SDK 分支的复跑中，第二阶段相对第一阶段 RSS 增长 `2,228,224 bytes`、tracemalloc current 增长 `344,669 bytes`，总耗时 `12.559s`。Session 淘汰改为 Workspace 索引和最小堆后，同一 audit 工作量相对此前 `16.150s` 明显下降。

Populated Workspace audit 为 5,000 个 Workspace 各加载一个 Provider、LLM、Embedding、Rerank、Pipeline、Bot、KnowledgeBase 和 MCP session，然后全部推进两个 generation：

- 三个阶段的活跃 provider/model、pipeline、bot、knowledge 和 MCP registry 均精确维持 `5,000`，不存在按历史 generation 增长。
- 到第三阶段，前两代的 requester、Bot adapter 和 MCP session 各 `10,000` 个全部收到确定性关闭；weak reference 断言旧代对象可被回收。
- event-loop task、线程和文件描述符保持 `1 / 1 / 6`；使用远端精确钉住 SDK 的当前复跑中，第三阶段相对第二阶段 RSS 增长 `1,245,184 bytes`，tracemalloc current 仅增长 `2,061 bytes`。
- 初始/第一次替换/第二次替换分别耗时 `1.893s / 2.549s / 2.659s`，最大替换耗时比为 `1.405`，未随历史代次出现 CPU 退化。
- macOS RSS sample 从初始的 `154,648,576` 增至第一阶段 `368,181,248`、第二阶段 `389,087,232` 和第三阶段 `390,332,416 bytes`；第二次替换只比第一次替换增加约 1.19 MiB，但“合法活跃租户资源的线性容量”仍必须作为 placement 容量输入。这里使用轻量 fake adapter/requester，不应把第一阶段约 204 MiB 增量外推为生产每租户成本。

Plugin SDK audit 每个阶段执行 25,000 次 loopback RPC、5,000 次安装 binding 激活/撤销、10,000 个 Workspace generation 更新和 2,500 次带 Workspace 上下文的 Box session 创建/删除。第一、第二阶段的保留状态完全一致：

- RPC waiter、stream queue、action task 和活跃 installation binding 均为 `0`。
- installation watermark 为有界的 `5,000`；Workspace generation record 为有界的 `10,000`，没有等待者时 generation event 为 `0`。
- generation active task/index、Box session、Box Workspace session index、creating/closing/background task 和 session lock 均为 `0`。
- event-loop task 和文件描述符保持 `1 / 7`；当前复跑第二阶段相对第一阶段 RSS peak 增长 `2,637,824 bytes`、tracemalloc current 增长 `289,746 bytes`，总耗时 `11.270s`。耗时增加来自本轮把大协议消息的 JSON/Pydantic、UTF-8 编码、分片和拼接移入有界线程池；结构状态和第二阶段 tracemalloc 增量保持平稳。

第二轮反向静态审查另外枚举了 Core 的 50 个显式 task 创建点和 204 个线程、阻塞调用及子进程调用点，以及 SDK 的 28 个显式 task 创建点和 62 个线程、阻塞调用及子进程调用点。第三轮独立复核继续从高基数定时器、目录遍历、准入全表扫描和取消竞态反推，新增关闭了 Plugin restart 冷却唤醒群、MCP idle 数据库轮询、nsjail orphan 的 O(session × process) 启动扫描、message aggregation 的 O(buffer) 准入及 Skill inode/文本列表边界。显式 task 均具有持有者、完成回调或 `finally` 回收路径；所有生产入口在第一次 `asyncio.to_thread()` 前安装有界默认 executor。Core、Plugin Runtime 和 Box 的公开 `/healthz`（Box `/readyz` 亦同）会输出各自的 aggregate runtime/resource counter 和 event-loop lag，供 soak 对比活跃量、pending、累计 capacity rejection 与调度延迟；不输出 debug key、控制 token、租户或插件身份。Plugin Runtime 的授权 debug info 复用同一资源快照，避免公开/私有指标语义漂移。

真实 PostgreSQL populated 启动门禁会先通过 release migration 创建最新 schema，再用无 `BYPASSRLS` 的临时 Cloud Runtime 角色启动。每个 Workspace 都含九类代表性资源，测试会走实际的 instance discovery、tenant UoW、启动 binding 快照和 Model/Platform/Pipeline/RAG/MCP/Plugin 加载路径：

- 500 Workspace：启动加载 `6.178s`，进程 CPU `3.026s`。
- 当前 1,000 Workspace 复跑：启动加载 `12.109s`，进程 CPU `5.967s`；相对此前 500 Workspace 的墙钟比为 `1.960`。
- `model_providers`、`llm_models`、`embedding_models`、`rerank_models`、`bots`、`legacy_pipelines`、`knowledge_bases`、`mcp_servers`、`plugin_settings` 九张表的 SELECT 次数均精确等于 Workspace 数，没有重复的全租户发现或超线性资源扫描。
- MCP host dispatcher、host task 和临时 Runtime 角色/asyncpg 连接在测试结束后均清空；严格 `ResourceWarning` 模式通过。

探针要求第二阶段的结构状态与第一阶段精确相等，并对第二阶段 RSS 与 tracemalloc 增长设置失败阈值。macOS 的 RSS 来源是 `getrusage` peak，因此这里验证的是峰值增量边界而非“当前 RSS 回落”；最终 Linux 24 小时 soak 仍需采集 current RSS/PSS 和 cgroup `memory.current`。

LangBot 全量测试的 33 个 skip 中，22 个是默认全量运行未提供 PostgreSQL/pgvector 而跳过的集成用例，10 个是未提供 Valkey，另 1 个是可选环境的 collection skip；真实 PostgreSQL 相关路径已由上表单独运行覆盖。Plugin SDK 的 26 个 warning 为现有 Pydantic v2 deprecation 与 aiohttp AppKey 建议；没有失败、未关闭资源或资源上限降级。Core 当前全量产生 194 个既有第三方/兼容性 warning；`ResourceWarning` 和 `PytestUnraisableExceptionWarning` 仍由 pytest 配置提升为错误，本轮没有此类泄漏告警。

Linux Runtime 探针使用上述镜像并只读挂载本地最新 SDK 源码：

- 普通容器：nsjail binary 可执行，但 namespace、mount、network 与 cgroup v2 检查均为 `false`，严格 readiness 按预期失败关闭。
- `--privileged` + private cgroup namespace：namespace、mount、network 通过，但 cgroup v2 delegation 为 `false`，仍按预期不能进入 Cloud ready。
- 一次性容器内建立可写 delegated cgroup 子树后：Plugin 与 Box cgroup 探针均为 `true`，nsjail namespace、mount、network 和 cgroup v2 均通过；硬文件系统与 inode quota 继续报告 `false`。
- `cpus=0.1` 的 1.0 秒 process-CPU busy loop 实际耗时 `9.13s`；`memory_mb=48` 下逐页提交 128 MiB 以 exit `137` 终止；`pids_limit=8` 下批量 fork 返回 `EAGAIN`。这些结果验证了 CPU、memory+swap 和 PID 的实际内核执行路径。
- 新增 `scripts/cloud_runtime_soak.py` 后，在同一 Linux 镜像的独立容器中设置 `--cpus 0.5 --memory 256m --memory-swap 256m --pids-limit 128`，工具从目标 cgroup 读回 quota `50000/100000 usec`、memory `268435456 bytes`、swap `0 bytes` 和 PID `128`。最终复跑中，32 MiB 子负载退出后的 4 秒冷却尾段 `memory.current` 稳健增长和斜率均为 `0`，平均 CPU `0.00132 cores`，OOM、memory pressure、PID max 和 throttle delta 均为 `0`，最终 verdict 为 `pass`。这只是采集器/判定器自检，不替代最终 24 小时生产候选运行。
- 本地实际启动 Plugin Runtime 后，控制端口与 debug 端口的公开 `/healthz` 均返回相同聚合 JSON，event-loop monitor 为 running，且正文不含 debug key。采集器显式绕过进程级 HTTP proxy 后，对控制端口执行 6 秒短时 endpoint gate：无失败，观测到的 recent max/p95 均为 `2.233 ms`，verdict 为 `pass`。
- 本地实际启动 Box Runtime（未创建 sandbox session）后，`/healthz` 与 `/readyz` 均返回 event-loop、blocking executor、session/process/task 聚合快照；monitor 为 running、样本持续增长，两个端点观测到的 recent max 均为 `2.265 ms`。SIGINT 后 aiohttp、Runtime、reaper 与 monitor 走统一清理路径并正常退出。

## 上线配置与监控门禁

最终 24 小时命令、运行位置、阈值语义、负载矩阵和产物要求见 [LangBot Cloud 24 小时资源 Soak 门禁](./cloud-runtime-soak-gate.md)。该工具默认把任一健康失败、OOM/memory pressure、PID limit、CPU throttling 超阈值、blocking executor rejection、冷却尾段内存持续增长或空闲 CPU 过高判为失败；生产运行必须使用 `--require-hard-limits`。

至少需要监控并告警：

- Core/Plugin Runtime/Box Runtime 的 RSS、CPU throttling、OOM、PID 数和 event-loop lag。
- 各进程 blocking executor 的 running、pending、inflight、active scopes、`global_rejected_total` 和 `scope_rejected_total`；pending 持续不归零或 rejection 增长都应告警。
- QueryPool、WebSocket、session、task、plugin worker、Box session 的当前量、容量拒绝和淘汰计数。
- Plugin crash/restart 频率、dependency prepare 耗时和失败率。
- PostgreSQL pool checked-out/overflow/wait timeout、事务耗时和连接错误。
- 临时文件、artifact、dependency environment、Box Workspace volume 的字节数和 inode。

生产 soak 应覆盖租户突发登录、批量插件 reconcile、插件崩溃重启、WebSocket 断连、Box 并发执行、PG pool 饱和和应用 SIGTERM；持续运行至少 24 小时，并验证负载停止后 RSS、task、socket、文件和子进程数量回到稳定基线。
