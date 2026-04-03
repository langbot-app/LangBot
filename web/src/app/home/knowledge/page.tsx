

import { useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useEffect, useState } from 'react';
import { httpClient } from '@/app/infra/http/HttpClient';
import KBMigrationDialog from '@/app/home/knowledge/components/kb-migration-dialog/KBMigrationDialog';
import { useSidebarData } from '@/app/home/components/home-sidebar/SidebarDataContext';
import KBDetailContent from './KBDetailContent';

export default function KnowledgePage() {
  const { t } = useTranslation();
  const searchParams = useSearchParams();
  const detailId = searchParams.get('id');
  const { refreshKnowledgeBases } = useSidebarData();

  // Migration dialog state — checked on page load regardless of detail view
  const [migrationDialogOpen, setMigrationDialogOpen] = useState(false);
  const [migrationInternalCount, setMigrationInternalCount] = useState(0);
  const [migrationExternalCount, setMigrationExternalCount] = useState(0);

  useEffect(() => {
    checkMigrationStatus();
  }, []);

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

  function handleMigrationComplete() {
    refreshKnowledgeBases();
  }

  if (detailId) {
    return (
      <>
        <KBMigrationDialog
          open={migrationDialogOpen}
          onOpenChange={setMigrationDialogOpen}
          internalKbCount={migrationInternalCount}
          externalKbCount={migrationExternalCount}
          onMigrationComplete={handleMigrationComplete}
        />
        <KBDetailContent id={detailId} />
      </>
    );
  }

  return (
    <>
      <KBMigrationDialog
        open={migrationDialogOpen}
        onOpenChange={setMigrationDialogOpen}
        internalKbCount={migrationInternalCount}
        externalKbCount={migrationExternalCount}
        onMigrationComplete={handleMigrationComplete}
      />
      <div className="flex h-full items-center justify-center text-muted-foreground">
        <p>{t('knowledge.selectFromSidebar')}</p>
      </div>
    </>
  );
}
