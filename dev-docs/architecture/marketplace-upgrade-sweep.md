# Marketplace upgrade sweep (operator)

Multi-Workspace (Cloud) instances only offer plugin upgrades per Workspace in the WebUI. `plugin.marketplace_upgrade` lets an operator upgrade selected Marketplace plugins in every Workspace from inside the running Core (`src/langbot/pkg/plugin/marketplace_upgrade.py`).

## Behaviour

- Disabled unless `plugin.marketplace_upgrade.plugins` lists `author/name` IDs. Env: `PLUGIN__MARKETPLACE_UPGRADE__PLUGINS=langbot-team/LocalAgent,RockChinQ/WebSearch`.
- Runs once per process after the shared Plugin Runtime handshake and desired-state replay, after `start_delay_seconds` (default 120).
- Reads each plugin's `latest_version` from the configured Space Marketplace, then walks `workspace_service.list_active_execution_bindings()` with `concurrency` Workspaces at a time (default 2). The optional `workspaces` list limits the sweep to canary Workspace UUIDs.
- Each Workspace is entered with `persistence_mgr.tenant_scope()` and `plugin_connector._prepare_workspace_context()`, the same fence as HTTP requests. Outdated `marketplace` installations go through `upgrade_plugin()`, the WebUI upgrade path.
- An upgrade to a version without `spec.permissions` disables the installation until a member confirms. With `confirm_permissions` (default true), the sweep calls `auto_confirm_declared()` for installations that were **enabled before the sweep**. Installations the tenant had disabled stay disabled.
- The operator principal is `SUPPORT_ADMIN` with `support_session_id=operator:marketplace-upgrade`, owner role. Failures are logged per installation and do not stop the sweep. The summary is logged as `Marketplace upgrade finished: {...}`.

Remove the env setting after the run. Re-running is idempotent: installations already at the latest version are only re-confirmed if they are pending confirmation.
