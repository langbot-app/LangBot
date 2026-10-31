# Agente WeKnora

`agent-id` es opcional en ambos modos. Si se omite, `chat` usa `builtin-quick-answer` y `agent` usa `builtin-smart-reasoning`; un valor vacío explícito no envía el ID. Los valores guardados no se sustituyen. `knowledge-base-ids` contiene IDs remotos de WeKnora para ambos modos, no UUIDs de LangBot.

## Descripción general

Ejecuta un agente WeKnora o una aplicación de chat con base de conocimiento como LangBot Runner.

## Información del paquete

- **Runner ID**: `plugin:langbot-team/WeKnoraAgent/default`
- **Versión**: `0.1.2`
- **Repositorio**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/weknora-agent](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/weknora-agent)

## Capacidades principales

- **Activada**: `streaming`
- **No declarada**: `tool calling`, `knowledge retrieval`, `multimodal input`, `interrupt`

## Configuración

| Campo | Tipo | Obligatorio | Valor predeterminado |
| --- | --- | --- | --- |
| `base-url` | `string` | Sí | `http://localhost:8080/api/v1` |
| `api-key` | `secret` | Sí | Vacío |
| `app-type` | `select` | Sí | `agent` |
| `agent-id` | `string` | No | `chat`: `builtin-quick-answer`; `agent`: `builtin-smart-reasoning` |
| `knowledge-base-ids` | `array[string]` | No | `[]` |
| `web-search-enabled` | `boolean` | No | false |
| `advanced-settings` | `boolean` | No | false |
| `timeout` | `integer` | No | `120` |
| `base-prompt` | `string` | No | `请回答用户的问题。` |

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
