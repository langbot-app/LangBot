export default {
  title: 'Webhook 地址',
  description:
    '外部系统可以向下面的地址推送事件，插件收到后可以主动给用户发消息。地址无需登录即可访问，来源校验由插件负责。',
  disabled: '插件已停用，推送到这些地址的请求会被拒绝。',
  loadFailed: '加载 Webhook 地址失败',
  prefixHint: '地址前缀来自配置项 api.webhook_prefix，请确保外部系统能够访问。',
  copy: '复制地址',
};
