# Workspace failure alerts

User guide: `docs/*/deploy/alerts.mdx`. This note records the internal contracts.

## Opt-in

Without a saved `alert_settings` row, alerts are off on self-hosted/dedicated instances and on for multi-tenant Cloud (`deployment.mode == 'cloud'`, `AlertService.default_enabled`). A saved row always wins. The dashboard
reads `GET /api/v1/alerts/summary` to offer an "Enable alerts" shortcut on the Failed card.

## Signal path

- `MonitoringService.record_error` → rule `pipeline_failures` (subject: Pipeline).
- `MonitoringService.record_llm_call(status='error')` → rule `model_failures` (subject: model name).
- `RuntimeBot.run` adapter task: exception → `bot_offline` failure; every (re)start → `bot_offline` recovery.

Producers call `AlertService.observe_failure/observe_recovery`, which only enqueue (bounded queue, drops when full). One
worker task per process (`workspace-alerts`) owns the sliding windows, so producers never wait on alert storage or
delivery, and alert delivery failures never create new alerts.

## Persistence and replicas

`alert_settings`, `alert_incidents`, `alert_deliveries` are tenant tables (RLS, `TENANT_TABLE_COLUMNS`, migration
`0047_workspace_alerts`). A partial unique index allows one firing incident per `(workspace_uuid, fingerprint)`.
Notifications are claimed per incident with compare-and-set updates on `notified_at` / `last_notified_at` /
`resolved_notified_at`, so replicas sharing a database notify once. Workspaces are only scanned while they have firing
incidents (startup discovery via `list_active_execution_bindings`), never on every tick.

## Email

`pkg/notification/email.EmailService` reads the top-level `email` section (env `EMAIL__*`) and is shared with
invitations. `LoadConfigStage` moves the legacy `workspace.invitations.email` section and maps
`WORKSPACE__INVITATIONS__EMAIL__*` to `EMAIL__*` (new names win). Core-side cap: 50 sent emails per Workspace per day.

## LangBot Space official channel

`POST {space.url}/api/v1/notifications/alert-email` with the account's own Space OAuth access token, called once per
Space-linked owner/admin. The body is strict (unknown fields → 400) and has no recipient, subject, body or link:

```json
{"instance_id": "", "workspace_uuid": "", "workspace_name": "≤64", "kind": "fired|reminder|resolved|test",
 "language": "en|zh", "idempotency_key": "[A-Za-z0-9:_-]{1,128}",
 "incidents": [{"rule": "pipeline_failures|model_failures|bot_offline", "subject_name": "≤64", "count": 0,
                "error_type": "≤64", "error_summary": "≤300", "opened_at": "RFC3339"}]}
```

Space mails the token owner's address only, renders a fixed template, strips links, and enforces quotas in Redis
(per account 20/day and 200/month, per Workspace 20/day, tests 3/hour, global `ALERT_EMAIL_DAILY_BUDGET`), the
`email_preference_alerts` opt-out and the Resend bounce/complaint suppression list. Responses: 200 (sent or
`deduplicated`), 400, 403 (`alert_email_opted_out`, suppressed, inactive account), 429 (`scope`, `retry_after`),
502. Core maps 404 to `space_endpoint_unavailable` so a Core newer than Space degrades instead of failing.
Multi-tenant Cloud never uses this channel; it mails through the platform-configured `email` section.
