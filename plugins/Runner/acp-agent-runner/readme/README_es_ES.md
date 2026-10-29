# ACP Runner

## Descripción general

Ejecuta cualquier agente de programación compatible con Agent Client Protocol como LangBot Runner.

## Información del paquete

- **Runner ID**: `plugin:langbot-team/ACPAgentRunner/default`
- **Versión**: `0.1.4`
- **Repositorio**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/acp-agent-runner](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/acp-agent-runner)

## Capacidades principales

- **Activada**: `streaming`, `tool calling`, `knowledge retrieval`, `multimodal input`, `steering`
- **No declarada**: `interrupt`

## Configuración

| Campo | Tipo | Obligatorio | Valor predeterminado |
| --- | --- | --- | --- |
| `daemon-enabled` | `boolean` | No | false |
| `daemon-host` | `string` | No | `127.0.0.1` |
| `daemon-port` | `integer` | No | `8766` |
| `daemon-token` | `secret` | No | Vacío |
| `provider` | `select` | Sí | `claude-code` |
| `location` | `select` | Sí | `local` |
| `workspace` | `string` | No | Vacío |
| `advanced-settings` | `boolean` | No | false |
| `ssh-target` | `string` | No | Vacío |
| `daemon-id` | `string` | No | Vacío |
| `daemon-connect-timeout` | `integer` | No | `30` |
| `ssh-port` | `integer` | No | `22` |
| `ssh-identity-file` | `string` | No | Vacío |
| `acp-command` | `string` | No | Vacío |
| `knowledge-bases` | `knowledge-base-multi-selector` | No | `[]` |
| `langbot-assets-enabled` | `boolean` | No | true |
| `langbot-assets-mode` | `select` | No | `auto` |
| `langbot-assets-gateway-host` | `string` | No | `127.0.0.1` |
| `langbot-assets-gateway-port` | `integer` | No | `0` |
| `langbot-assets-gateway-public-url` | `string` | No | Vacío |
| `langbot-assets-token-ttl` | `integer` | No | `3600` |
| `timeout` | `integer` | No | `300` |
| `reuse-session` | `boolean` | No | true |
| `env-json` | `text` | No | Vacío |
| `ssh-connect-timeout` | `integer` | No | `10` |
| `ssh-extra-options` | `string` | No | Vacío |
| `startup-timeout` | `integer` | No | `30` |
| `initialize-timeout` | `integer` | No | `120` |
| `create-session-if-missing` | `boolean` | No | true |
| `streaming` | `boolean` | No | true |
| `append-run-scope-prompt` | `boolean` | No | true |
| `mcp-servers-json` | `text` | No | Vacío |

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


> Shared runtime / daemon upgrade: [required setup and safety contract](../README.md#shared-worker-candidate--daemon-upgrade). Shared 模式必须配置独立强 token 和端口；默认本地工作目录为 `/data/workspace`。请同时升级 daemon.py 与完整 pkg 目录；旧客户端不兼容。
