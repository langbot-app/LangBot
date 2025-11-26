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
import ExternalKBDetailDialog from '@/app/home/knowledge/components/external-kb-form/ExternalKBDetailDialog';
import { httpClient } from '@/app/infra/http/HttpClient';
import { KnowledgeBase, ExternalKnowledgeBase } from '@/app/infra/entities/api';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

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
  const [selectedExternalKbId, setSelectedExternalKbId] = useState<string>('');

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
            retrieverName: `${kb.plugin_author}/${kb.plugin_name}/${kb.retriever_name}`,
            retrieverConfig: kb.retriever_config || {},
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
    setSelectedExternalKbId(kbId);
    setExternalKBDialogOpen(true);
  };

  const handleCreateExternalKB = () => {
    setSelectedExternalKbId('');
    setExternalKBDialogOpen(true);
  };

  const handleExternalKBDeleted = () => {
    getExternalKBList();
    setExternalKBDialogOpen(false);
  };

  const handleNewExternalKBCreated = (newKbId: string) => {
    getExternalKBList();
    setSelectedExternalKbId(newKbId);
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

      <ExternalKBDetailDialog
        open={externalKBDialogOpen}
        onOpenChange={setExternalKBDialogOpen}
        kbId={selectedExternalKbId || undefined}
        onKBDeleted={handleExternalKBDeleted}
        onNewKBCreated={handleNewExternalKBCreated}
      />

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <div className="flex flex-row justify-between items-center px-[0.8rem]">
          <TabsList className="shadow-md py-5 bg-[#f0f0f0] dark:bg-[#2a2a2e]">
            <TabsTrigger value="builtin" className="px-6 py-4 cursor-pointer">
              {t('knowledge.builtIn')}
            </TabsTrigger>
            <TabsTrigger value="external" className="px-6 py-4 cursor-pointer">
              {t('knowledge.external')}
            </TabsTrigger>
          </TabsList>
        </div>

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
