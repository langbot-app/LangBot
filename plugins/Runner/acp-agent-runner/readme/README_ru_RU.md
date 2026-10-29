# ACP Runner

## Обзор

Запускает совместимый с Agent Client Protocol агент программирования как LangBot Runner.

## Информация о пакете

- **Runner ID**: `plugin:langbot-team/ACPAgentRunner/default`
- **Версия**: `0.1.4`
- **Репозиторий**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/acp-agent-runner](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/acp-agent-runner)

## Основные возможности

- **Включено**: `streaming`, `tool calling`, `knowledge retrieval`, `multimodal input`, `steering`
- **Не заявлено**: `interrupt`

## Настройка

| Поле | Тип | Обязательно | По умолчанию |
| --- | --- | --- | --- |
| `daemon-enabled` | `boolean` | Нет | false |
| `daemon-host` | `string` | Нет | `127.0.0.1` |
| `daemon-port` | `integer` | Нет | `8766` |
| `daemon-token` | `secret` | Нет | Пусто |
| `provider` | `select` | Да | `claude-code` |
| `location` | `select` | Да | `local` |
| `workspace` | `string` | Нет | Пусто |
| `advanced-settings` | `boolean` | Нет | false |
| `ssh-target` | `string` | Нет | Пусто |
| `daemon-id` | `string` | Нет | Пусто |
| `daemon-connect-timeout` | `integer` | Нет | `30` |
| `ssh-port` | `integer` | Нет | `22` |
| `ssh-identity-file` | `string` | Нет | Пусто |
| `acp-command` | `string` | Нет | Пусто |
| `knowledge-bases` | `knowledge-base-multi-selector` | Нет | `[]` |
| `langbot-assets-enabled` | `boolean` | Нет | true |
| `langbot-assets-mode` | `select` | Нет | `auto` |
| `langbot-assets-gateway-host` | `string` | Нет | `127.0.0.1` |
| `langbot-assets-gateway-port` | `integer` | Нет | `0` |
| `langbot-assets-gateway-public-url` | `string` | Нет | Пусто |
| `langbot-assets-token-ttl` | `integer` | Нет | `3600` |
| `timeout` | `integer` | Нет | `300` |
| `reuse-session` | `boolean` | Нет | true |
| `env-json` | `text` | Нет | Пусто |
| `ssh-connect-timeout` | `integer` | Нет | `10` |
| `ssh-extra-options` | `string` | Нет | Пусто |
| `startup-timeout` | `integer` | Нет | `30` |
| `initialize-timeout` | `integer` | Нет | `120` |
| `create-session-if-missing` | `boolean` | Нет | true |
| `streaming` | `boolean` | Нет | true |
| `append-run-scope-prompt` | `boolean` | Нет | true |
| `mcp-servers-json` | `text` | Нет | Пусто |

## Разрешения Host

- **`tools`**: `detail`, `call`
- **`knowledge_bases`**: `retrieve`
- **`history`**: `page`
- **`storage`**: `plugin`

## Установка и использование

1. Установите плагин из магазина плагинов LangBot.
2. Выберите указанный Runner ID в селекторе Runner вашего Pipeline.
3. Заполните параметры подключения по таблице и храните секреты в полях secret панели управления.

## Безопасность и ограничения

- Runner использует только ресурсы LangBot, разрешённые для текущего запуска.
- Доступность, возможности моделей и лимиты запросов зависят от внешнего сервиса.
- Расширенное поведение и ограничения продукта описаны в китайском README в корне и английском README_en_US.md.


> Shared runtime / daemon upgrade: [required setup and safety contract](../README.md#shared-worker-candidate--daemon-upgrade). Shared 模式必须配置独立强 token 和端口；默认本地工作目录为 `/data/workspace`。请同时升级 daemon.py 与完整 pkg 目录；旧客户端不兼容。
