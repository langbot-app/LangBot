import { createContext, useContext } from 'react';
import type {
  Agent,
  LLMModel,
  WorkflowGraph,
  WorkflowIssue,
  WorkflowStepRun,
  WorkflowSummary,
} from '@/app/infra/entities/api';

export interface EditorResources {
  models: LLMModel[];
  processors: Agent[];
  workflows: WorkflowSummary[];
  bots: { uuid: string; name: string }[];
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
}

export const EditorContext = createContext<EditorState | null>(null);

export function useEditor(): EditorState {
  const value = useContext(EditorContext);
  if (!value) throw new Error('useEditor must be used inside the editor');
  return value;
}
