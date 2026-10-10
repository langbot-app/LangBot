export default {
  title: 'Slack 快速設定',
  description: '自動建立及設定應用程式，授權安裝後填入介接器憑證。',
  saveFirst: '請先建立機器人草稿，再開啟設定助手。',
  generate: '產生 App Configuration Tokens',
  name: '應用程式名稱',
  redirect: 'OAuth 授權返回網址',
  webhook: 'Webhook 網址',
  redirectHint:
    '此網址只需瀏覽器能存取，支援 HTTPS 或 http://localhost；無需公開事件回呼。',
  webhookHint: '填寫公開 HTTPS 網址，保留結尾 /bots/… 路徑。',
  create: '建立並自動設定',
  creating: '正在建立及設定應用程式…',
  authorizing: '正在完成授權…',
  waiting: '設定完成。請在 Slack 確認安裝授權，再返回此處。',
  authorize: '前往 Slack 授權',
  appTokenHint:
    '長連線還需要 App-Level Token。在 Basic Information → App-Level Tokens 產生具有 connections:write 權限的 Token，填入下方。',
  openApp: '開啟應用程式設定',
  failed: '設定失敗：',
  appCreated:
    '應用程式已建立。重新開始會建立另一個應用程式，可在 Slack 後台管理現有應用程式：',
  retry: '重新開始設定',
  success: '授權完成。填入憑證後，請儲存機器人設定。',
  apply: '填入介接器設定',
};
