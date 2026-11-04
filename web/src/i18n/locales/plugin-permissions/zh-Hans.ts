export default {
  managerRequired:
    '管理插件权限需要 resource.manage 权限。仅账户可确认授权，API Key 只能撤销已有授权。',
  title: '插件权限',
  undeclared: '未声明权限',
  compatibilityWarning:
    '该插件未声明权限。确认时必须授予全部 16 项旧版插件 API 权限，确认后可逐项撤销；不包含任何工作区 Application API 操作。',
  pending: '需要确认插件权限',
  saved: '权限已保存',
  failed: '无法更新权限',
  retry: '重试',
  revoke: '撤销',
  dangerous: '危险操作',
  sendsMessages: '可发送机器人消息',
  requires: '需要 {{permissions}}',
  review: '审阅权限',
  confirm: '确认授予',
  confirmDescription:
    '向此插件安装授予选中的权限。危险权限和机器人发消息能力已单独标出。',
  grantInPlugin: '需先在插件权限中授予此操作',
};
