import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import {
  AlertTriangle,
  ArrowDown,
  ArrowDownToLine,
  ArrowUp,
  ChevronLeft,
  Copy,
  Globe,
  Keyboard,
  LayoutGrid,
  Loader2,
  Menu,
  MessageSquareText,
  MoreHorizontal,
  Plus,
  RefreshCw,
  Send,
  Sparkles,
  Trash2,
  User,
  Zap,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
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
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { httpClient } from '@/app/infra/http/HttpClient';
import { cn } from '@/lib/utils';
import {
  ACTION_TYPES,
  ButtonError,
  CustomMenu,
  MAX_SUB_BUTTONS,
  MAX_SUB_NAME_BYTES,
  MAX_TOP_BUTTONS,
  MAX_TOP_NAME_BYTES,
  MENU_CONFIG_KEY,
  MenuButton,
  MenuButtonType,
  WECHAT_ERROR_HINTS,
  byteLength,
  createButton,
  isPublishedInSync,
  normalizeMenu,
  restoreLangBotButtons,
  validateMenu,
} from './wxoa-menu-model';

const TYPE_ICONS: Record<MenuButtonType, LucideIcon> = {
  group: Menu,
  view: Globe,
  miniprogram: LayoutGrid,
  reply: MessageSquareText,
  ai: Sparkles,
  event: Zap,
  unsupported: AlertTriangle,
};

type PublishedState = 'loading' | 'unknown' | null | Record<string, unknown>;

interface ChatLine {
  id: number;
  role: 'bot' | 'user' | 'system';
  text: string;
  muted?: boolean;
}

interface PlatformApiError {
  msg?: string;
  data?: { errcode?: number; errmsg?: string } | null;
}

function findButton(
  menu: CustomMenu,
  id: string | null,
): { button: MenuButton; parent: MenuButton | null; index: number } | null {
  if (!id) return null;
  for (const [index, button] of menu.buttons.entries()) {
    if (button.id === id) return { button, parent: null, index };
    const subIndex = (button.sub_buttons || []).findIndex((s) => s.id === id);
    if (button.type === 'group' && subIndex >= 0)
      return {
        button: button.sub_buttons![subIndex],
        parent: button,
        index: subIndex,
      };
  }
  return null;
}

function updateButton(
  menu: CustomMenu,
  id: string,
  patch: (button: MenuButton) => MenuButton,
): CustomMenu {
  return {
    buttons: menu.buttons.map((button) =>
      button.id === id
        ? patch(button)
        : button.sub_buttons
          ? {
              ...button,
              sub_buttons: button.sub_buttons.map((sub) =>
                sub.id === id ? patch(sub) : sub,
              ),
            }
          : button,
    ),
  };
}

function move<T>(items: T[], index: number, delta: number): T[] {
  const target = index + delta;
  if (target < 0 || target >= items.length) return items;
  const next = [...items];
  [next[index], next[target]] = [next[target], next[index]];
  return next;
}

export default function WxoaMenuEditor({
  botId,
  botName,
  enabled,
  canManage,
}: {
  botId: string;
  botName: string;
  enabled: boolean;
  canManage: boolean;
}) {
  const { t } = useTranslation();
  const [adapterConfig, setAdapterConfig] = useState<Record<
    string,
    unknown
  > | null>(null);
  const [menu, setMenu] = useState<CustomMenu>({ buttons: [] });
  const [savedSnapshot, setSavedSnapshot] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [openGroupId, setOpenGroupId] = useState<string | null>(null);
  const [published, setPublished] = useState<PublishedState>('loading');
  const [busy, setBusy] = useState<null | 'save' | 'import' | 'delete'>(null);
  const [confirm, setConfirm] = useState<null | 'import' | 'delete'>(null);
  const [chat, setChat] = useState<ChatLine[]>([]);

  const dirty = JSON.stringify(menu) !== savedSnapshot;
  const errors = useMemo(() => validateMenu(menu), [menu]);
  const errorCount = Object.keys(errors).length;
  const selected = findButton(menu, selectedId);
  // Web-console material buttons (news, images, ...) imported as placeholders.
  const unsupportedCount = Object.values(errors).filter((codes) =>
    codes.includes('unsupported'),
  ).length;

  const describeError = useCallback(
    (error: unknown): string => {
      const detail = (error || {}) as PlatformApiError;
      const errcode = detail.data?.errcode;
      if (typeof errcode === 'number') {
        const hint = WECHAT_ERROR_HINTS[errcode];
        return hint
          ? `${t(`wxoaMenu.wechatErrors.${hint}`)} (errcode ${errcode})`
          : t('wxoaMenu.wechatErrors.generic', {
              errcode,
              errmsg: detail.data?.errmsg || '',
            });
      }
      return detail.msg || String(error);
    },
    [t],
  );

  const refreshPublished = useCallback(async () => {
    if (!enabled) {
      setPublished('unknown');
      return;
    }
    setPublished('loading');
    try {
      const result = await httpClient.callBotPlatformApi<{
        published: Record<string, unknown> | null;
      }>(botId, 'menu.get');
      setPublished(result.published);
    } catch {
      setPublished('unknown');
    }
  }, [botId, enabled]);

  useEffect(() => {
    let cancelled = false;
    httpClient.getBot(botId).then((res) => {
      if (cancelled) return;
      const config = (res.bot.adapter_config || {}) as Record<string, unknown>;
      const loaded = normalizeMenu(config[MENU_CONFIG_KEY]);
      setAdapterConfig(config);
      setMenu(loaded);
      setSavedSnapshot(JSON.stringify(loaded));
      setSelectedId(loaded.buttons[0]?.id ?? null);
    });
    return () => {
      cancelled = true;
    };
  }, [botId]);

  useEffect(() => {
    refreshPublished();
  }, [refreshPublished]);

  const syncState: 'published' | 'outOfSync' | 'unpublished' | 'unknown' =
    published === 'loading' || published === 'unknown'
      ? 'unknown'
      : published === null
        ? 'unpublished'
        : isPublishedInSync(
              normalizeMenu(JSON.parse(savedSnapshot || '{}')),
              published,
            ) && !dirty
          ? 'published'
          : 'outOfSync';

  // Saved but WeChat still serves something else (or we cannot tell).
  const needsSync =
    enabled &&
    errorCount === 0 &&
    syncState !== 'published' &&
    !(syncState === 'unpublished' && !menu.buttons.length);

  // ---------- Mutations ----------
  function addTopButton() {
    if (menu.buttons.length >= MAX_TOP_BUTTONS) return;
    const button = createButton(
      t('wxoaMenu.editor.defaultTopName', { n: menu.buttons.length + 1 }),
    );
    setMenu({ buttons: [...menu.buttons, button] });
    setSelectedId(button.id);
    setOpenGroupId(null);
  }

  function addSubButton(parentId: string) {
    const parent = menu.buttons.find((b) => b.id === parentId);
    if (!parent || (parent.sub_buttons?.length ?? 0) >= MAX_SUB_BUTTONS) return;
    const sub = createButton(
      t('wxoaMenu.editor.defaultSubName', {
        n: (parent.sub_buttons?.length ?? 0) + 1,
      }),
    );
    setMenu(
      updateButton(menu, parentId, (b) => ({
        ...b,
        type: 'group',
        sub_buttons: [...(b.sub_buttons || []), sub],
      })),
    );
    setSelectedId(sub.id);
    setOpenGroupId(parentId);
  }

  function patchSelected(patch: Partial<MenuButton>) {
    if (!selected) return;
    setMenu(
      updateButton(menu, selected.button.id, (b) => ({ ...b, ...patch })),
    );
  }

  function changeType(type: MenuButtonType) {
    if (!selected) return;
    if (type === 'group') {
      const subs = selected.button.sub_buttons?.length
        ? selected.button.sub_buttons
        : [createButton(t('wxoaMenu.editor.defaultSubName', { n: 1 }))];
      patchSelected({ type, sub_buttons: subs });
      setOpenGroupId(selected.button.id);
    } else {
      patchSelected({ type });
    }
  }

  /** Select a button and keep the preview showing it. */
  function selectButton(id: string) {
    setSelectedId(id);
    const found = findButton(menu, id);
    if (!found) return;
    if (found.parent) setOpenGroupId(found.parent.id);
    else setOpenGroupId(found.button.type === 'group' ? found.button.id : null);
  }

  function deleteButton(id: string) {
    const found = findButton(menu, id);
    if (!found) return;
    const { button, parent, index } = found;
    if (parent) {
      const siblings = (parent.sub_buttons || []).filter(
        (s) => s.id !== button.id,
      );
      setMenu(
        updateButton(menu, parent.id, (p) => ({ ...p, sub_buttons: siblings })),
      );
      if (selectedId === button.id)
        setSelectedId(
          siblings[Math.min(index, siblings.length - 1)]?.id ?? parent.id,
        );
    } else {
      const remaining = menu.buttons.filter((b) => b.id !== button.id);
      setMenu({ buttons: remaining });
      if (
        selectedId === button.id ||
        (button.sub_buttons || []).some((s) => s.id === selectedId)
      ) {
        setSelectedId(
          remaining[Math.min(index, remaining.length - 1)]?.id ?? null,
        );
        setOpenGroupId(null);
      }
    }
  }

  function moveButton(id: string, delta: number) {
    const found = findButton(menu, id);
    if (!found) return;
    const { parent, index } = found;
    if (parent) {
      setMenu(
        updateButton(menu, parent.id, (p) => ({
          ...p,
          sub_buttons: move(p.sub_buttons || [], index, delta),
        })),
      );
    } else {
      setMenu({ buttons: move(menu.buttons, index, delta) });
    }
  }

  // ---------- Preview simulation ----------
  function simulate(button: MenuButton) {
    const empty = t('wxoaMenu.preview.empty');
    const lines: Omit<ChatLine, 'id'>[] = [];
    switch (button.type) {
      case 'reply':
        lines.push({
          role: 'system',
          text: t('wxoaMenu.preview.clickedReply', { name: button.name }),
        });
        lines.push({ role: 'bot', text: button.text?.trim() || empty });
        break;
      case 'ai':
        lines.push({
          role: 'system',
          text: t('wxoaMenu.preview.clickedAi', { name: button.name }),
        });
        lines.push({ role: 'user', text: button.text?.trim() || empty });
        lines.push({
          role: 'bot',
          text: t('wxoaMenu.preview.aiReply'),
          muted: true,
        });
        break;
      case 'view':
        lines.push({
          role: 'system',
          text: t('wxoaMenu.preview.opensUrl', { url: button.url || empty }),
        });
        break;
      case 'miniprogram':
        lines.push({
          role: 'system',
          text: t('wxoaMenu.preview.opensMiniprogram', {
            appid: button.appid || empty,
          }),
        });
        break;
      case 'event':
        lines.push({
          role: 'system',
          text: t('wxoaMenu.preview.eventSent', { key: button.key || empty }),
        });
        break;
      default:
        return;
    }
    setChat((current) =>
      [
        ...current,
        ...lines.map((line, offset) => ({
          ...line,
          id: Date.now() + offset,
        })),
      ].slice(-8),
    );
  }

  function clickTop(button: MenuButton) {
    setSelectedId(button.id);
    if (button.type === 'group') {
      setOpenGroupId(openGroupId === button.id ? null : button.id);
    } else {
      setOpenGroupId(null);
      simulate(button);
    }
  }

  // ---------- Remote actions ----------
  /** Store a menu in the bot's adapter config (LangBot side only). */
  async function persist(next: CustomMenu): Promise<boolean> {
    if (!adapterConfig) return false;
    try {
      const nextConfig = { ...adapterConfig, [MENU_CONFIG_KEY]: next };
      await httpClient.updateBot(botId, { adapter_config: nextConfig });
      setAdapterConfig(nextConfig);
      setSavedSnapshot(JSON.stringify(next));
      return true;
    } catch (error) {
      toast.error(t('wxoaMenu.toasts.saveFailed'), {
        description: describeError(error),
      });
      return false;
    }
  }

  function isNoMenuError(error: unknown): boolean {
    return (error as PlatformApiError | null)?.data?.errcode === 46003;
  }

  /** Save to LangBot, then push the saved menu to WeChat when possible. */
  async function saveAndSync() {
    setBusy('save');
    try {
      if (dirty && !(await persist(menu))) return;
      if (!enabled) {
        toast.success(t('wxoaMenu.toasts.savedBotDisabled'));
        return;
      }
      if (errorCount > 0) {
        toast.warning(t('wxoaMenu.toasts.savedNotSynced'), {
          description: t('wxoaMenu.validationSummary', { count: errorCount }),
        });
        return;
      }
      try {
        if (menu.buttons.length) {
          const result = await httpClient.callBotPlatformApi<{
            published: Record<string, unknown>;
          }>(botId, 'menu.publish');
          setPublished(result.published);
        } else {
          // An empty menu means "no menu" on WeChat too.
          try {
            await httpClient.callBotPlatformApi(botId, 'menu.delete');
          } catch (error) {
            if (!isNoMenuError(error)) throw error;
          }
          setPublished(null);
        }
        toast.success(t('wxoaMenu.toasts.synced'));
      } catch (error) {
        toast.error(t('wxoaMenu.toasts.syncFailed'), {
          description: describeError(error),
          duration: 12000,
        });
      }
    } finally {
      setBusy(null);
    }
  }

  async function importConsole() {
    setConfirm(null);
    setBusy('import');
    try {
      const result = await httpClient.callBotPlatformApi<{
        menu: CustomMenu;
        warnings: string[];
      }>(botId, 'menu.import_console');
      const imported = restoreLangBotButtons(
        normalizeMenu(result.menu),
        normalizeMenu(adapterConfig?.[MENU_CONFIG_KEY]),
      );
      // Keep the imported menu as LangBot's own snapshot right away.
      if (!(await persist(imported))) return;
      setMenu(imported);
      setSelectedId(imported.buttons[0]?.id ?? null);
      setOpenGroupId(null);
      setChat([]);
      toast.success(
        t(
          imported.buttons.length
            ? 'wxoaMenu.toasts.imported'
            : 'wxoaMenu.toasts.importedEmpty',
        ),
      );
    } catch (error) {
      toast.error(t('wxoaMenu.toasts.importFailed'), {
        description: describeError(error),
        duration: 12000,
      });
    } finally {
      setBusy(null);
    }
  }

  async function deleteRemote() {
    setConfirm(null);
    setBusy('delete');
    try {
      await httpClient.callBotPlatformApi(botId, 'menu.delete');
      setPublished(null);
      toast.success(t('wxoaMenu.toasts.deleted'));
    } catch (error) {
      toast.error(t('wxoaMenu.toasts.deleteFailed'), {
        description: describeError(error),
      });
    } finally {
      setBusy(null);
    }
  }

  if (!adapterConfig) {
    return (
      <div className="flex h-40 items-center justify-center text-muted-foreground">
        <Loader2 className="size-5 animate-spin" />
      </div>
    );
  }

  const readOnly = !canManage;
  const statusBadge = {
    published: 'success',
    outOfSync: 'warning',
    unpublished: 'disabled',
    unknown: 'disabled',
  }[syncState];

  return (
    <div className="flex flex-col gap-4 pb-6" data-testid="wxoa-menu-editor">
      {/* Header */}
      <Card>
        <CardHeader className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div className="space-y-1.5">
            <div className="flex flex-wrap items-center gap-2">
              <CardTitle>{t('wxoaMenu.title')}</CardTitle>
              <Badge status={statusBadge} className="rounded-full">
                {published === 'loading' ? (
                  <Loader2 className="animate-spin" />
                ) : null}
                {t(`wxoaMenu.status.${syncState}`)}
              </Badge>
              {dirty && (
                <Badge status="pending" className="rounded-full">
                  {t('wxoaMenu.unsaved')}
                </Badge>
              )}
            </div>
            <CardDescription className="max-w-3xl">
              {t('wxoaMenu.description')}
            </CardDescription>
          </div>
          {!readOnly && (
            <div className="flex shrink-0 flex-wrap items-center gap-2">
              <Button
                variant="outline"
                onClick={() =>
                  menu.buttons.length ? setConfirm('import') : importConsole()
                }
                disabled={!enabled || busy !== null}
              >
                {busy === 'import' ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <ArrowDownToLine className="size-4" />
                )}
                {t(
                  busy === 'import'
                    ? 'wxoaMenu.actions.importing'
                    : 'wxoaMenu.actions.import',
                )}
              </Button>
              <Button
                onClick={saveAndSync}
                disabled={busy !== null || (!dirty && !needsSync)}
                data-testid="wxoa-menu-save"
              >
                {busy === 'save' ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : enabled ? (
                  <Send className="size-4" />
                ) : null}
                {t(
                  busy === 'save'
                    ? 'wxoaMenu.actions.saving'
                    : enabled
                      ? 'wxoaMenu.actions.saveAndSync'
                      : 'wxoaMenu.actions.save',
                )}
              </Button>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={t('wxoaMenu.actions.more')}
                    disabled={busy !== null}
                  >
                    <MoreHorizontal className="size-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem
                    onClick={refreshPublished}
                    disabled={!enabled}
                  >
                    <RefreshCw className="size-4" />
                    {t('wxoaMenu.actions.refresh')}
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    className="text-destructive focus:text-destructive"
                    onClick={() => setConfirm('delete')}
                    disabled={!enabled}
                  >
                    <Trash2 className="size-4" />
                    {t('wxoaMenu.actions.deleteRemote')}
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          )}
        </CardHeader>
        {(!enabled || errorCount > 0 || unsupportedCount > 0) && (
          <CardContent className="space-y-3">
            {!enabled && (
              <Alert>
                <AlertTriangle className="size-4" />
                <AlertDescription>{t('wxoaMenu.botDisabled')}</AlertDescription>
              </Alert>
            )}
            {unsupportedCount > 0 && (
              <Alert>
                <AlertTriangle className="size-4" />
                <AlertTitle>
                  {t('wxoaMenu.toasts.importWarnings', {
                    count: unsupportedCount,
                  })}
                </AlertTitle>
                <AlertDescription>
                  {t('wxoaMenu.types.unsupported.description')}
                </AlertDescription>
              </Alert>
            )}
            {errorCount > 0 && menu.buttons.length > 0 && (
              <p className="text-sm text-amber-700 dark:text-amber-400">
                {t('wxoaMenu.validationSummary', { count: errorCount })}
              </p>
            )}
          </CardContent>
        )}
      </Card>

      <div className="grid gap-4 lg:grid-cols-[minmax(320px,360px)_1fr] 2xl:grid-cols-[minmax(320px,360px)_280px_1fr]">
        {/* Phone preview */}
        <Card className="h-fit">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">
              {t('wxoaMenu.preview.title')}
            </CardTitle>
            <CardDescription>{t('wxoaMenu.preview.hint')}</CardDescription>
          </CardHeader>
          <CardContent>
            <PhonePreview
              botName={botName}
              menu={menu}
              errors={errors}
              chat={chat}
              selectedId={selectedId}
              openGroupId={openGroupId}
              readOnly={readOnly}
              onClickTop={clickTop}
              onClickSub={(sub) => {
                setSelectedId(sub.id);
                simulate(sub);
              }}
              onAddTop={addTopButton}
              onAddSub={addSubButton}
            />
          </CardContent>
        </Card>

        <div className="grid h-fit gap-4 lg:col-span-1 2xl:contents">
          {/* Menu structure */}
          <Card className="h-fit">
            <CardHeader className="pb-2">
              <CardTitle className="text-base">
                {t('wxoaMenu.structure.title')}
              </CardTitle>
              <CardDescription>{t('wxoaMenu.structure.hint')}</CardDescription>
            </CardHeader>
            <CardContent>
              <MenuStructure
                menu={menu}
                errors={errors}
                selectedId={selectedId}
                readOnly={readOnly}
                onSelect={selectButton}
                onMove={moveButton}
                onDelete={deleteButton}
                onAddTop={addTopButton}
                onAddSub={addSubButton}
              />
            </CardContent>
          </Card>

          {/* Button editor */}
          <Card className="h-fit">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <CardTitle className="text-base">
                    {t('wxoaMenu.editor.title')}
                  </CardTitle>
                  {selected && (
                    <CardDescription>
                      {selected.parent
                        ? `${selected.parent.name} › ${t('wxoaMenu.editor.subLevel')}`
                        : t('wxoaMenu.editor.topLevel')}
                    </CardDescription>
                  )}
                </div>
                {selected && !readOnly && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-destructive hover:text-destructive"
                    onClick={() => deleteButton(selected.button.id)}
                  >
                    <Trash2 className="size-4" />
                    {t(
                      selected.parent
                        ? 'wxoaMenu.actions.deleteSub'
                        : 'wxoaMenu.actions.deleteTop',
                    )}
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {!menu.buttons.length ? (
                <EmptyState
                  readOnly={readOnly}
                  enabled={enabled}
                  onAdd={addTopButton}
                  onImport={importConsole}
                />
              ) : !selected ? (
                <p className="py-10 text-center text-sm text-muted-foreground">
                  {t('wxoaMenu.editor.noSelection')}
                </p>
              ) : (
                <fieldset disabled={readOnly} className="space-y-5">
                  <ButtonFields
                    button={selected.button}
                    isTop={!selected.parent}
                    errors={errors[selected.button.id] || []}
                    onPatch={patchSelected}
                    onChangeType={changeType}
                    onAddSub={() => addSubButton(selected.button.id)}
                  />
                </fieldset>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      <AlertDialog
        open={confirm !== null}
        onOpenChange={(open) => !open && setConfirm(null)}
      >
        <AlertDialogContent>
          {confirm && (
            <>
              <AlertDialogHeader>
                <AlertDialogTitle>
                  {t(`wxoaMenu.${confirm}Confirm.title`)}
                </AlertDialogTitle>
                <AlertDialogDescription>
                  {t(`wxoaMenu.${confirm}Confirm.description`)}
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                <AlertDialogAction
                  className={cn(
                    confirm === 'delete' &&
                      'bg-destructive text-white hover:bg-destructive/90',
                  )}
                  onClick={confirm === 'import' ? importConsole : deleteRemote}
                >
                  {t(`wxoaMenu.${confirm}Confirm.confirm`)}
                </AlertDialogAction>
              </AlertDialogFooter>
            </>
          )}
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function EmptyState({
  readOnly,
  enabled,
  onAdd,
  onImport,
}: {
  readOnly: boolean;
  enabled: boolean;
  onAdd: () => void;
  onImport: () => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col items-center gap-3 py-10 text-center">
      <div className="flex size-12 items-center justify-center rounded-full bg-muted">
        <Menu className="size-6 text-muted-foreground" />
      </div>
      <div className="space-y-1">
        <p className="font-medium">{t('wxoaMenu.empty.title')}</p>
        <p className="max-w-md text-sm text-muted-foreground">
          {t('wxoaMenu.empty.description')}
        </p>
      </div>
      {!readOnly && (
        <div className="flex flex-wrap justify-center gap-2">
          <Button variant="outline" onClick={onImport} disabled={!enabled}>
            <ArrowDownToLine className="size-4" />
            {t('wxoaMenu.actions.import')}
          </Button>
          <Button onClick={onAdd}>
            <Plus className="size-4" />
            {t('wxoaMenu.actions.addTop')}
          </Button>
        </div>
      )}
    </div>
  );
}

function PhonePreview({
  botName,
  menu,
  errors,
  chat,
  selectedId,
  openGroupId,
  readOnly,
  onClickTop,
  onClickSub,
  onAddTop,
  onAddSub,
}: {
  botName: string;
  menu: CustomMenu;
  errors: Record<string, ButtonError[]>;
  chat: ChatLine[];
  selectedId: string | null;
  openGroupId: string | null;
  readOnly: boolean;
  onClickTop: (button: MenuButton) => void;
  onClickSub: (button: MenuButton) => void;
  onAddTop: () => void;
  onAddSub: (parentId: string) => void;
}) {
  const { t } = useTranslation();
  const hasError = (button: MenuButton) =>
    Boolean(errors[button.id]) ||
    (button.type === 'group' &&
      (button.sub_buttons || []).some((sub) => errors[sub.id]));

  return (
    <div className="mx-auto w-full max-w-[320px] rounded-[2.2rem] border border-zinc-300 bg-zinc-900 p-2.5 shadow-lg dark:border-zinc-700">
      <div className="flex h-[560px] flex-col overflow-hidden rounded-[1.7rem] bg-[#ededed] text-zinc-900 dark:bg-zinc-800 dark:text-zinc-100">
        {/* Title bar */}
        <div className="flex h-11 shrink-0 items-center justify-between border-b border-black/5 bg-[#ededed] px-3 dark:border-white/10 dark:bg-zinc-800">
          <ChevronLeft className="size-5 opacity-70" />
          <span className="truncate text-sm font-medium">{botName}</span>
          <User className="size-4 opacity-70" />
        </div>

        {/* Chat */}
        <div className="flex min-h-0 flex-1 flex-col gap-2.5 overflow-y-auto px-3 py-3 text-[13px] leading-snug">
          <Bubble role="bot" text={t('wxoaMenu.preview.welcome')} />
          {chat.map((line) => (
            <Bubble
              key={line.id}
              role={line.role}
              text={line.text}
              muted={line.muted}
            />
          ))}
        </div>

        {/* Menu bar */}
        <div className="relative flex h-12 shrink-0 border-t border-black/10 bg-[#f7f7f7] dark:border-white/10 dark:bg-zinc-900">
          <div className="flex w-10 shrink-0 items-center justify-center border-r border-black/10 dark:border-white/10">
            <Keyboard className="size-4 opacity-60" />
          </div>
          {menu.buttons.map((button) => (
            <div key={button.id} className="relative flex min-w-0 flex-1">
              {button.type === 'group' && openGroupId === button.id && (
                <div className="absolute bottom-full left-1/2 z-10 mb-2 w-[94%] -translate-x-1/2 rounded-md border border-black/10 bg-white shadow-md dark:border-white/10 dark:bg-zinc-800">
                  {(button.sub_buttons || []).map((sub) => (
                    <button
                      key={sub.id}
                      type="button"
                      onClick={() => onClickSub(sub)}
                      className={cn(
                        'flex w-full items-center justify-center gap-1 border-b border-black/5 px-2 py-2.5 text-xs last:border-b-0 hover:bg-black/5 dark:border-white/10 dark:hover:bg-white/5',
                        selectedId === sub.id &&
                          'bg-emerald-50 font-medium text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300',
                        errors[sub.id] && 'text-red-600 dark:text-red-400',
                      )}
                    >
                      <span className="truncate">
                        {sub.name || t('wxoaMenu.preview.empty')}
                      </span>
                    </button>
                  ))}
                  {!readOnly &&
                    (button.sub_buttons?.length ?? 0) < MAX_SUB_BUTTONS && (
                      <button
                        type="button"
                        onClick={() => onAddSub(button.id)}
                        className="flex w-full items-center justify-center gap-1 px-2 py-2 text-xs text-muted-foreground hover:bg-black/5 dark:hover:bg-white/5"
                        aria-label={t('wxoaMenu.actions.addSub')}
                      >
                        <Plus className="size-3.5" />
                      </button>
                    )}
                  <div className="absolute -bottom-1.5 left-1/2 size-3 -translate-x-1/2 rotate-45 border-b border-r border-black/10 bg-white dark:border-white/10 dark:bg-zinc-800" />
                </div>
              )}
              <button
                type="button"
                onClick={() => onClickTop(button)}
                className={cn(
                  'relative flex min-w-0 flex-1 items-center justify-center gap-1 border-r border-black/10 px-1 text-xs last:border-r-0 hover:bg-black/5 dark:border-white/10 dark:hover:bg-white/5',
                  selectedId === button.id &&
                    'bg-emerald-50 font-medium text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300',
                )}
              >
                {button.type === 'group' && (
                  <Menu className="size-3 shrink-0 opacity-60" />
                )}
                <span className="truncate">
                  {button.name || t('wxoaMenu.preview.empty')}
                </span>
                {hasError(button) && (
                  <span className="absolute right-1.5 top-1.5 size-1.5 rounded-full bg-red-500" />
                )}
              </button>
            </div>
          ))}
          {!readOnly && menu.buttons.length < MAX_TOP_BUTTONS && (
            <button
              type="button"
              onClick={onAddTop}
              className="flex flex-1 items-center justify-center gap-1 text-xs text-muted-foreground hover:bg-black/5 dark:hover:bg-white/5"
            >
              <Plus className="size-3.5" />
              {t('wxoaMenu.actions.addTop')}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function Bubble({
  role,
  text,
  muted,
}: {
  role: ChatLine['role'];
  text: string;
  muted?: boolean;
}) {
  if (role === 'system') {
    return (
      <div className="mx-auto max-w-[90%] rounded bg-black/5 px-2 py-1 text-center text-[11px] text-zinc-500 dark:bg-white/10 dark:text-zinc-400">
        {text}
      </div>
    );
  }
  const isUser = role === 'user';
  return (
    <div className={cn('flex items-start gap-2', isUser && 'flex-row-reverse')}>
      <div
        className={cn(
          'flex size-7 shrink-0 items-center justify-center rounded',
          isUser ? 'bg-sky-200 dark:bg-sky-700' : 'bg-emerald-600 text-white',
        )}
      >
        {isUser ? <User className="size-4" /> : <Sparkles className="size-4" />}
      </div>
      <div
        className={cn(
          'max-w-[75%] whitespace-pre-wrap break-words rounded-md px-2.5 py-1.5 shadow-sm',
          isUser ? 'bg-[#95ec69] text-zinc-900' : 'bg-white dark:bg-zinc-700',
          muted && 'italic text-zinc-500 dark:text-zinc-300',
        )}
      >
        {text}
      </div>
    </div>
  );
}

function FieldError({
  errors,
  codes,
}: {
  errors: ButtonError[];
  codes: ButtonError[];
}) {
  const { t } = useTranslation();
  const shown = errors.filter((e) => codes.includes(e));
  if (!shown.length) return null;
  return (
    <p className="text-xs text-red-600 dark:text-red-400">
      {shown.map((e) => t(`wxoaMenu.errors.${e}`)).join('；')}
    </p>
  );
}

function ButtonFields({
  button,
  isTop,
  errors,
  onPatch,
  onChangeType,
  onAddSub,
}: {
  button: MenuButton;
  isTop: boolean;
  errors: ButtonError[];
  onPatch: (patch: Partial<MenuButton>) => void;
  onChangeType: (type: MenuButtonType) => void;
  onAddSub: () => void;
}) {
  const { t } = useTranslation();
  const maxBytes = isTop ? MAX_TOP_NAME_BYTES : MAX_SUB_NAME_BYTES;
  const usedBytes = byteLength((button.name || '').trim());
  const types: MenuButtonType[] = [
    ...(isTop ? (['group'] as MenuButtonType[]) : []),
    ...ACTION_TYPES,
    ...(button.type === 'unsupported'
      ? (['unsupported'] as MenuButtonType[])
      : []),
  ];
  const eventFilter = JSON.stringify({
    field: 'data.EventKey',
    operator: 'eq',
    value: button.key || '',
  });

  return (
    <>
      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <Label htmlFor="wxoa-menu-name">{t('wxoaMenu.editor.name')}</Label>
          <span
            className={cn(
              'text-xs text-muted-foreground',
              usedBytes > maxBytes && 'text-red-600 dark:text-red-400',
            )}
          >
            {t('wxoaMenu.editor.nameBytes', { used: usedBytes, max: maxBytes })}
          </span>
        </div>
        <Input
          id="wxoa-menu-name"
          value={button.name}
          onChange={(e) => onPatch({ name: e.target.value })}
          aria-invalid={errors.some((e) => e.startsWith('name'))}
        />
        <FieldError errors={errors} codes={['nameRequired', 'nameTooLong']} />
      </div>

      <div className="space-y-2">
        <Label>{t('wxoaMenu.editor.type')}</Label>
        <div className="grid gap-2 sm:grid-cols-2" role="radiogroup">
          {types.map((type) => {
            const Icon = TYPE_ICONS[type];
            const active = button.type === type;
            return (
              <button
                key={type}
                type="button"
                role="radio"
                aria-checked={active}
                disabled={type === 'unsupported'}
                onClick={() => onChangeType(type)}
                className={cn(
                  'flex items-start gap-2.5 rounded-lg border p-3 text-left transition-colors hover:bg-accent disabled:cursor-default',
                  active
                    ? 'border-primary bg-primary/5 ring-1 ring-primary'
                    : 'border-border',
                  type === 'unsupported' &&
                    'border-amber-500/40 bg-amber-500/5',
                )}
              >
                <Icon
                  className={cn(
                    'mt-0.5 size-4 shrink-0',
                    active ? 'text-primary' : 'text-muted-foreground',
                  )}
                />
                <span className="min-w-0">
                  <span className="block text-sm font-medium">
                    {t(`wxoaMenu.types.${type}.label`)}
                  </span>
                  <span className="block text-xs text-muted-foreground">
                    {t(`wxoaMenu.types.${type}.description`)}
                  </span>
                </span>
              </button>
            );
          })}
        </div>
        <FieldError errors={errors} codes={['unsupported']} />
      </div>

      {button.type === 'group' && (
        <div className="space-y-2">
          <Label>
            {t('wxoaMenu.editor.subButtons', {
              count: button.sub_buttons?.length ?? 0,
              max: MAX_SUB_BUTTONS,
            })}
          </Label>
          <p className="text-xs text-muted-foreground">
            {t('wxoaMenu.editor.groupHint')}
          </p>
          {(button.sub_buttons?.length ?? 0) < MAX_SUB_BUTTONS && (
            <Button variant="outline" size="sm" onClick={onAddSub}>
              <Plus className="size-4" />
              {t('wxoaMenu.actions.addSub')}
            </Button>
          )}
          <FieldError errors={errors} codes={['groupEmpty']} />
        </div>
      )}

      {button.type === 'view' && (
        <div className="space-y-1.5">
          <Label htmlFor="wxoa-menu-url">{t('wxoaMenu.fields.url')}</Label>
          <Input
            id="wxoa-menu-url"
            value={button.url || ''}
            placeholder={t('wxoaMenu.fields.urlPlaceholder')}
            onChange={(e) => onPatch({ url: e.target.value })}
          />
          <FieldError errors={errors} codes={['urlInvalid', 'urlTooLong']} />
        </div>
      )}

      {button.type === 'miniprogram' && (
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="wxoa-menu-appid">
                {t('wxoaMenu.fields.appid')}
              </Label>
              <Input
                id="wxoa-menu-appid"
                value={button.appid || ''}
                placeholder={t('wxoaMenu.fields.appidPlaceholder')}
                onChange={(e) => onPatch({ appid: e.target.value })}
              />
              <FieldError errors={errors} codes={['appidRequired']} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="wxoa-menu-pagepath">
                {t('wxoaMenu.fields.pagepath')}
              </Label>
              <Input
                id="wxoa-menu-pagepath"
                value={button.pagepath || ''}
                placeholder={t('wxoaMenu.fields.pagepathPlaceholder')}
                onChange={(e) => onPatch({ pagepath: e.target.value })}
              />
              <FieldError errors={errors} codes={['pagepathRequired']} />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="wxoa-menu-fallback">
              {t('wxoaMenu.fields.fallbackUrl')}
            </Label>
            <Input
              id="wxoa-menu-fallback"
              value={button.url || ''}
              placeholder={t('wxoaMenu.fields.urlPlaceholder')}
              onChange={(e) => onPatch({ url: e.target.value })}
            />
            <p className="text-xs text-muted-foreground">
              {t('wxoaMenu.fields.fallbackUrlHint')}
            </p>
            <FieldError errors={errors} codes={['urlInvalid', 'urlTooLong']} />
          </div>
        </div>
      )}

      {(button.type === 'reply' || button.type === 'ai') && (
        <div className="space-y-1.5">
          <Label htmlFor="wxoa-menu-text">
            {t(
              button.type === 'reply'
                ? 'wxoaMenu.fields.replyText'
                : 'wxoaMenu.fields.aiText',
            )}
          </Label>
          <Textarea
            id="wxoa-menu-text"
            rows={button.type === 'reply' ? 5 : 3}
            value={button.text || ''}
            placeholder={t(
              button.type === 'reply'
                ? 'wxoaMenu.fields.replyTextPlaceholder'
                : 'wxoaMenu.fields.aiTextPlaceholder',
            )}
            onChange={(e) => onPatch({ text: e.target.value })}
          />
          <p className="text-xs text-muted-foreground">
            {t(
              button.type === 'reply'
                ? 'wxoaMenu.fields.replyTextHint'
                : 'wxoaMenu.fields.aiTextHint',
            )}
          </p>
          <FieldError errors={errors} codes={['textRequired', 'textTooLong']} />
        </div>
      )}

      {button.type === 'event' && (
        <div className="space-y-1.5">
          <Label htmlFor="wxoa-menu-key">{t('wxoaMenu.fields.eventKey')}</Label>
          <Input
            id="wxoa-menu-key"
            className="font-mono"
            value={button.key || ''}
            placeholder={t('wxoaMenu.fields.eventKeyPlaceholder')}
            onChange={(e) => onPatch({ key: e.target.value })}
          />
          <FieldError
            errors={errors}
            codes={['keyRequired', 'keyReserved', 'keyTooLong']}
          />
          <div className="rounded-md bg-muted/60 p-3 text-xs text-muted-foreground">
            <p>{t('wxoaMenu.fields.eventKeyHint')}</p>
            <div className="mt-2 flex items-center gap-2">
              <code className="min-w-0 flex-1 truncate rounded bg-background px-2 py-1 font-mono">
                {eventFilter}
              </code>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  navigator.clipboard?.writeText(eventFilter);
                  toast.success(t('wxoaMenu.fields.filterCopied'));
                }}
              >
                <Copy className="size-3.5" />
                {t('wxoaMenu.fields.copyFilter')}
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function IconAction({
  label,
  icon: Icon,
  onClick,
  disabled,
  destructive,
}: {
  label: string;
  icon: LucideIcon;
  onClick: () => void;
  disabled?: boolean;
  destructive?: boolean;
}) {
  return (
    <Button
      variant="ghost"
      size="icon"
      className={cn(
        'size-7',
        destructive && 'text-muted-foreground hover:text-destructive',
      )}
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={(event) => {
        event.stopPropagation();
        onClick();
      }}
    >
      <Icon className="size-3.5" />
    </Button>
  );
}

function StructureRow({
  button,
  level,
  index,
  count,
  selected,
  hasError,
  readOnly,
  onSelect,
  onMove,
  onDelete,
}: {
  button: MenuButton;
  level: 'top' | 'sub';
  index: number;
  count: number;
  selected: boolean;
  hasError: boolean;
  readOnly: boolean;
  onSelect: (id: string) => void;
  onMove: (id: string, delta: number) => void;
  onDelete: (id: string) => void;
}) {
  const { t } = useTranslation();
  const Icon = TYPE_ICONS[button.type] || MessageSquareText;
  return (
    <div
      role="button"
      tabIndex={0}
      data-testid={`wxoa-structure-${button.id}`}
      onClick={() => onSelect(button.id)}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          onSelect(button.id);
        }
      }}
      className={cn(
        'group flex cursor-pointer items-center gap-2 rounded-md py-1.5 pr-1 text-sm outline-none transition-colors hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring',
        level === 'top' ? 'pl-2' : 'pl-7',
        selected && 'bg-primary/10 text-primary hover:bg-primary/10',
      )}
    >
      <Icon
        className={cn(
          'size-4 shrink-0',
          selected ? 'text-primary' : 'text-muted-foreground',
        )}
      />
      <span
        className={cn(
          'min-w-0 flex-1 truncate',
          level === 'top' && 'font-medium',
        )}
      >
        {button.name || t('wxoaMenu.preview.empty')}
      </span>
      {hasError && (
        <span
          className="size-1.5 shrink-0 rounded-full bg-red-500"
          title={t('wxoaMenu.structure.needsFix')}
        />
      )}
      {!readOnly && (
        <span
          className={cn(
            'flex shrink-0 items-center opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100',
            selected && 'opacity-100',
          )}
        >
          <IconAction
            label={t('wxoaMenu.actions.moveUp')}
            icon={ArrowUp}
            disabled={index === 0}
            onClick={() => onMove(button.id, -1)}
          />
          <IconAction
            label={t('wxoaMenu.actions.moveDown')}
            icon={ArrowDown}
            disabled={index === count - 1}
            onClick={() => onMove(button.id, 1)}
          />
          <IconAction
            label={t(
              level === 'top'
                ? 'wxoaMenu.actions.deleteTop'
                : 'wxoaMenu.actions.deleteSub',
            )}
            icon={Trash2}
            destructive
            onClick={() => onDelete(button.id)}
          />
        </span>
      )}
    </div>
  );
}

/** Tree of all buttons: the place to switch, reorder, add and remove them. */
function MenuStructure({
  menu,
  errors,
  selectedId,
  readOnly,
  onSelect,
  onMove,
  onDelete,
  onAddTop,
  onAddSub,
}: {
  menu: CustomMenu;
  errors: Record<string, ButtonError[]>;
  selectedId: string | null;
  readOnly: boolean;
  onSelect: (id: string) => void;
  onMove: (id: string, delta: number) => void;
  onDelete: (id: string) => void;
  onAddTop: () => void;
  onAddSub: (parentId: string) => void;
}) {
  const { t } = useTranslation();
  const rowProps = { readOnly, onSelect, onMove, onDelete };
  return (
    <div className="space-y-1" data-testid="wxoa-menu-structure">
      {menu.buttons.map((button, index) => {
        const subs = button.type === 'group' ? button.sub_buttons || [] : [];
        return (
          <div key={button.id} className="space-y-0.5">
            <StructureRow
              button={button}
              level="top"
              index={index}
              count={menu.buttons.length}
              selected={selectedId === button.id}
              hasError={Boolean(errors[button.id])}
              {...rowProps}
            />
            {subs.map((sub, subIndex) => (
              <StructureRow
                key={sub.id}
                button={sub}
                level="sub"
                index={subIndex}
                count={subs.length}
                selected={selectedId === sub.id}
                hasError={Boolean(errors[sub.id])}
                {...rowProps}
              />
            ))}
            {!readOnly && button.type === 'group' && (
              <button
                type="button"
                disabled={subs.length >= MAX_SUB_BUTTONS}
                onClick={() => onAddSub(button.id)}
                className="flex w-full items-center gap-2 rounded-md py-1.5 pl-7 text-xs text-muted-foreground hover:bg-accent hover:text-foreground disabled:pointer-events-none disabled:opacity-50"
              >
                <Plus className="size-3.5" />
                {subs.length >= MAX_SUB_BUTTONS
                  ? t('wxoaMenu.structure.subFull', { max: MAX_SUB_BUTTONS })
                  : t('wxoaMenu.actions.addSub')}
              </button>
            )}
          </div>
        );
      })}
      {!menu.buttons.length && (
        <p className="py-4 text-center text-sm text-muted-foreground">
          {t('wxoaMenu.empty.title')}
        </p>
      )}
      {!readOnly && (
        <Button
          variant="outline"
          size="sm"
          className="mt-2 w-full"
          disabled={menu.buttons.length >= MAX_TOP_BUTTONS}
          onClick={onAddTop}
        >
          <Plus className="size-4" />
          {menu.buttons.length >= MAX_TOP_BUTTONS
            ? t('wxoaMenu.structure.topFull', { max: MAX_TOP_BUTTONS })
            : t('wxoaMenu.actions.addTopFull')}
        </Button>
      )}
    </div>
  );
}
