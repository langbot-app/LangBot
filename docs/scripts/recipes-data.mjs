// Source data for the generated "integration recipe" pages
// ({lang}/recipes/<source>/<platform>.mdx). Every statement here must be
// backed by the full platform or runner guide it links to; when a guide
// changes, update the matching entry and run `npm run generate:recipes`.

export const LANGS = ["en", "zh", "ja"];

/** Messaging platforms. `guide` is the full setup page (language-neutral path). */
export const PLATFORMS = [
  {
    slug: "telegram",
    guide: "usage/platforms/telegram",
    name: { en: "Telegram", zh: "Telegram", ja: "Telegram" },
    network: "outbound",
    streaming: true,
    creds: {
      en: "A bot token from [@BotFather](https://t.me/BotFather) (send `/newbot` and pick a username ending in `bot`).",
      zh: "通过 [@BotFather](https://t.me/BotFather) 获取的机器人 Token（发送 `/newbot`，用户名需以 `bot` 结尾）。",
      ja: "[@BotFather](https://t.me/BotFather) で取得したボットトークン（`/newbot` を送り、`bot` で終わるユーザー名を付けます）。",
    },
    setup: {
      en: ["Under **Bots**, create a bot and select the **Telegram** adapter (the new adapter in LangBot 4.11, not the deprecated legacy one).", "Paste the token, enable Markdown and streaming if you want them, then enable and save the bot."],
      zh: ["在 **机器人** 页面新建机器人，选择 **Telegram** 适配器（LangBot 4.11 的新适配器，不要选已弃用的旧版）。", "填入 Token，按需开启 Markdown 和流式输出，启用并保存。"],
      ja: ["**ボット** で新しいボットを作成し、**Telegram** アダプター（LangBot 4.11 の新しいアダプター。非推奨の旧版は選ばない）を選びます。", "トークンを貼り付け、必要に応じて Markdown とストリーミングを有効にし、ボットを有効化して保存します。"],
    },
    networkNote: {
      en: "Telegram uses long polling: LangBot only needs outbound access to `api.telegram.org`. No public webhook URL is required, so a laptop or home server works.",
      zh: "Telegram 使用长轮询：LangBot 只需要能访问 `api.telegram.org`，不需要公网 Webhook 地址，本地电脑或家用服务器也能运行。",
      ja: "Telegram はロングポーリングを使うため、LangBot から `api.telegram.org` へ外向きに接続できれば十分です。公開 Webhook URL は不要で、手元の PC や自宅サーバーでも動きます。",
    },
    test: {
      en: "Press **Start** in a private chat with the bot and send a message. In groups, the message must match the pipeline's trigger rules (for example, mention the bot or reply to it).",
      zh: "在与机器人的私聊中点击 **Start** 后发送消息。群聊中消息需要满足流水线的触发规则（例如 @ 机器人或回复它的消息）。",
      ja: "ボットとの個人チャットで **Start** を押してからメッセージを送ります。グループではパイプラインのトリガー条件（ボットへのメンションや返信など）を満たす必要があります。",
    },
    trouble: {
      en: ["Only one running instance may poll a token. If replies are missing, make sure the same bot is not enabled in another LangBot instance or script."],
      zh: ["同一个 Token 只能被一个实例轮询。如果收不到回复，请确认没有在其他 LangBot 实例或脚本中启用同一个机器人。"],
      ja: ["1 つのトークンをポーリングできるのは 1 インスタンスだけです。返信がない場合は、同じボットを別の LangBot インスタンスやスクリプトで有効にしていないか確認してください。"],
    },
  },
  {
    slug: "discord",
    guide: "usage/platforms/discord",
    name: { en: "Discord", zh: "Discord", ja: "Discord" },
    network: "outbound",
    streaming: true,
    creds: {
      en: "A Discord application with a bot: its **Client ID** and **bot token** from the [Developer Portal](https://discord.com/developers/applications), with **Server Members Intent** and **Message Content Intent** enabled.",
      zh: "在 [Discord Developer Portal](https://discord.com/developers/applications) 创建的应用与机器人：**Client ID** 和 **Bot Token**，并开启 **Server Members Intent** 与 **Message Content Intent**。",
      ja: "[Discord Developer Portal](https://discord.com/developers/applications) で作成したアプリとボットの **Client ID** と **ボットトークン**。**Server Members Intent** と **Message Content Intent** を有効にしておきます。",
    },
    setup: {
      en: ["Create a bot with the **Discord** adapter and enter the Client ID and token.", "Invite the bot from **OAuth2 → URL Generator** with the `bot` scope and **Guild Install**, granting permission to view channels and send messages."],
      zh: ["新建机器人，选择 **Discord** 适配器，填入 Client ID 和 Token。", "在 **OAuth2 → URL Generator** 勾选 `bot` 与 **Guild Install** 生成邀请链接，授予查看频道和发送消息等权限，把机器人拉进服务器。"],
      ja: ["**Discord** アダプターでボットを作成し、Client ID とトークンを入力します。", "**OAuth2 → URL Generator** で `bot` スコープと **Guild Install** を選び、チャンネル閲覧とメッセージ送信の権限を付けてサーバーに招待します。"],
    },
    networkNote: {
      en: "Discord bots connect out to the Discord gateway, so no public webhook URL is required.",
      zh: "Discord 机器人主动连接 Discord Gateway，不需要公网 Webhook 地址。",
      ja: "Discord ボットは Discord ゲートウェイへ外向きに接続するため、公開 Webhook URL は不要です。",
    },
    test: {
      en: "Send a message that matches the trigger rules in a server channel, then try a DM from the bot's profile.",
      zh: "在服务器频道中发送一条满足触发规则的消息，再从机器人资料页发起私信测试。",
      ja: "サーバーのチャンネルでトリガー条件に合うメッセージを送り、続いてボットのプロフィールから DM も試します。",
    },
    trouble: {
      en: ["Gateway login fails: check the current token and that both privileged intents are enabled and saved.", "Discord limits message length, so long streaming replies arrive as several messages."],
      zh: ["Gateway 登录失败：检查 Token 是否为最新，两个特权 Intent 是否都已开启并保存。", "Discord 限制单条消息长度，较长的流式回复会拆成多条消息发送。"],
      ja: ["ゲートウェイへのログインに失敗する場合は、最新のトークンか、2 つの特権インテントが有効で保存済みかを確認します。", "Discord は 1 メッセージの長さに上限があるため、長いストリーミング返信は複数メッセージに分かれます。"],
    },
  },
  {
    slug: "slack",
    guide: "usage/platforms/slack",
    name: { en: "Slack", zh: "Slack", ja: "Slack" },
    network: "either",
    streaming: false,
    creds: {
      en: "A Slack workspace where you can install apps, plus **App Configuration Tokens** from the [Slack apps page](https://api.slack.com/apps) for the quick setup assistant.",
      zh: "可以安装应用的 Slack 工作区，以及在 [Slack apps 页面](https://api.slack.com/apps) 生成的 **App Configuration Tokens**（供快速配置助手使用）。",
      ja: "アプリをインストールできる Slack ワークスペースと、[Slack アプリページ](https://api.slack.com/apps) で発行した **App Configuration Tokens**（クイックセットアップ用）。",
    },
    setup: {
      en: ["Create a bot with the **Slack** adapter and use **Quick Slack setup**: it creates the app, scopes and event subscriptions for you.", "Choose **Socket Mode** (recommended) and add an App-Level Token (`xapp-...`), or choose **Webhook** if LangBot has a public HTTPS address. Then fill the adapter configuration and enable the bot."],
      zh: ["新建机器人，选择 **Slack** 适配器，使用 **快速配置 Slack**：助手会自动创建应用、权限范围和事件订阅。", "选择 **Socket Mode**（推荐）并填写 App-Level Token（`xapp-...`）；如果 LangBot 有公网 HTTPS 地址，也可以选 **Webhook**。然后填充适配器配置并启用。"],
      ja: ["**Slack** アダプターでボットを作成し、**Slack クイックセットアップ** を使います。アプリ、スコープ、イベント購読が自動で作成されます。", "**Socket Mode**（推奨）を選んで App-Level Token（`xapp-...`）を追加するか、LangBot に公開 HTTPS アドレスがあれば **Webhook** を選びます。設定を反映してボットを有効にします。"],
    },
    networkNote: {
      en: "With Socket Mode, LangBot connects out to Slack and no public event URL is needed. Webhook mode needs a publicly reachable HTTPS endpoint.",
      zh: "Socket Mode 下 LangBot 主动连接 Slack，不需要公网事件地址；Webhook 模式需要可公网访问的 HTTPS 地址。",
      ja: "Socket Mode では LangBot から Slack へ接続するため公開イベント URL は不要です。Webhook モードでは公開 HTTPS エンドポイントが必要です。",
    },
    test: {
      en: "Message the app from its **Messages** tab, or mention it in a channel it has been added to.",
      zh: "在应用的 **Messages** 标签页私聊它，或在已加入的频道中 @ 它。",
      ja: "アプリの **メッセージ** タブから話しかけるか、追加済みのチャンネルでメンションします。",
    },
    trouble: {
      en: ["Do not paste the App Configuration Access/Refresh tokens into the App-Level Token field; it needs the `xapp-` token of the same app.", "Leave token rotation disabled for the App-Level Token."],
      zh: ["不要把 App Configuration 的 Access/Refresh Token 填进 App-Level Token 字段，这里需要同一个应用的 `xapp-` Token。", "App-Level Token 不要开启 Token rotation。"],
      ja: ["App Configuration のアクセス/リフレッシュトークンを App-Level Token 欄に入れないでください。同じアプリの `xapp-` トークンが必要です。", "App-Level Token のトークンローテーションは無効のままにします。"],
    },
  },
  {
    slug: "lark",
    guide: "usage/platforms/lark",
    name: { en: "Lark (Feishu)", zh: "飞书", ja: "Lark（Feishu）" },
    network: "either",
    streaming: true,
    creds: {
      en: "A Feishu or Lark custom app (`app_id` and `app_secret`). The one-click setup in LangBot can create and authorize it for you.",
      zh: "飞书或 Lark 自建应用（`app_id` 与 `app_secret`）。可以直接用 LangBot 的一键创建完成创建与授权。",
      ja: "Feishu または Lark のカスタムアプリ（`app_id` と `app_secret`）。LangBot のワンクリック設定で作成と認可ができます。",
    },
    setup: {
      en: ["Create a bot with the **Lark** adapter, select the platform domain (Feishu or Lark) and use **One-Click Setup**, or enter `app_id` and `app_secret` manually.", "Add the message permissions and event subscriptions from the guide (and the card permissions if you want streaming cards), then publish an app version."],
      zh: ["新建机器人，选择 **飞书** 适配器，选择平台域名（飞书或 Lark）后使用 **一键创建**，或手动填写 `app_id` 与 `app_secret`。", "按文档补充消息权限和事件订阅（需要流式卡片时再加卡片权限），然后发布应用版本。"],
      ja: ["**Lark** アダプターでボットを作成し、プラットフォームのドメイン（Feishu / Lark）を選んで **ワンクリック設定** を使うか、`app_id` と `app_secret` を手動入力します。", "ガイドに沿ってメッセージ権限とイベント購読（ストリーミングカードを使う場合はカード権限も）を追加し、アプリのバージョンを公開します。"],
    },
    networkNote: {
      en: "The default WebSocket long connection needs no public IP. Where long connection is unavailable (for example some Lark international setups), webhook mode requires a public HTTPS address; LangBot Cloud includes one.",
      zh: "默认的 WebSocket 长连接模式不需要公网 IP。长连接不可用时（例如部分国际版 Lark），需要改用 Webhook 模式，此时需要公网 HTTPS 地址；LangBot Cloud 自带该地址。",
      ja: "既定の WebSocket 長期接続では公開 IP は不要です。長期接続が使えない場合（一部の Lark 国際版など）は Webhook モードとなり、公開 HTTPS アドレスが必要です。LangBot Cloud には最初から用意されています。",
    },
    test: {
      en: "Search for the bot in Feishu/Lark, send it a direct message, then add it to a group and mention it.",
      zh: "在飞书中搜索机器人并私聊，再把它拉进群里 @ 它测试。",
      ja: "Feishu/Lark でボットを検索して DM を送り、グループに追加してメンションでも試します。",
    },
    trouble: {
      en: ["No messages arrive: confirm the app version is published and the event subscription uses the same mode (long connection or webhook) as LangBot."],
      zh: ["收不到消息：确认应用版本已发布，且事件订阅方式（长连接或 Webhook）与 LangBot 配置一致。"],
      ja: ["メッセージが届かない場合は、アプリのバージョンが公開済みか、イベント購読方式（長期接続 / Webhook）が LangBot 側と一致しているかを確認します。"],
    },
  },
  {
    slug: "dingtalk",
    guide: "usage/platforms/dingtalk",
    name: { en: "DingTalk", zh: "钉钉", ja: "DingTalk" },
    network: "outbound",
    streaming: true,
    creds: {
      en: "A DingTalk app robot (**Client ID** and **Client Secret**). The one-click setup fills both after you authorize on your phone.",
      zh: "钉钉应用机器人（**Client ID** 与 **Client Secret**）。使用一键创建并在手机上授权后会自动填好。",
      ja: "DingTalk アプリロボット（**Client ID** と **Client Secret**）。ワンクリック設定でスマートフォンから認可すると自動入力されます。",
    },
    setup: {
      en: ["Create a bot with the **DingTalk** adapter and use **One-Click Setup**, or create the robot manually and enter its credentials.", "Use **Stream Mode** for event delivery. For streaming replies, import LangBot's `dingtalk_stream_card.json` card template, enable **Use Card Replies** and paste the Card Template ID."],
      zh: ["新建机器人，选择 **钉钉** 适配器并使用 **一键创建**，或手动创建机器人后填写凭据。", "消息推送方式选择 **Stream 模式**。需要流式回复时，导入 LangBot 提供的 `dingtalk_stream_card.json` 卡片模板，开启 **使用卡片回复** 并填入卡片模板 ID。"],
      ja: ["**DingTalk** アダプターでボットを作成して **ワンクリック設定** を使うか、ロボットを手動で作成して認証情報を入力します。", "イベント配信は **Stream モード** を使います。ストリーミング返信には LangBot の `dingtalk_stream_card.json` カードテンプレートをインポートし、**カード返信を使用** を有効にしてテンプレート ID を入力します。"],
    },
    networkNote: {
      en: "In Stream Mode LangBot connects out to DingTalk, so no public callback URL is needed.",
      zh: "Stream 模式下由 LangBot 主动连接钉钉，不需要公网回调地址。",
      ja: "Stream モードでは LangBot から DingTalk へ接続するため、公開コールバック URL は不要です。",
    },
    test: {
      en: "Message the robot directly, then add it to a group and @mention it.",
      zh: "先单聊机器人，再把它加入群聊并 @ 它。",
      ja: "まずロボットと個別チャットし、次にグループへ追加してメンションします。",
    },
    trouble: {
      en: ["Replies arrive as plain text instead of streaming: the card template is not imported or **Use Card Replies** is off.", "Messages do not arrive: publish the app version and check that Stream Mode is selected under event subscriptions."],
      zh: ["回复不是流式而是纯文本：卡片模板未导入，或没有开启 **使用卡片回复**。", "收不到消息：确认应用版本已发布，并在事件订阅中选择了 Stream 模式。"],
      ja: ["ストリーミングでなくプレーンテキストで返る場合は、カードテンプレート未インポートか **カード返信を使用** が無効です。", "メッセージが届かない場合は、アプリのバージョンを公開し、イベント購読で Stream モードが選ばれているか確認します。"],
    },
  },
  {
    slug: "wecom",
    guide: "usage/platforms/wecom/wecom",
    name: { en: "WeCom (internal app)", zh: "企业微信应用", ja: "WeCom（社内アプリ）" },
    network: "webhook",
    streaming: false,
    creds: {
      en: "A WeCom self-built app: **Corporate ID**, the app **Secret**, the **Contact Sync Secret**, and the callback **Token** and **EncodingAESKey**.",
      zh: "企业微信自建应用：**企业 ID**、应用 **Secret**、**通讯录同步 Secret**，以及回调用的 **Token** 和 **EncodingAESKey**。",
      ja: "WeCom の自社開発アプリ：**企業 ID**、アプリの **Secret**、**連絡先同期 Secret**、コールバック用の **Token** と **EncodingAESKey**。",
    },
    setup: {
      en: ["Create a bot with the **WeCom** adapter, enter the Corporate ID, app Secret and Contact Sync Secret, enable it and copy the webhook callback URL.", "In the WeCom admin console, open **Receive Messages → Set API Reception**, paste the URL, generate the Token and EncodingAESKey, save them in LangBot first and then in WeCom. Add LangBot's outbound IP to **Corporate Trusted IP**."],
      zh: ["新建机器人，选择 **企业微信** 适配器，填写企业 ID、应用 Secret 和通讯录同步 Secret，启用后复制 Webhook 回调地址。", "在企业微信管理后台打开 **接收消息 → 设置 API 接收**，填入回调地址，随机生成 Token 和 EncodingAESKey，先在 LangBot 保存，再回到企业微信保存。最后在 **企业可信 IP** 中加入 LangBot 的出口 IP。"],
      ja: ["**WeCom** アダプターでボットを作成し、企業 ID、アプリ Secret、連絡先同期 Secret を入力して有効化し、Webhook コールバック URL をコピーします。", "WeCom 管理画面の **メッセージ受信 → API 受信の設定** に URL を貼り、Token と EncodingAESKey を生成して、先に LangBot、次に WeCom で保存します。LangBot の送信元 IP を **企業の信頼 IP** に追加します。"],
    },
    networkNote: {
      en: "WeCom delivers messages to a callback URL, so LangBot needs a public domain with HTTPS (see [reverse proxy and SSL](/en/workshop/production/proxy-and-ssl)). LangBot Cloud includes a ready-to-use public URL.",
      zh: "企业微信通过回调地址推送消息，因此 LangBot 需要可公网访问的域名和 HTTPS（参考[反向代理与 SSL](/zh/workshop/production/proxy-and-ssl)）。LangBot Cloud 自带可直接使用的公网地址。",
      ja: "WeCom はコールバック URL にメッセージを送るため、LangBot には公開ドメインと HTTPS が必要です（[リバースプロキシと SSL](/ja/workshop/production/proxy-and-ssl) を参照）。LangBot Cloud にはすぐ使える公開 URL があります。",
    },
    test: {
      en: "Open the app in the WeCom client and send it a message.",
      zh: "在企业微信客户端打开该应用并发送消息。",
      ja: "WeCom クライアントでアプリを開き、メッセージを送ります。",
    },
    trouble: {
      en: ["**request URL failed** when saving the callback: the URL is not publicly reachable over HTTPS, or the Token/EncodingAESKey in LangBot does not match.", "Replies fail to send: add LangBot's outbound IP to the corporate trusted IP list."],
      zh: ["保存回调时提示 **请求 URL 失败**：回调地址无法通过公网 HTTPS 访问，或 LangBot 中的 Token/EncodingAESKey 不一致。", "无法发出回复：把 LangBot 的出口 IP 加入企业可信 IP。"],
      ja: ["コールバック保存時に **request URL failed** となる場合は、URL が公開 HTTPS で到達できないか、LangBot の Token/EncodingAESKey が一致していません。", "返信が送れない場合は、LangBot の送信元 IP を企業の信頼 IP に追加します。"],
    },
  },
  {
    slug: "wecombot",
    guide: "usage/platforms/wecom/wecombot",
    name: { en: "WeCom Intelligent Bot", zh: "企业微信智能机器人", ja: "WeCom インテリジェントボット" },
    network: "outbound",
    streaming: true,
    creds: {
      en: "A WeCom intelligent bot in **long connection** API mode: its **BotID** and long-connection **Secret**. One-click setup can fill both.",
      zh: "使用 **长连接** API 模式的企业微信智能机器人：**BotID** 与长连接 **Secret**。一键创建可以自动填好。",
      ja: "**長期接続** API モードの WeCom インテリジェントボット：**BotID** と長期接続用 **Secret**。ワンクリック設定で自動入力できます。",
    },
    setup: {
      en: ["Create a bot with the **WeCom Intelligent Bot** adapter and use **One-Click Setup**, or create the bot in WeCom, switch its API mode to **long connection** and enter the BotID and Secret.", "Set the bot's visibility scope so the right people can use it, then save and enable."],
      zh: ["新建机器人，选择 **企业微信智能机器人** 适配器并使用 **一键创建**；或在企业微信中创建机器人，把 API 模式切换为 **长连接**，再填写 BotID 和 Secret。", "设置机器人的可见范围，保存并启用。"],
      ja: ["**WeCom インテリジェントボット** アダプターでボットを作成して **ワンクリック設定** を使うか、WeCom でボットを作って API モードを **長期接続** に切り替え、BotID と Secret を入力します。", "ボットの公開範囲を設定し、保存して有効化します。"],
    },
    networkNote: {
      en: "Long connection mode needs no public callback URL. The alternative callback-URL mode does, and the two modes cannot be used at the same time.",
      zh: "长连接模式不需要公网回调地址；另一种回调 URL 模式需要。两种模式只能二选一，切换会让另一种失效。",
      ja: "長期接続モードでは公開コールバック URL は不要です。もう一方のコールバック URL モードでは必要で、両モードは同時に使えません。",
    },
    test: {
      en: "Find the bot in the WeCom client, chat with it directly, then add it to a group chat and mention it.",
      zh: "在企业微信中找到机器人单聊，再拉进群聊 @ 它。",
      ja: "WeCom クライアントでボットを見つけて個別に話しかけ、グループに追加してメンションします。",
    },
    trouble: {
      en: ["The long-connection Secret differs from the callback Token/EncodingAESKey. Switching the API mode to callback URL invalidates existing long connections."],
      zh: ["长连接 Secret 与回调模式的 Token/EncodingAESKey 不是同一个东西；把 API 模式切到回调 URL 会使现有长连接失效。"],
      ja: ["長期接続の Secret はコールバックモードの Token/EncodingAESKey とは別物です。API モードをコールバック URL に切り替えると既存の長期接続は無効になります。"],
    },
  },
  {
    slug: "wecomcs",
    guide: "usage/platforms/wecom/wecomcs",
    name: { en: "WeCom Customer Service", zh: "微信客服", ja: "WeCom カスタマーサービス" },
    network: "webhook",
    streaming: false,
    creds: {
      en: "WeCom Customer Service (WeChat Kefu) with API access: **Corporate ID**, **Secret**, and a callback **Token** and **EncodingAESKey**.",
      zh: "开通 API 的微信客服：**企业 ID**、**Secret**，以及回调用的 **Token** 和 **EncodingAESKey**。",
      ja: "API を有効にした WeCom カスタマーサービス（WeChat Kefu）：**企業 ID**、**Secret**、コールバック用 **Token** と **EncodingAESKey**。",
    },
    setup: {
      en: ["In WeCom Customer Service **Developer Settings**, generate the Token and EncodingAESKey and enter them with the Corporate ID in a bot using the **WeCom Customer Service** adapter.", "Enable the bot, paste its webhook callback URL into the admin console, then fill in the Secret and restart the bot. Generate the customer service link or QR code users will open."],
      zh: ["在微信客服 **开发配置** 中随机生成 Token 和 EncodingAESKey，与企业 ID 一起填入 **微信客服** 适配器的机器人。", "启用机器人，把 Webhook 回调地址填入管理后台，再填写 Secret 并重启机器人。最后生成用户进入会话用的客服链接或二维码。"],
      ja: ["WeCom カスタマーサービスの **開発者設定** で Token と EncodingAESKey を生成し、企業 ID とともに **WeCom カスタマーサービス** アダプターのボットに入力します。", "ボットを有効化して Webhook コールバック URL を管理画面に貼り、Secret を入力してボットを再起動します。ユーザーが会話を始めるためのリンクや QR コードを発行します。"],
    },
    networkNote: {
      en: "Customer Service delivers events to a callback URL, so LangBot needs a public HTTPS address. LangBot Cloud includes one.",
      zh: "微信客服通过回调地址推送事件，LangBot 需要公网 HTTPS 地址；LangBot Cloud 自带。",
      ja: "カスタマーサービスはコールバック URL にイベントを送るため、LangBot には公開 HTTPS アドレスが必要です。LangBot Cloud には用意されています。",
    },
    test: {
      en: "Open the customer service link or scan the QR code in WeChat and send a message.",
      zh: "在微信中打开客服链接或扫描二维码，发送一条消息。",
      ja: "WeChat でカスタマーサービスのリンクを開くか QR コードを読み取り、メッセージを送ります。",
    },
    trouble: {
      en: ["Welcome messages can only be sent when WeChat supplies a `welcome_code`, and only once before it expires."],
      zh: ["欢迎语只能在微信下发 `welcome_code` 时发送，并且在过期前只能发一次。"],
      ja: ["ウェルカムメッセージは WeChat が `welcome_code` を渡したときだけ、期限内に 1 回だけ送れます。"],
    },
  },
  {
    slug: "wechat-official-account",
    guide: "usage/platforms/wxoa",
    name: { en: "WeChat Official Account", zh: "微信公众号", ja: "WeChat 公式アカウント" },
    network: "webhook",
    streaming: false,
    creds: {
      en: "A WeChat Official Account or Service Account: **AppID**, **AppSecret**, a server **Token** and **EncodingAESKey**, with LangBot's server IP in the **IP whitelist**.",
      zh: "微信公众号或服务号：**AppID**、**AppSecret**、服务器配置的 **Token** 和 **EncodingAESKey**，并把 LangBot 服务器 IP 加入 **IP 白名单**。",
      ja: "WeChat 公式アカウントまたはサービスアカウント：**AppID**、**AppSecret**、サーバー設定の **Token** と **EncodingAESKey**。LangBot サーバーの IP を **IP ホワイトリスト** に追加します。",
    },
    setup: {
      en: ["Create a bot with the **WeChat Official Account** adapter and choose a reply mode: `drop` (reply within the 5-second callback), `passive` or `auto` (answer later through the customer service API when the account is enterprise-verified).", "Paste the bot's callback URL into the account's server configuration and save."],
      zh: ["新建机器人，选择 **微信公众号** 适配器并选择回复模式：`drop`（5 秒回调内直接回复）、`passive` 或 `auto`（企业认证账号可通过客服消息接口稍后回复）。", "把机器人的回调地址填入公众号服务器配置并保存。"],
      ja: ["**WeChat 公式アカウント** アダプターでボットを作成し、返信モードを選びます：`drop`（5 秒のコールバック内で返信）、`passive`、または `auto`（企業認証済みアカウントならカスタマーサービス API で後から返信）。", "ボットのコールバック URL をアカウントのサーバー設定に貼り付けて保存します。"],
    },
    networkNote: {
      en: "Official Accounts require a public domain with HTTPS and must get a response within 5 seconds. Slow AI replies need `passive` or `auto` mode. LangBot Cloud includes a public domain.",
      zh: "公众号要求公网域名和 HTTPS，并且必须在 5 秒内响应回调；AI 回复较慢时请使用 `passive` 或 `auto` 模式。LangBot Cloud 自带公网域名。",
      ja: "公式アカウントには公開ドメインと HTTPS が必要で、コールバックには 5 秒以内に応答しなければなりません。AI の応答が遅い場合は `passive` または `auto` を使います。LangBot Cloud には公開ドメインがあります。",
    },
    test: {
      en: "Follow the account in WeChat and send it a message.",
      zh: "在微信中关注公众号并发送消息。",
      ja: "WeChat でアカウントをフォローし、メッセージを送ります。",
    },
    trouble: {
      en: ["Users see the loading message but no answer: in `passive` mode (or after `auto` falls back) the user must send another message to retrieve the queued answer.", "Customer service messages require an enterprise-verified account; identity verification alone is not enough."],
      zh: ["用户只收到加载提示没有答案：`passive` 模式（或 `auto` 回退后）需要用户再发一条消息来取回答案。", "客服消息接口需要企业认证，仅个人身份认证不够。"],
      ja: ["読み込みメッセージだけで回答が来ない場合、`passive` モード（または `auto` のフォールバック後）は次のメッセージで回答を受け取る仕組みです。", "カスタマーサービス API には企業認証が必要で、本人確認だけでは使えません。"],
    },
  },
  {
    slug: "qq-official",
    guide: "usage/platforms/qq/official_webhook",
    name: { en: "QQ Official Bot", zh: "QQ 官方机器人", ja: "QQ 公式ボット" },
    network: "webhook",
    streaming: false,
    creds: {
      en: "A bot registered on the QQ Open Platform: **AppID**, **Token** and **AppSecret**, with LangBot's server IP in the IP whitelist.",
      zh: "在 QQ 开放平台注册的机器人：**AppID**、**Token** 和 **AppSecret**，并把 LangBot 服务器 IP 加入 IP 白名单。",
      ja: "QQ オープンプラットフォームで登録したボット：**AppID**、**Token**、**AppSecret**。LangBot サーバーの IP を IP ホワイトリストに追加します。",
    },
    setup: {
      en: ["Create a bot with the **QQ Official** adapter and enter AppID, Token and AppSecret.", "Copy the bot's webhook callback URL, replace the host with your HTTPS domain, and save it as the request address in the QQ management portal. Add test users in the sandbox settings."],
      zh: ["新建机器人，选择 **QQ 官方** 适配器，填写 AppID、Token 和 AppSecret。", "复制机器人的 Webhook 回调地址，把 IP 和端口换成你的 HTTPS 域名后填入 QQ 管理端的请求地址；在沙箱配置里添加测试成员。"],
      ja: ["**QQ 公式** アダプターでボットを作成し、AppID、Token、AppSecret を入力します。", "ボットの Webhook コールバック URL をコピーし、ホストを HTTPS ドメインに置き換えて QQ 管理ポータルのリクエストアドレスに保存します。サンドボックス設定でテストユーザーを追加します。"],
    },
    networkNote: {
      en: "The QQ Official Bot API (webhook) requires a public IP and working HTTPS. LangBot Cloud includes a public domain.",
      zh: "QQ 官方机器人 Webhook 方式要求公网 IP 并正确配置 HTTPS；LangBot Cloud 自带公网域名。",
      ja: "QQ 公式ボット API（Webhook）には公開 IP と HTTPS が必要です。LangBot Cloud には公開ドメインがあります。",
    },
    test: {
      en: "As a sandbox member, message the bot in a private chat or @mention it in a sandbox group.",
      zh: "以沙箱成员身份私聊机器人，或在沙箱群中 @ 它。",
      ja: "サンドボックスのメンバーとしてボットに個別チャットするか、サンドボックスのグループでメンションします。",
    },
    trouble: {
      en: ["Saving the request address fails: the domain is not reachable over HTTPS or the path does not end with `/bots/<bot id>`."],
      zh: ["保存请求地址失败：域名无法通过 HTTPS 访问，或路径不是以 `/bots/<机器人 ID>` 结尾。"],
      ja: ["リクエストアドレスの保存に失敗する場合は、ドメインが HTTPS で到達できないか、パスが `/bots/<ボット ID>` で終わっていません。"],
    },
  },
  {
    slug: "line",
    guide: "usage/platforms/line",
    name: { en: "LINE", zh: "LINE", ja: "LINE" },
    network: "webhook",
    streaming: false,
    creds: {
      en: "A Messaging API channel in the [LINE Developers Console](https://developers.line.biz/): **Channel Secret** and **Channel Access Token** (click **Issue**).",
      zh: "在 [LINE Developers Console](https://developers.line.biz/) 创建的 Messaging API Channel：**Channel Secret** 和 **Channel Access Token**（点击 **Issue** 生成）。",
      ja: "[LINE Developers コンソール](https://developers.line.biz/) の Messaging API チャネル：**チャネルシークレット** と **チャネルアクセストークン**（**発行** をクリック）。",
    },
    setup: {
      en: ["Create a bot with the **LINE** adapter and enter the Channel Secret and Channel Access Token.", "Copy the webhook callback URL from LangBot into the channel's **Webhook URL**, verify it, and turn on **Use webhook**."],
      zh: ["新建机器人，选择 **LINE** 适配器，填写 Channel Secret 和 Channel Access Token。", "把 LangBot 中的 Webhook 回调地址填入 Channel 的 **Webhook URL**，验证后开启 **Use webhook**。"],
      ja: ["**LINE** アダプターでボットを作成し、チャネルシークレットとチャネルアクセストークンを入力します。", "LangBot の Webhook コールバック URL をチャネルの **Webhook URL** に貼って検証し、**Webhook の利用** をオンにします。"],
    },
    networkNote: {
      en: "LINE calls a webhook, so LangBot needs a public HTTPS URL. LangBot Cloud includes a domain and HTTPS.",
      zh: "LINE 通过 Webhook 推送消息，LangBot 需要公网 HTTPS 地址；LangBot Cloud 自带域名和 HTTPS。",
      ja: "LINE は Webhook を呼び出すため、LangBot には公開 HTTPS URL が必要です。LangBot Cloud にはドメインと HTTPS があります。",
    },
    test: {
      en: "Add the official account as a friend with its QR code and send a message.",
      zh: "扫描二维码添加官方账号为好友并发送消息。",
      ja: "QR コードで公式アカウントを友だち追加し、メッセージを送ります。",
    },
    trouble: {
      en: ["Webhook verification fails: check the URL and that HTTPS works from the public internet.", "No replies: turn off LINE's auto-reply messages in the Official Account Manager so they do not answer instead of the bot."],
      zh: ["Webhook 验证失败：检查地址是否正确、HTTPS 能否从公网访问。", "没有回复：在 Official Account Manager 中关闭 LINE 自带的自动回复，避免它代替机器人回复。"],
      ja: ["Webhook の検証に失敗する場合は、URL と、インターネットから HTTPS で到達できるかを確認します。", "返信がない場合は、LINE Official Account Manager の応答メッセージをオフにし、ボットの代わりに自動応答しないようにします。"],
    },
  },
  {
    slug: "kook",
    guide: "usage/platforms/kook",
    name: { en: "KOOK", zh: "KOOK", ja: "KOOK" },
    network: "outbound",
    streaming: false,
    creds: {
      en: "A bot created in the KOOK developer center and its **Bot Token**.",
      zh: "在 KOOK 开发者中心创建的机器人及其 **Bot Token**。",
      ja: "KOOK 開発者センターで作成したボットとその **Bot Token**。",
    },
    setup: {
      en: ["Create a bot with the **KOOK** adapter and enter the Bot Token.", "Grant the bot permissions and invite it to your server."],
      zh: ["新建机器人，选择 **KOOK** 适配器并填写 Bot Token。", "为机器人配置权限并邀请进你的服务器。"],
      ja: ["**KOOK** アダプターでボットを作成し、Bot Token を入力します。", "ボットの権限を設定し、サーバーへ招待します。"],
    },
    networkNote: {
      en: "The KOOK adapter only needs a bot token; LangBot connects out to KOOK.",
      zh: "KOOK 适配器只需要 Bot Token，由 LangBot 主动连接 KOOK。",
      ja: "KOOK アダプターに必要なのはボットトークンだけで、LangBot から KOOK に接続します。",
    },
    test: {
      en: "Send a message that matches the trigger rules in a channel the bot can read.",
      zh: "在机器人可读的频道中发送满足触发规则的消息。",
      ja: "ボットが読めるチャンネルで、トリガー条件に合うメッセージを送ります。",
    },
    trouble: {
      en: ["No reply in a channel: check the bot's channel permissions and the pipeline's group trigger rules."],
      zh: ["频道中没有回复：检查机器人的频道权限以及流水线的群聊触发规则。"],
      ja: ["チャンネルで返信がない場合は、ボットのチャンネル権限とパイプラインのグループトリガー条件を確認します。"],
    },
  },
  {
    slug: "mattermost",
    guide: "usage/platforms/mattermost",
    name: { en: "Mattermost", zh: "Mattermost", ja: "Mattermost" },
    network: "outbound",
    streaming: true,
    creds: {
      en: "A Mattermost **bot account** (role `Member`) and its access token, plus your Mattermost server URL.",
      zh: "Mattermost **机器人账号**（角色为 `Member`）及其访问 Token，以及你的 Mattermost 服务器地址。",
      ja: "Mattermost の **ボットアカウント**（ロール `Member`）とアクセストークン、Mattermost サーバーの URL。",
    },
    setup: {
      en: ["Create the bot account in Mattermost (choose `post:all` for direct messages) and copy its token; it is shown only once.", "Create a bot with the **Mattermost** adapter, enter the server address and token, and bind a pipeline."],
      zh: ["在 Mattermost 创建机器人账号（需要私信时勾选 `post:all`）并复制 Token，Token 只显示一次。", "新建机器人，选择 **Mattermost** 适配器，填写服务器地址和 Token，并绑定流水线。"],
      ja: ["Mattermost でボットアカウントを作成し（DM を使う場合は `post:all`）、一度しか表示されないトークンをコピーします。", "**Mattermost** アダプターでボットを作成し、サーバーアドレスとトークンを入力してパイプラインを紐付けます。"],
    },
    networkNote: {
      en: "LangBot only needs to reach your Mattermost server; Mattermost does not need to reach LangBot.",
      zh: "只需要 LangBot 能访问你的 Mattermost 服务器，Mattermost 不需要反向访问 LangBot。",
      ja: "LangBot から Mattermost サーバーに到達できれば十分で、Mattermost から LangBot への接続は不要です。",
    },
    test: {
      en: "Send the bot a direct message, or mention it in a channel it has joined.",
      zh: "私信机器人，或在它加入的频道中 @ 它。",
      ja: "ボットに DM を送るか、参加しているチャンネルでメンションします。",
    },
    trouble: {
      en: ["Administrator-related features are not supported; keep the bot role as `Member`.", "Disable streaming on the bot if your pipeline or AI provider does not support it."],
      zh: ["暂不支持管理员相关功能，机器人角色保持 `Member` 即可。", "如果流水线或 AI 服务不支持流式输出，请在机器人上关闭流式。"],
      ja: ["管理者向け機能には対応していないため、ボットのロールは `Member` のままにします。", "パイプラインや AI 側がストリーミングに対応しない場合は、ボットのストリーミングを無効にします。"],
    },
  },
  {
    slug: "web-page",
    guide: "usage/platforms/webpage",
    name: { en: "a website chat widget", zh: "网页聊天挂件", ja: "Web サイトのチャットウィジェット" },
    network: "webhook",
    streaming: false,
    creds: {
      en: "Nothing from a third party. Optionally a Cloudflare Turnstile site key and secret key for anti-abuse.",
      zh: "不需要第三方凭据。可选：用于防刷的 Cloudflare Turnstile Site Key 和 Secret Key。",
      ja: "外部サービスの認証情報は不要です。任意で、不正利用対策の Cloudflare Turnstile のサイトキーとシークレットキー。",
    },
    setup: {
      en: ["Create a bot with the **Web Page Bot** adapter and bind a pipeline.", "Copy the embed code into your site and replace `localhost:5300` with LangBot's public address."],
      zh: ["新建机器人，选择 **网页机器人** 适配器并绑定流水线。", "把嵌入代码放进你的网站，并把其中的 `localhost:5300` 换成 LangBot 的公网地址。"],
      ja: ["**Web ページボット** アダプターでボットを作成し、パイプラインを紐付けます。", "埋め込みコードをサイトに貼り、`localhost:5300` を LangBot の公開アドレスに置き換えます。"],
    },
    networkNote: {
      en: "Visitors' browsers talk to LangBot directly, so LangBot must be reachable at a public HTTPS address. LangBot Cloud includes one.",
      zh: "访客的浏览器会直接连接 LangBot，因此 LangBot 需要可公网访问的 HTTPS 地址；LangBot Cloud 自带。",
      ja: "訪問者のブラウザーが LangBot に直接接続するため、LangBot は公開 HTTPS アドレスで到達できる必要があります。LangBot Cloud には用意されています。",
    },
    test: {
      en: "Open the page with the widget and start a conversation.",
      zh: "打开嵌入了挂件的网页，发起对话。",
      ja: "ウィジェットを埋め込んだページを開き、会話を始めます。",
    },
    trouble: {
      en: ["The widget does not load: the embed code still points at `localhost`, or the LangBot address is not served over HTTPS."],
      zh: ["挂件加载不出来：嵌入代码仍指向 `localhost`，或 LangBot 地址没有使用 HTTPS。"],
      ja: ["ウィジェットが読み込まれない場合は、埋め込みコードが `localhost` のままか、LangBot のアドレスが HTTPS ではありません。"],
    },
  },
];

