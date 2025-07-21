'use client';

import { useEffect, useState } from 'react';
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
import { useTranslation } from 'react-i18next';
import { httpClient } from '@/app/infra/http/HttpClient';
// import { KnowledgeBase } from '@/app/infra/entities/api';
import KBForm from '@/app/home/knowledge/components/kb-form/KBForm';
import KBDoc from '@/app/home/knowledge/components/kb-docs/KBDoc';
import KBRetrieve from '@/app/home/knowledge/components/kb-retrieve/KBRetrieve';

interface KBDetailDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  kbId?: string;
  onFormCancel: () => void;
  onKbDeleted: () => void;
  onNewKbCreated: (kbId: string) => void;
  onKbUpdated: (kbId: string) => void;
}

export default function KBDetailDialog({
  open,
  onOpenChange,
  kbId: propKbId,
  onFormCancel,
  onKbDeleted,
  onNewKbCreated,
  onKbUpdated,
}: KBDetailDialogProps) {
  const { t } = useTranslation();
  const [kbId, setKbId] = useState<string | undefined>(propKbId);
  const [activeMenu, setActiveMenu] = useState('metadata');
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  useEffect(() => {
    setKbId(propKbId);
    setActiveMenu('metadata');
  }, [propKbId, open]);

  const menu = [
    {
      key: 'metadata',
      label: t('knowledge.metadata'),
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
      key: 'documents',
      label: t('knowledge.documents'),
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
    {
      key: 'retrieve',
      label: t('knowledge.retrieve'),
      icon: (
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="currentColor"
        >
          <path d="M18.031 16.617l4.283 4.282-1.415 1.415-4.282-4.283A8.96 8.96 0 0 1 11 20c-4.968 0-9-4.032-9-9s4.032-9 9-9 9 4.032 9 9a8.96 8.96 0 0 1-1.969 5.617zm-2.006-.742A6.977 6.977 0 0 0 18 11c0-3.868-3.133-7-7-7-3.868 0-7 3.132-7 7 0 3.867 3.132 7 7 7a6.977 6.977 0 0 0 4.875-1.975l.15-.15z"></path>
        </svg>
      ),
    },
  ];

  const confirmDelete = () => {
    httpClient.deleteKnowledgeBase(kbId ?? '').then(() => {
      onKbDeleted();
    });
    setShowDeleteConfirm(false);
  };

  if (!kbId) {
    // new kb
    return (
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="overflow-hidden p-0 !max-w-[40vw] max-h-[70vh] flex">
          <main className="flex flex-1 flex-col h-[70vh]">
            <DialogHeader className="px-6 pt-6 pb-4 shrink-0">
              <DialogTitle>{t('knowledge.createKnowledgeBase')}</DialogTitle>
            </DialogHeader>
            <div className="flex-1 overflow-y-auto px-6 pb-6">
              {activeMenu === 'metadata' && (
                <KBForm
                  initKbId={undefined}
                  onNewKbCreated={onNewKbCreated}
                  onKbUpdated={onKbUpdated}
                />
              )}
              {activeMenu === 'documents' && <div>documents</div>}
            </div>
            {activeMenu === 'metadata' && (
              <DialogFooter className="px-6 py-4 border-t shrink-0">
                <div className="flex justify-end gap-2">
                  <Button type="submit" form="kb-form">
                    {t('common.save')}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={onFormCancel}
                  >
                    {t('common.cancel')}
                  </Button>
                </div>
              </DialogFooter>
            )}
          </main>
        </DialogContent>
      </Dialog>
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
                  {activeMenu === 'metadata'
                    ? t('knowledge.editKnowledgeBase')
                    : activeMenu === 'documents'
                      ? t('knowledge.editDocument')
                      : t('knowledge.retrieveTest')}
                </DialogTitle>
              </DialogHeader>
              <div className="flex-1 overflow-y-auto px-6 pb-6">
                {activeMenu === 'metadata' && (
                  <KBForm
                    initKbId={kbId}
                    onNewKbCreated={onNewKbCreated}
                    onKbUpdated={onKbUpdated}
                  />
                )}
                {activeMenu === 'documents' && <KBDoc kbId={kbId} />}
                {activeMenu === 'retrieve' && <KBRetrieve kbId={kbId} />}
              </div>
              {activeMenu === 'metadata' && (
                <DialogFooter className="px-6 py-4 border-t shrink-0">
                  <div className="flex justify-end gap-2">
                    <Button
                      type="button"
                      variant="destructive"
                      onClick={() => setShowDeleteConfirm(true)}
                    >
                      {t('common.delete')}
                    </Button>
                    <Button type="submit" form="kb-form">
                      {t('common.save')}
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={onFormCancel}
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
          <div className="py-4">
            {t('knowledge.deleteKnowledgeBaseConfirmation')}
          </div>
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
