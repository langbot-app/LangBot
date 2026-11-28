export default {
  title: 'Webhook URL',
  description:
    '外部システムは以下の URL にイベントを送信でき、プラグインはそれを受けてユーザーへ能動的にメッセージを送れます。URL は認証不要で公開されるため、送信元の検証はプラグインが行います。',
  disabled:
    'プラグインが無効なため、これらの URL へのリクエストは拒否されます。',
  loadFailed: 'Webhook URL の読み込みに失敗しました',
  prefixHint:
    'URL のプレフィックスは api.webhook_prefix の設定値です。外部システムからアクセスできることを確認してください。',
  copy: 'URL をコピー',
};
