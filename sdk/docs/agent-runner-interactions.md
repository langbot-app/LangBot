# Runner Structured Interactions

Structured interactions are a provider-neutral Runner Protocol v1
capability. Dify human input, deployment approval, a remote harness question,
and a CLI permission confirmation all use the same Host contract.

## Manifest

Only runners that actually emit and resume interactions should opt in:

```yaml
spec:
  capabilities:
    interactions: true
  permissions:
    interactions: [request]
    storage: [plugin]
```

The Host also applies the binding delivery policy. A manifest declaration does
not bypass Host authorization.

## Request

Call the blocking SDK method while the current Runner is active:

```python
from langbot_plugin.api.entities.builtin.runner import (
    InteractionAction,
    InteractionRequest,
)

result = await ctx.request_interaction(
    InteractionRequest(
        interaction_id="provider-neutral-correlation-id",
        kind="confirmation",
        title="Approve this operation?",
        actions=[
            InteractionAction(id="approve", label="Approve", style="primary"),
            InteractionAction(id="deny", label="Deny", style="danger"),
        ],
        fallback_text="Approval is required to continue.",
    ),
    timeout=600,
    on_unsupported="degrade",
)
if result.submission is not None:
    selected_action = result.submission.action_id
```

Use `ctx.delivery.interactions` to inspect the current surface's supported
field types, action styles, update support, and field limit. Always provide a
plain-text fallback. A form with multiple fields requires a native card; the
Host rejects a text fallback for that structure.

## Continuation

The call waits in the same run and returns an `InteractionResult`. Check
`status` before reading `submission`; a timeout has no submission. The Host
validates callback token, actor, fields, options, and repeated submissions.
On cancellation or Host restart, the pending card becomes invalid.

## Long-Lived Processes

CLI and harness protocols may wait on their live stdin/stdout channel. Keep
that process alive while `ctx.request_interaction` waits, then write the
validated answer to the same channel.
