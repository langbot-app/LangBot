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
