# Агент рабочих процессов n8n

## Обзор

Запускает webhook рабочего процесса n8n как LangBot Runner.

## Информация о пакете

- **Runner ID**: `plugin:langbot-team/N8nAgent/default`
- **Версия**: `0.1.2`
- **Репозиторий**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/n8n-agent](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/n8n-agent)

## Основные возможности

- **Включено**: `streaming`, `tool calling`, `knowledge retrieval`
- **Не заявлено**: `multimodal input`, `interrupt`

## Настройка

| Поле | Тип | Обязательно | По умолчанию |
| --- | --- | --- | --- |
| `webhook-url` | `string` | Да | Пусто |
| `auth-type` | `select` | Да | `none` |
| `basic-username` | `string` | Нет | Пусто |
| `basic-password` | `secret` | Нет | Пусто |
| `jwt-secret` | `secret` | Нет | Пусто |
| `jwt-algorithm` | `string` | Нет | `HS256` |
| `header-name` | `string` | Нет | Пусто |
| `header-value` | `secret` | Нет | Пусто |
| `advanced-settings` | `boolean` | Нет | false |
| `timeout` | `integer` | Нет | `120` |
| `output-key` | `string` | Нет | `response` |
| `response-handling` (`reply` / `ignore`) | `select` | Нет | `reply` |
| `basic-encoding` (`utf-8` / `latin1`) | `select` | Нет | `utf-8` |
| `langbot-assets-enabled` | `boolean` | Нет | false |
| `langbot-assets-gateway-host` | `string` | Нет | `0.0.0.0` |
| `langbot-assets-gateway-port` | `integer` | Нет | `8765` |
| `langbot-assets-gateway-request-timeout` | `integer` | Нет | `60` |
| `langbot-assets-token-ttl` | `integer` | Нет | `3600` |
| `langbot-assets-input-name` | `string` | Нет | `langbot_asset_run_token` |

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

### Provider identity compatibility (`user-id-source`)

Per-pipeline Runner parameter, not plugin-global configuration. `sender` remains the default.
A `sender` run whose Host actor is missing or empty is refused before any upstream request, instead of minting a per-run provider user; select `legacy-session` explicitly when a conversation-scoped provider user is intended.
Explicit `legacy-session` preserves native provider identity using trusted Host run context only;
missing identity fails before any upstream request, never falls back to the sender or business params.
`legacy-session` uses `conversation.launcher_type` (`group`/`person`) plus `_` plus the exact `conversation.launcher_id`. Host must project the native Query.session launcher into those fields, including interaction/resume runs. Older Hosts that leave these fields empty must be upgraded.
Provider conversation/session persistence remains Runner-owned. Configuration migration does not import old conversation IDs, threads, transcripts, pending forms or files; finish/cancel pending work or perform a separately authorized state migration. Changing identity on an existing stored provider conversation requires an explicit reset/migration decision.
