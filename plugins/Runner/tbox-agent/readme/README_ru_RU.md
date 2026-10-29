# Агент Tbox

`remove-think` принимает только логическое значение (по умолчанию `false`). Значение `true` скрывает рассуждения и блоки `<think>`, включая границы потоковых фрагментов, сохраняя ответ и содержимое инструментов.

## Обзор

Запускает приложение Ant Tbox как LangBot Runner.

## Информация о пакете

- **Runner ID**: `plugin:langbot-team/TboxAgent/default`
- **Версия**: `0.1.0`
- **Репозиторий**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/tbox-agent](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/tbox-agent)

## Основные возможности

- **Включено**: `streaming`, `multimodal input`
- **Не заявлено**: `tool calling`, `knowledge retrieval`, `interrupt`

## Настройка

| Поле | Тип | Обязательно | По умолчанию |
| --- | --- | --- | --- |
| `api-key` | `secret` | Да | Пусто |
| `app-id` | `string` | Да | Пусто |
| `timeout` | `number` | Нет | `120` |

## Разрешения Host

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
A `sender` run whose Host actor is missing or empty is refused before any upstream request, instead of minting a per-run provider user; select `legacy-bot` explicitly when a conversation-scoped provider user is intended.
Explicit `legacy-bot` preserves native provider identity using trusted Host run context only;
missing identity fails before any upstream request, never falls back to the sender or business params.
`legacy-bot` uses `conversation.bot_id` (or Host runtime `bot_id` when there is no conversation), exactly, without a prefix.
Provider conversation/session persistence remains Runner-owned. Configuration migration does not import old conversation IDs, threads, transcripts, pending forms or files; finish/cancel pending work or perform a separately authorized state migration. Changing identity on an existing stored provider conversation requires an explicit reset/migration decision.
