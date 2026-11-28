export default {
  managerRequired:
    'Для управления разрешениями требуется resource.manage. Подтверждать доступ могут только учётные записи; ключи API могут лишь отзывать его.',
  title: 'Разрешения плагина',
  compatibilityNote:
    'Плагин не объявляет нужные разрешения. Для обратной совместимости он получает перечисленные ниже устаревшие возможности; позже их можно отключить по одной.',
  statusPending: 'Требует одобрения',
  statusNone: 'Разрешения не нужны',
  grant: 'Разрешить',
  pendingHint: 'Плагин останется выключенным, пока вы не выдадите разрешения.',
  confirmTitle: 'Выдать разрешения плагину',
  highlightedList: 'Обратите внимание: {{items}}',
  listSeparator: ', ',
  grantCount: 'Выдать: {{count}}',
  undeclared: 'Разрешения не объявлены',
  pending: 'Требуется подтверждение разрешений',
  saved: 'Разрешения сохранены',
  failed: 'Не удалось обновить разрешения',
  retry: 'Повторить',
  revoke: 'Отозвать',
  dangerous: 'Опасно',
  sendsMessages: 'Отправка сообщений бота',
  requires: 'Требуется {{permissions}}',
  review: 'Проверить',
  reviewLabel: 'Проверить разрешения',
  confirmDescription:
    'Предоставить выбранные разрешения этому плагину. Опасные разрешения и отправка сообщений выделены отдельно.',
  grantInPlugin: 'Сначала разрешите операцию в разрешениях плагина',
  workspaceOperations: 'Операции рабочего пространства',
  capabilities: 'Возможности плагина',
  granted: 'Выдано',
  grantedCount: 'Выдано {{granted}} из {{total}}',
  empty: 'Плагин не запрашивает разрешений.',
  pendingCount: 'Плагинов, ожидающих подтверждения: {{count}}',
  searchPlaceholder: 'Поиск по названию или ID…',
  selectAll: 'Выбрать все',
  noResults: 'Нет подходящих разрешений',
  willGrant: 'Будет выдано',
  willRevoke: 'Будет отозвано',
  selectedCount: 'Выбрано: {{count}}',
  pendingChanges: '+{{added}} выдано, −{{removed}} отозвано',
  newGrants: 'Будет выдано разрешений: {{count}}',
  alsoRevoking: 'Также будет отозвано: {{count}}.',
  capabilityGroup: {
    bot: 'Боты',
    models: 'Модели',
    knowledge: 'Знания',
    storage: 'Хранилище',
    extensions: 'Плагины и MCP',
    runtime: 'Среда выполнения',
    other: 'Прочее',
  },
  capability: {
    langbot_info: {
      label: 'Версия LangBot',
      description: 'Читать версию LangBot',
    },
    bot_read: {
      label: 'Чтение ботов',
      description: 'Список ботов и их данные',
    },
    bot_message_send: {
      label: 'Отправка сообщений',
      description: 'Отправлять сообщения через ботов',
    },
    bot_platform_api: {
      label: 'API платформы',
      description: 'Вызывать нативный API IM-платформы через бота',
    },
    models_read: {
      label: 'Чтение моделей',
      description: 'Список настроенных моделей',
    },
    models_invoke: {
      label: 'Вызов моделей',
      description: 'Вызывать LLM, эмбеддинги и реранкинг',
    },
    storage_plugin: {
      label: 'Хранилище плагина',
      description: 'Чтение и запись собственного хранилища',
    },
    storage_workspace: {
      label: 'Общее хранилище',
      description: 'Чтение и запись общего хранилища пространства',
    },
    knowledge_read: {
      label: 'Чтение знаний',
      description: 'Список и поиск по базам знаний',
    },
    knowledge_vector: {
      label: 'Векторное хранилище',
      description: 'Запись, поиск и удаление векторов',
    },
    knowledge_parser: {
      label: 'Парсеры документов',
      description: 'Список и вызов парсеров',
    },
    config_read: {
      label: 'Чтение конфигурации',
      description: 'Читать загруженные файлы конфигурации',
    },
    plugin_tools: {
      label: 'Инструменты плагинов',
      description: 'Список и вызов инструментов других плагинов',
    },
    mcp: {
      label: 'MCP',
      description: 'Вызов инструментов и чтение ресурсов MCP',
    },
    sandbox: {
      label: 'Песочница',
      description: 'Получить песочницу Box и выполнять код',
    },
    plugin_read: {
      label: 'Чтение плагинов',
      description: 'Список установленных плагинов и команд',
    },
  },
};