const llmPrepare = (provider, url, extra = {}) => ({
  en: [`Create an API key in the ${provider} console.`, `In LangBot, open **Models**, add an LLM model with the provider set to ${provider}${url ? ` and request URL \`${url}\`` : ""}, then paste the API key and the model ID.`, "Enable **Tool Use** if the model supports function calling; MCP tools, Skills and the sandbox need it.", ...(extra.en ?? [])],
  zh: [`在 ${provider} 控制台创建 API Key。`, `在 LangBot 的 **模型** 页面新增 LLM 模型，供应商选择 ${provider}${url ? `，请求地址填写 \`${url}\`` : ""}，再填入 API Key 和模型名称。`, "如果模型支持函数调用，请勾选 **工具调用**；MCP 工具、Skills 和沙箱都依赖它。", ...(extra.zh ?? [])],
  ja: [`${provider} のコンソールで API キーを作成します。`, `LangBot の **モデル** で LLM モデルを追加し、プロバイダーに ${provider}${url ? `、リクエスト URL に \`${url}\`` : ""} を指定して、API キーとモデル ID を入力します。`, "モデルが関数呼び出しに対応していれば **ツール使用** を有効にします。MCP ツール、Skills、サンドボックスに必要です。", ...(extra.ja ?? [])],
});

const localAgentFields = {
  en: [["Runner", "**Local Agent** (built-in Agent)"], ["Model", "The model you just added. You can add fallback models."], ["Prompt", "Instructions: who the bot is, tone, what it must not do."], ["Knowledge Bases", "Optional. Attach a knowledge base so answers come from your documents."]],
  zh: [["运行器", "**内置 Agent**"], ["模型", "刚添加的模型，可以再加备用模型。"], ["提示词", "机器人的身份、语气以及不能做的事。"], ["知识库", "可选。绑定知识库后按你的资料回答。"]],
  ja: [["ランナー", "**Local Agent**（内蔵エージェント）"], ["モデル", "追加したモデル。予備モデルも指定できます。"], ["プロンプト", "ボットの役割、口調、してはいけないこと。"], ["ナレッジベース", "任意。ナレッジベースを付けると資料に基づいて回答します。"]],
};

/** AI back ends: external agent platforms (runner plugins) and models used by the built-in Agent. */
export const SOURCES = [
  {
    slug: "dify",
    name: "Dify",
    guide: "usage/pipelines/dify",
    kind: "runner",
    blurb: {
      en: "Dify builds chat assistants, Chatflows, Agents and Workflows. LangBot calls the published app through its Service API, so prompts, tools and knowledge stay in Dify.",
      zh: "Dify 可以搭建聊天助手、Chatflow、Agent 和工作流。LangBot 通过 Service API 调用你发布的应用，提示词、工具和知识库都留在 Dify 里维护。",
      ja: "Dify ではチャットアシスタント、Chatflow、エージェント、ワークフローを作れます。LangBot は公開したアプリを Service API 経由で呼び出すため、プロンプト、ツール、ナレッジは Dify 側で管理できます。",
    },
    prepare: {
      en: ["Build and **publish** a Chat Assistant (including Chatflow), Agent or Workflow app in Dify.", "Open the app's **Access API** page and create an API key.", "For a Workflow app, output the answer under the key `summary`."],
      zh: ["在 Dify 中搭建并 **发布** 聊天助手（含 Chatflow）、Agent 或工作流应用。", "进入应用的 **访问 API** 页面生成 API Key。", "如果是工作流应用，请用 `summary` 作为输出变量名。"],
      ja: ["Dify でチャットアシスタント（Chatflow を含む）、エージェント、ワークフローのいずれかを作成して **公開** します。", "アプリの **API アクセス** ページで API キーを作成します。", "ワークフローアプリの場合は、回答を `summary` というキーで出力します。"],
    },
    fields: {
      en: [["Runner", "**Dify** (official Dify Agent runner plugin)"], ["Base URL", "`https://api.dify.ai/v1` for Dify Cloud, or your own Dify address with `/v1` appended"], ["API Key", "The key from the app's Access API page"]],
      zh: [["运行器", "**Dify**（官方 Dify Agent 运行器插件）"], ["Base URL", "Dify 云服务填 `https://api.dify.ai/v1`；自部署填你的 Dify 地址并加上 `/v1`"], ["API Key", "应用访问 API 页面生成的密钥"]],
      ja: [["ランナー", "**Dify**（公式 Dify Agent ランナープラグイン）"], ["Base URL", "Dify Cloud は `https://api.dify.ai/v1`、セルフホストは自分の Dify アドレスの末尾に `/v1`"], ["API Key", "アプリの API アクセスページで作成したキー"]],
    },
    trouble: {
      en: ["Self-hosted Dify in Docker on the same host: put both stacks on a shared Docker network and use the container address (for example `http://dify-nginx/v1`), not `localhost`.", "Chatflow apps only return what the Answer node outputs."],
      zh: ["自部署的 Dify 与 LangBot 在同一台机器的 Docker 中：让两边加入同一个 Docker 网络，用容器地址（例如 `http://dify-nginx/v1`），不要用 `localhost`。", "Chatflow 应用只会返回 “直接回复” 节点输出的内容。"],
      ja: ["同じホストの Docker でセルフホスト版 Dify を動かす場合は、両方を共通の Docker ネットワークに参加させ、`localhost` ではなくコンテナのアドレス（例：`http://dify-nginx/v1`）を使います。", "Chatflow アプリが返すのは回答（Answer）ノードの出力だけです。"],
    },
  },
  {
    slug: "n8n",
    name: "n8n",
    guide: "usage/pipelines/n8n",
    kind: "runner",
    blurb: {
      en: "n8n runs the workflow; LangBot handles the chat platform, sessions and delivery and calls your workflow through a webhook for every message.",
      zh: "n8n 负责执行工作流，LangBot 负责聊天平台接入、会话和消息投递，并在每条消息到来时通过 Webhook 调用你的工作流。",
      ja: "n8n がワークフローを実行し、LangBot がチャットプラットフォーム、セッション、配信を担当します。メッセージごとに Webhook でワークフローを呼び出します。",
    },
    prepare: {
      en: ["Start the workflow with a **Webhook** or **On chat message** trigger. Set **Response Mode** to **Streaming** if you want streamed replies.", "Answer with an **AI Agent** node (streaming) or a **Respond to Webhook** node whose response key matches LangBot's output key.", "Click **Active** to enable the workflow and copy its production webhook URL."],
      zh: ["工作流以 **Webhook** 或 **On chat message** 触发器开始；需要流式回复时把 **Response Mode** 设为 **Streaming**。", "用 **AI Agent** 节点（流式）或 **Respond to Webhook** 节点返回结果，响应字段名要与 LangBot 中的输出键名一致。", "点击 **Active** 启用工作流，复制生产环境的 Webhook 地址。"],
      ja: ["ワークフローを **Webhook** または **On chat message** トリガーで開始します。ストリーミング返信には **Response Mode** を **Streaming** にします。", "**AI Agent** ノード（ストリーミング）か **Respond to Webhook** ノードで応答し、応答キー名を LangBot の出力キー名と一致させます。", "**Active** でワークフローを有効にし、本番用 Webhook URL をコピーします。"],
    },
    fields: {
      en: [["Runner", "**n8n** (official n8n workflow runner plugin)"], ["Webhook URL", "The workflow's production webhook URL"], ["Authentication Type", "None, Basic Auth, JWT or Header, matching the trigger node"]],
      zh: [["运行器", "**n8n**（官方 n8n 工作流运行器插件）"], ["Webhook URL", "工作流的生产环境 Webhook 地址"], ["认证方式", "无、Basic Auth、JWT 或 Header，与触发节点设置一致"]],
      ja: [["ランナー", "**n8n**（公式 n8n ワークフローランナープラグイン）"], ["Webhook URL", "ワークフローの本番用 Webhook URL"], ["認証方式", "なし、Basic Auth、JWT、Header のいずれか（トリガーノードと同じ設定）"]],
    },
    trouble: {
      en: ["Empty replies: the key in **Respond to Webhook** must match the output key configured in LangBot.", "The test URL only works while the n8n editor is listening; use the production URL of an active workflow."],
      zh: ["回复为空：**Respond to Webhook** 中的字段名必须与 LangBot 配置的输出键名一致。", "测试地址只在 n8n 编辑器监听时可用，请使用已激活工作流的生产地址。"],
      ja: ["返信が空の場合は、**Respond to Webhook** のキー名が LangBot の出力キー名と一致しているか確認します。", "テスト URL はエディターが待ち受けている間しか使えません。有効化したワークフローの本番 URL を使います。"],
    },
  },
  {
    slug: "coze",
    name: "Coze",
    guide: "usage/pipelines/coze",
    kind: "runner",
    blurb: {
      en: "Coze builds agents visually. LangBot calls a Coze bot through the Coze API, so you can reach platforms Coze does not publish to and keep one bot across many channels.",
      zh: "扣子（Coze）可以可视化搭建智能体。LangBot 通过 Coze API 调用你的智能体，让它出现在扣子本身不支持发布的平台上，并在多个渠道共用同一个智能体。",
      ja: "Coze ではエージェントをビジュアルに作れます。LangBot は Coze API で Coze ボットを呼び出すため、Coze が直接公開できないプラットフォームにも同じボットを展開できます。",
    },
    prepare: {
      en: ["In the Coze developer console, create a token under **API Management** (coze.com offers Personal Access Tokens; coze.cn also supports service credentials).", "Publish your agent with the **API** channel selected and copy its `bot_id`."],
      zh: ["在扣子开发者控制台的 **API 管理** 中创建令牌（coze.cn 支持服务身份长期凭据，coze.com 只提供个人访问令牌）。", "发布智能体时勾选 **API** 渠道，并记录 `bot_id`。"],
      ja: ["Coze の開発者コンソールの **API 管理** でトークンを作成します（coze.com は個人アクセストークン、coze.cn はサービス資格情報にも対応）。", "公開時に **API** チャネルを選んでエージェントを公開し、`bot_id` を控えます。"],
    },
    fields: {
      en: [["Runner", "**Coze** (official Coze Agent runner plugin)"], ["API Key", "The Coze token"], ["Bot ID", "The agent's `bot_id`"], ["API Base URL", "`https://api.coze.cn` for coze.cn or `https://api.coze.com` for coze.com"]],
      zh: [["运行器", "**扣子**（官方扣子 Agent 运行器插件）"], ["API Key", "扣子令牌"], ["Bot ID", "智能体的 `bot_id`"], ["API Base URL", "coze.cn 填 `https://api.coze.cn`，coze.com 填 `https://api.coze.com`"]],
      ja: [["ランナー", "**Coze**（公式 Coze Agent ランナープラグイン）"], ["API Key", "Coze のトークン"], ["Bot ID", "エージェントの `bot_id`"], ["API Base URL", "coze.cn は `https://api.coze.cn`、coze.com は `https://api.coze.com`"]],
    },
    trouble: {
      en: ["Calls fail: check the token and `bot_id` for extra spaces, that the agent was published with the API channel, and that the base URL matches the Coze site."],
      zh: ["调用失败：检查令牌和 `bot_id` 是否带了多余空格、智能体发布时是否勾选了 API 渠道、Base URL 是否与所用站点一致。"],
      ja: ["呼び出しに失敗する場合は、トークンと `bot_id` に余分な空白がないか、API チャネルで公開したか、Base URL が利用サイトと一致しているかを確認します。"],
    },
  },
  {
    slug: "langflow",
    name: "Langflow",
    guide: "usage/pipelines/langflow",
    kind: "runner",
    blurb: {
      en: "Langflow builds agents and flows with a drag-and-drop editor. LangBot runs a flow through the Langflow API for every message.",
      zh: "Langflow 用拖拽方式搭建 Agent 和流程。LangBot 在每条消息到来时通过 Langflow API 运行你的流程。",
      ja: "Langflow はドラッグ＆ドロップでエージェントやフローを作れます。LangBot はメッセージごとに Langflow API でフローを実行します。",
    },
    prepare: {
      en: ["Build a flow in Langflow (the Simple Agent template is a good start).", "Create an API key under **Settings**.", "Copy the **Flow ID** from **Share → API access**."],
      zh: ["在 Langflow 中搭建流程（可以从 Simple Agent 模板开始）。", "在 **Settings** 中创建 API Key。", "在 **Share → API access** 的示例代码中找到 **Flow ID**。"],
      ja: ["Langflow でフローを作成します（Simple Agent テンプレートから始めると簡単です）。", "**Settings** で API キーを作成します。", "**Share → API access** のサンプルコードから **Flow ID** を取得します。"],
    },
    fields: {
      en: [["Runner", "**Langflow** (official Langflow Agent runner plugin)"], ["Base URL", "Your Langflow address, reachable from LangBot"], ["API Key", "The Langflow API key"], ["Flow ID", "The flow to run"]],
      zh: [["运行器", "**Langflow**（官方 Langflow Agent 运行器插件）"], ["Base URL", "LangBot 能访问到的 Langflow 地址"], ["API Key", "Langflow API Key"], ["Flow ID", "要运行的流程 ID"]],
      ja: [["ランナー", "**Langflow**（公式 Langflow Agent ランナープラグイン）"], ["Base URL", "LangBot から到達できる Langflow のアドレス"], ["API Key", "Langflow の API キー"], ["Flow ID", "実行するフローの ID"]],
    },
    trouble: {
      en: ["Connection refused: `http://localhost:7860` only works when Langflow runs on the same host and network namespace as LangBot."],
      zh: ["连接被拒绝：只有 Langflow 与 LangBot 在同一主机、同一网络命名空间时，`http://localhost:7860` 才可用。"],
      ja: ["接続が拒否される場合、`http://localhost:7860` が使えるのは Langflow と LangBot が同じホスト・同じネットワーク名前空間にあるときだけです。"],
    },
  },
  {
    slug: "deepseek",
    name: "DeepSeek",
    guide: "usage/models/readme",
    kind: "model",
    blurb: {
      en: "Use DeepSeek models directly with LangBot's built-in Agent: no separate agent platform needed, with optional knowledge bases, MCP tools and Skills.",
      zh: "直接用 LangBot 内置 Agent 调用 DeepSeek 模型，不需要额外的智能体平台，还可以按需加知识库、MCP 工具和 Skills。",
      ja: "LangBot の内蔵エージェントから DeepSeek のモデルを直接使います。別のエージェント基盤は不要で、ナレッジベース、MCP ツール、Skills も追加できます。",
    },
    prepare: llmPrepare("DeepSeek", "https://api.deepseek.com", {
      en: ["Typical model IDs are `deepseek-chat` and `deepseek-reasoner`; check DeepSeek's documentation for the current list."],
      zh: ["常用模型名为 `deepseek-chat` 和 `deepseek-reasoner`，以 DeepSeek 官方文档的最新列表为准。"],
      ja: ["代表的なモデル ID は `deepseek-chat` と `deepseek-reasoner` です。最新の一覧は DeepSeek のドキュメントで確認してください。"],
    }),
    fields: localAgentFields,
    trouble: {
      en: ["401 errors: the API key is wrong or has no balance in the DeepSeek console."],
      zh: ["返回 401：API Key 错误，或 DeepSeek 账户余额不足。"],
      ja: ["401 エラーは、API キーの誤りか DeepSeek アカウントの残高不足です。"],
    },
  },
  {
    slug: "openai",
    name: "OpenAI (ChatGPT models)",
    guide: "usage/models/readme",
    kind: "model",
    blurb: {
      en: "Use OpenAI's GPT models with LangBot's built-in Agent, with optional knowledge bases, MCP tools, Skills and a code sandbox.",
      zh: "用 LangBot 内置 Agent 调用 OpenAI 的 GPT 模型，可以按需加知识库、MCP 工具、Skills 和代码沙箱。",
      ja: "LangBot の内蔵エージェントで OpenAI の GPT モデルを使います。ナレッジベース、MCP ツール、Skills、コードサンドボックスも追加できます。",
    },
    prepare: llmPrepare("OpenAI", "https://api.openai.com/v1", {
      en: ["Use a current model ID from OpenAI's model list. Any OpenAI-compatible endpoint works the same way with its own request URL."],
      zh: ["模型名请使用 OpenAI 模型列表中的最新 ID；其他 OpenAI 兼容接口也按同样方式填写各自的请求地址。"],
      ja: ["モデル ID は OpenAI のモデル一覧にある現行のものを使います。OpenAI 互換のエンドポイントも同じ手順で、それぞれのリクエスト URL を指定します。"],
    }),
    fields: localAgentFields,
    trouble: {
      en: ["Region or network errors: LangBot must be able to reach the request URL. Behind a restricted network, use a compatible gateway you can reach."],
      zh: ["网络或地区错误：LangBot 必须能访问请求地址；网络受限时请使用可访问的兼容网关。"],
      ja: ["ネットワークや地域のエラーは、LangBot からリクエスト URL に到達できないことが原因です。制限のある環境では到達可能な互換ゲートウェイを使います。"],
    },
  },
  {
    slug: "claude",
    name: "Claude",
    guide: "usage/models/readme",
    kind: "model",
    blurb: {
      en: "Use Anthropic's Claude models with LangBot's built-in Agent, including tool use with MCP servers, Skills and the code sandbox.",
      zh: "用 LangBot 内置 Agent 调用 Anthropic 的 Claude 模型，可配合 MCP、Skills 和代码沙箱使用工具。",
      ja: "LangBot の内蔵エージェントで Anthropic の Claude モデルを使います。MCP サーバー、Skills、コードサンドボックスとのツール連携も可能です。",
    },
    prepare: llmPrepare("Anthropic", "", {
      en: ["Keep the provider's default request URL unless you use a gateway. Use a current Claude model ID from Anthropic's documentation."],
      zh: ["除非使用网关，请保留供应商默认请求地址；模型名请使用 Anthropic 文档中当前可用的 Claude 模型 ID。"],
      ja: ["ゲートウェイを使わない限り、リクエスト URL はプロバイダー既定のままにします。モデル ID は Anthropic のドキュメントにある現行の Claude モデルを使います。"],
    }),
    fields: localAgentFields,
    trouble: {
      en: ["The agent never calls tools: enable **Tool Use** on the model."],
      zh: ["Agent 从不调用工具：请在模型上勾选 **工具调用**。"],
      ja: ["エージェントがツールを呼ばない場合は、モデルの **ツール使用** を有効にします。"],
    },
  },
  {
    slug: "gemini",
    name: "Gemini",
    guide: "usage/models/readme",
    kind: "model",
    blurb: {
      en: "Use Google's Gemini models with LangBot's built-in Agent, including image input when the model supports vision.",
      zh: "用 LangBot 内置 Agent 调用 Google Gemini 模型；模型支持视觉时还可以识别图片。",
      ja: "LangBot の内蔵エージェントで Google の Gemini モデルを使います。視覚対応モデルなら画像入力も扱えます。",
    },
    prepare: llmPrepare("Google Gemini", "", {
      en: ["Create the key in Google AI Studio. Enable **Vision** on the model if you want the bot to read images."],
      zh: ["在 Google AI Studio 创建密钥。需要识别图片时在模型上勾选 **视觉**。"],
      ja: ["キーは Google AI Studio で作成します。画像を読ませたい場合はモデルの **ビジョン** を有効にします。"],
    }),
    fields: localAgentFields,
    trouble: {
      en: ["Images are ignored: enable **Vision** on the model and check that the platform adapter forwards images."],
      zh: ["图片被忽略：在模型上勾选 **视觉**，并确认该平台适配器支持接收图片。"],
      ja: ["画像が無視される場合は、モデルの **ビジョン** を有効にし、アダプターが画像を受け取れるか確認します。"],
    },
  },
  {
    slug: "qwen",
    name: "Qwen",
    guide: "usage/models/readme",
    kind: "model",
    blurb: {
      en: "Use Alibaba Cloud's Qwen models through Model Studio (DashScope) with LangBot's built-in Agent.",
      zh: "通过阿里云百炼（DashScope）用 LangBot 内置 Agent 调用通义千问模型。",
      ja: "Alibaba Cloud Model Studio（DashScope）経由で、LangBot の内蔵エージェントから Qwen モデルを使います。",
    },
    prepare: llmPrepare("Aliyun Bailian (DashScope)", "https://dashscope.aliyuncs.com/compatible-mode/v1", {
      en: ["Use a Qwen model ID listed in Model Studio."],
      zh: ["模型名使用百炼控制台中列出的通义千问模型 ID。"],
      ja: ["モデル ID は Model Studio に表示される Qwen モデルを使います。"],
    }),
    fields: localAgentFields,
    trouble: {
      en: ["International accounts use a different DashScope endpoint; copy the OpenAI-compatible URL shown in your console."],
      zh: ["国际站账号的 DashScope 地址不同，请以控制台显示的 OpenAI 兼容地址为准。"],
      ja: ["国際版アカウントは DashScope のエンドポイントが異なります。コンソールに表示される OpenAI 互換 URL を使ってください。"],
    },
  },
  {
    slug: "ollama",
    name: "Ollama",
    guide: "usage/models/readme",
    kind: "model",
    blurb: {
      en: "Run open models locally with Ollama and serve them through LangBot's built-in Agent, so conversations never leave your machines.",
      zh: "用 Ollama 在本地运行开源模型，通过 LangBot 内置 Agent 提供服务，对话数据不出你的机器。",
      ja: "Ollama でオープンモデルをローカル実行し、LangBot の内蔵エージェントから提供します。会話データは手元のマシンから出ません。",
    },
    prepare: {
      en: ["Install Ollama and pull a model (for example `ollama pull` followed by the model name).", "In LangBot, open **Models** and add an LLM model with the provider set to Ollama and the request URL pointing at your Ollama server (by default port `11434`).", "If LangBot runs in Docker, `localhost` is the container itself: use the host's address (for example `host.docker.internal`) instead."],
      zh: ["安装 Ollama 并拉取模型（`ollama pull` 加模型名）。", "在 LangBot 的 **模型** 页面新增 LLM 模型，供应商选 Ollama，请求地址指向你的 Ollama 服务（默认端口 `11434`）。", "如果 LangBot 运行在 Docker 中，`localhost` 指的是容器本身，请改用宿主机地址（例如 `host.docker.internal`）。"],
      ja: ["Ollama をインストールしてモデルを取得します（`ollama pull` にモデル名）。", "LangBot の **モデル** で LLM モデルを追加し、プロバイダーに Ollama、リクエスト URL に Ollama サーバー（既定ポート `11434`）を指定します。", "LangBot が Docker で動いている場合、`localhost` はコンテナ自身を指すため、ホストのアドレス（例：`host.docker.internal`）を使います。"],
    },
    fields: localAgentFields,
    trouble: {
      en: ["Small local models may not support tool calling well; leave **Tool Use** off for models that do not support it."],
      zh: ["小型本地模型的工具调用能力可能较弱；不支持函数调用的模型请不要勾选 **工具调用**。"],
      ja: ["小さなローカルモデルはツール呼び出しが苦手な場合があります。関数呼び出しに対応しないモデルでは **ツール使用** をオフにします。"],
    },
  },
];
