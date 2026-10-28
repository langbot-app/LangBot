# LongTermMemory issue planning

本文档记录 `langbot-longterm-memory` 插件后续优化计划。当前阶段的原则是：

- 不要求修改 LangBot core 或 langbot-plugin-sdk。
- 保持 LongTermMemory 作为插件实现，而不是把 memory 变成 LangBot 内置业务功能。
- 保留当前 L1/L2 两层架构，不急于引入 L0 goals、L3 procedural memory 等新事实层。
- 优先补齐生产可用性：写入策略、召回质量、治理、审计、整合、透明性。

## Current position

当前实现已经满足核心长期记忆闭环：

- L1 core profile：稳定事实，存储在 plugin storage，并注入 system prompt。
- L2 episodic memory：事件记忆，写入 vector DB，通过 metadata 做 scope 隔离和检索。
- 自动注入：PromptPreProcessing 阶段注入 L1，并基于当前消息自动召回少量 L2。
- 主动工具：`remember`、`recall_memory`、`update_profile`、`forget`。
- 管理命令：`!memory`、`!memory profile`、`!memory search`、`!memory list`、`!memory forget`、`!memory export`。
- 纠正机制：带 `correction` / `fact-update` / `clarification` 标签的新 episode 会尝试 supersede 相似旧 episode，降低旧记忆权重。

当前不会自动删除记忆：

- L1 profile 只有显式 `remove` 或覆盖才会改变。
- L2 episode 只有 `forget` 或 `!memory forget <episode_id>` 才会删除。
- superseded episode 仍然保留在 vector DB 中，只是 importance 降低并标记 `superseded_by`。
- time decay 只影响召回排序，不会硬删除。

## Design stance

不建议把插件对外模型扩成多层：

- 不新增 L0 Active Goals 作为 LongTermMemory 的核心层。
- 不新增 L3 Procedural Memory 作为 LongTermMemory 的核心层。
- goals / tasks 更像独立任务管理或个人助手插件，不应塞进长期记忆插件第一阶段。
- procedural knowledge 可暂时用 L1 notes、session profile 或 L2 summary episode 表达。

推荐模型仍然是：

- L1：当前稳定事实和画像。
- L2：可追溯事件和历史。
- Derived views：摘要、索引、候选记忆、归档状态、审计日志、supersede 关系。这些是派生能力，不是新的事实来源。

## Issue 1: Clarify L1/L2 memory write policy

Priority: P0

### Background

当前工具已有基本说明，但模型仍可能过度调用 `remember`，或把稳定偏好写成 L2 episode，把短期事件写进 L1 profile。长期运行后，这会带来噪声和画像污染。

### Goal

明确告诉模型：

- 什么时候写 L1。
- 什么时候写 L2。
- 什么时候不要写。
- 纠正类信息如何同时处理 profile 和 episode。

### Scope

更新以下位置：

- `components/tools/remember.yaml`
- `components/tools/update_profile.yaml`
- `components/tools/recall_memory.yaml`
- `components/event_listener/memory_injector.py` 中的注入说明
- `README.md` 的 usage / best practices 部分

### Suggested policy

L1 profile 只保存稳定、低频、当前有效的事实：

- 姓名、身份、长期偏好。
- 长期沟通风格。
- 群聊或会话长期约定。
- 用户明确纠正后的当前事实。

L2 episode 保存有时间语义、历史价值或上下文价值的事件：

- 计划、行程、近期状态。
- 某次对话中的决定。
- 用户明确希望以后参考的事件。
- 纠正发生的历史记录。

不要保存：

- 一次性寒暄。
- 临时情绪，除非用户明确希望记住。
- 敏感隐私、密钥、凭证、一次性验证码。
- 可能伤害用户或他人的推断性标签。
- 未经确认的群聊八卦或第三方隐私。

### Acceptance criteria

- Tool prompts 对 L1/L2 边界表述一致。
- README 中有 `When to write L1 / L2 / nothing` 小节。
- 至少包含中文群聊和个人私聊示例。
- 纠正类信息的处理规则清晰：更新 L1，必要时写 L2 保留历史。

### Non-goals

