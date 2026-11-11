# Workspace Runner Plugin Example

A minimal Runner plugin demonstrating listing and executing authorized LangBot Application API workspace operations.

## Features

- **Plugin Manifest Declarations**: Requests `bot.list` and `stats.basic` in plugin-level `spec.permissions.workspace_operations`. A member must confirm installation grants in WebUI before the plugin can run.
- **Runtime Execution**:
  - Invokes `await ctx.api.workspace.list()` to inspect authorized operations and domains.
  - Invokes `await ctx.api.workspace.call("bot.list")` to directly call an authorized operation.
  - Returns the results structured as JSON in the completion message.
- Used for end-to-end verification in LANG-228.
