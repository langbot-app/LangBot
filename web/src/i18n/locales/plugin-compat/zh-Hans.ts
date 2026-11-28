export default {
  rangeAtLeast: '≥ {{min}}',
  rangeAtMost: '≤ {{max}}',
  rangeSeparator: '，',
  rangeAny: '不限',
  declared: '声明兼容 LangBot {{range}}',
  badge: '版本不兼容',
  badgeInvalid: '兼容声明无效',
  incompatibleTitle: '该插件声明不兼容当前 LangBot',
  incompatibleBody:
    '插件声明支持 LangBot {{range}}，当前版本为 {{current}}。安装后可能无法正常运行。',
  invalidTitle: '该插件的版本兼容声明无效',
  invalidBody:
    '插件的 LangBot 版本范围格式不正确，无法判断是否兼容当前版本 {{current}}。安装后可能无法正常运行。',
  acknowledge: '我了解该插件声明不兼容当前版本，仍要安装',
  installAnyway: '仍然安装',
  installedIncompatibleBody:
    '插件声明支持 LangBot {{range}}，当前版本为 {{current}}。插件仍会按原设置运行，如遇异常请更新插件或调整 LangBot 版本。',
  installedInvalidBody:
    '插件的 LangBot 版本范围格式不正确，当前版本为 {{current}}。插件仍会按原设置运行。',
  githubRetryHint: '确认后将重新下载并安装。',
  retrying: '正在重新提交…',
  noCompatibleVersion:
    '该插件没有兼容当前 LangBot（{{current}}）的版本，暂时无法安装。',
  switchedVersion:
    '链接中的版本 {{requested}} 不兼容当前 LangBot，已为你选择兼容版本 {{version}}。',
  resolvingVersion: '正在确认兼容版本…',
};
