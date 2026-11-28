# Workflow processors

A bot route with `target_type: workflow` sends a message to a workspace-owned tree. The graph has one `start`, one parent per subsequent step, and at most one child per branch. A terminal step needs no outgoing edge. Stable node IDs are template names; display names can change without breaking references.

## Execution

The catalog at `GET /api/v1/workflows/_/node-types` describes each step’s configuration, outputs and branches. The executor follows one path and records rendered inputs, outputs, branch, timings and errors per step. Jinja expressions can reference ancestor outputs, scoped memory and time. The workflow timezone defaults to UTC. Memory scopes are `run`, `user`, `group` and `workflow`.

Message routing admits the entry query once. A handoff to Chat, Agent or another workflow reuses that admission; replacement text must pass inbound content filtering. Target replies use their normal outbound hooks and policy. Nested handoffs are bounded at eight levels. Explicit sends target the selected conversation rather than replying to the originating message.

## Editing and testing

Create or update a graph through `/api/v1/workflows`. The detail and update responses include `workflow` and `issues`; invalid definitions may be edited but cannot execute. `POST /<uuid>/test` takes `text`, `session_type` and optionally an unsaved `graph`. A saved test requires `runtime.operate`; a draft additionally requires `resource.manage`. Tests capture replies rather than replying to a platform user. The response includes the execution UUID, status, error, handoff, replies and ordered steps. Inspect recorded runs with `GET /<uuid>/executions` and `GET /<uuid>/executions/<execution_uuid>`.
