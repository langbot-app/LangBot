# GitHubKit — GitHub toolbox in your IM

Query GitHub, search repositories, and push repository **events** (commits / PRs / issues / releases / stars / forks) into any chat. Powered by background polling of the GitHub Events API, so it needs **no public webhook ingress** and works in any deployment.

[简体中文](readme/README_zh_Hans.md)

## Commands

### Query / integration
| Command | Description |
|---|---|
| `!gh repo <owner/repo>` | Repo info (stars/forks/language/license…) |
| `!gh issues <owner/repo> [open\|closed\|all]` | Issue list |
| `!gh prs <owner/repo> [open\|closed\|all]` | PR list |
| `!gh issue <owner/repo> <number>` | Issue/PR detail |
| `!gh releases <owner/repo>` | Release list |
| `!gh user <username>` | User info |
| `!gh search <keyword>` | Search repos (by stars) |

You can also paste a repo URL directly (`https://github.com/owner/repo`).

### Event push (subscriptions)
| Command | Description |
|---|---|
| `!gh sub <owner/repo> [events...]` | Subscribe push to this chat |
| `!gh unsub <owner/repo>` | Unsubscribe |
| `!gh subs` | List this chat's subscriptions |

Event types (multi-select, default all): `push`(commits) / `pr` / `issue` / `release` / `star` / `fork`.

Example:
```
!gh sub langbot-app/LangBot push pr release
```
Only posts when that repo has new commits, PR changes, or a new release.

## How it works

- On the first invocation of an installation the plugin starts a background `asyncio` poller for that installation's subscriptions, fetching `GET /repos/{owner}/{repo}/events` at the configured interval. Pollers are keyed by installation binding and stopped by `on_installation_revoked`.
- Deduplicates with `last_event_id`, pushing only events newer than the last seen; on first subscription it records the current cursor and never backfills history.
- Subscriptions (including `bot_uuid` + chat target) are persisted in the plugin KV store, so push continues after a restart.

## Configuration

- `language` (default `zh_Hans`): language for all bot messages and event-push notifications — `en_US` or `zh_Hans`.
- `github_token`: GitHub personal access token. **Strongly recommended** — raises the rate limit from 60/hr to 5000/hr (required for event polling) and enables private repos.
- `poll_interval` (default 120, min 60): poll interval in seconds. GitHub caches the events feed ~60s, so lower values don't help.
- `max_events_per_push` (default 5): max events per repo per push, to avoid flooding after downtime.

## Rate limit note

Without a token the anonymous quota is only 60 requests/hour, which a few subscribed repos will exhaust quickly. Always configure a token for production use.

## Shared runtime

`manifest.yaml` declares `sharedRuntime: shared-runtime-v1` +
`componentModel: stateless-v1`, so this plugin can be placed on a multi-tenant
shared worker: config is read per invocation, subscriptions are namespaced per
installation, and each installation's poller is stopped in
`on_installation_revoked`. See [SHARED_RUNTIME.md](SHARED_RUNTIME.md) for what is
per-invocation, what is binding-keyed, and the known limits. This source is not
certified.
