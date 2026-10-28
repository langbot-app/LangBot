# GitHubKit — IM 里的 GitHub 工具箱

在任意聊天里查询 GitHub、搜索仓库，并把仓库的**事件推送**（提交 / PR / Issue / Release / Star / Fork）自动播报到当前会话。基于后台轮询 GitHub Events API，**无需公网 webhook 入口**，任何部署方式都能用。

[English](../README.md)

## 命令

### 查询 / 集成
| 命令 | 说明 |
|---|---|
| `!gh repo <owner/repo>` | 仓库信息（star/fork/语言/许可证…） |
| `!gh issues <owner/repo> [open\|closed\|all]` | Issue 列表 |
| `!gh prs <owner/repo> [open\|closed\|all]` | PR 列表 |
| `!gh issue <owner/repo> <编号>` | Issue/PR 详情 |
| `!gh releases <owner/repo>` | Release 列表 |
| `!gh user <用户名>` | 用户信息 |
| `!gh search <关键词>` | 搜索仓库（按 star 排序） |

支持直接粘贴仓库 URL（`https://github.com/owner/repo`）。

### 事件推送（订阅）
| 命令 | 说明 |
|---|---|
| `!gh sub <owner/repo> [事件...]` | 订阅推送到本会话 |
| `!gh unsub <owner/repo>` | 退订 |
| `!gh subs` | 查看本会话的订阅 |

事件类型（可多选，默认全部）：`push`(提交) / `pr` / `issue` / `release` / `star` / `fork`。

示例：
```
!gh sub langbot-app/LangBot push pr release
```
仅在该仓库有新提交、PR 变更、发布 Release 时播报。

## 工作原理

- 插件在 `initialize()` 启动一个后台 `asyncio` 轮询任务，按配置间隔拉取每个被订阅仓库的 `GET /repos/{owner}/{repo}/events`。
- 用 `last_event_id` 去重，只推送上次之后的新事件；首次订阅时记录当前游标，不会回灌历史。
- 订阅信息（含 `bot_uuid` + 会话目标）持久化在插件 KV，重启后继续推送。

## 配置项

- `github_token`：GitHub 个人访问令牌。**强烈建议填写** —— 把速率从 60/小时 提到 5000/小时（事件轮询必需），并可访问私有仓库。
- `poll_interval`（默认 120，最小 60）：轮询间隔（秒）。GitHub 事件流约缓存 60 秒，更小无意义。
- `max_events_per_push`（默认 5）：每仓库单次最多推送条数，避免停机后刷屏。

## 速率限制提示

不配 token 时匿名额度仅 60 次/小时，订阅多个仓库会很快耗尽。生产使用务必配置 token。
