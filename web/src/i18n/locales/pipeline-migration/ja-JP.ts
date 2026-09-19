export default {
  complete: '完了',
  checkingPlugin: 'プラグインを確認',
  preparingPlugin: 'インストールを準備',
  installDetails: 'インストール詳細',
  stageProgress: '段階の進捗',
  downloaded: 'ダウンロード済み {{size}}',
  processed: '{{completed}} / {{total}} 件のパイプラインを処理済み',
  installErrors: {
    plugin_version_unavailable:
      '必要なバージョンはまだマーケットにありません。公開後に再試行するかデータのみ移行してください。',
    plugin_download_timeout:
      'ダウンロードがタイムアウトしました。ネットワークを確認して再試行してください。',
    plugin_marketplace_unavailable:
      'マーケットからプラグインを取得できません。後で再試行してください。',
    plugin_download_failed:
      'ダウンロードに失敗しました。ネットワークを確認してください。',
    dependency_prepare_failed:
      '依存関係のインストールに失敗しました。実行環境を確認してください。',
    plugin_launch_failed:
      'プラグインを起動できません。実行環境を確認してください。',
  },
  autoDescription:
    '従来の実行方式はプラグインになりました。設定を保持して全パイプラインを移行します。元の設定はバックアップされ、会話は新しく始まります。',
  viewPipelines: 'パイプラインを表示',
  autoInstall: 'プラグインを自動インストールして移行',
  dataOnly: 'データのみ移行',
  dataOnlyHint:
    'オフラインやイントラネット向けです。移行後、対応するランナープラグインを手動でインストールしてください。',
  installing: '必要なプラグインをインストール中…',
  migrating: 'パイプラインを移行中…',
  summary: '{{migrated}} 件移行済み、{{remaining}} 件の確認が必要です。',
  installFailed:
    'インストールに失敗しました。詳細で失敗した段階を確認し、再試行するかデータのみ移行してください。',

  activationRetryHint:
    '実行環境を確認して再読み込みし、このパイプラインを選択して確定すると、有効化のみを再試行します。保存済み設定は再移行しません。',
  details: '移行の詳細',
  notices: {
    runtimeUnavailable:
      'プラグインランタイムが未接続です。接続を復旧して再試行するか、データのみ移行してください。',
    executionFailed:
      '移行に失敗しました。サーバーログを確認して再試行してください。',
    pluginRequired:
      '上記のランナープラグインをインストールまたは有効化し、プレビューを更新してください。',
    legacyArchive:
      '有効な設定には選択した Runner のみを残します。未使用のものを含むすべての旧 Runner 設定は移行バックアップに保存します。',
    contextDefaults:
      '履歴には固定の往復数制限ではなく、新しいコンテキスト予算と要約の既定値を適用します。',
    modelReasoning: 'モデル別の推論設定を保持し、ホスト側で適用します。',
    serialTools: '移行後もツール呼び出しは順番に実行します。',
    retrievalDefaults:
      '検索には新しい top-k と結果長の既定値を適用します。移行後に確認してください。',
    boxReset:
      'サンドボックスの再利用設定は保持されます。既存コンテナの状態は移行せず、同じ再利用ルールで新しく作成されます。',
    persistentHistory:
      '新しい会話の履歴は分離して永続化します。既存のリモート履歴は取り込みません。',
    tweaksDefault: 'Langflow tweaks の既定値は空のオブジェクトです。',
    timeoutDefault: 'Dify のリクエストタイムアウトは既定で 30 秒です。',
    historyReset:
      '既存の会話履歴とセッション ID は引き継ぎません。移行後は新しい会話を開始します。',
    sessionTitle:
      '新しい WeKnora セッションにはプラグインが生成したタイトルを使用します。',
    aliasRepaired: '旧フィールド名を現在サポートされている名前に置き換えます。',
    nullDefault: 'この空の値には新しいプラグインの既定値を使用します。',
    outputPolicy: '推論内容の表示設定は保持します。',
    filteredVariables:
      '対応する変数のみ移行します。予約変数は会話コンテキストから提供します。',
    identityPreserved:
      'サービス側のユーザー識別子には従来と同じ情報源を使用します。',
    newDefaults:
      '追加された設定には文書化された既定値を使い、対応する既存の値は保持します。',
    externalState:
      '移行前に待機中のリモート操作を完了またはキャンセルしてください。実行状態は引き継ぎません。',
    pluginVersion:
      '必要なバージョンのプラグインをインストールして再読み込みしてください。旧バージョンは移行に対応していません。',
    schemaChanged:
      'インストール済み Runner の設定形式が移行先と一致しません。プラグインのバージョンを確認してください。',
    runnerExcluded:
      'このパイプラインでは必要な Runner プラグインが除外されています。拡張機能の設定を変更してください。',
    boxTemplateInvalid:
      '再利用テンプレートが無効です。{変数名} を使用してください。位置引数、書式変換、属性アクセスは使用できません。',
    pendingInteraction:
      '入力待ちの会話があります。完了またはキャンセルしてから移行してください。',
  },
  title: 'パイプライン移行',
  description:
    '移行するパイプラインを選択してください。元の設定はバックアップされ、移行後は新しい会話を開始します。',
  detected: '{{count}} 件のパイプラインに移行確認が必要です。',
  review: '移行を確認',
  readOnly: '移行できるのはワークスペースの管理権限を持つユーザーのみです。',
  previewError: 'プレビューを取得できません。更新してください。',
  submitting: '選択したパイプラインを送信中…',
  running: '移行中です。ダイアログを閉じてもタスクは停止しません。',
  finished: 'タスクが終了しました。各パイプラインの結果を確認してください。',
  failed: 'タスクが失敗しました。各パイプラインの結果を確認してください。',
  lost: 'タスクの追跡が失われ、結果は不明です。次の操作前にプレビューを更新してください。',
  requestError:
    'リクエストを完了できませんでした。プレビューを更新して再選択してください。',
  warningFallback: '移行前にこの設定を確認してください。',
  blockerFallback:
    'この設定または実行状態は安全に移行できません。解決してプレビューを更新してください。',
  changedFields: '変更フィールド',
  activationHint:
    '設定は保存されましたが、有効化待ちです。管理者に実行環境の確認を依頼してから更新してください。移行を無条件に再実行しないでください。',
  pluginHint:
    'プラグインが不足している場合は、拡張機能でランナーをインストールまたは有効化し、プレビューを更新してください。',
  extensions: '拡張機能を開く',
  results: 'パイプラインごとの結果',
  selection: '{{count}} 件選択（最大 50 件）',
  confirm: '選択したパイプラインの移行を確認します。',
  refresh: 'プレビューを更新',
  execute: '選択項目を移行',
  legacyGate:
    '旧設定は移行まで読み取り専用です。暗黙の変換を防ぐため、保存とデバッグは使用できません。',
  states: {
    ready: '移行可能',
    needs_plugin: 'プラグインが必要',
    blocked: '移行不可',
    already_current: '移行済みの形式',
    not_legacy: '旧形式ではない',
    activation_pending: '有効化待ち',
    pending: '待機中',
    migrated: '移行済み',
    stale: 'プレビューが古い',
    failed: '失敗',
  },
};
