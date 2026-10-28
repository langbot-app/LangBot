# Claude Code Agent

## Обзор

Запускает Claude Code CLI как LangBot Runner.

## Информация о пакете

- **Runner ID**: `plugin:langbot-team/ClaudeCodeAgent/default`
- **Версия**: `0.1.3`
- **Репозиторий**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/claude-code-agent](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/claude-code-agent)

## Основные возможности

- **Включено**: `streaming`, `tool calling`, `knowledge retrieval`, `steering`
- **Не заявлено**: `multimodal input`, `interrupt`

## Настройка

| Поле | Тип | Обязательно | По умолчанию |
| --- | --- | --- | --- |
| `daemon-enabled` | `boolean` | Нет | false |
| `daemon-host` | `string` | Нет | `127.0.0.1` |
| `daemon-port` | `integer` | Нет | `8767` |
| `daemon-token` | `secret` | Нет | Пусто |
| `location` | `select` | Да | `local` |
| `workspace` | `string` | Нет | Пусто |
| `advanced-settings` | `boolean` | Нет | false |
| `command` | `string` | Нет | `claude` |
| `args-json` | `string` | Нет | `[]` |
| `env-json` | `string` | Нет | `{}` |
| `ssh-target` | `string` | Нет | Пусто |
| `ssh-port` | `integer` | Нет | `22` |
| `daemon-id` | `string` | Нет | Пусто |
| `timeout` | `integer` | Нет | `300` |
| `streaming` | `boolean` | Нет | true |
| `reuse-session` | `boolean` | Нет | true |
| `dangerously-skip-permissions` | `boolean` | Нет | true |
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

- Runner использует только ресурсы LangBot, разрешённые для текущего запуска.
- По умолчанию Claude Code запускается с `--dangerously-skip-permissions`, поскольку в LangBot пока нет интерактивного подтверждения. Используйте этот режим только в доверенном рабочем каталоге и под ограниченной системной учётной записью; задайте false, чтобы вернуть обычную проверку разрешений.
- Доступность, возможности моделей и лимиты запросов зависят от внешнего сервиса.
- Расширенное поведение и ограничения продукта описаны в китайском README в корне и английском README_en_US.md.


> Shared runtime / daemon upgrade: [required setup and safety contract](../README.md#shared-worker-candidate--daemon-upgrade). Shared 模式必须配置独立强 token 和端口；默认本地工作目录为 `/data/workspace`。请同时升级 daemon.py 与完整 pkg 目录；旧客户端不兼容。
