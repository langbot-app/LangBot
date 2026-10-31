# Агент Coze

`remove-think` принимает только логическое значение (по умолчанию `false`). Значение `true` скрывает рассуждения и блоки `<think>`, включая границы потоковых фрагментов, сохраняя ответ и содержимое инструментов.

## Обзор

Запускает бота Coze как LangBot Runner.

## Информация о пакете

- **Runner ID**: `plugin:langbot-team/CozeAgent/default`
- **Версия**: `0.1.2`
- **Репозиторий**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/coze-agent](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/coze-agent)

## Основные возможности

- **Включено**: `streaming`, `tool calling`, `knowledge retrieval`, `multimodal input`
- **Не заявлено**: `interrupt`

## Настройка

| Поле | Тип | Обязательно | По умолчанию |
| --- | --- | --- | --- |
| `api-key` | `secret` | Да | Пусто |
| `bot-id` | `string` | Да | Пусто |
| `api-base` | `string` | Да | `https://api.coze.cn` |
| `advanced-settings` | `boolean` | Нет | false |
| `auto-save-history` | `boolean` | Нет | true |
| `timeout` | `number` | Нет | `120` |
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
`legacy-session` uses `conversation.launcher_type` (`group`/`person`) plus `_` plus the exact `conversation.launcher_id`. Host must project the Query launcher for Coze into those fields, including interaction/resume runs. Older Hosts that leave these fields empty must be upgraded.
Provider conversation/session persistence remains Runner-owned. Configuration migration does not import old conversation IDs, threads, transcripts, pending forms or files; finish/cancel pending work or perform a separately authorized state migration. Changing identity on an existing stored provider conversation requires an explicit reset/migration decision.
