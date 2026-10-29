# Codex Agent

## Обзор

Запускает Codex CLI как LangBot Runner.

## Информация о пакете

- **Runner ID**: `plugin:langbot-team/CodexAgent/default`
- **Версия**: `0.1.9`
- **Репозиторий**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/codex-agent](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/codex-agent)

## Основные возможности

- **Включено**: `streaming`, `tool calling`, `knowledge retrieval`, `steering`
- **Не заявлено**: `multimodal input`, `interrupt`

## Настройка

| Поле | Тип | Обязательно | По умолчанию |
| --- | --- | --- | --- |
| `daemon-enabled` | `boolean` | Нет | false |
| `daemon-host` | `string` | Нет | `127.0.0.1` |
| `daemon-port` | `integer` | Нет | `8768` |
| `daemon-token` | `secret` | Нет | Пусто |
| `location` | `select` | Да | `local` |
| `workspace` | `string` | Нет | Пусто |
| `advanced-settings` | `boolean` | Нет | false |
| `command` | `string` | Нет | `codex` |
| `args-json` | `string` | Нет | `[]` |
| `env-json` | `string` | Нет | `{}` |
| `ssh-target` | `string` | Нет | Пусто |
| `ssh-port` | `integer` | Нет | `22` |
| `daemon-id` | `string` | Нет | Пусто |
| `timeout` | `integer` | Нет | `300` |
| `streaming` | `boolean` | Нет | true |
| `reuse-session` | `boolean` | Нет | true |
| `approval-policy` | `select` | Нет | `never` |
| `sandbox-mode` | `select` | Нет | `danger-full-access` |
| `knowledge-bases` | `knowledge-base-multi-selector` | Нет | `[]` |
| `langbot-assets-enabled` | `boolean` | Нет | true |
| `mcp-bridge-transport` | `select` | Нет | `auto` |
| `mcp-servers-json` | `string` | Нет | `[]` |

## Разрешения Host

- **`tools`**: `detail`, `call`
- **`knowledge_bases`**: `retrieve`
- **`history`**: `page`

## Установка и использование

1. Установите плагин из магазина плагинов LangBot.
2. Выберите указанный Runner ID в селекторе Runner вашего Pipeline.
3. Заполните параметры подключения по таблице и храните секреты в полях secret панели управления.

## Безопасность и ограничения

- Конфигурация по умолчанию запускает Codex с `approvalPolicy=never` и `sandbox=danger-full-access` и не ожидает интерактивного подтверждения. Используйте её только с доверенными рабочими каталогами и учётной записью ОС с ограниченными правами.
- Runner использует только ресурсы LangBot, разрешённые для текущего запуска.
- Доступность, возможности моделей и лимиты запросов зависят от внешнего сервиса.
- Расширенное поведение и ограничения продукта описаны в китайском README в корне и английском README_en_US.md.


> Shared runtime / daemon upgrade: [required setup and safety contract](../README.md#shared-worker-candidate--daemon-upgrade). Shared 模式必须配置独立强 token 和端口；默认本地工作目录为 `/data/workspace`。请同时升级 daemon.py 与完整 pkg 目录；旧客户端不兼容。
