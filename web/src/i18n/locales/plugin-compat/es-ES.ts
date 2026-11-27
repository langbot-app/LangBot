export default {
  rangeAtLeast: '≥ {{min}}',
  rangeAtMost: '≤ {{max}}',
  rangeSeparator: ', ',
  rangeAny: 'cualquier versión',
  declared: 'Compatible con LangBot {{range}}',
  badge: 'Incompatible',
  badgeInvalid: 'Rango no válido',
  incompatibleTitle: 'Este plugin no es compatible con tu versión de LangBot',
  incompatibleBody:
    'El plugin declara LangBot {{range}}; usas {{current}}. Puede que no funcione correctamente.',
  invalidTitle: 'Este plugin tiene una declaración de compatibilidad no válida',
  invalidBody:
    'El rango de versiones de LangBot del plugin no es válido, así que no se puede determinar la compatibilidad con {{current}}. Puede que no funcione correctamente.',
  acknowledge:
    'Entiendo que este plugin no declara compatibilidad con mi versión y quiero instalarlo igualmente',
  installAnyway: 'Instalar de todos modos',
  installedIncompatibleBody:
    'El plugin declara LangBot {{range}}; usas {{current}}. Sigue funcionando con su configuración actual. Si falla, actualiza el plugin o cambia la versión de LangBot.',
  installedInvalidBody:
    'El rango de versiones de LangBot del plugin no es válido; usas {{current}}. Sigue funcionando con su configuración actual.',
  githubRetryHint: 'El paquete se descargará e instalará de nuevo.',
  retrying: 'Reenviando…',
  noCompatibleVersion:
    'Ninguna versión de este plugin es compatible con tu versión de LangBot ({{current}}), por lo que aún no se puede instalar.',
  switchedVersion:
    'La versión {{requested}} del enlace no es compatible con tu LangBot. Se instalará la versión compatible {{version}}.',
  resolvingVersion: 'Buscando una versión compatible…',
};
