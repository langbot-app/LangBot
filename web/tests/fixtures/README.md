# Sandbox condition compatibility fixture

`sandbox-scope-schema.json` preserves the sandbox field from master
`9b7ba0d64708496ace30a82866f6dbc185f089dc` (`templates/metadata/pipeline/ai.yaml`)
solely as regression input for the generic dynamic-form condition renderer.
It is **not** shipped pipeline metadata, an installed plugin manifest, or an
assertion that 4.11 plugins may select the Host's execution sandbox scope.

The old local-agent page is retired. Its unit matrix (availability precedence,
trimmed forced scope, ordered overrides, locale parity and live/external/system
resolution) remains covered. Browser coverage now mounts the real
`DynamicFormComponent` and updates caller context without remounting, rather
than expecting a removed PipelineForm Box poller or scope-value coercion.
A separate real-pipeline browser regression verifies plugin `runner_config`
round-tripping and absence of an injected Core sandbox selector.

The fixture uses no real Box, provider credentials, or production resources.
