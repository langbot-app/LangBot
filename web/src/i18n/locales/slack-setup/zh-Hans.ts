export default {
  title: 'Slack 快速配置',
  description: '自动创建和配置应用，授权安装后填入适配器凭据。',
  saveFirst: '请先创建机器人草稿，再打开快速配置助手。',
  generate: '生成 App Configuration Tokens',
  name: '应用名称',
  redirect: 'OAuth 授权返回地址',
  webhook: 'Webhook 地址',
  redirectHint:
    '此地址只需浏览器能够访问，支持 HTTPS 或 http://localhost；不需要公网事件回调。',
  webhookHint: '填写公网 HTTPS 地址，保留末尾 /bots/… 路径。',
  create: '创建并自动配置',
  creating: '正在创建和配置应用…',
  authorizing: '正在完成授权…',
  waiting: '应用配置完成。请在 Slack 确认安装授权，然后返回此处。',
  authorize: '前往 Slack 授权',
  appTokenHint:
    '长连接还需要 App-Level Token。在 Basic Information → App-Level Tokens 中生成带 connections:write 权限的 Token，填入下方。',
  openApp: '打开应用设置',
  failed: '配置失败：',
  appCreated:
    '应用已创建。重新开始会创建另一个应用，已有应用可在 Slack 后台管理：',
  retry: '重新开始配置',
  success: '授权完成。填入凭据后，请保存机器人配置。',
  apply: '填入适配器配置',
};
