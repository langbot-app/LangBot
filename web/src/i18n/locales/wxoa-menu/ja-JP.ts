export default {
  tab: 'カスタムメニュー',
  title: '公式アカウントのカスタムメニュー',
  description:
    '公式アカウントのチャット画面下部にあるメニューボタンを編集します。LangBot に接続すると、WeChat の Web コンソールで編集したメニューは停止されるため、ここから公開してください。',
  status: {
    published: '公開済み',
    outOfSync: '未同期の変更あり',
    unpublished: 'WeChat に未同期',
    unknown: '公開状態不明',
  },
  actions: {
    import: 'WeChat からインポート',
    importing: 'インポート中…',
    save: '保存',
    saving: '保存中…',
    more: 'その他の操作',
    deleteRemote: 'WeChat 上のメニューを削除',
    refresh: '同期状態を更新',
    addTop: 'メニューを追加',
    addSub: 'サブボタンを追加',
    saveAndSync: '保存して WeChat に同期',
    addTopFull: 'トップメニューを追加',
    deleteTop: 'このメニューを削除',
    deleteSub: 'このサブボタンを削除',
    moveUp: '上へ移動',
    moveDown: '下へ移動',
  },
  unsaved: '未保存の変更あり',
  botDisabled:
    'ボットが無効です。有効にするとインポート・同期・削除ができます。編集と保存は今すぐ行えます。',
  validationSummary:
    'あと {{count}} 個のボタンを修正すると WeChat に同期できます。',
  structure: {
    title: 'メニュー構成',
    hint: 'クリックで編集するボタンを切り替え、矢印で順序を変更します。',
    needsFix: '要修正',
    subFull: 'サブボタンは最大 {{max}} 個です',
    topFull: 'トップメニューは最大 {{max}} 個です',
  },
  empty: {
    title: 'メニューがまだありません',
    description:
      'WeChat で使っていたメニューをインポートするか、最初から追加できます。トップレベルは最大 3 個、それぞれにサブボタンを最大 5 個まで追加できます。',
  },
  preview: {
    title: 'プレビュー',
    hint: 'プレビューのボタンをクリックすると、ユーザーがタップしたときの動作を確認できます。',
    welcome: 'こんにちは、何かお手伝いできますか？',
    clickedReply: '（「{{name}}」をタップすると自動返信）',
    clickedAi:
      '（「{{name}}」をタップするとユーザーがこの文を送信したことになります）',
    aiReply: 'AI がチャット設定に従ってこのメッセージに返信します。',
    opensUrl: 'Web ページを開く：{{url}}',
    opensMiniprogram: 'ミニプログラムを開く：{{appid}}',
    eventSent:
      'イベント {{key}} を送信し、イベントルーティングで割り当てた処理器が処理します。',
    empty: '（未入力）',
  },
  editor: {
    title: 'ボタン設定',
    noSelection:
      '「メニュー構成」またはプレビューでボタンを選択して編集します。',
    name: 'ボタン名',
    nameBytes: '{{used}}/{{max}} バイト（漢字・かなは約 3 バイト）',
    type: 'タップ時の動作',
    topLevel: 'トップレベルメニュー',
    subLevel: 'サブボタン',
    defaultTopName: 'メニュー{{n}}',
    defaultSubName: '項目{{n}}',
    subButtons: 'サブボタン（{{count}}/{{max}}）',
    groupHint:
      'トップメニューをタップするとサブボタンが開き、それ自体は動作しません。サブボタンの追加・並べ替え・削除は「メニュー構成」で行えます。',
  },
  types: {
    group: {
      label: 'サブボタンを開く',
      description: '複数のボタンを 1 つのメニューにまとめます',
    },
    view: {
      label: 'Web ページを開く',
      description: '指定した URL に移動します',
    },
    miniprogram: {
      label: 'ミニプログラムを開く',
      description: '関連付けたミニプログラムのページを開きます',
    },
    reply: {
      label: '定型文で返信',
      description: 'AI を使わずに設定した文で返信します',
    },
    ai: {
      label: 'AI に返信させる',
      description: 'ユーザーの代わりにメッセージを送り、AI が返信します',
    },
    event: {
      label: 'イベントを発生（上級）',
      description: 'イベントルーティングで Agent やプラグインが処理します',
    },
    unsupported: {
      label: '未対応のタイプ',
      description:
        'WeChat コンソールのニュース・画像などの素材ボタンです。別のタイプに変更してください',
    },
  },
  fields: {
    url: 'URL',
    urlPlaceholder: 'https://example.com',
    appid: 'ミニプログラム AppID',
    appidPlaceholder: 'wx1234567890abcdef',
    pagepath: 'ミニプログラムのページパス',
    pagepathPlaceholder: 'pages/index/index',
    fallbackUrl: '代替 Web ページ',
    fallbackUrlHint:
      'ミニプログラムに対応しない古い WeChat クライアントではこの URL が開きます。',
    replyText: '返信内容',
    replyTextPlaceholder: '例：営業時間は月曜〜金曜 9:00-18:00 です',
    replyTextHint:
      'タップ直後にこの文が届きます。AI クレジットは消費しません。',
    aiText: 'AI に送るメッセージ',
    aiTextPlaceholder: '例：製品について教えてください',
    aiTextHint:
      'LangBot はこの文をユーザーのメッセージとして扱い、現在のチャットパイプラインまたは Agent に返信させます。',
    eventKey: 'イベントキー',
    eventKeyPlaceholder: 'ORDER_QUERY',
    eventKeyHint:
      'タップすると EventKey がこの値の platform.specific イベント（officialaccount.CLICK）が発生します。「設定 → イベントルーティング」でバインドを追加し、EventKey で絞り込むと Agent に渡せます。',
    copyFilter: 'フィルターをコピー',
    filterCopied: 'フィルターをコピーしました',
  },
  errors: {
    nameRequired: 'ボタン名を入力してください',
    nameTooLong: '名前が長すぎます',
    urlInvalid: 'URL は http:// または https:// で始めてください',
    urlTooLong: 'URL は 1024 バイト以内にしてください',
    appidRequired: 'ミニプログラムの AppID を入力してください',
    pagepathRequired: 'ミニプログラムのページパスを入力してください',
    textRequired: '内容を入力してください',
    textTooLong: '内容は 2000 文字以内にしてください',
    keyRequired: 'イベントキーを入力してください',
    keyReserved: 'イベントキーは lb: で始められません',
    keyTooLong: 'イベントキーは 128 バイト以内にしてください',
    groupEmpty: 'サブボタンを 1 つ以上追加してください',
    unsupported: '対応しているボタンタイプに変更してください',
  },
  importConfirm: {
    title: 'WeChat のメニューで現在のメニューを置き換えますか？',
    description:
      '公式アカウントの現在のメニュー（Web 管理画面で編集され、停止されたものを含む）を読み込み、LangBot に保存してここのメニューを置き換えます。WeChat に反映するには「保存して WeChat に同期」をクリックしてください。',
    confirm: 'インポート',
  },
  deleteConfirm: {
    title: 'WeChat 上のメニューを削除しますか？',
    description:
      '公式アカウントのチャットにメニューが表示されなくなります。LangBot に保存したメニューは残り、後で再公開できます。',
    confirm: '削除',
  },
  toasts: {
    saved: 'メニューを保存しました',
    imported:
      'インポートして LangBot に保存しました。確認後「保存して WeChat に同期」をクリックしてください。',
    importedEmpty: '公式アカウントには現在メニューがありません',
    importWarnings: '{{count}} 個のボタンを調整する必要があります',
    deleted: 'WeChat 上のメニューを削除しました',
    saveFailed: 'メニューの保存に失敗しました',
    importFailed: 'インポートに失敗しました',
    deleteFailed: '削除に失敗しました',
    savedBotDisabled:
      '保存しました。ボットを有効にしてから再度保存すると WeChat に同期されます。',
    savedNotSynced: 'LangBot に保存しましたが、まだ WeChat に同期できません',
    synced: '保存して WeChat に同期しました',
    syncFailed: 'LangBot に保存しましたが、WeChat への同期に失敗しました',
  },
  wechatErrors: {
    credentials:
      'AppID または AppSecret が正しくありません。ボットの設定を確認してください。',
    ipWhitelist:
      'LangBot サーバーの送信元 IP が公式アカウントの IP ホワイトリストにありません。「設定」タブの「IP ホワイトリスト」のアドレスをコピーし、WeChat 開発者プラットフォームの API IP ホワイトリストに追加してください。',
    unauthorized:
      'この公式アカウントにはカスタムメニュー API の権限がありません。未認証の購読アカウントには通常ありません。サービスアカウントと認証済み購読アカウントは利用できます。',
    url: 'URL が無効です。ボタンの URL を確認してください。',
    buttonCount: 'ボタンの数が WeChat の制限を超えています。',
    buttonName: 'ボタン名が長すぎます。',
    buttonKey: 'イベントキーが WeChat の制限を満たしていません。',
    miniprogram:
      'ミニプログラムがこの公式アカウントに関連付けられていません。先に WeChat コンソールで関連付けてください。',
    noMenu: 'API で公開されたメニューはありません。',
    generic: 'WeChat がエラー {{errcode}} を返しました：{{errmsg}}',
  },
};
