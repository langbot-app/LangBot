export default {
  title: 'Webhook 位址',
  description:
    '外部系統可以向下方位址推送事件，插件收到後可以主動向使用者傳送訊息。位址無需登入即可存取，來源驗證由插件負責。',
  disabled: '插件已停用，推送到這些位址的請求會被拒絕。',
  loadFailed: '載入 Webhook 位址失敗',
  prefixHint: '位址前綴來自設定項 api.webhook_prefix，請確保外部系統能夠存取。',
  copy: '複製位址',
};
