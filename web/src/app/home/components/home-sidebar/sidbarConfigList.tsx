import { SidebarChildVO } from '@/app/home/components/home-sidebar/HomeSidebarChild';
import i18n from '@/i18n';

const t = (key: string) => {
  return i18n.t(key);
};

export const sidebarConfigList = [
  // ── Quick Start ──
  new SidebarChildVO({
    id: 'wizard',
    name: t('sidebar.quickStart'),
    icon: (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill="currentColor"
        className="text-blue-500"
      >
        <path d="M13 9H21L11 24V15H4L13 0V9ZM11 11V7.22063L7.53238 13H13V17.3944L17.263 11H11Z"></path>
      </svg>
    ),
    route: '/wizard',
    description: t('wizard.sidebarDescription'),
    helpLink: {
      en_US: '',
      zh_Hans: '',
    },
    section: 'standalone',
  }),

  // ── Home section ──
  new SidebarChildVO({
    id: 'monitoring',
    name: t('monitoring.title'),
    icon: (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill="currentColor"
        className="text-blue-500"
      >
        <path d="M2 3.9934C2 3.44476 2.45531 3 2.9918 3H21.0082C21.556 3 22 3.44495 22 3.9934V20.0066C22 20.5552 21.5447 21 21.0082 21H2.9918C2.44405 21 2 20.5551 2 20.0066V3.9934ZM4 5V19H20V5H4ZM6 7H18V9H6V7ZM6 11H18V13H6V11ZM6 15H12V17H6V15Z"></path>
      </svg>
    ),
    route: '/home/monitoring',
    description: t('monitoring.description'),
    helpLink: {
      en_US: '',
      zh_Hans: '',
    },
    section: 'home',
  }),
  new SidebarChildVO({
    id: 'bots',
    name: t('bots.title'),
    icon: (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill="currentColor"
        className="text-blue-500"
      >
        <path d="M13.5 2C13.5 2.44425 13.3069 2.84339 13 3.11805V5H18C19.6569 5 21 6.34315 21 8V18C21 19.6569 19.6569 21 18 21H6C4.34315 21 3 19.6569 3 18V8C3 6.34315 4.34315 5 6 5H11V3.11805C10.6931 2.84339 10.5 2.44425 10.5 2C10.5 1.17157 11.1716 0.5 12 0.5C12.8284 0.5 13.5 1.17157 13.5 2ZM6 7C5.44772 7 5 7.44772 5 8V18C5 18.5523 5.44772 19 6 19H18C18.5523 19 19 18.5523 19 18V8C19 7.44772 18.5523 7 18 7H13H11H6ZM2 10H0V16H2V10ZM22 10H24V16H22V10ZM9 14.5C9.82843 14.5 10.5 13.8284 10.5 13C10.5 12.1716 9.82843 11.5 9 11.5C8.17157 11.5 7.5 12.1716 7.5 13C7.5 13.8284 8.17157 14.5 9 14.5ZM15 14.5C15.8284 14.5 16.5 13.8284 16.5 13C16.5 12.1716 15.8284 11.5 15 11.5C14.1716 11.5 13.5 12.1716 13.5 13C13.5 13.8284 14.1716 14.5 15 14.5Z"></path>
      </svg>
    ),
    route: '/home/bots',
    description: t('bots.description'),
    helpLink: {
      en_US: 'https://docs.langbot.app/en/usage/platforms/readme',
      zh_Hans: 'https://docs.langbot.app/zh/usage/platforms/readme',
      ja_JP: 'https://docs.langbot.app/ja/usage/platforms/readme',
    },
    section: 'home',
  }),
  new SidebarChildVO({
    id: 'pipelines',
    name: t('pipelines.title'),
    icon: (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill="currentColor"
        className="text-blue-500"
      >
        <path d="M6 21.5C4.067 21.5 2.5 19.933 2.5 18C2.5 16.067 4.067 14.5 6 14.5C7.5852 14.5 8.92427 15.5539 9.35481 16.9992L15 16.9994V15L17 14.9994V9.24339L14.757 6.99938H9V9.00003H3V3.00003H9V4.99939H14.757L18 1.75739L22.2426 6.00003L19 9.24139V14.9994L21 15V21H15V18.9994L9.35499 19.0003C8.92464 20.4459 7.58543 21.5 6 21.5ZM6 16.5C5.17157 16.5 4.5 17.1716 4.5 18C4.5 18.8285 5.17157 19.5 6 19.5C6.82843 19.5 7.5 18.8285 7.5 18C7.5 17.1716 6.82843 16.5 6 16.5ZM19 17H17V19H19V17ZM18 4.58581L16.5858 6.00003L18 7.41424L19.4142 6.00003L18 4.58581ZM7 5.00003H5V7.00003H7V5.00003Z"></path>
      </svg>
    ),
    route: '/home/pipelines',
    description: t('pipelines.description'),
    helpLink: {
      en_US: 'https://docs.langbot.app/en/usage/pipelines/readme',
      zh_Hans: 'https://docs.langbot.app/zh/usage/pipelines/readme',
      ja_JP: 'https://docs.langbot.app/ja/usage/pipelines/readme',
    },
    section: 'home',
  }),
  new SidebarChildVO({
    id: 'knowledge',
    name: t('knowledge.title'),
    icon: (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill="currentColor"
        className="text-blue-500"
      >
        <path d="M3 18.5V5C3 3.34315 4.34315 2 6 2H20C20.5523 2 21 2.44772 21 3V21C21 21.5523 20.5523 22 20 22H6.5C4.567 22 3 20.433 3 18.5ZM19 20V17H6.5C5.67157 17 5 17.6716 5 18.5C5 19.3284 5.67157 20 6.5 20H19ZM10 4H6C5.44772 4 5 4.44772 5 5V15.3368C5.45463 15.1208 5.9632 15 6.5 15H19V4H17V12L13.5 10L10 12V4Z"></path>
      </svg>
    ),
    route: '/home/knowledge',
    description: t('knowledge.description'),
    helpLink: {
      en_US: 'https://docs.langbot.app/en/usage/knowledge/readme',
      zh_Hans: 'https://docs.langbot.app/zh/usage/knowledge/readme',
      ja_JP: 'https://docs.langbot.app/ja/usage/knowledge/readme',
    },
    section: 'home',
  }),

  // ── Extensions section ──
  new SidebarChildVO({
    id: 'plugins',
    name: t('sidebar.installedPlugins'),
    icon: (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill="currentColor"
        className="text-blue-500"
      >
        <path d="M7 5C7 2.79086 8.79086 1 11 1C13.2091 1 15 2.79086 15 5H18C18.5523 5 19 5.44772 19 6V9C21.2091 9 23 10.7909 23 13C23 15.2091 21.2091 17 19 17V20C19 20.5523 18.5523 21 18 21H4C3.44772 21 3 20.5523 3 20V6C3 5.44772 3.44772 5 4 5H7ZM11 3C9.89543 3 9 3.89543 9 5C9 5.23554 9.0403 5.45952 9.11355 5.66675C9.22172 5.97282 9.17461 6.31235 8.98718 6.57739C8.79974 6.84243 8.49532 7 8.17071 7H5V19H17V15.8293C17 15.5047 17.1576 15.2003 17.4226 15.0128C17.6877 14.8254 18.0272 14.7783 18.3332 14.8865C18.5405 14.9597 18.7645 15 19 15C20.1046 15 21 14.1046 21 13C21 11.8954 20.1046 11 19 11C18.7645 11 18.5405 11.0403 18.3332 11.1135C18.0272 11.2217 17.6877 11.1746 17.4226 10.9872C17.1576 10.7997 17 10.4953 17 10.1707V7H13.8293C13.5047 7 13.2003 6.84243 13.0128 6.57739C12.8254 6.31235 12.7783 5.97282 12.8865 5.66675C12.9597 5.45952 13 5.23555 13 5C13 3.89543 12.1046 3 11 3Z"></path>
      </svg>
    ),
    route: '/home/plugins',
    description: t('plugins.description'),
    helpLink: {
      en_US: 'https://docs.langbot.app/en/usage/plugin/plugin-intro',
      zh_Hans: 'https://docs.langbot.app/zh/usage/plugin/plugin-intro',
      ja_JP: 'https://docs.langbot.app/ja/usage/plugin/plugin-intro',
    },
    section: 'extensions',
  }),
  new SidebarChildVO({
    id: 'market',
    name: t('sidebar.pluginMarket'),
    icon: (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill="currentColor"
        className="text-blue-500"
      >
        <path d="M21 13.242V20H22V22H2V20H3V13.242C1.79401 12.435 1 11.0602 1 9.5C1 8.67286 1.25027 7.90335 1.67755 7.2612L4.5547 2.36088C4.80513 1.93859 5.26028 1.67578 5.76 1.67578H18.24C18.7397 1.67578 19.1949 1.93859 19.4453 2.36088L22.3225 7.2612C22.7497 7.90335 23 8.67286 23 9.5C23 11.0602 22.206 12.435 21 13.242ZM19 13.972C18.4511 14.0706 17.8794 14.0706 17.3305 13.972C16.1644 13.7566 15.1377 13.0712 14.5 12.1C13.8623 13.0712 12.8356 13.7566 11.6695 13.972C11.1206 14.0706 10.5489 14.0706 10 13.972C9.45108 14.0706 8.87938 14.0706 8.33053 13.972C7.16437 13.7566 6.13771 13.0712 5.5 12.1C4.86229 13.0712 3.83563 13.7566 2.66947 13.972C2.44883 14.0124 2.22434 14.0352 2 14.0404V20H5V15H10V20H19V13.972Z"></path>
      </svg>
    ),
    route: '/home/market',
    description: t('plugins.description'),
    helpLink: {
      en_US: 'https://docs.langbot.app/en/usage/plugin/plugin-intro',
      zh_Hans: 'https://docs.langbot.app/zh/usage/plugin/plugin-intro',
      ja_JP: 'https://docs.langbot.app/ja/usage/plugin/plugin-intro',
    },
    section: 'extensions',
  }),
  new SidebarChildVO({
    id: 'mcp',
    name: t('sidebar.mcpServers'),
    icon: (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill="currentColor"
        className="text-blue-500"
      >
        <path d="M4.5 7.65311V16.3469L12 20.689L19.5 16.3469V7.65311L12 3.311L4.5 7.65311ZM12 1L21.5 6.5V17.5L12 23L2.5 17.5V6.5L12 1ZM6.49896 9.97065L11 12.5765V17.625H13V12.5765L17.501 9.97066L16.499 8.2398L12 10.8445L7.50104 8.2398L6.49896 9.97065Z"></path>
      </svg>
    ),
    route: '/home/mcp',
    description: t('mcp.title'),
    helpLink: {
      en_US: '',
      zh_Hans: '',
    },
    section: 'extensions',
  }),
];
