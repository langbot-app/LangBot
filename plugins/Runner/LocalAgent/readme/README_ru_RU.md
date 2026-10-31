# Встроенный агент

## Обзор

Встроенный агент с резервными моделями, инструментами и поиском по базе знаний.

## Информация о пакете

- **Runner ID**: `plugin:langbot-team/LocalAgent/default`
- **Версия**: `0.1.0`
- **Репозиторий**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/LocalAgent](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/LocalAgent)

## Основные возможности

- **Включено**: `streaming`, `tool calling`, `knowledge retrieval`, `multimodal input`, `skill authoring`, `interrupt`, `steering`
- **Не заявлено**: Пусто

## Настройка

| Поле | Тип | Обязательно | По умолчанию |
| --- | --- | --- | --- |
| `model` | `model-fallback-selector` | Да | `{fallbacks: [], primary: '', reasoning: {}}` |
| `timeout` | `integer` | Нет | `300` |
| `prompt` | `prompt-editor` | Да | `[{content: You are a helpful assistant., role: system}]` |
| `remove-think` | `boolean` | Нет | false |
| `knowledge-bases` | `knowledge-base-multi-selector` | Нет | `[]` |
| `advanced-settings` | `boolean` | Нет | `false` |
| `date-grounding` | `boolean` | Нет | `true` |
| `retrieval-top-k` | `integer` | Нет | `5` |
| `rerank-model` | `rerank-model-selector` | Нет | Пусто |
| `rerank-top-k` | `integer` | Нет | `5` |
| `max-tool-iterations` | `integer` | Нет | `100` |
| `tool-execution-mode` | `select` | Нет | `parallel` |
| `max-tool-result-chars` | `integer` | Нет | `20000` |
| `context-history-fetch-limit` | `integer` | Нет | `50` |
| `context-window-tokens` | `integer` | Нет | `200000` |
| `context-reserve-tokens` | `integer` | Нет | `16384` |
| `context-keep-recent-tokens` | `integer` | Нет | `20000` |
| `context-summary-tokens` | `integer` | Нет | `8000` |

## Разрешения Host

- **`models`**: `count_tokens`, `invoke`, `stream`, `rerank`
- **`tools`**: `detail`, `call`
- **`knowledge_bases`**: `list`, `retrieve`
- **`history`**: `page`

## Установка и использование

1. Установите плагин из магазина плагинов LangBot.
2. Выберите указанный Runner ID в селекторе Runner вашего Pipeline.
3. Заполните параметры подключения по таблице и храните секреты в полях secret панели управления.

## Безопасность и ограничения

- Runner использует только ресурсы LangBot, разрешённые для текущего запуска.
- Доступность, возможности моделей и лимиты запросов зависят от внешнего сервиса.
- Расширенное поведение и ограничения продукта описаны в китайском README в корне и английском README_en_US.md.

## Box

`box-enabled` включает песочницу. Шаблон `box-session-id-template` по умолчанию равен `{launcher_type}_{launcher_id}` для повторного использования по чатам; `{global}` задаёт общий Box в рабочем пространстве. Доступны `{sender_id}`, `{bot_id}`, `{run_id}` и переменные запроса. Runner выбирает Box, импортирует вложения и после успешного завершения явно экспортирует outbox текущего запуска.
