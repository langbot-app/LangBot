import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  ArrowDownToLine,
  ArrowUpRight,
  Search,
  Package,
  Check,
  Layers,
} from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import ScenarioPacks from '../bots/ScenarioPacks';

// UI fixtures only: never submitted to the import API or presented as real Space listings.
const samples = [
  {
    id: 'support',
    title: 'sampleSupport',
    category: 'categorySupport',
    emoji: '💬',
    color: 'bg-blue-50 dark:bg-blue-950/30',
    author: 'LangBot Community',
    downloads: 2480,
    agents: 1,
    plugins: ['LocalAgent', 'LangRAG'],
    featured: true,
  },
  {
    id: 'research',
    title: 'sampleResearch',
    category: 'categoryProductivity',
    emoji: '🗞️',
    color: 'bg-orange-50 dark:bg-orange-950/30',
    author: 'Mia',
    downloads: 1860,
    agents: 1,
    plugins: ['LocalAgent', 'WebSearch', 'ScheNotify'],
    featured: true,
  },
  {
    id: 'community',
    title: 'sampleCommunity',
    category: 'categoryCommunity',
    emoji: '🌱',
    color: 'bg-emerald-50 dark:bg-emerald-950/30',
    author: 'Open Builders',
    downloads: 1240,
    agents: 1,
    plugins: ['LocalAgent', 'TaskTimer'],
    featured: false,
  },
  {
    id: 'knowledge',
    title: 'sampleKnowledge',
    category: 'categoryKnowledge',
    emoji: '📚',
    color: 'bg-violet-50 dark:bg-violet-950/30',
    author: 'LangBot Community',
    downloads: 980,
    agents: 1,
    plugins: ['LocalAgent', 'LangRAG'],
    featured: false,
  },
  {
    id: 'writing',
    title: 'sampleWriting',
    category: 'categoryProductivity',
    emoji: '✍️',
    color: 'bg-rose-50 dark:bg-rose-950/30',
    author: 'Studio Notes',
    downloads: 760,
    agents: 1,
    plugins: ['LocalAgent'],
    featured: false,
  },
  {
    id: 'workflow',
    title: 'sampleWorkflow',
    category: 'categoryProductivity',
    emoji: '⚡',
    color: 'bg-amber-50 dark:bg-amber-950/30',
    author: 'Flow Lab',
    downloads: 520,
    agents: 1,
    plugins: ['n8n-agent'],
    featured: false,
  },
];
const categories = [
  'allCategories',
  'categorySupport',
  'categoryProductivity',
  'categoryKnowledge',
  'categoryCommunity',
];

