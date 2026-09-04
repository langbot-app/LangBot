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
      en_US: 'https://langbot.app/docs/en/usage/platforms/readme',
      zh_Hans: 'https://langbot.app/docs/zh/usage/platforms/readme',
      ja_JP: 'https://langbot.app/docs/ja/usage/platforms/readme',
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
      en_US: 'https://langbot.app/docs/en/usage/pipelines/readme',
      zh_Hans: 'https://langbot.app/docs/zh/usage/pipelines/readme',
      ja_JP: 'https://langbot.app/docs/ja/usage/pipelines/readme',
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
      en_US: 'https://langbot.app/docs/en/usage/knowledge/readme',
      zh_Hans: 'https://langbot.app/docs/zh/usage/knowledge/readme',
      ja_JP: 'https://langbot.app/docs/ja/usage/knowledge/readme',
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
      en_US: 'https://langbot.app/docs/en/plugin/plugin-intro',
      zh_Hans: 'https://langbot.app/docs/zh/plugin/plugin-intro',
      ja_JP: 'https://langbot.app/docs/ja/plugin/plugin-intro',
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
      en_US: 'https://langbot.app/docs/en/plugin/plugin-intro',
      zh_Hans: 'https://langbot.app/docs/zh/plugin/plugin-intro',
      ja_JP: 'https://langbot.app/docs/ja/plugin/plugin-intro',
    },
    section: 'extensions',
  }),
];
