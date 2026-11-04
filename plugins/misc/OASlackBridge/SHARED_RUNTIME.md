# Shared runtime

OASlackBridge declares `shared-runtime-v1` and `stateless-v1`. The event listener retains no invocation data. The plugin reads configuration and the active installation binding only inside event invocations, not during initialization.

Storage keys include the stable `instance_uuid:workspace_uuid:installation_uuid` scope. Runtime revision is excluded so upgrades preserve mappings. Session rows additionally include Official Account bot UUID and full openid; thread lookup rows include Slack bot UUID, channel ID, and root message timestamp. Each row is written separately. A shared worker without a binding refuses storage access; dedicated placement uses a dedicated scope.

One process-local lock per installation serializes session creation, updates, and staff sends. This prevents concurrent messages from creating two roots in the same worker and prevents `/close` from racing a send. It deliberately serializes that installation's conversations while allowing other installations to proceed independently. Persistent rows are read on demand, never cached across invocations. Revocation removes only the affected lock and makes no Host calls; destruction releases all locks. No background tasks are created.

The tests run one plugin/listener object graph across separate installation and Workspace bindings over a flat mock Host storage namespace. They verify that identical user/thread IDs do not cross installation boundaries, runtime revision changes preserve routing, and revocation does not delete persistent data or sibling locks. The Host remains responsible for enforcing Workspace-scoped bot and storage authorization.
