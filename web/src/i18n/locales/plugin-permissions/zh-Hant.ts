export default {
  managerRequired:
    '管理外掛權限需要 resource.manage 權限。僅帳戶可確認授權，API Key 只能撤銷既有授權。',
  title: '外掛權限',
  undeclared: '未宣告權限',
  compatibilityWarning:
    '此外掛未宣告權限。確認時必須授予全部 16 項舊版外掛 API 權限，確認後可逐項撤銷；不包含任何工作區 Application API 操作。',
  pending: '需要確認外掛權限',
  saved: '權限已儲存',
  failed: '無法更新權限',
  retry: '重試',
  revoke: '撤銷',
  dangerous: '危險操作',
  sendsMessages: '可傳送機器人訊息',
  requires: '需要 {{permissions}}',
  review: '檢閱權限',
  confirm: '確認授予',
  confirmDescription:
    '向此外掛安裝授予所選權限。危險權限和機器人傳訊能力已單獨標示。',
  grantInPlugin: '請先在外掛權限中授予此操作',
};