export default function ScenariosPage() {
  const { t } = useTranslation();
  const [category, setCategory] = useState('allCategories');
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState('popular');
  const [selected, setSelected] = useState<(typeof samples)[number] | null>(
    null,
  );
  const filtered = samples.filter(
    (item) =>
      (category === 'allCategories' || item.category === category) &&
      `${t(`scenario.${item.title}`)} ${t(`scenario.${item.title}Desc`)} ${item.author} ${item.plugins.join(' ')}`
        .toLowerCase()
        .includes(query.toLowerCase()),
  );
  if (sort === 'newest') filtered.reverse();

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-7xl space-y-7 px-6 py-8 lg:px-10">
        <header className="flex flex-wrap items-start justify-between gap-5">
          <div>
            <div className="mb-2 flex items-center gap-3">
              <Package className="size-6 text-blue-500" />
              <h1 className="text-2xl font-semibold tracking-tight">
                {t('scenario.title')}
              </h1>
              <Badge variant="secondary">Space</Badge>
            </div>
            <p className="text-sm text-muted-foreground">
              {t('scenario.marketSubtitle')}
            </p>
          </div>
          <ScenarioPacks toolbarOnly />
        </header>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="relative w-full sm:max-w-sm">
            <Search className="absolute left-3 top-3 size-4 text-muted-foreground" />
            <Input
              className="pl-9"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t('scenario.searchMarket')}
              aria-label={t('scenario.searchMarket')}
            />
          </div>
          <select
            className="rounded-md border bg-background px-3 py-2 text-sm"
            value={sort}
            onChange={(e) => setSort(e.target.value)}
            aria-label={t('scenario.popular')}
          >
            <option value="popular">{t('scenario.popular')}</option>
            <option value="newest">{t('scenario.newest')}</option>
          </select>
        </div>
        <div className="flex flex-wrap gap-2">
          {categories.map((value) => (
            <Button
              key={value}
              size="sm"
              variant={category === value ? 'default' : 'ghost'}
              className="rounded-full"
              onClick={() => setCategory(value)}
            >
              {t(`scenario.${value}`)}
            </Button>
          ))}
        </div>
        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          {filtered.map((item) => (
            <article
              key={item.id}
              className="group flex flex-col rounded-xl border bg-card p-5 transition-all hover:border-blue-300 dark:hover:border-blue-700 hover:shadow-md"
            >
              <div className="mb-5 flex items-start justify-between">
                <div
                  className={`flex size-14 items-center justify-center rounded-2xl text-3xl ${item.color}`}
                >
                  {item.emoji}
                </div>
                <Badge variant="secondary" className="font-normal">
                  {t(`scenario.${item.featured ? 'featured' : item.category}`)}
                </Badge>
              </div>
              <button className="text-left" onClick={() => setSelected(item)}>
                <h2 className="mb-1.5 text-base font-semibold group-hover:text-blue-500">
                  {t(`scenario.${item.title}`)}
                </h2>
                <p className="text-xs text-muted-foreground">{item.author}</p>
              </button>
              <p className="mb-5 mt-4 min-h-12 text-sm leading-6 text-muted-foreground">
                {t(`scenario.${item.title}Desc`)}
              </p>
              <div className="mb-4 flex flex-wrap gap-1.5">
                {item.plugins.map((plugin) => (
                  <span
                    key={plugin}
                    className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground"
                  >
                    {plugin}
                  </span>
                ))}
              </div>
              <div className="mb-5 flex items-center gap-2 text-xs text-muted-foreground">
                <Layers className="size-3.5" />
                {t('scenario.resourceSummary', {
                  agents: item.agents,
                  plugins: item.plugins.length,
                })}
              </div>
              <div className="mt-auto flex items-center justify-between border-t pt-4">
                <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <ArrowDownToLine className="size-3.5" />
                  {item.downloads.toLocaleString()} {t('scenario.downloads')}
                </span>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setSelected(item)}
                >
                  {t('scenario.marketDownload')}
                  <ArrowUpRight className="ml-2 size-3.5" />
                </Button>
              </div>
            </article>
          ))}
        </div>
        {!filtered.length && (
          <div className="py-16 text-center text-sm text-muted-foreground">
            {t('scenario.noResults')}
          </div>
        )}
      </div>
      <Dialog
        open={!!selected}
        onOpenChange={(open) => !open && setSelected(null)}
      >
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-3">
              <span className="text-3xl">{selected?.emoji}</span>
              {selected && t(`scenario.${selected.title}`)}
            </DialogTitle>
            <DialogDescription>
              {selected && t(`scenario.${selected.title}Desc`)}
            </DialogDescription>
          </DialogHeader>
          {selected && (
            <div className="space-y-5">
              <div>
                <h3 className="mb-3 text-sm font-medium">
                  {t('scenario.included')}
                </h3>
                {selected.plugins.map((plugin) => (
                  <div
                    key={plugin}
                    className="mb-2 flex items-center gap-2 text-sm text-muted-foreground"
                  >
                    <Check className="size-4 text-emerald-500" />
                    {plugin}
                  </div>
                ))}
              </div>
              <div className="rounded-lg bg-muted/60 p-4">
                <h3 className="mb-2 text-sm font-medium">
                  {t('scenario.requirements')}
                </h3>
                <p className="text-sm leading-6 text-muted-foreground">
                  {t('scenario.setupHint')}
                </p>
              </div>
              <Button
                className="w-full"
                onClick={() => toast.info(t('scenario.demoDownload'))}
              >
                <ArrowDownToLine className="mr-2 size-4" />
                {t('scenario.marketDownload')}
              </Button>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
