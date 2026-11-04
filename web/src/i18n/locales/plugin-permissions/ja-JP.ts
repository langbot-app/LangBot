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
  workspaceOperations: 'ワークスペース操作',
  capabilities: 'プラグイン機能',
  granted: '許可済み',
  grantedCount: '{{total}} 件中 {{granted}} 件を許可済み',
  empty: 'このプラグインは権限を要求していません。',
  pendingCount: '{{count}} 個のプラグインが権限の確認を待っています',
  highlighted: '要注意',
  grantSummary: '{{count}} 件の権限を許可します',
  capability: {
    langbot_info: {
      label: 'LangBot バージョン',
      description: 'LangBot のバージョンを取得',
    },
    bot_read: {
      label: 'ボットの読み取り',
      description: 'ボット一覧と詳細を取得',
    },
    bot_message_send: {
      label: 'ボットメッセージ送信',
      description: 'ワークスペースのボットでメッセージを送信',
    },
    bot_platform_api: {
      label: 'プラットフォーム API',
      description: 'ボット経由で IM プラットフォームの API を直接呼び出す',
    },
    models_read: {
      label: 'モデルの読み取り',
      description: '設定済みモデルの一覧を取得',
    },
    models_invoke: {
      label: 'モデルの呼び出し',
      description: 'LLM・埋め込み・リランクモデルを呼び出す',
    },
    storage_plugin: {
      label: 'プラグインストレージ',
      description: 'プラグイン専用ストレージの読み書き',
    },
    storage_workspace: {
      label: 'ワークスペースストレージ',
      description: 'ワークスペース共有ストレージの読み書き',
    },
    knowledge_read: {
      label: 'ナレッジの読み取り',
      description: 'ナレッジベースの一覧と検索',
    },
    knowledge_vector: {
      label: 'ベクトルストア',
      description: 'ベクトルの書き込み・検索・削除',
    },
    knowledge_parser: {
      label: 'ドキュメントパーサー',
      description: 'パーサーの一覧と呼び出し',
    },
    config_read: {
      label: '設定ファイルの読み取り',
      description: 'アップロードされた設定ファイルを読む',
    },
    plugin_tools: {
      label: 'プラグインツール',
      description: '他のプラグインのツールを一覧・呼び出し',
    },
    mcp: {
      label: 'MCP',
      description: 'MCP ツールの呼び出しとリソースの読み取り',
    },
    sandbox: {
      label: 'サンドボックス',
      description: 'Box サンドボックスを確保してコードを実行',
    },
    plugin_read: {
      label: 'プラグインの読み取り',
      description: 'インストール済みプラグインとコマンドの一覧',
    },
  },
};
