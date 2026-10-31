# Агент WeKnora

`agent-id` необязателен в обоих режимах. При отсутствии `chat` использует `builtin-quick-answer`, а `agent` — `builtin-smart-reasoning`; явно пустое значение не отправляет ID. Сохранённые ID не заменяются. `knowledge-base-ids` содержит удалённые ID WeKnora для обоих режимов, а не UUID LangBot.

## Обзор

Запускает агент WeKnora или чат с базой знаний как LangBot Runner.

## Информация о пакете

- **Runner ID**: `plugin:langbot-team/WeKnoraAgent/default`
- **Версия**: `0.1.2`
- **Репозиторий**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/weknora-agent](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/weknora-agent)

## Основные возможности

- **Включено**: `streaming`
- **Не заявлено**: `tool calling`, `knowledge retrieval`, `multimodal input`, `interrupt`

## Настройка

| Поле | Тип | Обязательно | По умолчанию |
| --- | --- | --- | --- |
| `base-url` | `string` | Да | `http://localhost:8080/api/v1` |
| `api-key` | `secret` | Да | Пусто |
| `app-type` | `select` | Да | `agent` |
| `agent-id` | `string` | Нет | `chat`: `builtin-quick-answer`; `agent`: `builtin-smart-reasoning` |
| `knowledge-base-ids` | `array[string]` | Нет | `[]` |
| `web-search-enabled` | `boolean` | Нет | false |
| `advanced-settings` | `boolean` | Нет | false |
| `timeout` | `integer` | Нет | `120` |
| `base-prompt` | `string` | Нет | `请回答用户的问题。` |

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
