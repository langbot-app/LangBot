## 共享契约 usage-telemetry-v1（三个子任务都必须严格遵守，改动须先在父 issue LANG-492 提出）

背景和决策见父 issue LANG-492 的设计评论。Rock 已确认：
- 自部署实例按天汇总即可；
- lbctl 要做到命令级；
- 不做任何纯前端漏斗/前端埋点；
- 用量明细保留 180 天。

原则：不新增上报请求，也不新增原始上报行。用量计数放在进程内存里，作为差值随现有 `instance_heartbeat` 一起发送。不采集任何用户内容：KB、文件、prompt 的名称，query，文件名，URL 和错误 message 都不发。

### 1. heartbeat 新增字段（`features` 内）

```jsonc
{
  "usage": {
    "v": 1,
    "batch_id": "<uuid4，每个待发批次一个；重发同一批次时沿用原 id>",
    "since": 1731628800,           // 这批计数的起始 unix 秒
    "c": [["kb.file.ingest", {"engine":"langbot/rag-engine","parser":"builtin","ext":"pdf","outcome":"ok","err":"","dur":"<60s"}, 12]]
  },
  "kb_engines": ["author/name", ...],   // 当前已加载 KB 用到的引擎插件 ID，去重，最多 16 个
  "kb_file_count": 123,                 // 无法得到时为 -1（Cloud runtime 和其他资源计数一样给 -1）
  "deploy_source": "lbctl",             // 取环境变量 LANGBOT_DEPLOY_SOURCE，只接受 ^[a-z0-9_-]{1,32}$，否则省略
  "deploy_tool_version": "0.4.1",       // 取 LANGBOT_DEPLOY_TOOL_VERSION，只接受 ^[0-9A-Za-z.+_-]{1,32}$，否则省略
  "lbctl_versions": ["0.4.1"]           // 本批次内见过的 lbctl UA 版本，最多 5 个
}
```

- `c` 是 `[metric, dims, count]` 三元组列表。每个 Workspace 每批最多 256 条。
- dims 的 key 和 value 都只能取下表白名单。value 是不超过 64 字符的字符串，空值用 `""`。
- count 是 1..1000000 的整数。
- 只有一个周期内没有任何计数时才省略 `usage`。

### 2. metric 白名单（Core 只发这些，Space 只收这些，其余丢弃）

| metric | dims（全部必填，按此顺序） | 取值 |
| --- | --- | --- |
| `api.call` | group, method, client, status | group = RouterGroup.name；method = GET/POST/PUT/PATCH/DELETE；client = webui / lbctl / mcp / api_other；status = 2xx/3xx/4xx/5xx |
| `lbctl.cmd` | cmd, status | cmd 取 `X-LangBot-Client-Command`，须匹配 `^[a-z0-9-]+(\.[a-z0-9-]+){0,5}$` 且 ≤64 字符，否则记为 `other`；status 同上 |
| `lbctl.client` | version, os | 解析自 `User-Agent: lbctl/<version> (<os>/<arch>)`；version 规则同 deploy_tool_version；os = linux/darwin/windows/other |
| `kb.create` / `kb.update` / `kb.delete` | engine | engine = knowledge_engine_plugin_id（author/name），截断到 64 字符 |
| `kb.file.upload` | engine, ext, size | ext = pdf/docx/doc/md/txt/html/xlsx/csv/pptx/json/zip/other；size = <1M / <10M / <50M / >=50M |
| `kb.file.ingest` | engine, parser, outcome, err, dur | parser = builtin/plugin；outcome = ok/failed/cancelled；err = 异常类名（匹配 `^[A-Za-z0-9_.]{0,64}$`，成功时为 ""）；dur = <10s / <60s / <5m / >=5m |
| `kb.file.delete` | engine | |
| `kb.retrieve` | engine, origin, outcome, hit, dur | origin = pipeline/agent/plugin/webui_test/api；outcome = ok/failed；hit = empty/nonempty；dur = <500ms / <2s / <10s / >=10s |
| `kb.migration.run` | outcome | ok/failed |
| `ugc.share.preview` | type | prompt/skill/mcp/plugin |
| `ugc.share.submit` | type, mode, outcome, err | mode = new/update；outcome = ok/failed；err 同上 |
| `ugc.library.browse` | kind | messaging/agent/other |
| `ugc.prompt.apply` | kind | 同上 |
| `ugc.install` | type, source, outcome, unfilled | type = plugin/mcp/skill；source = market/community/local/github/other；outcome = ok/failed；unfilled = yes/no（仅 MCP 有意义，其他填 no） |

### 3. Core → Space 的确认语义

- Core 只在 `telemetry.send()` 返回 True 时，从计数器里**减去已发送的部分**。不能直接清零，因为发送期间可能有新的增量。
- 发送失败时保留该批次（同一个 batch_id），下一次连同新增量一起发。实现方式：把未确认批次和新增量合并成一个新批次，这时生成新的 batch_id。
- Space 用 `telemetry_usage_batches(batch_id)` 去重：已见过的 batch_id 直接忽略 usage，但 heartbeat 本身照常处理并返回成功。
- Space 对非法条目逐条丢弃，**绝不能**因为 usage 有问题而拒绝整个 heartbeat。

### 4. 存储与保留（Space）

- 新表 `telemetry_usage_daily(day date, workspace_uuid text, metric text, dims jsonb, dims_key text, count bigint, reporter_trusted bool, updated_at)`，主键 `(day, workspace_uuid, metric, dims_key)`，`count` 用 upsert 累加。
  - `dims_key` 是按 key 排序后的 dims 规范化 JSON。
  - `day` 取 Space 接收时间的 UTC 日期。
- 新表 `telemetry_usage_batches(batch_id text pk, created_at)`，保留 7 天。
- 新表 `content_events_daily(day, content_type, item_key, action, count)`，主键 `(day, content_type, item_key, action)`。
  - content_type = plugin/mcp/skill/prompt。
  - item_key = `author/name`。
  - action = view_detail/use/favorite/unfavorite/install/submit/approve/reject/unlist/relist/delete。
- 原始 heartbeat 行存入 `telemetry_events.features` 前必须删掉 `usage`。其余新字段体积很小，保留在 features 里。
- `telemetry_usage_daily` 和 `content_events_daily` 保留 180 天，`telemetry_usage_batches` 保留 7 天。都复用现有 retention ticker 分批删除。

### 5. 测试钩子

Core 新增一个未在文档中公开的环境变量 `LANGBOT_TELEMETRY_HEARTBEAT_SECONDS`（最小 30），用于覆盖 heartbeat 周期，方便 E2E 测试。不设置时行为不变。