- 不引入自动记忆提取。
- 不修改 LangBot core 或 SDK。

## Issue 2: Add memory KB health check

Priority: P0

### Background

L2 依赖 metadata filter 做隔离。README 已说明 Milvus / pgvector 等固定 schema 后端不适合当前实现，但用户仍可能误配。仅靠文档提醒不够。

### Goal

增加运行时健康检查，帮助用户确认当前 pipeline 的 memory KB 是否可用且隔离可靠。

### Proposed command

```text
!memory health
```

### Checks

- memory KB 是否已创建。
- memory KB 是否绑定到当前 pipeline。
- embedding model 是否配置。
- 当前 vector backend 是否能在写入后通过 `user_key` metadata filter 正确检索。
- `vector_list` / `vector_delete` 是否能按 filter 工作。

### Suggested probe

写入两条临时 probe：

- `user_key = health_probe_a`
- `user_key = health_probe_b`

然后分别按 user_key 查询，确认不会串 scope。最后删除 probe。

### Acceptance criteria

- `!memory health` 输出 `OK`、`WARN` 或 `ERROR`。
- filter probe 失败时，明确提示该后端不适合 LongTermMemory。
- health check 不会留下 probe 记忆。
- README 安装步骤中增加 health check 建议。

### Non-goals

- 不要求 LangBot core 暴露 vector backend capability API。
- 不强制阻止用户使用不兼容后端，但要给出明确风险提示。

## Issue 3: Improve episodic recall with hybrid search and exact-match fallback

Priority: P1

### Background

当前 L2 recall 主要依赖 vector similarity，再叠加 recency、importance、speaker、update signal。中文群聊、人名、ID、短标签、episode_id 等场景下，纯向量召回可能不稳定。

LangBot 的 vector API 已支持 `search_type`、`query_text`、`vector_weight`。Chroma 和 SeekDB 已有 hybrid / full-text 能力，插件可以优先使用，不需要改 core。

### Goal

提升 recall 稳定性，特别是：

- 中文短词。
- 人名和群成员名。
- sender_id / sender_name。
- tags。
- episode_id。
- 精确事件名称。

### Scope

- `MemoryStore.search_episodes`
- `LongTermMemoryEngine.retrieve`
- `recall_memory` tool 参数和文档
- `memory_engine.yaml` retrieval / creation schema

### Proposed config

```yaml
retrieval_strategy: vector | hybrid | auto
vector_weight: 0.7
exact_match_boost: true
```

Default should be `auto`:

- use hybrid when backend supports it or when it succeeds;
- fallback to vector when hybrid fails.

### Acceptance criteria

- Automatic L2 recall and `recall_memory` both support the configured strategy.
- Hybrid mode passes `query_text` to `vector_search`.
- Exact match on episode_id can find the episode without relying on embedding.
- Exact match on sender_name / tags can boost or include results.
- If hybrid search fails, recall falls back to vector and logs warning.

### Non-goals

- 不实现新的 CJK tokenizer。
- 不引入外部 search service。

## Issue 4: Add episode lifecycle status

Priority: P1

### Background

当前只有 delete 和 supersede。旧记忆不会自动删除，superseded episode 仍可能被召回，只是权重降低。长期运行后，需要更清晰的生命周期。

### Goal

为 L2 episode 增加生命周期状态，避免默认召回过期或被整合的记忆，同时保留可追溯性。

### Proposed statuses

```text
active
superseded
archived
deleted
```

Recommended semantics:

- `active`: 默认可召回。
- `superseded`: 默认不召回，或强降权；管理命令可查。
- `archived`: 普通 recall 不返回；管理命令可查。
- `deleted`: 物理删除或 tombstone，取决于审计策略。

### Scope

- episode metadata 增加 `status`
- auto-supersede 时设置旧 episode `status=superseded`
- recall 默认过滤 `status=active`
- 管理命令支持 `--include-superseded` 和 `--include-archived`

### Acceptance criteria

- 新写入 episode 默认 `status=active`。
- superseded episode 默认不会进入自动 recall。
- `!memory list --include-superseded` 可以查看旧记忆。
- `!memory search` 默认只查 active，可选包含 archived/superseded。

### Non-goals

