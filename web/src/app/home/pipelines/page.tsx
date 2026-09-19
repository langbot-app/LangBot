import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useCurrentWorkspace } from '@/app/infra/http';
import { useSidebarData } from '@/app/home/components/home-sidebar/SidebarDataContext';
import PipelineDetailContent from './PipelineDetailContent';
import PipelineMigration, { migrationWorkspaceKey } from './PipelineMigration';

export default function PipelineConfigPage() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const detailId = searchParams.get('id');
  const workspace = useCurrentWorkspace();
  const { refreshPipelines } = useSidebarData();
  const [revision, setRevision] = useState(0);
  const scopeKey = migrationWorkspaceKey(workspace);

  return (
    <div className="flex h-full min-h-0 flex-col">
      {workspace && workspace.permissions.includes('resource.view') && (
        <PipelineMigration
          key={scopeKey}
          workspace={workspace}
          onComplete={() => {
            void refreshPipelines();
            setRevision((current) => current + 1);
          }}
        />
      )}
      <div className="flex-1 min-h-0">
        {detailId ? (
          <PipelineDetailContent
            key={`${scopeKey}:${detailId}:${revision}`}
            id={detailId}
          />
        ) : (
          <div className="flex h-full items-center justify-center text-muted-foreground">
            <p>{t('pipelines.selectFromSidebar')}</p>
          </div>
        )}
      </div>
    </div>
  );
}
