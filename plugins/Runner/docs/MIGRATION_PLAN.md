# Historical Migration Plan

This document is archived. The official runner plugins are developed directly
against Runner Protocol v1; there is no supported intermediate protocol or
compatibility layer for earlier unpublished designs.

Current implementation guidance lives in:

- [README.md](../README.md)
- Each plugin's local `README.md`
- LangBot host docs under `docs/agent-runner-pluginization/`

Current Protocol v1 rules for this repository:

- Do not depend on top-level `ctx.params`, `ctx.prompt`, or `ctx.messages`.
- Read adapter params from `ctx.adapter.extra["params"]` when the host provides
  Pipeline adapter metadata.
- Do not read `ctx.bootstrap`; Protocol v1 does not inline bootstrap/history
  windows. Use authorized history pull APIs when more context is needed.
- Use `ctx.input` for the current event input.
- Include `ctx.run_id` in every `RunnerResult` factory call.
- Use explicit state scopes in `RunnerResult.state_updated(...)`.
