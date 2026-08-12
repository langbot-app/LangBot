import { systemInfo } from '@/app/infra/http/HttpClient';
import { useSidebarData } from '@/app/home/components/home-sidebar/SidebarDataContext';

export interface WorkspaceQuotaItem {
  count: number;
  max: number;
  reached: boolean;
  loading: boolean;
  disabled: boolean;
}

export interface WorkspaceQuotaStatus {
  bots: WorkspaceQuotaItem;
  pipelines: WorkspaceQuotaItem;
  knowledgeBases: WorkspaceQuotaItem;
  extensions: WorkspaceQuotaItem;
  botsReached: boolean;
  pipelinesReached: boolean;
  knowledgeBasesReached: boolean;
  extensionsReached: boolean;
}

function quotaItem(
  count: number,
  max: number | undefined,
  loaded: boolean,
): WorkspaceQuotaItem {
  const normalizedMax = typeof max === 'number' ? max : -1;
  const reached = loaded && normalizedMax >= 0 && count >= normalizedMax;
  return {
    count,
    max: normalizedMax,
    reached,
    loading: !loaded,
    disabled: !loaded || reached,
  };
}

export function useWorkspaceQuotaStatus(): WorkspaceQuotaStatus {
  const {
    bots,
    pipelines,
    knowledgeBases,
    pluginCount,
    mcpServers,
    skills,
    quotaDataLoaded,
  } = useSidebarData();
  const limitation = systemInfo.limitation;

  const botQuota = quotaItem(
    bots.length,
    limitation?.max_bots,
    quotaDataLoaded,
  );
  const pipelineQuota = quotaItem(
    pipelines.length,
    limitation?.max_pipelines,
    quotaDataLoaded,
  );
  const knowledgeBaseQuota = quotaItem(
    knowledgeBases.length,
    limitation?.max_knowledge_bases,
    quotaDataLoaded,
  );
  const extensionQuota = quotaItem(
    pluginCount + mcpServers.length + skills.length,
    limitation?.max_extensions,
    quotaDataLoaded,
  );

  return {
    bots: botQuota,
    pipelines: pipelineQuota,
    knowledgeBases: knowledgeBaseQuota,
    extensions: extensionQuota,
    botsReached: botQuota.disabled,
    pipelinesReached: pipelineQuota.disabled,
    knowledgeBasesReached: knowledgeBaseQuota.disabled,
    extensionsReached: extensionQuota.disabled,
  };
}
