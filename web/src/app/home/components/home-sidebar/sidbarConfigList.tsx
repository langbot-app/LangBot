import { SidebarChildVO } from '@/app/home/components/home-sidebar/HomeSidebarChild';
import i18n from '@/i18n';
import {
  Zap,
  LayoutDashboard,
  Bot,
  Workflow,
  BookMarked,
  Puzzle,
  Store,
  Hexagon,
  Mountain,
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
    route: '/home/plugins',
    description: t('plugins.description'),
    helpLink: {
      en_US: 'https://link.langbot.app/en/docs/plugins',
      zh_Hans: 'https://link.langbot.app/zh/docs/plugins',
      ja_JP: 'https://link.langbot.app/ja/docs/plugins',
    },
    section: 'extensions',
  }),
  new SidebarChildVO({
    id: 'market',
    name: t('sidebar.pluginMarket'),
    icon: <Store className="text-blue-500" />,
    route: '/home/market',
    description: t('plugins.description'),
    helpLink: {
      en_US: 'https://link.langbot.app/en/docs/plugins',
      zh_Hans: 'https://link.langbot.app/zh/docs/plugins',
      ja_JP: 'https://link.langbot.app/ja/docs/plugins',
    },
    section: 'extensions',
  }),
  new SidebarChildVO({
    id: 'mcp',
    name: t('sidebar.mcpServers'),
    icon: <Hexagon className="text-blue-500" />,
    route: '/home/mcp',
    description: t('mcp.title'),
    helpLink: {
      en_US: '',
      zh_Hans: '',
    },
    section: 'extensions',
  }),
  new SidebarChildVO({
    id: 'skills',
    name: t('skills.title'),
    icon: <Mountain className="text-blue-500" />,
    route: '/home/skills',
    description: t('skills.description'),
    helpLink: {
      en_US: '',
      zh_Hans: '',
      ja_JP: '',
    },
    section: 'extensions',
  }),
];
