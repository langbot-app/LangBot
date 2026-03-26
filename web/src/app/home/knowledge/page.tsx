'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import CreateCardComponent from '@/app/infra/basic-component/create-card-component/CreateCardComponent';
import styles from './knowledgeBase.module.css';
import { useTranslation } from 'react-i18next';
import { useEffect, useState } from 'react';
import { KnowledgeBaseVO } from '@/app/home/knowledge/components/kb-card/KBCardVO';
import KBCard from '@/app/home/knowledge/components/kb-card/KBCard';
import KBMigrationDialog from '@/app/home/knowledge/components/kb-migration-dialog/KBMigrationDialog';
import { httpClient } from '@/app/infra/http/HttpClient';
import { KnowledgeBase } from '@/app/infra/entities/api';
import KBDetailContent from './KBDetailContent';

export default function KnowledgePage() {
  const { t } = useTranslation();
  const router = useRouter();
  const searchParams = useSearchParams();
  const detailId = searchParams.get('id');
  const [knowledgeBaseList, setKnowledgeBaseList] = useState<KnowledgeBaseVO[]>(
    [],
  );

  // Migration dialog state
  const [migrationDialogOpen, setMigrationDialogOpen] = useState(false);
  const [migrationInternalCount, setMigrationInternalCount] = useState(0);
  const [migrationExternalCount, setMigrationExternalCount] = useState(0);

  useEffect(() => {
    if (detailId) return;
    getKnowledgeBaseList();
    checkMigrationStatus();
  }, [detailId]);

  async function checkMigrationStatus() {
    try {
      const resp = await httpClient.getRagMigrationStatus();
      if (resp.needed) {
        setMigrationInternalCount(resp.internal_kb_count);
        setMigrationExternalCount(resp.external_kb_count);
        setMigrationDialogOpen(true);
      }
    } catch {
      // Silently ignore - migration check is non-critical
    }
  }

  async function getKnowledgeBaseList() {
    const resp = await httpClient.getKnowledgeBases();

    const currentTime = new Date();

    const kbs = resp.bases.map((kb: KnowledgeBase) => {
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
        emoji: kb.emoji,
        lastUpdatedTimeAgo: lastUpdatedTimeAgoText,
        ragEngine: kb.knowledge_engine,
        ragEnginePluginId: kb.knowledge_engine_plugin_id,
      });
    });

    setKnowledgeBaseList(kbs);
  }

  const handleKBCardClick = (kbId: string) => {
    router.push(`/home/knowledge?id=${encodeURIComponent(kbId)}`);
  };

  const handleCreateKBClick = () => {
    router.push('/home/knowledge?id=new');
  };

  const handleMigrationComplete = () => {
    getKnowledgeBaseList();
  };

  return (
    <div>
      <KBMigrationDialog
        open={migrationDialogOpen}
        onOpenChange={setMigrationDialogOpen}
        internalKbCount={migrationInternalCount}
        externalKbCount={migrationExternalCount}
        onMigrationComplete={handleMigrationComplete}
      />

      <div className={styles.knowledgeListContainer}>
        <CreateCardComponent
          width={'100%'}
          height={'10rem'}
          plusSize={'90px'}
          onClick={handleCreateKBClick}
        />

        {knowledgeBaseList.map((kb) => {
          // Show detail/edit view when ?id= query param is present
          if (detailId) {
            return <KBDetailContent id={detailId} />;
          }

          return (
            <div key={kb.id} onClick={() => handleKBCardClick(kb.id)}>
              <KBCard kbCardVO={kb} />
            </div>
          );
        })}
      </div>
    </div>
  );
}
