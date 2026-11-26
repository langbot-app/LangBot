export default {
  rangeAtLeast: '≥ {{min}}',
  rangeAtMost: '≤ {{max}}',
  rangeSeparator: '，',
  rangeAny: '不限',
  declared: '宣告相容 LangBot {{range}}',
  badge: '版本不相容',
  badgeInvalid: '相容宣告無效',
  incompatibleTitle: '此插件宣告不相容目前的 LangBot',
  incompatibleBody:
    '插件宣告支援 LangBot {{range}}，目前版本為 {{current}}。安裝後可能無法正常執行。',
  invalidTitle: '此插件的版本相容宣告無效',
  invalidBody:
    '插件的 LangBot 版本範圍格式不正確，無法判斷是否相容目前版本 {{current}}。安裝後可能無法正常執行。',
  acknowledge: '我了解此插件宣告不相容目前版本，仍要安裝',
  installAnyway: '仍然安裝',
  installedIncompatibleBody:
    '插件宣告支援 LangBot {{range}}，目前版本為 {{current}}。插件仍會依原設定執行，如遇異常請更新插件或調整 LangBot 版本。',
  installedInvalidBody:
    '插件的 LangBot 版本範圍格式不正確，目前版本為 {{current}}。插件仍會依原設定執行。',
  githubRetryHint: '確認後將重新下載並安裝。',
  retrying: '正在重新提交…',
  noCompatibleVersion:
    '此插件沒有相容目前 LangBot（{{current}}）的版本，暫時無法安裝。',
  switchedVersion:
    '連結中的版本 {{requested}} 不相容目前的 LangBot，已為你選擇相容版本 {{version}}。',
  resolvingVersion: '正在確認相容版本…',
};
