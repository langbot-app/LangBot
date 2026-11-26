export default {
  rangeAtLeast: '≥ {{min}}',
  rangeAtMost: '≤ {{max}}',
  rangeSeparator: ', ',
  rangeAny: 'any version',
  declared: 'Supports LangBot {{range}}',
  badge: 'Incompatible',
  badgeInvalid: 'Invalid range',
  incompatibleTitle: 'This plugin does not support your LangBot version',
  incompatibleBody:
    'The plugin declares LangBot {{range}}; you are running {{current}}. It may not work correctly.',
  invalidTitle: 'This plugin has an invalid compatibility declaration',
  invalidBody:
    "The plugin's LangBot version range is malformed, so compatibility with {{current}} cannot be determined. It may not work correctly.",
  acknowledge:
    'I understand this plugin does not declare support for my version and want to install it anyway',
  installAnyway: 'Install anyway',
  installedIncompatibleBody:
    'The plugin declares LangBot {{range}}; you are running {{current}}. It keeps running with its current settings. If it misbehaves, update the plugin or change your LangBot version.',
  installedInvalidBody:
    "The plugin's LangBot version range is malformed; you are running {{current}}. It keeps running with its current settings.",
  githubRetryHint: 'The package will be downloaded and installed again.',
  retrying: 'Resubmitting…',
  noCompatibleVersion:
    'No version of this plugin supports your LangBot version ({{current}}), so it cannot be installed yet.',
  switchedVersion:
    'Version {{requested}} from the link does not support your LangBot version. Installing compatible version {{version}} instead.',
  resolvingVersion: 'Checking for a compatible version…',
};
