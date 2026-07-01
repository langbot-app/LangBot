import { SidebarChildVO } from '@/app/home/components/home-sidebar/HomeSidebarChild';
import i18n from '@/i18n';
import {
  Zap,
  LayoutDashboard,
  Bot,
  Workflow,
  BookMarked,
  Puzzle,
  PlusCircle,
} from 'lucide-react';

const t = (key: string) => {
  return i18n.t(key);
};

export const sidebarConfigList = [
  // ── Quick Start ──
  new SidebarChildVO({
    id: 'wizard',
    name: t('sidebar.quickStart'),
    icon: <Zap className="text-blue-500" />,
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
    icon: <LayoutDashboard className="text-blue-500" />,
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
    icon: <Bot className="text-blue-500" />,
    route: '/home/bots',
    description: t('bots.description'),
    helpLink: {
      en_US: 'https://link.langbot.app/en/docs/platforms',
      zh_Hans: 'https://link.langbot.app/zh/docs/platforms',
      ja_JP: 'https://link.langbot.app/ja/docs/platforms',
    },
    section: 'home',
  }),
  new SidebarChildVO({
    id: 'pipelines',
    name: t('pipelines.title'),
    icon: <Workflow className="text-blue-500" />,
    route: '/home/pipelines',
    description: t('pipelines.description'),
    helpLink: {
      en_US: 'https://link.langbot.app/en/docs/pipelines',
      zh_Hans: 'https://link.langbot.app/zh/docs/pipelines',
      ja_JP: 'https://link.langbot.app/ja/docs/pipelines',
    },
    section: 'home',
  }),
  new SidebarChildVO({
    id: 'workflows',
    name: t('workflows.title'),
    icon: (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill="currentColor"
        className="text-blue-500"
      >
        <path d="M2 3C2 2.44772 2.44772 2 3 2H7C7.55228 2 8 2.44772 8 3V7C8 7.55228 7.55228 8 7 8H5V11H11V9C11 8.44772 11.4477 8 12 8H21C21.5523 8 22 8.44772 22 9V13C22 13.5523 21.5523 14 21 14H12C11.4477 14 11 13.5523 11 13V12H5V17H11V15C11 14.4477 11.4477 14 12 14H21C21.5523 14 22 14.4477 22 15V19C22 19.5523 21.5523 20 21 20H12C11.4477 20 11 19.5523 11 19V18H4C3.44772 18 3 17.5523 3 17V8H3C2.44772 8 2 7.55228 2 7V3ZM4 4V6H6V4H4ZM13 10V12H20V10H13ZM13 16V18H20V16H13Z"></path>
      </svg>
    ),
    route: '/home/workflows',
    description: t('workflows.description'),
    helpLink: {
      en_US: '',
      zh_Hans: '',
    },
    section: 'home',
  }),
  new SidebarChildVO({
    id: 'knowledge',
    name: t('knowledge.title'),
    icon: <BookMarked className="text-blue-500" />,
    route: '/home/knowledge',
    description: t('knowledge.description'),
    helpLink: {
      en_US: 'https://link.langbot.app/en/docs/knowledge',
      zh_Hans: 'https://link.langbot.app/zh/docs/knowledge',
      ja_JP: 'https://link.langbot.app/ja/docs/knowledge',
    },
    section: 'home',
  }),
  // ── Extensions section ──
  new SidebarChildVO({
    id: 'plugins',
    name: t('sidebar.installedPlugins'),
    icon: <Puzzle className="text-blue-500" />,
    route: '/home/extensions',
    description: t('plugins.description'),
    helpLink: {
      en_US: 'https://docs.langbot.app/en/plugin/plugin-intro',
      zh_Hans: 'https://docs.langbot.app/zh/plugin/plugin-intro',
      ja_JP: 'https://docs.langbot.app/ja/plugin/plugin-intro',
    },
    section: 'extensions',
  }),
  new SidebarChildVO({
    id: 'add-extension',
    name: t('sidebar.addExtension'),
    icon: <PlusCircle className="text-blue-500" />,
    route: '/home/add-extension',
    description: t('plugins.description'),
    helpLink: {
      en_US: 'https://docs.langbot.app/en/plugin/plugin-intro',
      zh_Hans: 'https://docs.langbot.app/zh/plugin/plugin-intro',
      ja_JP: 'https://docs.langbot.app/ja/plugin/plugin-intro',
    },
    section: 'extensions',
  }),
];
