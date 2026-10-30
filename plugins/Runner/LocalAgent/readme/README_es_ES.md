# Agente integrado

## Descripción general

Agente integrado con modelos de respaldo, herramientas y recuperación de conocimiento.

## Información del paquete

- **Runner ID**: `plugin:langbot-team/LocalAgent/default`
- **Versión**: `0.1.0`
- **Repositorio**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/LocalAgent](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/LocalAgent)

## Capacidades principales

- **Activada**: `streaming`, `tool calling`, `knowledge retrieval`, `multimodal input`, `skill authoring`, `interrupt`, `steering`
- **No declarada**: Vacío

## Configuración

| Campo | Tipo | Obligatorio | Valor predeterminado |
| --- | --- | --- | --- |
| `model` | `model-fallback-selector` | Sí | `{fallbacks: [], primary: '', reasoning: {}}` |
| `timeout` | `integer` | No | `300` |
| `prompt` | `prompt-editor` | Sí | `[{content: You are a helpful assistant., role: system}]` |
| `remove-think` | `boolean` | No | false |
| `knowledge-bases` | `knowledge-base-multi-selector` | No | `[]` |
| `advanced-settings` | `boolean` | No | `false` |
| `date-grounding` | `boolean` | No | `true` |
| `retrieval-top-k` | `integer` | No | `5` |
| `rerank-model` | `rerank-model-selector` | No | Vacío |
| `rerank-top-k` | `integer` | No | `5` |
| `max-tool-iterations` | `integer` | No | `100` |
| `tool-execution-mode` | `select` | No | `parallel` |
| `max-tool-result-chars` | `integer` | No | `20000` |
| `context-history-fetch-limit` | `integer` | No | `50` |
| `context-window-tokens` | `integer` | No | `200000` |
| `context-reserve-tokens` | `integer` | No | `16384` |
| `context-keep-recent-tokens` | `integer` | No | `20000` |
| `context-summary-tokens` | `integer` | No | `8000` |

## Permisos del Host

- **`models`**: `count_tokens`, `invoke`, `stream`, `rerank`
- **`tools`**: `detail`, `call`
- **`knowledge_bases`**: `list`, `retrieve`
- **`history`**: `page`

## Instalación y uso

1. Instala el plugin desde el mercado de plugins de LangBot.
2. Selecciona el Runner ID indicado en el selector Runner del Pipeline.
3. Completa la conexión según la tabla y guarda los valores sensibles en campos secret del panel de administración.

## Seguridad y limitaciones

- El runner solo puede usar recursos de LangBot autorizados para la ejecución actual.
- La disponibilidad, las capacidades del modelo y los límites de uso dependen del servicio externo.
- Consulta el README chino de la raíz o README_en_US.md para el comportamiento avanzado y las limitaciones específicas.

## Box

`box-enabled` activa el entorno aislado. `box-session-id-template` usa `{launcher_type}_{launcher_id}` para reutilizar por chat y `{global}` para compartir dentro del espacio de trabajo. Admite `{sender_id}`, `{bot_id}`, `{run_id}` y variables de la solicitud. El ejecutor selecciona el Box, importa los adjuntos y exporta explícitamente el outbox de la ejecución al finalizar correctamente.