- 不默认自动物理删除。
- 不要求历史数据迁移；缺失 status 的旧数据可视为 active。

## Issue 5: Add L2 export/import and scoped deletion commands

Priority: P1

### Background

当前 `!memory export` 只导出 L1 profiles。L2 可通过 KB UI 导入 JSON，但没有完整的命令式 export/import 和批量治理能力。

### Goal

让管理员可以迁移、备份、清理当前 scope 的 L2 episodes。

### Proposed commands

```text
!memory export l2
!memory import l2 <json>
!memory delete --speaker <sender_id>
!memory delete --tag <tag>
!memory delete --before <timestamp>
!memory delete --status archived
```

### Export fields

```json
{
  "id": "episode_id",
  "content": "...",
  "tags": ["..."],
  "importance": 2,
  "timestamp": "2026-05-15T00:00:00Z",
  "user_key": "...",
  "sender_id": "...",
  "sender_name": "...",
  "source": "agent",
  "status": "active",
  "superseded_by": ""
}
```

### Acceptance criteria

- Export 只导出当前 `user_key` scope。
- Import 默认写入当前 scope，不允许导入覆盖其他 scope。
- 批量删除必须 scope-safe。
- 删除前返回 preview 或至少返回将删除数量。
- 批量删除写 audit log。

### Non-goals

- 不实现跨 scope 全量备份。
- 不开放任意 raw metadata filter 给模型。

## Issue 6: Add memory audit log

Priority: P1

### Background

长期记忆涉及误写、误删、隐私和治理。当前 delete / update 没有独立 audit 记录，排查困难。

### Goal

记录所有会改变 memory state 的操作。

### Operations to audit

- `remember`
- `update_profile`
- `forget`
- L2 import
- L2 export
- bulk delete
- consolidation apply
- archive / restore

### Storage

Audit log 存 plugin storage，不进入 L2 vector DB。

### Proposed command

```text
!memory audit [page]
!memory audit export
```

### Audit fields

```json
{
  "audit_id": "...",
  "operation": "remember",
  "scope_key": "...",
  "user_key": "...",
  "sender_id": "...",
  "sender_name": "...",
  "target_type": "episode",
  "target_id": "...",
  "summary": "...",
  "timestamp": "2026-05-15T00:00:00Z",
  "query_id": 123
}
```

### Acceptance criteria

- 单条删除和批量删除都有 audit。
- profile 更新记录 field / action / scope。
- audit list 支持分页。
- audit export 不泄漏其他 scope。

### Non-goals

- 不做不可篡改日志。
- 不要求外部 SIEM 集成。

## Issue 7: Expose superseded and archived memories

Priority: P1

### Background

supersede 机制已经存在，但管理员看不到旧记忆为什么不再优先召回，也不容易验证 correction 是否生效。

### Goal

增强可解释性和可调试性。

### Proposed commands

```text
!memory show <episode_id>
!memory superseded [page]
!memory archived [page]
!memory restore <episode_id>
!memory archive <episode_id>
```

### Acceptance criteria

- `!memory show` 显示 status、superseded_by、timestamp、tags、importance、sender。
- `!memory superseded` 能列出被替代的 episode。
- `!memory restore` 可以把 archived episode 恢复为 active。
- 所有 status 修改写 audit log。

### Non-goals

- 不实现复杂合并 UI。

## Issue 8: Add consolidation preview and apply commands

Priority: P1

### Background

当前只有 time decay，没有主动整合。长期运行后，L2 会积累重复、过期、被纠正的 episode。OpenClaw 的 dreaming 和 Hermes 的 post-turn sync 都说明长期记忆需要整理，但自动后台直接改写记忆风险较高。

### Goal

增加安全的、管理员可控的 memory consolidation 流程。

### Proposed commands

```text
!memory consolidate preview
!memory consolidate run
```

### Recommended first version

第一版只做 preview-first，不默认后台自动执行。

Candidate selection:

- older than configured age, e.g. 7 days;
- same tag / high similarity duplicate;
- already superseded;
- low importance and rarely recalled;
- many episodes from the same speaker/topic.

Preview output:

