# Claude Code Agent

## Descripción general

Ejecuta Claude Code CLI como LangBot Runner.

## Información del paquete

- **Runner ID**: `plugin:langbot-team/ClaudeCodeAgent/default`
- **Versión**: `0.1.3`
- **Repositorio**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/claude-code-agent](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/claude-code-agent)

## Capacidades principales

- **Activada**: `streaming`, `tool calling`, `knowledge retrieval`, `steering`
- **No declarada**: `multimodal input`, `interrupt`

## Configuración

| Campo | Tipo | Obligatorio | Valor predeterminado |
| --- | --- | --- | --- |
| `daemon-enabled` | `boolean` | No | false |
| `daemon-host` | `string` | No | `127.0.0.1` |
| `daemon-port` | `integer` | No | `8767` |
| `daemon-token` | `secret` | No | Vacío |
| `location` | `select` | Sí | `local` |
| `workspace` | `string` | No | Vacío |
| `advanced-settings` | `boolean` | No | false |
| `command` | `string` | No | `claude` |
| `args-json` | `string` | No | `[]` |
| `env-json` | `string` | No | `{}` |
| `ssh-target` | `string` | No | Vacío |
| `ssh-port` | `integer` | No | `22` |
| `daemon-id` | `string` | No | Vacío |
| `timeout` | `integer` | No | `300` |
| `streaming` | `boolean` | No | true |
| `reuse-session` | `boolean` | No | true |
| `dangerously-skip-permissions` | `boolean` | No | true |
| `knowledge-bases` | `knowledge-base-multi-selector` | No | `[]` |
| `langbot-assets-enabled` | `boolean` | No | true |
| `mcp-bridge-transport` | `select` | No | `auto` |
| `mcp-servers-json` | `string` | No | `[]` |

## Permisos del Host

- **`tools`**: `detail`, `call`
- **`knowledge_bases`**: `retrieve`
- **`history`**: `page`

## Instalación y uso

1. Instala el plugin desde el mercado de plugins de LangBot.
2. Selecciona el Runner ID indicado en el selector Runner del Pipeline.
3. Completa la conexión según la tabla y guarda los valores sensibles en campos secret del panel de administración.

## Seguridad y limitaciones

- El runner solo puede usar recursos de LangBot autorizados para la ejecución actual.
- Claude Code usa `--dangerously-skip-permissions` por defecto porque LangBot aún no ofrece un flujo de aprobación interactivo. Úsalo solo con espacios de trabajo de confianza y una cuenta del sistema restringida; configúralo en false para restaurar las comprobaciones normales de permisos.
- La disponibilidad, las capacidades del modelo y los límites de uso dependen del servicio externo.
- Consulta el README chino de la raíz o README_en_US.md para el comportamiento avanzado y las limitaciones específicas.


> Shared runtime / daemon upgrade: [required setup and safety contract](../README.md#shared-worker-candidate--daemon-upgrade). Shared 模式必须配置独立强 token 和端口；默认本地工作目录为 `/data/workspace`。请同时升级 daemon.py 与完整 pkg 目录；旧客户端不兼容。
