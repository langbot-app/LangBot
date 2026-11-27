export default {
  rangeAtLeast: '≥ {{min}}',
  rangeAtMost: '≤ {{max}}',
  rangeSeparator: '、',
  rangeAny: '制限なし',
  declared: '対応 LangBot {{range}}',
  badge: '非対応バージョン',
  badgeInvalid: '無効な宣言',
  incompatibleTitle: 'このプラグインは現在の LangBot に対応していません',
  incompatibleBody:
    'プラグインの対応 LangBot は {{range}} で、現在のバージョンは {{current}} です。正常に動作しない可能性があります。',
  invalidTitle: 'このプラグインのバージョン互換宣言が無効です',
  invalidBody:
    'LangBot バージョン範囲の形式が正しくないため、現在のバージョン {{current}} との互換性を判断できません。正常に動作しない可能性があります。',
  acknowledge:
    'このプラグインが現在のバージョンに対応していないことを理解したうえでインストールします',
  installAnyway: 'それでもインストール',
  installedIncompatibleBody:
    'プラグインの対応 LangBot は {{range}} で、現在のバージョンは {{current}} です。現在の設定のまま動作します。問題がある場合はプラグインを更新するか LangBot のバージョンを変更してください。',
  installedInvalidBody:
    'LangBot バージョン範囲の形式が正しくありません（現在のバージョン {{current}}）。現在の設定のまま動作します。',
  githubRetryHint: '確認後、パッケージを再ダウンロードしてインストールします。',
  retrying: '再送信しています…',
  noCompatibleVersion:
    '現在の LangBot（{{current}}）に対応するバージョンがないため、インストールできません。',
  switchedVersion:
    'リンクのバージョン {{requested}} は現在の LangBot に対応していないため、対応バージョン {{version}} を選択しました。',
  resolvingVersion: '対応バージョンを確認しています…',
};
