import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import {
  Bot,
  Languages,
  Star,
  Loader2,
  MessagesSquare,
  Search,
} from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  Item,
  ItemContent,
  ItemDescription,
  ItemTitle,
} from '@/components/ui/item';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { httpClient } from '@/app/infra/http/HttpClient';
import {
  pickPromptVersion,
  promptLanguageName,
  promptVersions,
} from './prompt-i18n';
import { useSpaceBind } from './useSpaceBind';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { cn } from '@/lib/utils';
import type {
  LibraryPrompt,
  PromptKind,
  PromptMessage,
} from '@/app/infra/entities/space-share';

type Tab = 'all' | 'favorites';

function highlight(text: string) {
  return text.split(/(\{\{[^}]+\}\})/g).map((part, i) =>
    /^\{\{[^}]+\}\}$/.test(part) ? (
      <span
        key={i}
        className="rounded bg-amber-100 px-0.5 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200"
      >
        {part}
      </span>
    ) : (
      <span key={i}>{part}</span>
    ),
  );
}

/**
 * Search the LangBot Space prompt library from a Pipeline / Agent prompt
 * field and apply a prompt to it (LANG-439). The library opens in a dialog so
 * the configuration form itself stays uncluttered.
 */
export default function PromptLibraryDialog({
  open,
  onOpenChange,
  defaultKind,
  hasCurrentContent,
  onApply,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  defaultKind: PromptKind;
  hasCurrentContent: boolean;
  onApply: (messages: PromptMessage[], mode: 'replace' | 'append') => void;
}) {
  const { t, i18n } = useTranslation();
  const [kind, setKind] = useState<PromptKind>(defaultKind);
  const [tab, setTab] = useState<Tab>('all');
  const [query, setQuery] = useState('');
  const [submitted, setSubmitted] = useState('');
  const [prompts, setPrompts] = useState<LibraryPrompt[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState<LibraryPrompt | null>(null);
  // Apply the WebUI language's version by default (with fallback); the user
  // can pick another language before applying.
  const [chosenLanguage, setChosenLanguage] = useState<string | null>(null);
  const versions = useMemo(
    () => (selected ? promptVersions(selected) : []),
    [selected],
  );
  const version = selected
    ? versions.find((v) => v.language === chosenLanguage) ||
      pickPromptVersion(versions, i18n.language)
    : null;
  useEffect(() => setChosenLanguage(null), [selected?.prompt_id]);
  const [favoriteIds, setFavoriteIds] = useState<Set<string>>(new Set());
  const [favoritesAvailable, setFavoritesAvailable] = useState(false);
  const { bind, binding } = useSpaceBind();
  const [confirmReplace, setConfirmReplace] = useState(false);

  useEffect(() => {
    if (open) {
      setKind(defaultKind);
      setTab('all');
    }
  }, [open, defaultKind]);

  const loadFavorites = useCallback(async () => {
    try {
      const res = await httpClient.listFavoritePrompts();
      setFavoritesAvailable(res.available);
      setFavoriteIds(new Set(res.prompt_ids || []));
      return res.prompts || [];
    } catch {
      setFavoritesAvailable(false);
      return [];
    }
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      let list: LibraryPrompt[];
      if (tab === 'favorites') {
        list = (await loadFavorites()).filter((p) => p.kind === kind);
        if (submitted) {
          const q = submitted.toLowerCase();
          list = list.filter((p) =>
            JSON.stringify([p.label, p.description, p.name, p.tags])
              .toLowerCase()
              .includes(q),
          );
        }
      } else {
        const res = await httpClient.listLibraryPrompts({
          kind,
          q: submitted,
          page_size: 40,
        });
        list = res.prompts || [];
      }
      setPrompts(list);
      setSelected((prev) =>
        prev && list.some((p) => p.prompt_id === prev.prompt_id)
          ? prev
          : (list[0] ?? null),
      );
    } catch (e) {
      setError((e as { msg?: string })?.msg || t('promptLibrary.loadFailed'));
      setPrompts([]);
      setSelected(null);
    } finally {
      setLoading(false);
    }
  }, [kind, tab, submitted, loadFavorites, t]);

  useEffect(() => {
    if (open) void load();
  }, [open, load]);

  useEffect(() => {
    if (open) void loadFavorites();
  }, [open, loadFavorites]);

  const toggleFavorite = async (p: LibraryPrompt) => {
    const next = !favoriteIds.has(p.prompt_id);
    try {
      const res = await httpClient.setPromptFavorite(p.author, p.name, next);
      setFavoriteIds((prev) => {
        const s = new Set(prev);
        if (next) s.add(p.prompt_id);
        else s.delete(p.prompt_id);
        return s;
      });
      const patch = (x: LibraryPrompt) =>
        x.prompt_id === p.prompt_id
          ? { ...x, favorite_count: res.favorite_count }
          : x;
      setPrompts((list) =>
        tab === 'favorites' && !next
          ? list.filter((x) => x.prompt_id !== p.prompt_id)
          : list.map(patch),
      );
      setSelected((s) => (s ? patch(s) : s));
    } catch (e) {
      toast.error(
        (e as { msg?: string })?.msg || t('promptLibrary.favoriteFailed'),
      );
    }
  };

  const apply = (mode: 'replace' | 'append') => {
    if (!selected || !version) return;
    onApply(
      version.messages.map((m) => ({ role: m.role, content: m.content })),
      mode,
    );
    void httpClient
      .trackLibraryPromptUse(selected.author, selected.name)
      .catch(() => undefined);
    toast.success(t('promptLibrary.applied'));
    onOpenChange(false);
  };

  const kindLabel = useMemo(
    () => ({
      messaging: t('promptLibrary.kindMessaging'),
      agent: t('promptLibrary.kindAgent'),
    }),
    [t],
  );

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="flex h-[min(720px,88vh)] w-[min(1040px,94vw)] max-w-none flex-col gap-3 p-5 sm:max-w-none">
          <DialogHeader>
            <DialogTitle>{t('promptLibrary.title')}</DialogTitle>
            <DialogDescription>
              {t('promptLibrary.description')}
            </DialogDescription>
          </DialogHeader>

          <div className="flex flex-wrap items-center gap-2">
            <ToggleGroup
              type="single"
              variant="outline"
              size="sm"
              value={kind}
              onValueChange={(v) => v && setKind(v as PromptKind)}
            >
              <ToggleGroupItem value="messaging" className="gap-1 px-3">
                <MessagesSquare className="size-3.5" />
                {kindLabel.messaging}
              </ToggleGroupItem>
              <ToggleGroupItem value="agent" className="gap-1 px-3">
                <Bot className="size-3.5" />
                {kindLabel.agent}
              </ToggleGroupItem>
            </ToggleGroup>
            <form
              className="relative min-w-[220px] flex-1"
              onSubmit={(e) => {
                e.preventDefault();
                setSubmitted(query.trim());
              }}
            >
              <Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
              <Input
                className="pl-8"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={t('promptLibrary.searchPlaceholder')}
              />
            </form>
            <ToggleGroup
              type="single"
              size="sm"
              value={tab}
              onValueChange={(v) => v && setTab(v as Tab)}
            >
              <ToggleGroupItem value="all" className="px-3">
                {t('promptLibrary.tabAll')}
              </ToggleGroupItem>
              <ToggleGroupItem
                value="favorites"
                className="gap-1 px-3"
                disabled={!favoritesAvailable}
                title={
                  favoritesAvailable
                    ? undefined
                    : t('promptLibrary.favoritesNeedAccount')
                }
              >
                <Star className="size-3.5" />
                {t('promptLibrary.tabFavorites')}
              </ToggleGroupItem>
            </ToggleGroup>
          </div>
          {kind !== defaultKind && (
            <div className="rounded-md bg-amber-50 px-3 py-1.5 text-xs text-amber-800 dark:bg-amber-900/30 dark:text-amber-200">
              {t('promptLibrary.otherKindHint', {
                kind: kindLabel[kind],
              })}
            </div>
          )}

          <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 md:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
            <div className="min-h-0 overflow-y-auto rounded-lg border">
              {loading ? (
                <div className="flex h-full items-center justify-center py-10">
                  <Loader2 className="size-5 animate-spin text-muted-foreground" />
                </div>
              ) : error ? (
                <div className="p-6 text-sm text-destructive">{error}</div>
              ) : prompts.length === 0 ? (
                <div className="p-6 text-center text-sm text-muted-foreground">
                  {tab === 'favorites'
                    ? t('promptLibrary.noFavorites')
                    : t('promptLibrary.empty')}
                </div>
              ) : (
                prompts.map((p) => (
                  <Item
                    key={p.prompt_id}
                    size="sm"
                    role="button"
                    tabIndex={0}
                    aria-selected={selected?.prompt_id === p.prompt_id}
                    onClick={() => setSelected(p)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        setSelected(p);
                      }
                    }}
                    className={cn(
                      'cursor-pointer flex-nowrap rounded-none border-0 border-b px-3 py-2.5 last:border-b-0 hover:bg-muted/50',
                      selected?.prompt_id === p.prompt_id && 'bg-muted',
                    )}
                  >
                    <ItemContent className="min-w-0 gap-0.5">
                      <ItemTitle className="w-full min-w-0 justify-between">
                        <span className="truncate">
                          {extractI18nObject(p.label) || p.name}
                        </span>
                        {favoriteIds.has(p.prompt_id) && (
                          <Star className="size-3.5 shrink-0 fill-amber-500 text-amber-500" />
                        )}
                      </ItemTitle>
                      <ItemDescription className="line-clamp-1 text-xs">
                        @{p.author} · {extractI18nObject(p.description)}
                      </ItemDescription>
                      <div className="mt-0.5 flex items-center gap-2 text-[11px] text-muted-foreground">
                        <span>
                          {(() => {
                            const v = pickPromptVersion(
                              promptVersions(p),
                              i18n.language,
                            );
                            return v.language === 'und'
                              ? null
                              : promptLanguageName(v.language);
                          })()}
                        </span>
                        <span>
                          {t('promptLibrary.uses', { count: p.use_count })}
                        </span>
                        <span>★ {p.favorite_count}</span>
                      </div>
                    </ItemContent>
                  </Item>
                ))
              )}
            </div>

            <div className="flex min-h-0 flex-col rounded-lg border">
              {selected ? (
                <>
                  <div className="flex items-start justify-between gap-2 border-b p-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="truncate font-medium">
                          {extractI18nObject(selected.label) || selected.name}
                        </span>
                        <Badge variant="outline">
                          {kindLabel[selected.kind]}
                        </Badge>
                      </div>
                      <div className="text-xs text-muted-foreground">
                        @{selected.author} · v{selected.version}
                      </div>
                    </div>
                    {favoritesAvailable ? (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => void toggleFavorite(selected)}
                        title={t('promptLibrary.favorite')}
                      >
                        <Star
                          className={cn(
                            'size-4',
                            favoriteIds.has(selected.prompt_id) &&
                              'fill-amber-500 text-amber-500',
                          )}
                        />
                      </Button>
                    ) : (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="shrink-0 text-xs text-muted-foreground"
                        disabled={binding}
                        onClick={() => void bind()}
                      >
                        <Star className="size-3.5" />
                        {t('promptLibrary.bindToFavorite')}
                      </Button>
                    )}
                  </div>
                  <div className="min-h-0 flex-1 space-y-2 overflow-y-auto p-3">
                    {versions.length > 1 && version && (
                      <div className="flex justify-end">
                        <Select
                          value={version.language}
                          onValueChange={setChosenLanguage}
                        >
                          <SelectTrigger
                            size="sm"
                            className="h-7 w-auto gap-1.5 text-xs"
                          >
                            <Languages className="size-3.5 text-muted-foreground" />
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent align="end">
                            {versions.map((v) => (
                              <SelectItem
                                key={v.language}
                                value={v.language}
                                className="text-xs"
                              >
                                {v.language === 'und'
                                  ? t('promptLibrary.originalLanguage')
                                  : promptLanguageName(v.language)}
                                {v.original && v.language !== 'und' && (
                                  <span className="ml-1 text-muted-foreground">
                                    ({t('promptLibrary.originalLanguage')})
                                  </span>
                                )}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    )}
                    {(version?.messages || selected.messages).map((m, i) => (
                      <div key={i} className="rounded-md bg-muted/40 p-2.5">
                        <div className="mb-1 text-[11px] font-medium uppercase text-muted-foreground">
                          {m.role}
                        </div>
                        <div className="whitespace-pre-wrap break-words text-sm">
                          {highlight(m.content)}
                        </div>
                      </div>
                    ))}
                    {selected.variables && selected.variables.length > 0 && (
                      <div className="text-xs text-muted-foreground">
                        {t('promptLibrary.variablesHint')}{' '}
                        {selected.variables.map((v) => (
                          <code
                            key={v.name}
                            className="mr-1 rounded bg-muted px-1"
                          >
                            {`{{${v.name}}}`}
                            {v.description ? ` ${v.description}` : ''}
                          </code>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="flex justify-end gap-2 border-t p-3">
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => apply('append')}
                    >
                      {t('promptLibrary.append')}
                    </Button>
                    <Button
                      type="button"
                      onClick={() =>
                        hasCurrentContent
                          ? setConfirmReplace(true)
                          : apply('replace')
                      }
                    >
                      {t('promptLibrary.replace')}
                    </Button>
                  </div>
                </>
              ) : (
                <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
                  {t('promptLibrary.selectHint')}
                </div>
              )}
            </div>
          </div>
        </DialogContent>
      </Dialog>
      <AlertDialog open={confirmReplace} onOpenChange={setConfirmReplace}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {t('promptLibrary.replaceTitle')}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {t('promptLibrary.replaceDescription')}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={() => apply('replace')}>
              {t('promptLibrary.replace')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
