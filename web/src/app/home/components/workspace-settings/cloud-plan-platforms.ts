// Keep this public catalog aligned with Space web/lib/platform-adapters.ts.
// Do not use the workspace-filtered adapter API to describe other plans.
export const KNOWN_ADAPTERS = [
  {
    name: 'LINE',
    label: 'LINE',
    icon: '/platforms/line.png',
  },
  {
    name: 'aiocqhttp',
    label: 'OneBot v11',
    icon: '/platforms/aiocqhttp.svg',
  },
  {
    name: 'aiocqhttp-omni',
    label: 'OneBot v11 (Omni)',
    icon: '/platforms/aiocqhttp.svg',
  },
  {
    name: 'dingtalk',
    label: 'DingTalk',
    icon: '/platforms/dingtalk.svg',
  },
  {
    name: 'dingtalk-omni',
    label: 'DingTalk (Omni)',
    icon: '/platforms/dingtalk.svg',
  },
  {
    name: 'discord',
    label: 'Discord',
    icon: '/platforms/discord.svg',
  },
  {
    name: 'discord-omni',
    label: 'Discord (Omni)',
    icon: '/platforms/discord.svg',
  },
  {
    name: 'http_bot',
    label: 'HTTP Bot',
    icon: '/platforms/http_bot.svg',
  },
  {
    name: 'kook',
    label: 'KOOK',
    icon: '/platforms/kook.png',
  },
  {
    name: 'kook-omni',
    label: 'KOOK (Omni)',
    icon: '/platforms/kook.png',
  },
  {
    name: 'lark',
    label: 'Lark',
    icon: '/platforms/lark.svg',
  },
  {
    name: 'lark-omni',
    label: 'Lark / Feishu (Omni)',
    icon: '/platforms/lark.svg',
  },
  {
    name: 'matrix',
    label: 'Matrix',
    icon: '/platforms/matrix.png',
  },
  {
    name: 'mattermost',
    label: 'Mattermost',
    icon: '/platforms/mattermost.svg',
  },
  {
    name: 'officialaccount',
    label: 'Official Account',
    icon: '/platforms/officialaccount.png',
  },
  {
    name: 'officialaccount-omni',
    label: 'Official Account (Omni)',
    icon: '/platforms/officialaccount.png',
  },
  {
    name: 'openclaw-weixin',
    label: 'OpenClaw WeChat',
    icon: '/platforms/openclaw_weixin.png',
  },
  {
    name: 'qqofficial',
    label: 'QQ Official API',
    icon: '/platforms/qqofficial.svg',
  },
  {
    name: 'qqofficial-omni',
    label: 'QQ Official API (Omni)',
    icon: '/platforms/qqofficial.svg',
  },
  {
    name: 'satori',
    label: 'Satori',
    icon: '/platforms/satori.png',
  },
  {
    name: 'slack',
    label: 'Slack',
    icon: '/platforms/slack.png',
  },
  {
    name: 'slack-omni',
    label: 'Slack (Omni)',
    icon: '/platforms/slack.png',
  },
  {
    name: 'telegram',
    label: 'Telegram',
    icon: '/platforms/telegram.svg',
  },
  {
    name: 'telegram-omni',
    label: 'Telegram (Omni)',
    icon: '/platforms/telegram.svg',
  },
  {
    name: 'web_page_bot',
    label: 'Page Bot',
    icon: '/platforms/webpage.webp',
  },
  {
    name: 'wechatpad',
    label: 'WeChatPad',
    icon: '/platforms/wechatpad.png',
  },
  {
    name: 'wecom',
    label: 'WeCom',
    icon: '/platforms/wecom.png',
  },
  {
    name: 'wecom-omni',
    label: 'WeCom (Omni)',
    icon: '/platforms/wecom.png',
  },
  {
    name: 'wecombot',
    label: 'WeComBot',
    icon: '/platforms/wecombot.png',
  },
  {
    name: 'wecombot-omni',
    label: 'WeComBot (Omni)',
    icon: '/platforms/wecombot.png',
  },
  {
    name: 'wecomcs',
    label: 'WeComCustomerService',
    icon: '/platforms/wecomcs.png',
  },
  {
    name: 'wecomcs-omni',
    label: 'WeCom Customer Service (Omni)',
    icon: '/platforms/wecomcs.png',
  },
];

export function supportedPlanAdapters(disabled: string[] = []) {
  const blocked = new Set(
    disabled.map((name) =>
      name === 'line'
        ? 'LINE'
        : name.endsWith('-eba')
          ? name.slice(0, -4) + '-omni'
          : name,
    ),
  );
  return KNOWN_ADAPTERS.filter(
    (adapter) =>
      !blocked.has(adapter.name) &&
      !(
        adapter.name.endsWith('-omni') && blocked.has(adapter.name.slice(0, -5))
      ),
  );
}

/** Collapse transport variants into one platform logo after applying restrictions. */
export function supportedPlanPlatforms(disabled: string[] = []) {
  const platforms = new Map<
    string,
    { name: string; label: string; icon: string }
  >();
  for (const adapter of supportedPlanAdapters(disabled)) {
    const name = adapter.name.replace(/-omni$/, '');
    if (!platforms.has(name))
      platforms.set(name, {
        ...adapter,
        name,
        label: adapter.label.replace(/ \(Omni\)$/, ''),
      });
  }
  return [...platforms.values()];
}
