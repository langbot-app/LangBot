export default {
  rangeAtLeast: '≥ {{min}}',
  rangeAtMost: '≤ {{max}}',
  rangeSeparator: ', ',
  rangeAny: 'любая версия',
  declared: 'Поддерживает LangBot {{range}}',
  badge: 'Несовместим',
  badgeInvalid: 'Неверный диапазон',
  incompatibleTitle: 'Плагин не поддерживает вашу версию LangBot',
  incompatibleBody:
    'Плагин заявляет LangBot {{range}}, у вас {{current}}. Он может работать некорректно.',
  invalidTitle: 'У плагина неверное объявление совместимости',
  invalidBody:
    'Диапазон версий LangBot в плагине задан неверно, поэтому совместимость с {{current}} определить нельзя. Он может работать некорректно.',
  acknowledge:
    'Я понимаю, что плагин не заявляет поддержку моей версии, и всё равно хочу установить его',
  installAnyway: 'Всё равно установить',
  installedIncompatibleBody:
    'Плагин заявляет LangBot {{range}}, у вас {{current}}. Он продолжает работать с текущими настройками. При сбоях обновите плагин или смените версию LangBot.',
  installedInvalidBody:
    'Диапазон версий LangBot в плагине задан неверно, у вас {{current}}. Он продолжает работать с текущими настройками.',
  githubRetryHint: 'Пакет будет загружен и установлен заново.',
  retrying: 'Повторная отправка…',
  noCompatibleVersion:
    'Ни одна версия плагина не поддерживает вашу версию LangBot ({{current}}), поэтому установить его пока нельзя.',
  switchedVersion:
    'Версия {{requested}} из ссылки не поддерживает вашу версию LangBot. Будет установлена совместимая версия {{version}}.',
  resolvingVersion: 'Поиск совместимой версии…',
};
