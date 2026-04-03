

import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import BotForm from '@/app/home/bots/components/bot-form/BotForm';
import { BotLogListComponent } from '@/app/home/bots/components/bot-log/view/BotLogListComponent';
import BotSessionMonitor from '@/app/home/bots/components/bot-session/BotSessionMonitor';
import type { BotSessionMonitorHandle } from '@/app/home/bots/components/bot-session/BotSessionMonitor';
import { httpClient } from '@/app/infra/http/HttpClient';
import { useSidebarData } from '@/app/home/components/home-sidebar/SidebarDataContext';
import { useTranslation } from 'react-i18next';
import { Settings, FileText, Users, RefreshCw, Trash2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';

export default function BotDetailContent({ id }: { id: string }) {
  const isCreateMode = id === 'new';
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { refreshBots, bots, setDetailEntityName } = useSidebarData();

  // Set breadcrumb entity name
  useEffect(() => {
    if (isCreateMode) {
      setDetailEntityName(t('bots.createBot'));
    } else {
      const bot = bots.find((b) => b.id === id);
      setDetailEntityName(bot?.name ?? id);
    }
    return () => setDetailEntityName(null);
  }, [id, isCreateMode, bots, setDetailEntityName, t]);

  const [activeTab, setActiveTab] = useState('config');
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isRefreshingSessions, setIsRefreshingSessions] = useState(false);
  const sessionMonitorRef = useRef<BotSessionMonitorHandle>(null);

  // Track whether the form has unsaved changes
  const [formDirty, setFormDirty] = useState(false);

  // Enable state managed here so the header switch works
  const [botEnabled, setBotEnabled] = useState(true);
  const [enableLoaded, setEnableLoaded] = useState(false);

  // Fetch bot enable state
  useEffect(() => {
    if (!isCreateMode) {
      httpClient.getBot(id).then((res) => {
        setBotEnabled(res.bot.enable ?? true);
        setEnableLoaded(true);
      });
    }
  }, [id, isCreateMode]);

  const handleEnableToggle = useCallback(
    async (checked: boolean) => {
      const prev = botEnabled;
      setBotEnabled(checked);
      try {
        // Fetch current bot data to send a complete update
        const res = await httpClient.getBot(id);
        const bot = res.bot;
        await httpClient.updateBot(id, {
          name: bot.name,
          description: bot.description,
          adapter: bot.adapter,
          adapter_config: bot.adapter_config,
          enable: checked,
        });
        refreshBots();
      } catch {
        setBotEnabled(prev);
        toast.error(t('bots.setBotEnableError'));
      }
    },
    [id, botEnabled, refreshBots, t],
  );

  function handleFormSubmit() {
    // Re-sync enable state after form save (form may update enable too)
    httpClient.getBot(id).then((res) => {
      setBotEnabled(res.bot.enable ?? true);
    });
    refreshBots();
  }

  function handleBotDeleted() {
    refreshBots();
    navigate('/home/bots');
  }

  function handleNewBotCreated(newBotId: string) {
    refreshBots();
    navigate(`/home/bots?id=${encodeURIComponent(newBotId)}`);
  }

  function confirmDelete() {
    httpClient
      .deleteBot(id)
      .then(() => {
        setShowDeleteConfirm(false);
        toast.success(t('bots.deleteSuccess'));
        handleBotDeleted();
      })
      .catch((err) => {
        toast.error(t('bots.deleteError') + err.msg);
      });
  }

  // ==================== Create Mode ====================
  if (isCreateMode) {
    return (
      <div className="flex h-full flex-col">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 shrink-0">
          <h1 className="text-xl font-semibold">{t('bots.createBot')}</h1>
          <Button type="submit" form="bot-form">
            {t('common.submit')}
          </Button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto min-h-0">
          <div className="mx-auto max-w-3xl pb-8">
            <BotForm
              initBotId={undefined}
              onFormSubmit={handleFormSubmit}
              onNewBotCreated={handleNewBotCreated}
            />
          </div>
        </div>
      </div>
    );
  }

  // ==================== Edit Mode ====================
  return (
    <>
      <div className="flex h-full flex-col">
        {/* Sticky Header: title + enable switch + save button */}
        <div className="flex items-center justify-between pb-4 shrink-0">
          <div className="flex items-center gap-4">
            <h1 className="text-xl font-semibold">{t('bots.editBot')}</h1>
            {enableLoaded && (
              <div className="flex items-center gap-2">
                <Switch
                  id="bot-enable-switch"
                  checked={botEnabled}
                  onCheckedChange={handleEnableToggle}
                />
                <Label
                  htmlFor="bot-enable-switch"
                  className="text-sm text-muted-foreground cursor-pointer"
                >
                  {t('common.enable')}
                </Label>
              </div>
            )}
          </div>
          <Button type="submit" form="bot-form" disabled={!formDirty}>
            {t('common.save')}
          </Button>
        </div>

        {/* Horizontal Tabs */}
        <Tabs
          key={id}
          value={activeTab}
          onValueChange={setActiveTab}
          className="flex flex-1 flex-col min-h-0"
        >
          <TabsList className="shrink-0">
            <TabsTrigger value="config" className="gap-1.5">
              <Settings className="size-3.5" />
              {t('bots.configuration')}
            </TabsTrigger>
            <TabsTrigger value="logs" className="gap-1.5">
              <FileText className="size-3.5" />
              {t('bots.logs')}
            </TabsTrigger>
            <TabsTrigger value="sessions" className="gap-1.5">
              <Users className="size-3.5" />
              {t('bots.sessionMonitor.title')}
              {activeTab === 'sessions' && (
                <button
                  type="button"
                  className="inline-flex items-center justify-center ml-0.5"
                  onPointerDown={(e) => e.stopPropagation()}
                  onClick={(e) => {
                    e.stopPropagation();
                    e.preventDefault();
                    if (isRefreshingSessions) return;
                    setIsRefreshingSessions(true);
                    const minDelay = new Promise((r) => setTimeout(r, 500));
                    Promise.all([
                      sessionMonitorRef.current?.refreshSessions(),
                      minDelay,
                    ]).finally(() => setIsRefreshingSessions(false));
                  }}
                >
                  <RefreshCw
                    className={cn(
                      'size-3 text-muted-foreground hover:text-foreground transition-colors',
                      isRefreshingSessions && 'animate-spin',
                    )}
                  />
                </button>
              )}
            </TabsTrigger>
          </TabsList>

          {/* Tab: Configuration */}
          <TabsContent
            value="config"
            className="flex-1 min-h-0 overflow-y-auto mt-4"
          >
            <div className="mx-auto max-w-3xl space-y-6 pb-8">
              <BotForm
                initBotId={id}
                onFormSubmit={handleFormSubmit}
                onNewBotCreated={handleNewBotCreated}
                onDirtyChange={setFormDirty}
              />

              {/* Card: Danger Zone */}
              <Card className="border-destructive/50">
                <CardHeader>
                  <CardTitle className="text-destructive">
                    {t('bots.dangerZone')}
                  </CardTitle>
                  <CardDescription>
                    {t('bots.dangerZoneDescription')}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center justify-between">
                    <div className="space-y-1">
                      <p className="text-sm font-medium">
                        {t('bots.deleteBotAction')}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        {t('bots.deleteBotHint')}
                      </p>
                    </div>
                    <Button
                      type="button"
                      variant="destructive"
                      size="sm"
                      onClick={() => setShowDeleteConfirm(true)}
                    >
                      <Trash2 className="size-4 mr-1.5" />
                      {t('common.delete')}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Tab: Logs */}
          <TabsContent
            value="logs"
            className="flex-1 min-h-0 overflow-y-auto mt-4"
          >
            <BotLogListComponent botId={id} />
          </TabsContent>

          {/* Tab: Sessions */}
          <TabsContent value="sessions" className="flex-1 min-h-0 mt-4">
            <BotSessionMonitor ref={sessionMonitorRef} botId={id} />
          </TabsContent>
        </Tabs>
      </div>

      {/* Delete confirmation dialog */}
      <Dialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('common.confirmDelete')}</DialogTitle>
            <DialogDescription className="sr-only">
              {t('bots.deleteConfirmation')}
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">{t('bots.deleteConfirmation')}</div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowDeleteConfirm(false)}
            >
              {t('common.cancel')}
            </Button>
            <Button variant="destructive" onClick={confirmDelete}>
              {t('common.confirmDelete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
