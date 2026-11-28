export default {
  managerRequired:
    'Gestionar permisos requiere resource.manage. Solo las cuentas pueden confirmar concesiones; las claves API solo pueden revocarlas.',
  title: 'Permisos del complemento',
  compatibilityNote:
    'Este plugin no declara los permisos que necesita. Por compatibilidad, recibe las capacidades heredadas de abajo; puedes desactivarlas una a una después.',
  statusPending: 'Pendiente de aprobación',
  statusNone: 'No requiere permisos',
  grant: 'Conceder',
  pendingHint:
    'El plugin permanece desactivado hasta que concedas sus permisos.',
  confirmTitle: 'Conceder permisos al plugin',
  highlightedList: 'Atención: {{items}}',
  listSeparator: ', ',
  grantCount: 'Conceder {{count}}',
  undeclared: 'Permisos no declarados',
  pending: 'Se requiere confirmar los permisos',
  saved: 'Permisos guardados',
  failed: 'No se pudieron actualizar los permisos',
  retry: 'Reintentar',
  revoke: 'Revocar',
  dangerous: 'Peligroso',
  sendsMessages: 'Envía mensajes del bot',
  requires: 'Requiere {{permissions}}',
  review: 'Revisar',
  reviewLabel: 'Revisar permisos',
  confirmDescription:
    'Concede los permisos seleccionados a esta instalación. Se destacan los permisos peligrosos y el envío de mensajes.',
  grantInPlugin:
    'Concede primero esta operación en los permisos del complemento',
  workspaceOperations: 'Operaciones del espacio de trabajo',
  capabilities: 'Capacidades del plugin',
  granted: 'Concedido',
  grantedCount: '{{granted}} de {{total}} concedidos',
  empty: 'Este plugin no solicita ningún permiso.',
  pendingCount: 'Pendientes de confirmación: {{count}}',
  searchPlaceholder: 'Buscar por nombre o ID…',
  selectAll: 'Seleccionar todo',
  noResults: 'No hay permisos que coincidan',
  willGrant: 'Se concederá',
  willRevoke: 'Se revocará',
  selectedCount: '{{count}} seleccionados',
  pendingChanges: '+{{added}} concedidos, −{{removed}} revocados',
  newGrants: 'Se concederán {{count}} permisos',
  alsoRevoking: 'También se revocarán {{count}}.',
  capabilityGroup: {
    bot: 'Bots',
    models: 'Modelos',
    knowledge: 'Conocimiento',
    storage: 'Almacenamiento',
    extensions: 'Plugins y MCP',
    runtime: 'Entorno',
    other: 'Otros',
  },
  capability: {
    langbot_info: {
      label: 'Versión de LangBot',
      description: 'Leer la versión de LangBot',
    },
    bot_read: {
      label: 'Leer bots',
      description: 'Listar bots y leer sus detalles',
    },
    bot_message_send: {
      label: 'Enviar mensajes',
      description: 'Enviar mensajes a través de los bots',
    },
    bot_platform_api: {
      label: 'API de plataforma',
      description: 'Llamar a la API nativa de la plataforma IM',
    },
    models_read: {
      label: 'Leer modelos',
      description: 'Listar los modelos configurados',
    },
    models_invoke: {
      label: 'Invocar modelos',
      description: 'Llamar a modelos LLM, de embeddings y rerank',
    },
    storage_plugin: {
      label: 'Almacenamiento del plugin',
      description: 'Leer y escribir el almacenamiento propio',
    },
    storage_workspace: {
      label: 'Almacenamiento compartido',
      description: 'Leer y escribir almacenamiento compartido del espacio',
    },
    knowledge_read: {
      label: 'Leer conocimiento',
      description: 'Listar y consultar bases de conocimiento',
    },
    knowledge_vector: {
      label: 'Almacén vectorial',
      description: 'Escribir, buscar y borrar vectores',
    },
    knowledge_parser: {
      label: 'Analizadores',
      description: 'Listar e invocar analizadores de documentos',
    },
    config_read: {
      label: 'Leer archivos de configuración',
      description: 'Leer archivos de configuración subidos',
    },
    plugin_tools: {
      label: 'Herramientas de plugins',
      description: 'Listar y llamar herramientas de otros plugins',
    },
    mcp: {
      label: 'MCP',
      description: 'Llamar herramientas y leer recursos MCP',
    },
    sandbox: {
      label: 'Sandbox',
      description: 'Obtener un sandbox Box y ejecutar código',
    },
    plugin_read: {
      label: 'Leer plugins',
      description: 'Listar plugins y comandos instalados',
    },
  },
};
