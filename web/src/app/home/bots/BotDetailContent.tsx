'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
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
import { httpClient } from '@/app/infra/http/HttpClient';
import { useSidebarData } from '@/app/home/components/home-sidebar/SidebarDataContext';
import { useTranslation } from 'react-i18next';
import { ArrowLeft, Settings, FileText, Users } from 'lucide-react';

export default function BotDetailContent({ id }: { id: string }) {
  const isCreateMode = id === 'new';
  const router = useRouter();
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

  function handleFormSubmit() {
    refreshBots();
  }

  function handleFormCancel() {
    router.push('/home/bots');
  }

  function handleBotDeleted() {
    refreshBots();
    router.push('/home/bots');
  }

  function handleNewBotCreated(newBotId: string) {
    refreshBots();
    // Navigate to the newly created bot's detail view via query param
    router.push(`/home/bots?id=${encodeURIComponent(newBotId)}`);
  }

  function handleDelete() {
    setShowDeleteConfirm(true);
  }

  function confirmDelete() {
    httpClient.deleteBot(id).then(() => {
      setShowDeleteConfirm(false);
      handleBotDeleted();
    });
  }

  // Create mode: simple form layout
  if (isCreateMode) {
    return (
      <div className="h-full overflow-y-auto">
        <div className="mx-auto max-w-2xl space-y-6">
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => router.push('/home/bots')}
            >
              <ArrowLeft className="size-4" />
            </Button>
            <h1 className="text-xl font-semibold">{t('bots.createBot')}</h1>
          </div>

          <BotForm
            initBotId={undefined}
            onFormSubmit={handleFormSubmit}
            onBotDeleted={handleBotDeleted}
            onNewBotCreated={handleNewBotCreated}
          />

          <div className="flex justify-end gap-2">
            <Button type="submit" form="bot-form">
              {t('common.submit')}
            </Button>
            <Button variant="outline" onClick={handleFormCancel}>
              {t('common.cancel')}
            </Button>
          </div>
        </div>
      </div>
    );
  }

  // Edit mode: tabbed layout with config, logs, sessions
  return (
    <>
      <div className="flex h-full flex-col">
        <div className="flex items-center gap-3 pb-4 shrink-0">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => router.push('/home/bots')}
          >
            <ArrowLeft className="size-4" />
          </Button>
          <h1 className="text-xl font-semibold">{t('bots.editBot')}</h1>
        </div>

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
            </TabsTrigger>
          </TabsList>

          <TabsContent value="config" className="flex-1 overflow-y-auto mt-4">
            <div className="mx-auto max-w-2xl">
              <BotForm
                initBotId={id}
                onFormSubmit={handleFormSubmit}
                onBotDeleted={handleBotDeleted}
                onNewBotCreated={handleNewBotCreated}
              />

              <div className="flex justify-end gap-2 mt-6 pb-4">
                <Button
                  type="button"
                  variant="destructive"
                  onClick={handleDelete}
                >
                  {t('common.delete')}
                </Button>
                <Button type="submit" form="bot-form">
                  {t('common.save')}
                </Button>
                <Button variant="outline" onClick={handleFormCancel}>
                  {t('common.cancel')}
                </Button>
              </div>
            </div>
          </TabsContent>

          <TabsContent value="logs" className="flex-1 overflow-y-auto mt-4">
            <BotLogListComponent botId={id} />
          </TabsContent>

          <TabsContent value="sessions" className="flex-1 min-h-0 mt-4">
            <BotSessionMonitor botId={id} />
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
