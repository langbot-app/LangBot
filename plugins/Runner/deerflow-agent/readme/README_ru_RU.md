# Агент DeerFlow

## Обзор

Запускает агент DeerFlow LangGraph как LangBot Runner.

## Информация о пакете

- **Runner ID**: `plugin:langbot-team/DeerFlowAgent/default`
- **Версия**: `0.1.2`
- **Репозиторий**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/deerflow-agent](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/deerflow-agent)

## Основные возможности

- **Включено**: `streaming`, `multimodal input`
- **Не заявлено**: `tool calling`, `knowledge retrieval`, `interrupt`

## Настройка

| Поле | Тип | Обязательно | По умолчанию |
| --- | --- | --- | --- |
| `api-base` | `string` | Да | `http://127.0.0.1:2026` |
| `api-key` | `secret` | Нет | Пусто |
| `auth-header` | `secret` | Нет | Пусто |
| `assistant-id` | `string` | Да | `lead_agent` |
| `advanced-settings` | `boolean` | Нет | false |
| `model-name` | `string` | Нет | Пусто |
| `thinking-enabled` | `boolean` | Нет | false |
| `plan-mode` | `boolean` | Нет | false |
| `subagent-enabled` | `boolean` | Нет | false |
| `max-concurrent-subagents` | `integer` | Нет | `3` |
| `timeout` | `integer` | Нет | `300` |
| `recursion-limit` | `integer` | Нет | `1000` |

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
