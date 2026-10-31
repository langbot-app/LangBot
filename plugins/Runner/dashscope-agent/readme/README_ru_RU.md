# Агент DashScope

`remove-think` принимает только логическое значение (по умолчанию `false`). Значение `true` скрывает рассуждения и блоки `<think>`, включая границы потоковых фрагментов, сохраняя ответ и содержимое инструментов.

## Обзор

Запускает приложение Aliyun DashScope как LangBot Runner.

## Информация о пакете

- **Runner ID**: `plugin:langbot-team/DashScopeAgent/default`
- **Версия**: `0.1.2`
- **Репозиторий**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/dashscope-agent](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/dashscope-agent)

## Основные возможности

- **Включено**: `streaming`, `tool calling`, `knowledge retrieval`
- **Не заявлено**: `multimodal input`, `interrupt`

## Настройка

| Поле | Тип | Обязательно | По умолчанию |
| --- | --- | --- | --- |
| `app-type` | `select` | Да | `agent` |
| `api-key` | `secret` | Да | Пусто |
| `app-id` | `string` | Да | Пусто |
| `advanced-settings` | `boolean` | Нет | false |
| `references_quote` | `string` | Нет | `参考资料来自:` |
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
