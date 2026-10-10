export default {
  title: 'Slack クイック設定',
  description:
    'アプリを自動作成・設定し、インストール承認後に認証情報を入力します。',
  saveFirst: '先にボットの下書きを作成してください。',
  generate: 'App Configuration Tokens を生成',
  name: 'アプリ名',
  redirect: 'OAuth 戻り先 URL',
  webhook: 'Webhook URL',
  redirectHint:
    'ブラウザーからアクセス可能な HTTPS または http://localhost を指定します。公開イベント Webhook は不要です。',
  webhookHint: '公開 HTTPS URL を指定し、末尾の /bots/… を維持してください。',
  create: '作成して自動設定',
  creating: 'アプリを作成・設定中…',
  authorizing: '承認を完了中…',
  waiting: '設定が完了しました。Slack でインストールを承認して戻ってください。',
  authorize: 'Slack で承認',
  appTokenHint:
    'Socket Mode には App-Level Token が必要です。Basic Information → App-Level Tokens で connections:write 権限のトークンを生成し、入力してください。',
  openApp: 'アプリ設定を開く',
  failed: '設定に失敗しました：',
  appCreated:
    'アプリは作成済みです。再試行すると別のアプリが作成されます。既存のアプリは Slack で管理できます：',
  retry: '新しい設定を開始',
  success:
    '承認が完了しました。認証情報を入力してボット設定を保存してください。',
  apply: 'アダプター設定に入力',
};
