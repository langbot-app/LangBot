export default {
  managerRequired:
    '権限管理には resource.manage が必要です。付与の確認はアカウントのみ可能で、API キーでは既存の権限の取消のみ可能です。',
  title: 'プラグイン権限',
  undeclared: '権限未宣言',
  compatibilityWarning:
    'このプラグインは権限を宣言していません。確認時に従来の API の全16権限を付与します。確認後は個別に取り消せます。ワークスペース Application API 操作は含みません。',
  pending: '権限の確認が必要です',
  saved: '権限を保存しました',
  failed: '権限を更新できません',
  retry: '再試行',
  revoke: '取り消す',
  dangerous: '危険な操作',
  sendsMessages: 'ボットメッセージ送信',
  requires: '必要な権限: {{permissions}}',
  review: '権限を確認',
  confirm: '付与を確定',
  confirmDescription:
    '選択した権限をこのプラグインに付与します。危険な権限とボット送信権限を強調表示しています。',
  grantInPlugin: '先にプラグイン権限でこの操作を許可してください',
};
