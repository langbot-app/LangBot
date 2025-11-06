import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
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
import PipelineFormComponent from './components/pipeline-form/PipelineFormComponent';
import DebugDialog from './components/debug-dialog/DebugDialog';
import PipelineExtension from './components/pipeline-extensions/PipelineExtension';

interface PipelineDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  pipelineId?: string;
  isEditMode?: boolean;
  isDefaultPipeline?: boolean;
  onFinish: () => void;
  onNewPipelineCreated?: (pipelineId: string) => void;
  onDeletePipeline: () => void;
  onCancel: () => void;
}

type DialogMode = 'config' | 'debug' | 'extensions';

export default function PipelineDialog({
  open,
  onOpenChange,
  pipelineId: propPipelineId,
  isEditMode = false,
  isDefaultPipeline = false,
  onFinish,
  onNewPipelineCreated,
  onDeletePipeline,
  onCancel,
}: PipelineDialogProps) {
  const { t } = useTranslation();
  const [pipelineId, setPipelineId] = useState<string | undefined>(
    propPipelineId,
  );
  const [currentMode, setCurrentMode] = useState<DialogMode>('config');

  useEffect(() => {
    setPipelineId(propPipelineId);
    setCurrentMode('config');
  }, [propPipelineId, open]);

  const handleFinish = () => {
    onFinish();
  };

  const handleNewPipelineCreated = (newPipelineId: string) => {
    setPipelineId(newPipelineId);
    setCurrentMode('config');
    if (onNewPipelineCreated) {
      onNewPipelineCreated(newPipelineId);
    }
  };

  const menu = [
    {
      key: 'config',
      label: t('pipelines.configuration'),
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
      key: 'extensions',
      label: t('pipelines.extensions.title'),
      icon: (
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="currentColor"
        >
          <path d="M7 5C7 2.79086 8.79086 1 11 1C13.2091 1 15 2.79086 15 5H18C18.5523 5 19 5.44772 19 6V9C21.2091 9 23 10.7909 23 13C23 15.2091 21.2091 17 19 17V20C19 20.5523 18.5523 21 18 21H4C3.44772 21 3 20.5523 3 20V6C3 5.44772 3.44772 5 4 5H7ZM11 3C9.89543 3 9 3.89543 9 5C9 5.23554 9.0403 5.45952 9.11355 5.66675C9.22172 5.97282 9.17461 6.31235 8.98718 6.57739C8.79974 6.84243 8.49532 7 8.17071 7H5V19H17V15.8293C17 15.5047 17.1576 15.2003 17.4226 15.0128C17.6877 14.8254 18.0272 14.7783 18.3332 14.8865C18.5405 14.9597 18.7645 15 19 15C20.1046 15 21 14.1046 21 13C21 11.8954 20.1046 11 19 11C18.7645 11 18.5405 11.0403 18.3332 11.1135C18.0272 11.2217 17.6877 11.1746 17.4226 10.9872C17.1576 10.7997 17 10.4953 17 10.1707V7H13.8293C13.5047 7 13.2003 6.84243 13.0128 6.57739C12.8254 6.31235 12.7783 5.97282 12.8865 5.66675C12.9597 5.45952 13 5.23555 13 5C13 3.89543 12.1046 3 11 3Z"></path>
        </svg>
      ),
    },
    {
      key: 'debug',
      label: t('pipelines.debugChat'),
      icon: (
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="currentColor"
        >
          <path d="M13 19.9C15.2822 19.4367 17 17.419 17 15V12C17 11.299 16.8564 10.6219 16.5846 10H7.41538C7.14358 10.6219 7 11.299 7 12V15C7 17.419 8.71776 19.4367 11 19.9V14H13V19.9ZM5.5358 17.6907C5.19061 16.8623 5 15.9534 5 15H2V13H5V12C5 11.3573 5.08661 10.7348 5.2488 10.1436L3.0359 8.86602L4.0359 7.13397L6.05636 8.30049C6.11995 8.19854 6.18609 8.09835 6.25469 8H17.7453C17.8139 8.09835 17.88 8.19854 17.9436 8.30049L19.9641 7.13397L20.9641 8.86602L18.7512 10.1436C18.9134 10.7348 19 11.3573 19 12V13H22V15H19C19 15.9534 18.8094 16.8623 18.4642 17.6907L20.9641 19.134L19.9641 20.866L17.4383 19.4077C16.1549 20.9893 14.1955 22 12 22C9.80453 22 7.84512 20.9893 6.56171 19.4077L4.0359 20.866L3.0359 19.134L5.5358 17.6907ZM8 6C8 3.79086 9.79086 2 12 2C14.2091 2 16 3.79086 16 6H8Z"></path>
        </svg>
      ),
    },
  ];

  const getDialogTitle = () => {
    if (currentMode === 'config') {
      return isEditMode
        ? t('pipelines.editPipeline')
        : t('pipelines.createPipeline');
    }
    if (currentMode === 'extensions') {
      return t('pipelines.extensions.title');
    }
    return t('pipelines.debugDialog.title');
  };

  // 创建新流水线时的对话框
  if (!isEditMode) {
    return (
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="overflow-hidden p-0 !max-w-[40vw] max-h-[70vh] flex">
          <main className="flex flex-1 flex-col h-[70vh]">
            <DialogHeader className="px-6 pt-6 pb-4 shrink-0">
              <DialogTitle>{t('pipelines.createPipeline')}</DialogTitle>
            </DialogHeader>
            <div className="flex-1 overflow-y-auto px-6 pb-6">
              <PipelineFormComponent
                isDefaultPipeline={isDefaultPipeline}
                onFinish={handleFinish}
                onNewPipelineCreated={handleNewPipelineCreated}
                isEditMode={isEditMode}
                pipelineId={pipelineId}
                disableForm={false}
                showButtons={true}
                onDeletePipeline={onDeletePipeline}
                onCancel={() => {
                  onCancel();
                }}
              />
            </div>
          </main>
        </DialogContent>
      </Dialog>
    );
  }

  // 编辑流水线时的对话框
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="overflow-hidden p-0 !max-w-[50rem] h-[75vh] flex">
        <SidebarProvider className="items-start w-full flex h-full min-h-0">
          <Sidebar
            collapsible="none"
            className="hidden md:flex h-full min-h-0 w-40 border-r bg-white dark:bg-black"
          >
            <SidebarContent>
              <SidebarGroup>
                <SidebarGroupContent>
                  <SidebarMenu>
                    {menu.map((item) => (
                      <SidebarMenuItem key={item.key}>
                        <SidebarMenuButton
                          asChild
                          isActive={currentMode === item.key}
                          onClick={() => setCurrentMode(item.key as DialogMode)}
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
          <main className="flex flex-1 flex-col h-full min-h-0">
            <DialogHeader
              className="px-6 pt-6 pb-4 shrink-0"
              style={{ height: '4rem' }}
            >
              <DialogTitle>{getDialogTitle()}</DialogTitle>
            </DialogHeader>
            <div
              className="flex-1 auto px-6 pb-4 w-full"
              style={{ height: 'calc(100% - 4rem)' }}
            >
              {currentMode === 'config' && (
                <PipelineFormComponent
                  isDefaultPipeline={isDefaultPipeline}
                  onFinish={handleFinish}
                  onNewPipelineCreated={handleNewPipelineCreated}
                  isEditMode={isEditMode}
                  pipelineId={pipelineId}
                  disableForm={false}
                  showButtons={true}
                  onDeletePipeline={onDeletePipeline}
                  onCancel={() => {
                    onCancel();
                  }}
                />
              )}

              {currentMode === 'extensions' && pipelineId && (
                <PipelineExtension pipelineId={pipelineId} />
              )}

              {currentMode === 'debug' && pipelineId && (
                <DebugDialog
                  open={true}
                  pipelineId={pipelineId}
                  isEmbedded={true}
                />
              )}
            </div>
          </main>
        </SidebarProvider>
      </DialogContent>
    </Dialog>
  );
}
