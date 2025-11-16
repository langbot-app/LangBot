'use client';

import CreateCardComponent from '@/app/infra/basic-component/create-card-component/CreateCardComponent';
import styles from './knowledgeBase.module.css';
import { useTranslation } from 'react-i18next';
import { useEffect, useState } from 'react';
import { KnowledgeBaseVO } from '@/app/home/knowledge/components/kb-card/KBCardVO';
import { ExternalKBCardVO } from '@/app/home/knowledge/components/external-kb-card/ExternalKBCardVO';
import KBCard from '@/app/home/knowledge/components/kb-card/KBCard';
import ExternalKBCard from '@/app/home/knowledge/components/external-kb-card/ExternalKBCard';
import KBDetailDialog from '@/app/home/knowledge/KBDetailDialog';
import { httpClient } from '@/app/infra/http/HttpClient';
import { KnowledgeBase, ExternalKnowledgeBase } from '@/app/infra/entities/api';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { toast } from 'sonner';

export default function KnowledgePage() {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState('builtin');
  const [knowledgeBaseList, setKnowledgeBaseList] = useState<KnowledgeBaseVO[]>(
    [],
  );
  const [externalKBList, setExternalKBList] = useState<ExternalKBCardVO[]>([]);
  const [selectedKbId, setSelectedKbId] = useState<string>('');
  const [detailDialogOpen, setDetailDialogOpen] = useState(false);
  const [externalKBDialogOpen, setExternalKBDialogOpen] = useState(false);
  const [editingExternalKB, setEditingExternalKB] =
    useState<ExternalKnowledgeBase | null>(null);
  const [externalKBForm, setExternalKBForm] = useState({
    name: '',
    description: '',
    api_url: '',
    api_key: '',
    top_k: 5,
  });

  useEffect(() => {
    getKnowledgeBaseList();
    getExternalKBList();
  }, []);

  async function getKnowledgeBaseList() {
    const resp = await httpClient.getKnowledgeBases();
    setKnowledgeBaseList(
      resp.bases.map((kb: KnowledgeBase) => {
        const currentTime = new Date();
        const lastUpdatedTimeAgo = Math.floor(
          (currentTime.getTime() -
            new Date(kb.updated_at ?? currentTime.getTime()).getTime()) /
            1000 /
            60 /
            60 /
            24,
        );

        const lastUpdatedTimeAgoText =
          lastUpdatedTimeAgo > 0
            ? ` ${lastUpdatedTimeAgo} ${t('knowledge.daysAgo')}`
            : t('knowledge.today');

        return new KnowledgeBaseVO({
          id: kb.uuid || '',
          name: kb.name,
          description: kb.description,
          embeddingModelUUID: kb.embedding_model_uuid,
          top_k: kb.top_k ?? 5,
          lastUpdatedTimeAgo: lastUpdatedTimeAgoText,
        });
      }),
    );
  }

  async function getExternalKBList() {
    try {
      const resp = await httpClient.getExternalKnowledgeBases();
      setExternalKBList(
        resp.bases.map((kb: ExternalKnowledgeBase) => {
          const currentTime = new Date();
          const lastUpdatedTimeAgo = Math.floor(
            (currentTime.getTime() -
              new Date(kb.created_at ?? currentTime.getTime()).getTime()) /
              1000 /
              60 /
              60 /
              24,
          );

          const lastUpdatedTimeAgoText =
            lastUpdatedTimeAgo > 0
              ? ` ${lastUpdatedTimeAgo} ${t('knowledge.daysAgo')}`
              : t('knowledge.today');

          return new ExternalKBCardVO({
            id: kb.uuid || '',
            name: kb.name,
            description: kb.description,
            apiUrl: kb.api_url,
            top_k: kb.top_k ?? 5,
            lastUpdatedTimeAgo: lastUpdatedTimeAgoText,
          });
        }),
      );
    } catch (error) {
      console.error('Failed to load external knowledge bases:', error);
    }
  }

  const handleKBCardClick = (kbId: string) => {
    setSelectedKbId(kbId);
    setDetailDialogOpen(true);
  };

  const handleCreateKBClick = () => {
    setSelectedKbId('');
    setDetailDialogOpen(true);
  };

  const handleFormCancel = () => {
    setDetailDialogOpen(false);
  };

  const handleKbDeleted = () => {
    getKnowledgeBaseList();
    setDetailDialogOpen(false);
  };

  const handleNewKbCreated = (newKbId: string) => {
    getKnowledgeBaseList();
    setSelectedKbId(newKbId);
    setDetailDialogOpen(true);
  };

  const handleKbUpdated = () => {
    getKnowledgeBaseList();
  };

  const handleExternalKBCardClick = (kbId: string) => {
    const kb = externalKBList.find((kb) => kb.id === kbId);
    if (kb) {
      // Load full data
      httpClient.getExternalKnowledgeBase(kbId).then((resp) => {
        setEditingExternalKB(resp.base);
        setExternalKBForm({
          name: resp.base.name,
          description: resp.base.description,
          api_url: resp.base.api_url,
          api_key: resp.base.api_key || '',
          top_k: resp.base.top_k,
        });
        setExternalKBDialogOpen(true);
      });
    }
  };

  const handleCreateExternalKB = () => {
    setEditingExternalKB(null);
    setExternalKBForm({
      name: '',
      description: '',
      api_url: '',
      api_key: '',
      top_k: 5,
    });
    setExternalKBDialogOpen(true);
  };

  const handleSaveExternalKB = async () => {
    if (!externalKBForm.name || !externalKBForm.api_url) {
      toast.error(t('knowledge.externalApiUrlRequired'));
      return;
    }

    try {
      if (editingExternalKB) {
        await httpClient.updateExternalKnowledgeBase(
          editingExternalKB.uuid!,
          externalKBForm as ExternalKnowledgeBase,
        );
        toast.success(t('knowledge.updateExternalSuccess'));
      } else {
        await httpClient.createExternalKnowledgeBase(
          externalKBForm as ExternalKnowledgeBase,
        );
        toast.success(t('knowledge.createExternalSuccess'));
      }
      setExternalKBDialogOpen(false);
      getExternalKBList();
    } catch (error) {
      toast.error('Failed to save external knowledge base');
      console.error(error);
    }
  };

  const handleDeleteExternalKB = async () => {
    if (!editingExternalKB) return;

    try {
      await httpClient.deleteExternalKnowledgeBase(editingExternalKB.uuid!);
      toast.success(t('knowledge.deleteExternalSuccess'));
      setExternalKBDialogOpen(false);
      getExternalKBList();
    } catch (error) {
      toast.error('Failed to delete external knowledge base');
      console.error(error);
    }
  };

  return (
    <div>
      <KBDetailDialog
        open={detailDialogOpen}
        onOpenChange={setDetailDialogOpen}
        kbId={selectedKbId || undefined}
        onFormCancel={handleFormCancel}
        onKbDeleted={handleKbDeleted}
        onNewKbCreated={handleNewKbCreated}
        onKbUpdated={handleKbUpdated}
      />

      <Dialog open={externalKBDialogOpen} onOpenChange={setExternalKBDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>
              {editingExternalKB
                ? t('knowledge.editKnowledgeBase')
                : t('knowledge.addExternal')}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium">
                {t('knowledge.kbName')}
              </label>
              <Input
                value={externalKBForm.name}
                onChange={(e) =>
                  setExternalKBForm({ ...externalKBForm, name: e.target.value })
                }
                placeholder={t('knowledge.kbName')}
              />
            </div>
            <div>
              <label className="text-sm font-medium">
                {t('knowledge.kbDescription')}
              </label>
              <Textarea
                value={externalKBForm.description}
                onChange={(e) =>
                  setExternalKBForm({
                    ...externalKBForm,
                    description: e.target.value,
                  })
                }
                placeholder={t('knowledge.kbDescription')}
              />
            </div>
            <div>
              <label className="text-sm font-medium">
                {t('knowledge.externalApiUrl')}
              </label>
              <Input
                value={externalKBForm.api_url}
                onChange={(e) =>
                  setExternalKBForm({
                    ...externalKBForm,
                    api_url: e.target.value,
                  })
                }
                placeholder={t('knowledge.externalApiUrlPlaceholder')}
              />
            </div>
            <div>
              <label className="text-sm font-medium">
                {t('knowledge.externalApiKey')}
              </label>
              <Input
                value={externalKBForm.api_key}
                onChange={(e) =>
                  setExternalKBForm({
                    ...externalKBForm,
                    api_key: e.target.value,
                  })
                }
                placeholder={t('knowledge.externalApiKeyPlaceholder')}
                type="password"
              />
            </div>
            <div>
              <label className="text-sm font-medium">
                {t('knowledge.topK')}
              </label>
              <Input
                type="number"
                min={1}
                max={30}
                value={externalKBForm.top_k}
                onChange={(e) =>
                  setExternalKBForm({
                    ...externalKBForm,
                    top_k: parseInt(e.target.value) || 5,
                  })
                }
              />
            </div>
          </div>
          <DialogFooter>
            {editingExternalKB && (
              <Button variant="destructive" onClick={handleDeleteExternalKB}>
                {t('common.delete')}
              </Button>
            )}
            <Button variant="outline" onClick={() => setExternalKBDialogOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button onClick={handleSaveExternalKB}>{t('common.save')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="mb-4">
          <TabsTrigger value="builtin">{t('knowledge.builtIn')}</TabsTrigger>
          <TabsTrigger value="external">{t('knowledge.external')}</TabsTrigger>
        </TabsList>

        <TabsContent value="builtin">
          <div className={styles.knowledgeListContainer}>
            <CreateCardComponent
              width={'100%'}
              height={'10rem'}
              plusSize={'90px'}
              onClick={handleCreateKBClick}
            />

            {knowledgeBaseList.map((kb) => {
              return (
                <div key={kb.id} onClick={() => handleKBCardClick(kb.id)}>
                  <KBCard kbCardVO={kb} />
                </div>
              );
            })}
          </div>
        </TabsContent>

        <TabsContent value="external">
          <div className={styles.knowledgeListContainer}>
            <CreateCardComponent
              width={'100%'}
              height={'10rem'}
              plusSize={'90px'}
              onClick={handleCreateExternalKB}
            />

            {externalKBList.map((kb) => {
              return (
                <div
                  key={kb.id}
                  onClick={() => handleExternalKBCardClick(kb.id)}
                >
                  <ExternalKBCard kbCardVO={kb} />
                </div>
              );
            })}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
