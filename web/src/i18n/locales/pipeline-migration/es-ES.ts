export default {
  complete: 'Finalizar',
  checkingPlugin: 'Comprobar plugin',
  preparingPlugin: 'Preparar instalación',
  installDetails: 'Detalles de instalación',
  stageProgress: 'Progreso por etapas',
  downloaded: 'Descargado {{size}}',
  processed: 'Procesados {{completed}} / {{total}} pipelines',
  installErrors: {
    plugin_version_unavailable:
      'La versión requerida aún no está disponible en el mercado. Reintenta tras su publicación o migra solo los datos.',
    plugin_download_timeout:
      'La descarga agotó el tiempo de espera. Revisa la red y reintenta.',
    plugin_marketplace_unavailable:
      'El mercado no puede servir el paquete. Reintenta más tarde.',
    plugin_download_failed: 'No se pudo descargar el plugin. Revisa la red.',
    dependency_prepare_failed:
      'No se pudieron instalar las dependencias. Revisa el entorno de ejecución.',
    plugin_launch_failed:
      'El plugin no pudo iniciarse. Revisa el entorno de ejecución.',
  },
  autoDescription:
    'Los ejecutores antiguos ahora son plugins. Migra todos los pipelines conservando sus ajustes. Se guardará una copia de la configuración y las conversaciones empezarán de nuevo.',
  viewPipelines: 'Ver pipelines',
  autoInstall: 'Instalar plugins y migrar',
  dataOnly: 'Migrar solo los datos',
  dataOnlyHint:
    'Para redes privadas o sin conexión. Instala los plugins de ejecución correspondientes después de la migración.',
  installing: 'Instalando los plugins necesarios…',
  migrating: 'Migrando pipelines…',
  summary: '{{migrated}} migrados; {{remaining}} requieren atención.',
  installFailed:
    'La instalación falló. Consulta la etapa fallida en los detalles y reintenta, o migra solo los datos.',

  activationRetryHint:
    'Tras comprobar el entorno, actualiza, selecciona esta canalización y confirma para reintentar solo la activación. No se volverá a migrar la configuración guardada.',
  details: 'Detalles de migración',
  notices: {
    runtimeUnavailable:
      'El entorno de plugins está desconectado. Restablece la conexión y reintenta, o migra solo los datos.',
    executionFailed:
      'La migración falló. Revisa los registros del servidor y reintenta.',
    pluginRequired:
      'Instala o activa el plugin de ejecución indicado arriba y actualiza la vista previa.',
    legacyArchive:
      'La configuración activa contendrá solo el Runner seleccionado. Todos los ajustes anteriores, incluidos los inactivos, se conservan en la copia de seguridad de migración.',
    contextDefaults:
      'El historial usará el nuevo presupuesto de contexto y los valores de resumen, en lugar de un límite fijo de turnos.',
    modelReasoning:
      'Se conservan los ajustes de razonamiento por modelo y el host los aplica.',
    serialTools: 'Las herramientas seguirán ejecutándose de forma secuencial.',
    retrievalDefaults:
      'La recuperación usará los nuevos límites de top-k y longitud. Revísalos después de migrar.',
    boxReset:
      'Se conserva la configuración de reutilización del sandbox. El estado del contenedor no se migra; los nuevos sandboxes siguen las mismas reglas.',
    persistentHistory:
      'Las nuevas conversaciones tendrán un historial persistente y aislado. No se importa el historial remoto anterior.',
    tweaksDefault:
      'Langflow tweaks usa un objeto vacío de forma predeterminada.',
    timeoutDefault:
      'Dify usa un tiempo de espera de 30 segundos de forma predeterminada.',
    historyReset:
      'No se transfieren el historial ni los identificadores de sesión. Después de migrar se iniciarán conversaciones nuevas.',
    sessionTitle:
      'Las nuevas sesiones de WeKnora usan títulos generados por el plugin.',
    aliasRepaired:
      'El nombre antiguo del campo se sustituye por el nombre admitido.',
    nullDefault:
      'Este valor vacío usará el valor predeterminado del nuevo plugin.',
    outputPolicy:
      'Se conserva la visibilidad actual del contenido de razonamiento.',
    filteredVariables:
      'Solo se transfieren variables admitidas; el contexto de la conversación proporciona las variables reservadas.',
    identityPreserved:
      'La identidad de usuario del proveedor conserva su origen anterior.',
    newDefaults:
      'Las opciones nuevas usan los valores predeterminados documentados; se conservan los valores anteriores admitidos.',
    externalState:
      'Completa o cancela las interacciones remotas pendientes antes de migrar; su estado activo no se transfiere.',
    pluginVersion:
      'Instala la versión requerida del plugin y actualiza. Las versiones anteriores no admiten esta migración.',
    schemaChanged:
      'La configuración del Runner instalado no coincide con el destino. Revisa la versión del plugin y actualiza.',
    runnerExcluded:
      'Esta canalización excluye el plugin Runner necesario. Ajusta primero la configuración de extensiones.',
    boxTemplateInvalid:
      'Plantilla de reutilización inválida. Use {nombre_variable}; no se admiten campos posicionales, conversiones de formato ni acceso a atributos.',
    pendingInteraction:
      'Hay una conversación esperando una respuesta. Complétala o cancélala antes de migrar.',
  },
  title: 'Migración de pipelines',
  description:
    'Selecciona los pipelines que deseas migrar. Se guardará una copia de la configuración y las conversaciones empezarán de nuevo.',
  detected: '{{count}} pipelines requieren revisión.',
  review: 'Revisar migración',
  readOnly: 'Solo los gestores del espacio pueden migrar pipelines.',
  previewError: 'Vista previa no disponible. Actualícela.',
  submitting: 'Enviando pipelines seleccionados…',
  running: 'Migración en curso. Cerrar el diálogo no cancela la tarea.',
  finished: 'Tarea finalizada. Revise el resultado de cada pipeline.',
  failed: 'La tarea falló. Revise el resultado de cada pipeline.',
  lost: 'Se perdió el seguimiento de la tarea; se desconoce el resultado. Actualice la vista previa antes de actuar.',
  requestError:
    'Solicitud no completada. Actualice la vista previa y vuelva a seleccionar.',
  warningFallback: 'Revise este ajuste antes de migrar.',
  blockerFallback:
    'Este ajuste o estado de ejecución no se puede migrar de forma segura. Resuélvalo y actualice la vista previa.',
  changedFields: 'Campos modificados',
  activationHint:
    'Configuración guardada, pero activación pendiente. Pida al administrador que compruebe el entorno y actualice. No repita la migración a ciegas.',
  pluginHint:
    '¿Falta un plugin? Instala o activa su ejecutor en Extensiones y actualiza la vista previa.',
  extensions: 'Abrir Extensiones',
  results: 'Resultados por pipeline',
  selection: '{{count}} seleccionados (máximo 50)',
  confirm: 'Confirmo la migración de los pipelines seleccionados.',
  refresh: 'Actualizar vista previa',
  execute: 'Migrar seleccionados',
  legacyGate:
    'La configuración antigua es de solo lectura hasta la migración. Guardar y depurar no están disponibles para evitar una conversión implícita.',
  states: {
    ready: 'Listo',
    needs_plugin: 'Plugin requerido',
    blocked: 'Bloqueado',
    already_current: 'Ya actualizado',
    not_legacy: 'No es antiguo',
    activation_pending: 'Activación pendiente',
    pending: 'Pendiente',
    migrated: 'Migrado',
    stale: 'Vista previa caducada',
    failed: 'Fallido',
  },
};
