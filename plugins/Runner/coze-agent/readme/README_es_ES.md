# Agente Coze

`remove-think` acepta solo valores booleanos (predeterminado `false`). Con `true` oculta el razonamiento y los bloques `<think>`, incluso entre fragmentos, sin eliminar respuestas ni contenido de herramientas.

## Descripción general

Ejecuta un bot de Coze como LangBot Runner.

## Información del paquete

- **Runner ID**: `plugin:langbot-team/CozeAgent/default`
- **Versión**: `0.1.2`
- **Repositorio**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/coze-agent](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/coze-agent)

## Capacidades principales

- **Activada**: `streaming`, `tool calling`, `knowledge retrieval`, `multimodal input`
- **No declarada**: `interrupt`

## Configuración

| Campo | Tipo | Obligatorio | Valor predeterminado |
| --- | --- | --- | --- |
| `api-key` | `secret` | Sí | Vacío |
| `bot-id` | `string` | Sí | Vacío |
| `api-base` | `string` | Sí | `https://api.coze.cn` |
| `advanced-settings` | `boolean` | No | false |
| `auto-save-history` | `boolean` | No | true |
| `timeout` | `number` | No | `120` |
| `langbot-assets-enabled` | `boolean` | No | false |
| `langbot-assets-gateway-host` | `string` | No | `0.0.0.0` |
| `langbot-assets-gateway-port` | `integer` | No | `8765` |
| `langbot-assets-gateway-request-timeout` | `integer` | No | `60` |
| `langbot-assets-token-ttl` | `integer` | No | `3600` |
| `langbot-assets-input-name` | `string` | No | `langbot_asset_run_token` |

## Permisos del Host

- **`tools`**: `detail`, `call`
- **`knowledge_bases`**: `retrieve`
- **`history`**: `page`
- **`storage`**: `plugin`

## Instalación y uso

1. Instala el plugin desde el mercado de plugins de LangBot.
2. Selecciona el Runner ID indicado en el selector Runner del Pipeline.
3. Completa la conexión según la tabla y guarda los valores sensibles en campos secret del panel de administración.

## Seguridad y limitaciones

- El runner solo puede usar recursos de LangBot autorizados para la ejecución actual.
- La disponibilidad, las capacidades del modelo y los límites de uso dependen del servicio externo.
- Consulta el README chino de la raíz o README_en_US.md para el comportamiento avanzado y las limitaciones específicas.

### Provider identity compatibility (`user-id-source`)

Per-pipeline Runner parameter, not plugin-global configuration. `sender` remains the default.
A `sender` run whose Host actor is missing or empty is refused before any upstream request, instead of minting a per-run provider user; select `legacy-session` explicitly when a conversation-scoped provider user is intended.
Explicit `legacy-session` preserves native provider identity using trusted Host run context only;
missing identity fails before any upstream request, never falls back to the sender or business params.
`legacy-session` uses `conversation.launcher_type` (`group`/`person`) plus `_` plus the exact `conversation.launcher_id`. Host must project the Query launcher for Coze into those fields, including interaction/resume runs. Older Hosts that leave these fields empty must be upgraded.
Provider conversation/session persistence remains Runner-owned. Configuration migration does not import old conversation IDs, threads, transcripts, pending forms or files; finish/cancel pending work or perform a separately authorized state migration. Changing identity on an existing stored provider conversation requires an explicit reset/migration decision.
