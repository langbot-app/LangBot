'use client';

import { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
} from '@/components/ui/sidebar';
import { Button } from '@/components/ui/button';
import BotForm from '@/app/home/bots/components/bot-form/BotForm';
import { BotLogListComponent } from '@/app/home/bots/components/bot-log/view/BotLogListComponent';
import { useTranslation } from 'react-i18next';
import { z } from 'zod';
import { httpClient } from '@/app/infra/http/HttpClient';

interface BotDetailDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  botId?: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  onFormSubmit: (value: z.infer<any>) => void;
  onFormCancel: () => void;
  onBotDeleted: () => void;
  onNewBotCreated: (botId: string) => void;
}

export default function BotDetailDialog({
  open,
  onOpenChange,
  botId: propBotId,
  onFormSubmit,
  onFormCancel,
  onBotDeleted,
  onNewBotCreated,
}: BotDetailDialogProps) {
  const { t } = useTranslation();
  const [botId, setBotId] = useState<string | undefined>(propBotId);
  const [activeMenu, setActiveMenu] = useState('config');
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  useEffect(() => {
    setBotId(propBotId);
    setActiveMenu('config');
  }, [propBotId, open]);

  const menu = [
    {
      key: 'config',
      label: t('bots.configuration'),
      icon: (
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="currentColor"
        >
          <path d="M5 7C5 6.17157 5.67157 5.5 6.5 5.5C7.32843 5.5 8 6.17157 8 7C8 7.82843 7.32843 8.5 6.5 8.5C5.67157 8.5 5 7.82843 5 7ZM6.5 3.5C4.567 3.5 3 5.067 3 7C3 8.933 4.567 10.5 6.5 10.5C8.433 10.5 10 8.933 10 7C10 5.067 8.433 3.5 6.5 3.5ZM12 8H20V6H12V8ZM16 17C16 16.1716 16.6716 15.5 17.5 15.5C18.3284 15.5 19 16.1716 19 17C19 17.8284 18.3284 18.5 17.5 18.5C16.6716 18.5 16 17.8284 16 17ZM17.5 13.5C15.567 13.5 14 15.067 14 17C14 18.933 15.567 20.5 17.5 20.5C19.433 20.5 21 18.933 21 17C21 15.067 19.433 13.5 17.5 13.5ZM4 16V18H12V16H4Z"></path>
        </svg>
      ),
    },
    {
      key: 'logs',
      label: t('bots.logs'),
      icon: (
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="currentColor"
        >
          <path d="M21 8V20.9932C21 21.5501 20.5552 22 20.0066 22H3.9934C3.44495 22 3 21.556 3 21.0082V2.9918C3 2.45531 3.4487 2 4.00221 2H14.9968L21 8ZM19 9H14V4H5V20H19V9ZM8 7H11V9H8V7ZM8 11H16V13H8V11ZM8 15H16V17H8V15Z"></path>
        </svg>
      ),
    },
  ];

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const handleFormSubmit = (value: any) => {
    onFormSubmit(value);
  };

  const handleFormCancel = () => {
    onFormCancel();
  };

  const handleBotDeleted = () => {
    httpClient.deleteBot(botId ?? '').then(() => {
      onBotDeleted();
    });
  };

  const handleNewBotCreated = (newBotId: string) => {
    setBotId(newBotId);
    setActiveMenu('config');
    onNewBotCreated(newBotId);
  };

  const handleDelete = () => {
    setShowDeleteConfirm(true);
  };

  const confirmDelete = () => {
    handleBotDeleted();
    setShowDeleteConfirm(false);
  };

  if (!botId) {
    return (
      <>
        <Dialog open={open} onOpenChange={onOpenChange}>
          <DialogContent className="overflow-hidden p-0 !max-w-[40vw] max-h-[70vh] flex">
            <main className="flex flex-1 flex-col h-[70vh]">
              <DialogHeader className="px-6 pt-6 pb-4 shrink-0">
                <DialogTitle>{t('bots.createBot')}</DialogTitle>
              </DialogHeader>
              <div className="flex-1 overflow-y-auto px-6 pb-6">
                <BotForm
                  initBotId={undefined}
                  onFormSubmit={handleFormSubmit}
                  onBotDeleted={handleBotDeleted}
                  onNewBotCreated={handleNewBotCreated}
                />
              </div>
              <DialogFooter className="px-6 py-4 border-t shrink-0">
                <div className="flex justify-end gap-2">
                  <Button type="submit" form="bot-form">
                    {t('common.submit')}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={handleFormCancel}
                  >
                    {t('common.cancel')}
                  </Button>
                </div>
              </DialogFooter>
            </main>
          </DialogContent>
        </Dialog>
      </>
    );
  }

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="overflow-hidden p-0 !max-w-[50rem] max-h-[75vh] flex">
          <SidebarProvider className="items-start w-full flex">
            <Sidebar
              collapsible="none"
              className="hidden md:flex h-[80vh] w-40 min-w-[120px] border-r bg-white"
            >
              <SidebarContent>
                <SidebarGroup>
                  <SidebarGroupContent>
                    <SidebarMenu>
                      {menu.map((item) => (
                        <SidebarMenuItem key={item.key}>
                          <SidebarMenuButton
                            asChild
                            isActive={activeMenu === item.key}
                            onClick={() => setActiveMenu(item.key)}
                          >
                            <a href="#">
                              {item.icon}
                              <span>{item.label}</span>
                            </a>
                          </SidebarMenuButton>
                        </SidebarMenuItem>
                      ))}
                    </SidebarMenu>
                  </SidebarGroupContent>
                </SidebarGroup>
              </SidebarContent>
            </Sidebar>
            <main className="flex flex-1 flex-col h-[75vh]">
              <DialogHeader className="px-6 pt-6 pb-4 shrink-0">
                <DialogTitle>
                  {activeMenu === 'config'
                    ? t('bots.editBot')
                    : t('bots.botLogTitle')}
                </DialogTitle>
              </DialogHeader>
              <div className="flex-1 overflow-y-auto px-6 pb-6">
                {activeMenu === 'config' && (
                  <BotForm
                    initBotId={botId}
                    onFormSubmit={handleFormSubmit}
                    onBotDeleted={handleBotDeleted}
                    onNewBotCreated={handleNewBotCreated}
                  />
                )}
                {activeMenu === 'logs' && botId && (
                  <BotLogListComponent botId={botId} />
                )}
              </div>
              {activeMenu === 'config' && (
                <DialogFooter className="px-6 py-4 border-t shrink-0">
                  <div className="flex justify-end gap-2">
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
                    <Button
                      type="button"
                      variant="outline"
                      onClick={handleFormCancel}
                    >
                      {t('common.cancel')}
                    </Button>
                  </div>
                </DialogFooter>
              )}
            </main>
          </SidebarProvider>
        </DialogContent>
      </Dialog>

      {/* 删除确认对话框 */}
      <Dialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('common.confirmDelete')}</DialogTitle>
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
