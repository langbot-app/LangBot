# Runner

A Runner implements processing logic for Agents, plugin processors, or both.
It is a separate component kind from EventListener. Legacy EventListener plugins
continue to participate in Pipeline lifecycle hooks; they do not subscribe to
platform events automatically.

## Scaffold and activate

Run `lbp comp Runner` in a plugin project. Build and install the plugin,
then create a **Plugin processor** in LangBot's Processors area, select the
component, configure its parameters and bind a Bot event to that instance.
Installation and instance creation alone do not activate event subscriptions.

The plugin manifest declares the component directory:

```yaml
spec:
  components:
    Runner:
      fromDirs:
        - path: components/runner/
```

A component manifest uses this shape:

```yaml
apiVersion: langbot/v1
kind: Runner
metadata:
  name: welcome
  label:
    en_US: Welcome members
    zh_Hans: Welcome members
spec:
  usages: [event]
  events: [group.member_joined]
  config: []
  capabilities:
    tool_calling: true
  permissions:
    tools: [detail, call]
execution:
  python:
    path: welcome.py
    attr: WelcomeProcessor
```

```python
from langbot_plugin.api.definition.components.runner import (
    Runner,
    RunnerContext,
)
from langbot_plugin.api.entities.builtin.platform.events import MemberJoinedEvent


class WelcomeProcessor(Runner):
    async def initialize(self):
        @self.handler(MemberJoinedEvent)
        async def welcome(ctx: RunnerContext):
            await ctx.log(f"Welcoming {ctx.platform_event.member.id}")
            await ctx.reply(f"Hello, {ctx.platform_event.member.nickname}")
```

## Invocation contract

- `ctx.platform_event` is the typed EBA event, including its full public fields. All built-in
  event types, including `PlatformSpecificEvent`, are supported. Raw platform
  objects and the Host's legacy-event backup are excluded from transport.
- `ctx.config` contains parameters for the selected processor instance. It is
  separate from plugin installation configuration.
- `ctx.run_id` identifies the invocation. Context operations use `ctx`; platform
  and LangBot operations use `self.plugin`, as in other components. The current
  invocation and its grants are attached automatically.
- `await ctx.log(text, level='info')` records a log entry. Levels are `debug`,
  `info`, `warning` and `error`; a single entry is limited to 65,536 characters.
  Logs never send platform messages.
- `await ctx.reply(text)` calls the Host's `event_reply` tool. Platform capability
  and resource authorization still apply. Unsupported actions fail explicitly.
- Returning normally completes the run. Exceptions fail it and preserve preceding
  logs. Closing or cancelling the run cancels its handler. There is no implicit
  model loop or automatic retry of side effects.
- Register `EBAEvent` for a catch-all fallback. Exact typed handlers take precedence.
  Multiple handlers of the same type execute in registration order. Concurrent
  runs have separate contexts; do not store invocation state on `self`.

All components use the reference `plugin:author/plugin/name`. Component names must
be unique within a plugin. `spec.usages` accepts `agent`, `event`, or both; event
usage requires an explicit `spec.events` declaration. The Host filters selectors
by usage and checks the same declaration again at invocation.

Override `run(ctx)` for an execution engine, or use the default typed-handler
dispatch shown above. Both receive RunnerContext. A custom run may call
`await super().run(ctx)` to dispatch registered handlers. It can yield RunnerResult
objects; the runtime supplies completion when execution returns without a terminal
result. `ctx.event` remains the event envelope and `ctx.platform_event` exposes
typed platform fields.

`await ctx.get_available_tools()` returns callable tools with `name`,
`description`, `parameters` (JSON Schema), `type`, and `operations`. It includes
only tools granted for this invocation. Changing the returned copy does not grant
access. Use `ctx.call_tool(name, parameters)` for context actions, or
`self.plugin.call_tool(name, parameters)` from component code. Models, storage,
knowledge bases, and platform APIs use the same `self.plugin` entrypoint as other
components while retaining run authorization. Event-target grants cannot access
another target, and debug platform calls remain simulated.

Do not store a current run ID or context on the shared component instance, or
continue run-bound calls from background tasks after the handler has returned.
