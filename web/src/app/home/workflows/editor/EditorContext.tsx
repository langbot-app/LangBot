import { createContext, useContext } from 'react';
import type { AdapterCapabilities } from '../lib/platform';
import type {
  Agent,
  AgentPlatformTool,
  ASRModel,
  KnowledgeBase,
  LLMModel,
  TTSModel,
  WorkflowGraph,
  WorkflowIssue,
  WorkflowStepRun,
  WorkflowSummary,
  WorkflowTrigger,
} from '@/app/infra/entities/api';

export interface EditorResources {
  models: LLMModel[];
  ttsModels: TTSModel[];
  asrModels: ASRModel[];
  knowledgeBases: KnowledgeBase[];
  processors: Agent[];
  workflows: WorkflowSummary[];
  bots: { uuid: string; name: string; adapter: string }[];
  /** Capabilities of each platform adapter, by adapter name. */
  adapters: Record<string, AdapterCapabilities>;
  /** Event and platform actions shared with Agents. */
  platformTools: AgentPlatformTool[];
  /** Step types the server can run; others are hidden from the picker. */
  availableTypes: Set<string> | null;
}

export interface EditorState {
  workflowId: string;
  graph: WorkflowGraph;
  setGraph: (update: (graph: WorkflowGraph) => WorkflowGraph) => void;
  selected: string | null;
  select: (id: string | null) => void;
  issues: WorkflowIssue[];
  /** Step runs of the latest test run, by step id. */
  lastRun: Record<string, WorkflowStepRun>;
  resources: EditorResources;
  readOnly: boolean;
  /** Triggers live on the workflow, edited from the start step. */
  triggers: WorkflowTrigger[];
  setTriggers: (
    update: (triggers: WorkflowTrigger[]) => WorkflowTrigger[],
  ) => void;
  timezone: string;
  setTimezone: (timezone: string) => void;
}

export const EditorContext = createContext<EditorState | null>(null);

export function useEditor(): EditorState {
  const value = useContext(EditorContext);
  if (!value) throw new Error('useEditor must be used inside the editor');
  return value;
}
