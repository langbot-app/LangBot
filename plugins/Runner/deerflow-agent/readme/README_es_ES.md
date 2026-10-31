# Agente DeerFlow

## Descripción general

Ejecuta un agente DeerFlow LangGraph como LangBot Runner.

## Información del paquete

- **Runner ID**: `plugin:langbot-team/DeerFlowAgent/default`
- **Versión**: `0.1.2`
- **Repositorio**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/deerflow-agent](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/deerflow-agent)

## Capacidades principales

- **Activada**: `streaming`, `multimodal input`
- **No declarada**: `tool calling`, `knowledge retrieval`, `interrupt`

## Configuración

| Campo | Tipo | Obligatorio | Valor predeterminado |
| --- | --- | --- | --- |
| `api-base` | `string` | Sí | `http://127.0.0.1:2026` |
| `api-key` | `secret` | No | Vacío |
| `auth-header` | `secret` | No | Vacío |
| `assistant-id` | `string` | Sí | `lead_agent` |
| `advanced-settings` | `boolean` | No | false |
| `model-name` | `string` | No | Vacío |
| `thinking-enabled` | `boolean` | No | false |
| `plan-mode` | `boolean` | No | false |
| `subagent-enabled` | `boolean` | No | false |
| `max-concurrent-subagents` | `integer` | No | `3` |
| `timeout` | `integer` | No | `300` |
| `recursion-limit` | `integer` | No | `1000` |

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
