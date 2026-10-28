# Agente Tbox

`remove-think` acepta solo valores booleanos (predeterminado `false`). Con `true` oculta el razonamiento y los bloques `<think>`, incluso entre fragmentos, sin eliminar respuestas ni contenido de herramientas.

## Descripción general

Ejecuta una aplicación Ant Tbox como LangBot Runner.

## Información del paquete

- **Runner ID**: `plugin:langbot-team/TboxAgent/default`
- **Versión**: `0.1.0`
- **Repositorio**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/tbox-agent](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/tbox-agent)

## Capacidades principales

- **Activada**: `streaming`, `multimodal input`
- **No declarada**: `tool calling`, `knowledge retrieval`, `interrupt`

## Configuración

| Campo | Tipo | Obligatorio | Valor predeterminado |
| --- | --- | --- | --- |
| `api-key` | `secret` | Sí | Vacío |
| `app-id` | `string` | Sí | Vacío |
| `timeout` | `number` | No | `120` |

## Permisos del Host

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
A `sender` run whose Host actor is missing or empty is refused before any upstream request, instead of minting a per-run provider user; select `legacy-bot` explicitly when a conversation-scoped provider user is intended.
Explicit `legacy-bot` preserves native provider identity using trusted Host run context only;
missing identity fails before any upstream request, never falls back to the sender or business params.
`legacy-bot` uses `conversation.bot_id` (or Host runtime `bot_id` when there is no conversation), exactly, without a prefix.
Provider conversation/session persistence remains Runner-owned. Configuration migration does not import old conversation IDs, threads, transcripts, pending forms or files; finish/cancel pending work or perform a separately authorized state migration. Changing identity on an existing stored provider conversation requires an explicit reset/migration decision.
