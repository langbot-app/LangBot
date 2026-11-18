# Stateless component model (`stateless-v1`)

Certified cross-tenant plugins use one `BasePlugin` object and one object for every declared component manifest per artifact-digest worker. Multiple declared components of the same kind therefore have distinct shared objects. Installation attachments are lightweight immutable contexts; they do not create another plugin/component object graph.

## Manifest declaration

```yaml
execution:
  python:
    path: main.py
    attr: Plugin
  sharedRuntime: shared-runtime-v1
  componentModel: stateless-v1
```

`sharedRuntime` without `componentModel: stateless-v1` is not eligible for certification. Legacy source and unsigned packages remain compatible with the dedicated path. OSS ships no built-in issuer public key and supports dedicated execution only; configuring a certification key on OSS is unsupported. Cloud rejects an untrusted or legacy signed certificate rather than treating it as unsigned.

## Programming contract

- Treat `BasePlugin` and every component object as process-wide singletons.
- Keep `initialize()` process-scoped. It runs once per worker, not once per installation.
- On `BasePlugin`, read installation configuration with `self.get_config()`. In a component, use `self.get_plugin_config()` or `self.plugin.get_config()`.
- Do not copy configuration, credentials, Workspace IDs, request data, or installation identity into instance fields or module globals.
- Do not mutate the returned configuration. Runtime installs an immutable snapshot for each invocation; `get_config()` returns a compatibility copy.
- Use SDK Host APIs for tenant storage, credentials, files, logging, models, tools, and RAG. Authority comes from the task-local `InstallationBinding`.
- If identity is needed, call `get_installation_binding()` during an invocation. Do not retain it after the call returns.
- Components must be re-entrant: invocations from different Workspaces may overlap on the same object.
- The SDK does not track ownership of tasks you create. If you detach tenant-bearing work, keep your own registry keyed by the full installation binding and stop it in `on_installation_revoked` before returning.
- Process-level caches may contain only public/artifact-level data. A cache that holds tenant state must include the full installation binding and be released in `BasePlugin.on_installation_revoked()`.

This contract deliberately matches a future serverless execution model: component methods depend on input plus invocation context, while tenant state remains in Host services. The current release still uses long-lived workers; it does not provide a serverless deployment mode.

## Installation revocation

One object graph serves every installation of an artifact digest and is never
destroyed per installation, so releasing binding-keyed process state is the
plugin's own responsibility:

```python
class MyPlugin(BasePlugin):
    def __init__(self) -> None:
        super().__init__()
        self._caches: dict[str, Cache] = {}

    async def on_installation_revoked(self, binding: InstallationBinding) -> None:
        self._caches.pop(binding.installation_uuid, None)
```

The runtime calls this once per installation, after cancelling that
installation's in-flight messages and detaching its slot. It fires for
uninstall, disable, Workspace removal and upgrade (the superseded binding is
revoked when the new revision activates). Dedicated workers are shut down
instead of detached, so this hook runs for shared placement only; dedicated
state disappears with the process.

There is no active invocation during the call, so Host APIs (storage, config,
binding lookups) are unavailable and only the `binding` argument identifies the
installation. Return `None`; exceptions are logged and never block revocation.
Calls are serialized per installation but may overlap with invocations of
sibling installations on the same object graph.

## Example

```python
class LookupTool(Tool):
    async def initialize(self) -> None:
        # Process-wide initialization only.
        self.http = StatelessHTTPTransport()

    async def call(self, params, **kwargs):
        config = self.get_plugin_config()
        # Fetch secrets through Host APIs in the current invocation.
        return await self.http.lookup(config["endpoint"], params)
```

Do not write:

```python
async def initialize(self):
    self.endpoint = self.plugin.config["endpoint"]
    self.api_key = self.plugin.config["api_key"]
```

Shared initialization has no tenant config, so this captures empty/stale data or fails. Any attempt to retain invocation config on the shared object is a certification blocker.

## Compatibility

Legacy source and unsigned packages keep the dedicated worker and existing object/config semantics. OSS is dedicated-only and has no supported certification key configuration. Cloud must reject an invalid or legacy signed archive rather than treating it as unsigned. The stateless rules are an opt-in certification contract. Adding only the manifest fields is insufficient: source review and concurrency tests must prove the implementation follows the contract.
