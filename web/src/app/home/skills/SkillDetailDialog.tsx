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
import SkillForm from '@/app/home/skills/components/skill-form/SkillForm';
import { ScrollArea } from '@/components/ui/scroll-area';

interface SkillDetailDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  skillId?: string;
  onFormCancel: () => void;
  onSkillDeleted: () => void;
  onNewSkillCreated: (skillId: string) => void;
  onSkillUpdated: (skillId: string) => void;
}

export default function SkillDetailDialog({
  open,
  onOpenChange,
  skillId: propSkillId,
  onFormCancel,
  onSkillDeleted,
  onNewSkillCreated,
  onSkillUpdated,
}: SkillDetailDialogProps) {
  const { t } = useTranslation();
  const [skillId, setSkillId] = useState<string | undefined>(propSkillId);
  const [activeMenu, setActiveMenu] = useState('metadata');
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [previewContent, setPreviewContent] = useState<string>('');
  const [loadingPreview, setLoadingPreview] = useState(false);

  useEffect(() => {
    setSkillId(propSkillId);
    setActiveMenu('metadata');
    setPreviewContent('');
  }, [propSkillId, open]);

  useEffect(() => {
    if (activeMenu === 'preview' && skillId) {
      loadPreview();
    }
  }, [activeMenu, skillId]);

  async function loadPreview() {
    if (!skillId) return;
    setLoadingPreview(true);
    try {
      const resp = await httpClient.previewSkill(skillId);
      setPreviewContent(resp.instructions);
    } catch (error) {
      console.error('Failed to load preview:', error);
      setPreviewContent('Failed to load preview');
    } finally {
      setLoadingPreview(false);
    }
  }

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
    ...(skillId
      ? [
          {
            key: 'preview',
            label: t('skills.preview'),
            icon: (
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="currentColor"
              >
                <path d="M12 3C17.3923 3 21.8784 6.87976 22.8189 12C21.8784 17.1202 17.3923 21 12 21C6.60771 21 2.12163 17.1202 1.18115 12C2.12163 6.87976 6.60771 3 12 3ZM12 19C16.2359 19 19.8603 16.052 20.7777 12C19.8603 7.94803 16.2359 5 12 5C7.76411 5 4.13973 7.94803 3.22228 12C4.13973 16.052 7.76411 19 12 19ZM12 16.5C9.51472 16.5 7.5 14.4853 7.5 12C7.5 9.51472 9.51472 7.5 12 7.5C14.4853 7.5 16.5 9.51472 16.5 12C16.5 14.4853 14.4853 16.5 12 16.5ZM12 14.5C13.3807 14.5 14.5 13.3807 14.5 12C14.5 10.6193 13.3807 9.5 12 9.5C10.6193 9.5 9.5 10.6193 9.5 12C9.5 13.3807 10.6193 14.5 12 14.5Z"></path>
              </svg>
            ),
          },
        ]
      : []),
  ];

  const confirmDelete = async () => {
    if (!skillId) return;
    try {
      await httpClient.deleteSkill(skillId);
      onSkillDeleted();
    } catch (error) {
      console.error('Failed to delete skill:', error);
    }
    setShowDeleteConfirm(false);
  };

  if (!skillId) {
    // New skill
    return (
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="overflow-hidden p-0 !max-w-[40vw] max-h-[80vh] flex">
          <main className="flex flex-1 flex-col h-[80vh]">
            <DialogHeader className="px-6 pt-6 pb-4 shrink-0">
              <DialogTitle>{t('skills.createSkill')}</DialogTitle>
            </DialogHeader>
            <div className="flex-1 overflow-y-auto px-6 pb-6">
              <SkillForm
                initSkillId={undefined}
                onNewSkillCreated={onNewSkillCreated}
                onSkillUpdated={onSkillUpdated}
              />
            </div>
            <DialogFooter className="px-6 py-4 border-t shrink-0">
              <div className="flex justify-end gap-2">
                <Button type="submit" form="skill-form">
                  {t('common.save')}
                </Button>
                <Button type="button" variant="outline" onClick={onFormCancel}>
                  {t('common.cancel')}
                </Button>
              </div>
            </DialogFooter>
          </main>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="overflow-hidden p-0 !max-w-[50rem] max-h-[80vh] flex">
          <SidebarProvider className="items-start w-full flex">
            <Sidebar
              collapsible="none"
              className="hidden md:flex h-[80vh] w-40 min-w-[120px] border-r bg-white dark:bg-black"
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
            <main className="flex flex-1 flex-col h-[80vh]">
              <DialogHeader className="px-6 pt-6 pb-4 shrink-0">
                <DialogTitle>
                  {activeMenu === 'metadata'
                    ? t('skills.editSkill')
                    : t('skills.previewInstructions')}
                </DialogTitle>
              </DialogHeader>
              <div className="flex-1 overflow-y-auto px-6 pb-6">
                {activeMenu === 'metadata' && (
                  <SkillForm
                    initSkillId={skillId}
                    onNewSkillCreated={onNewSkillCreated}
                    onSkillUpdated={onSkillUpdated}
                  />
                )}
                {activeMenu === 'preview' && (
                  <ScrollArea className="h-full">
                    {loadingPreview ? (
                      <div className="text-center py-8 text-muted-foreground">
                        {t('common.loading')}
                      </div>
                    ) : (
                      <pre className="whitespace-pre-wrap font-mono text-sm bg-muted p-4 rounded-md">
                        {previewContent}
                      </pre>
                    )}
                  </ScrollArea>
                )}
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
                    <Button type="submit" form="skill-form">
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

      {/* Delete confirmation dialog */}
      <Dialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('common.confirmDelete')}</DialogTitle>
          </DialogHeader>
          <div className="py-4">{t('skills.deleteConfirmation')}</div>
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