- candidate episode IDs;
- suggested summary episode;
- suggested L1 profile updates;
- suggested archive list;
- risk notes.

Apply output:

- write summary episode;
- update L1 profile if configured;
- archive selected old episodes;
- write audit log.

### Proposed config

```yaml
consolidation_enabled: false
consolidation_min_age_days: 7
consolidation_max_candidates: 20
consolidation_apply_profile_updates: false
```

### Acceptance criteria

- Preview does not modify memory.
- Run modifies only current scope.
- Run writes audit log for every profile update / episode archive / summary write.
- Archived episodes are excluded from default recall.

### Non-goals

- 不做后台 cron。
- 不默认自动整合。
- 不新增 L3 procedural memory。

## Issue 9: Add optional post-turn memory candidate extraction

Priority: P1 / P2

### Background

当前 memory 写入主要依赖模型主动调用 `remember` / `update_profile`。这可控，但容易漏记。直接自动写入又可能污染 memory。

### Goal

增加一个默认关闭的候选记忆提取流程，让管理员观察模型会建议记什么，再决定是否自动化。

### Proposed behavior

Post-turn extraction 生成 candidates：

- candidate L1 profile update
- candidate L2 episode
- ignore reason

默认只记录候选，不写入正式 memory。

### Proposed commands

```text
!memory candidates [page]
!memory candidate accept <candidate_id>
!memory candidate reject <candidate_id>
```

### Proposed config

```yaml
candidate_extraction_enabled: false
candidate_auto_apply: false
candidate_max_per_turn: 3
```

### Acceptance criteria

- 默认关闭。
- 开启后不自动污染 L1/L2。
- accept 后走正常 `update_profile` / `remember` 路径，并写 audit log。
- reject 后候选可查。

### Non-goals

- 不要求修改 LangBot core 增加 TurnCompleted event。
- 第一版可以基于现有 `NormalMessageResponded` 事件或命令触发。

## Issue 10: Add richer memory management commands

Priority: P2

### Background

OpenClaw / Hermes 的文件式 memory 透明性较强。LongTermMemory 不应改成文件主存储，但需要提供足够透明的管理入口。

### Goal

用命令增强替代直接编辑 Markdown 文件的透明性。

### Proposed commands

```text
!memory show <episode_id>
!memory edit <episode_id>
!memory profile edit session
!memory profile edit speaker <sender_id>
!memory stats
!memory export all-current-scope
```

### Acceptance criteria

- 管理员能查看和编辑 L1/L2。
- 所有 edit/delete/archive 操作写 audit。
- 不允许跨 scope 操作，除非未来单独设计全局管理员权限。

### Non-goals

- 不做 Web UI 第一版。

## Issue 11: Design optional global speaker profile scope

Priority: P2 design only

### Background

当前 L1 speaker profile 绑定在 session_key 下。这适合群聊隔离，但不支持“同一个用户跨多个群共享画像”。

### Goal

做设计预研，不急着实现。

### Questions

- 是否需要 `speaker_global` scope？
- 如何识别同一个用户在不同平台/群的身份？
- 默认是否关闭？
- 用户如何授权跨群共享？
- 与 `bot` L2 isolation 如何组合？
- 冲突时 session speaker profile 和 global speaker profile 谁优先？

### Acceptance criteria

- 输出设计文档。
- 明确默认关闭。
- 明确隐私边界和迁移策略。

### Non-goals

- 不在第一阶段实现。

## Suggested implementation order

1. Issue 1: write policy.
2. Issue 2: health check.
3. Issue 4: lifecycle status.
4. Issue 6: audit log.
5. Issue 5: L2 export/import/delete.
6. Issue 7: superseded / archived visibility.
7. Issue 3: hybrid recall and exact-match fallback.
8. Issue 8: consolidation preview/apply.
9. Issue 9: post-turn candidates.
10. Issue 10 / 11: management UI and global profile design.

## What not to do yet

- Do not move memory implementation into LangBot core.
- Do not require LangBot SDK changes as a prerequisite.
- Do not add active goals into this plugin in the first phase.
- Do not add procedural memory as a first-class layer yet.
- Do not automatically delete old memories by default.
- Do not run background consolidation that modifies memory without preview or audit.

