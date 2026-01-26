'use client';

import CreateCardComponent from '@/app/infra/basic-component/create-card-component/CreateCardComponent';
import styles from './knowledgeBase.module.css';
import { useTranslation } from 'react-i18next';
import { useEffect, useState } from 'react';
import { KnowledgeBaseVO } from '@/app/home/knowledge/components/kb-card/KBCardVO';
import KBCard from '@/app/home/knowledge/components/kb-card/KBCard';
import KBDetailDialog from '@/app/home/knowledge/KBDetailDialog';
import { httpClient } from '@/app/infra/http/HttpClient';
import { KnowledgeBase, ExternalKnowledgeBase } from '@/app/infra/entities/api';

export default function KnowledgePage() {
  const { t } = useTranslation();
  const [knowledgeBaseList, setKnowledgeBaseList] = useState<KnowledgeBaseVO[]>(
    [],
  );
  const [selectedKbId, setSelectedKbId] = useState<string>('');
  const [selectedKbType, setSelectedKbType] = useState<'retriever' | 'rag_engine' | undefined>(undefined);
  const [detailDialogOpen, setDetailDialogOpen] = useState(false);

  useEffect(() => {
    getKnowledgeBaseList();
  }, []);

  async function getKnowledgeBaseList() {
    // Load both types of knowledge bases
    const [ragEngineResp, retrieverResp] = await Promise.all([
      httpClient.getKnowledgeBases(),
      httpClient.getExternalKnowledgeBases(),
    ]);

    const currentTime = new Date();

    // Convert rag_engine type KBs
    const ragEngineKBs = ragEngineResp.bases.map((kb: KnowledgeBase) => {
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
        ragEngine: kb.rag_engine,
        ragEnginePluginId: kb.rag_engine_plugin_id,
        type: 'rag_engine',
      });
    });

    // Convert retriever type (external) KBs
    const retrieverKBs = retrieverResp.bases.map((kb: ExternalKnowledgeBase) => {
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

      return new KnowledgeBaseVO({
        id: kb.uuid || '',
        name: kb.name,
        description: kb.description,
        embeddingModelUUID: '',
        top_k: 5,
        lastUpdatedTimeAgo: lastUpdatedTimeAgoText,
        ragEngine: {
          plugin_id: `${kb.plugin_author}/${kb.plugin_name}`,
          name: kb.retriever_name,
          capabilities: [],
        },
        ragEnginePluginId: `${kb.plugin_author}/${kb.plugin_name}`,
        type: 'retriever',
      });
    });

    // Combine both lists
    setKnowledgeBaseList([...ragEngineKBs, ...retrieverKBs]);
  }

  const handleKBCardClick = (kb: KnowledgeBaseVO) => {
    setSelectedKbId(kb.id);
    setSelectedKbType(kb.type);
    setDetailDialogOpen(true);
  };

  const handleCreateKBClick = () => {
    setSelectedKbId('');
    setSelectedKbType(undefined);
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

  return (
    <div>
      <KBDetailDialog
        open={detailDialogOpen}
        onOpenChange={setDetailDialogOpen}
        kbId={selectedKbId || undefined}
        kbType={selectedKbType}
        onFormCancel={handleFormCancel}
        onKbDeleted={handleKbDeleted}
        onNewKbCreated={handleNewKbCreated}
        onKbUpdated={handleKbUpdated}
      />

      <div className={styles.knowledgeListContainer}>
        <CreateCardComponent
          width={'100%'}
          height={'10rem'}
          plusSize={'90px'}
          onClick={handleCreateKBClick}
        />

        {knowledgeBaseList.map((kb) => {
          return (
            <div key={kb.id} onClick={() => handleKBCardClick(kb)}>
              <KBCard kbCardVO={kb} />
            </div>
          );
        })}
      </div>
    </div>
  );
}
