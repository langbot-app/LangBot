import { create } from 'zustand';
import {
  Node,
  Edge,
  Connection,
  addEdge,
  applyNodeChanges,
  applyEdgeChanges,
  NodeChange,
  EdgeChange,
} from '@xyflow/react';
import {
  Workflow,
  WorkflowNodeDefinition,
  WorkflowEdgeDefinition,
  WorkflowNodeTypeMetadata,
  WorkflowNodeCategory,
} from '@/app/infra/entities/api';
import { getNodeTypeLabel as sharedGetNodeTypeLabel } from '../components/workflow-editor/workflow-constants';
import { normalizeWorkflowNodeTypeMeta } from '../components/workflow-editor/workflow-node-metadata';
import i18n from '@/i18n';

export interface WorkflowNode extends Node {
  data: {
    label: string;
    type: string;
    config: Record<string, unknown>;
    inputs?: { name: string; label?: string; type?: string }[];
    outputs?: { name: string; label?: string; type?: string }[];
  };
}

export interface WorkflowEdge extends Edge {
  data?: {
    label?: string;
    condition?: string;
  };
}

// Debug related types
export type DebugState = 'idle' | 'running' | 'paused' | 'completed' | 'error';

export interface NodeExecutionResult {
  nodeId: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
  inputs?: Record<string, unknown>;
  outputs?: Record<string, unknown>;
  error?: string;
  startTime?: string;
  endTime?: string;
  duration?: number;
}

export interface DebugLog {
  id: string;
  timestamp: string;
  level: 'info' | 'warning' | 'error' | 'debug';
  nodeId?: string;
  message: string;
  data?: Record<string, unknown>;
}

export interface DebugContext {
  messageContent: string;
  senderId: string;
  senderName: string;
  platform: string;
  conversationId: string;
  isGroup: boolean;
  customVariables: Record<string, unknown>;
}

interface WorkflowState {
  // Current workflow being edited
  currentWorkflow: Workflow | null;

  // React Flow nodes and edges
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];

  // Node type metadata from backend
  nodeTypes: WorkflowNodeTypeMetadata[];
  nodeCategories: WorkflowNodeCategory[];

  // Selection state
  selectedNodeId: string | null;
  selectedEdgeId: string | null;

  // UI state
  isDirty: boolean;
  isSaving: boolean;
  isLoading: boolean;

  // Undo/Redo history
  history: { nodes: WorkflowNode[]; edges: WorkflowEdge[] }[];
  historyIndex: number;

  // Debug state
  debugMode: boolean;
  debugState: DebugState;
  debugExecutionId: string | null;
  currentNodeId: string | null;
  nodeExecutionResults: Record<string, NodeExecutionResult>;
  breakpoints: Record<string, boolean>;
  debugLogs: DebugLog[];
  debugContext: DebugContext;
  watchedVariables: string[];

  // Actions
  setCurrentWorkflow: (workflow: Workflow | null) => void;
  setNodes: (nodes: WorkflowNode[]) => void;
  setEdges: (edges: WorkflowEdge[]) => void;
  setNodeTypes: (
    types: WorkflowNodeTypeMetadata[],
    categories: WorkflowNodeCategory[],
  ) => void;

  // Node operations
  onNodesChange: (changes: NodeChange<WorkflowNode>[]) => void;
  onEdgesChange: (changes: EdgeChange<WorkflowEdge>[]) => void;
  onConnect: (connection: Connection) => void;

  addNode: (type: string, position: { x: number; y: number }) => void;
  updateNodeConfig: (nodeId: string, config: Record<string, unknown>) => void;
  updateNodeLabel: (nodeId: string, label: string) => void;
  deleteNode: (nodeId: string) => void;

  // Edge operations
  deleteEdge: (edgeId: string) => void;
  updateEdgeCondition: (edgeId: string, condition: string) => void;

  // Selection
  selectNode: (nodeId: string | null) => void;
  selectEdge: (edgeId: string | null) => void;
  clearSelection: () => void;

  // State management
  setDirty: (dirty: boolean) => void;
  setSaving: (saving: boolean) => void;
  setLoading: (loading: boolean) => void;

  // Undo/Redo
  undo: () => void;
  redo: () => void;
  pushHistory: () => void;

  // Convert to/from API format
  toWorkflowDefinition: () => {
    nodes: WorkflowNodeDefinition[];
    edges: WorkflowEdgeDefinition[];
  };
  fromWorkflowDefinition: (
    nodes: WorkflowNodeDefinition[],
    edges: WorkflowEdgeDefinition[],
  ) => void;

  // Reset
  reset: () => void;

  // Debug actions
  setDebugMode: (enabled: boolean) => void;
  setDebugState: (state: DebugState) => void;
  setDebugExecutionId: (executionId: string | null) => void;
  setCurrentNodeId: (nodeId: string | null) => void;
  updateNodeExecutionResult: (
    nodeId: string,
    result: Partial<NodeExecutionResult>,
  ) => void;
  clearNodeExecutionResults: () => void;
  toggleBreakpoint: (nodeId: string) => void;
  clearBreakpoints: () => void;
  addDebugLog: (log: Omit<DebugLog, 'id' | 'timestamp'>) => void;
  clearDebugLogs: () => void;
  setDebugContext: (context: Partial<DebugContext>) => void;
  resetDebugContext: () => void;
  addWatchedVariable: (variable: string) => void;
  removeWatchedVariable: (variable: string) => void;
  clearWatchedVariables: () => void;
  resetDebugState: () => void;
}

const generateUuidLikeId = () => {
  if (
    typeof crypto !== 'undefined' &&
    typeof crypto.randomUUID === 'function'
  ) {
    return crypto.randomUUID();
  }

  return `${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 11)}`;
};

const generateNodeId = () => `node_${generateUuidLikeId()}`;
const generateEdgeId = () => `edge_${generateUuidLikeId()}`;

const defaultDebugContext: DebugContext = {
  messageContent: '',
  senderId: `user_${Date.now().toString(36)}`,
  senderName: '',
  platform: '',
  conversationId: `session_${Date.now().toString(36)}`,
  isGroup: false,
  customVariables: {},
};

const generateLogId = () => `log_${generateUuidLikeId()}`;

export const useWorkflowStore = create<WorkflowState>((set, get) => ({
  // Initial state
  currentWorkflow: null,
  nodes: [],
  edges: [],
  nodeTypes: [],
  nodeCategories: [],
  selectedNodeId: null,
  selectedEdgeId: null,
  isDirty: false,
  isSaving: false,
  isLoading: false,
  history: [],
  historyIndex: -1,

  // Debug initial state
  debugMode: false,
  debugState: 'idle',
  debugExecutionId: null,
  currentNodeId: null,
  nodeExecutionResults: {},
  breakpoints: {} as Record<string, boolean>,
  debugLogs: [],
  debugContext: { ...defaultDebugContext },
  watchedVariables: [],

  // Setters
  setCurrentWorkflow: (workflow) => set({ currentWorkflow: workflow }),
  setNodes: (nodes) => set({ nodes, isDirty: true }),
  setEdges: (edges) => set({ edges, isDirty: true }),
  setNodeTypes: (types, categories) =>
    set({ nodeTypes: types, nodeCategories: categories }),

  // Node change handlers
  onNodesChange: (changes) => {
    set((state) => ({
      nodes: applyNodeChanges(changes, state.nodes) as WorkflowNode[],
      isDirty: true,
    }));
  },

  onEdgesChange: (changes) => {
    set((state) => ({
      edges: applyEdgeChanges(changes, state.edges) as WorkflowEdge[],
      isDirty: true,
    }));
  },

  onConnect: (connection) => {
    const newEdge: WorkflowEdge = {
      ...connection,
      id: generateEdgeId(),
      type: 'smoothstep',
    } as WorkflowEdge;

    set((state) => ({
      edges: addEdge(newEdge, state.edges) as WorkflowEdge[],
      isDirty: true,
    }));
    get().pushHistory();
  },

  // Add new node
  addNode: (type, position) => {
    const { nodeTypes } = get();
    const nodeType = normalizeWorkflowNodeTypeMeta(
      type,
      nodeTypes.find((t) => t.type === type),
    );

    const getNodeLabel = (
      nodeT: WorkflowNodeTypeMetadata | undefined,
      nodeType_str: string,
    ): string => {
      return sharedGetNodeTypeLabel(nodeType_str, nodeT?.label);
    };

    const newNode: WorkflowNode = {
      id: generateNodeId(),
      type: 'workflowNode',
      position,
      data: {
        label: getNodeLabel(nodeType, type),
        type,
        config: {},
        inputs: (nodeType.inputs || []).map((input) => ({
          name: input.name,
          type: input.type,
          label: input.label,
        })),
        outputs: (nodeType.outputs || []).map((output) => ({
          name: output.name,
          type: output.type,
          label: output.label,
        })),
      },
    };

    set((state) => ({
      nodes: [...state.nodes, newNode],
      isDirty: true,
    }));
    get().pushHistory();
  },

  // Update node config
  updateNodeConfig: (nodeId, config) => {
    set((state) => ({
      nodes: state.nodes.map((node) =>
        node.id === nodeId ? { ...node, data: { ...node.data, config } } : node,
      ),
      isDirty: true,
    }));
  },

  // Update node label
  updateNodeLabel: (nodeId, label) => {
    set((state) => ({
      nodes: state.nodes.map((node) =>
        node.id === nodeId ? { ...node, data: { ...node.data, label } } : node,
      ),
      isDirty: true,
    }));
  },

  // Delete node
  deleteNode: (nodeId) => {
    set((state) => ({
      nodes: state.nodes.filter((node) => node.id !== nodeId),
      edges: state.edges.filter(
        (edge) => edge.source !== nodeId && edge.target !== nodeId,
      ),
      selectedNodeId:
        state.selectedNodeId === nodeId ? null : state.selectedNodeId,
      isDirty: true,
    }));
    get().pushHistory();
  },

  // Delete edge
  deleteEdge: (edgeId) => {
    set((state) => ({
      edges: state.edges.filter((edge) => edge.id !== edgeId),
      selectedEdgeId:
        state.selectedEdgeId === edgeId ? null : state.selectedEdgeId,
      isDirty: true,
    }));
    get().pushHistory();
  },

  // Update edge condition
  updateEdgeCondition: (edgeId, condition) => {
    set((state) => ({
      edges: state.edges.map((edge) =>
        edge.id === edgeId
          ? { ...edge, data: { ...edge.data, condition } }
          : edge,
      ),
      isDirty: true,
    }));
  },

  // Selection
  selectNode: (nodeId) => set({ selectedNodeId: nodeId, selectedEdgeId: null }),
  selectEdge: (edgeId) => set({ selectedEdgeId: edgeId, selectedNodeId: null }),
  clearSelection: () => set({ selectedNodeId: null, selectedEdgeId: null }),

  // State management
  setDirty: (dirty) => set({ isDirty: dirty }),
  setSaving: (saving) => set({ isSaving: saving }),
  setLoading: (loading) => set({ isLoading: loading }),

  // Undo
  undo: () => {
    const { history, historyIndex } = get();
    if (historyIndex > 0) {
      const newIndex = historyIndex - 1;
      const { nodes, edges } = history[newIndex];
      set({ nodes, edges, historyIndex: newIndex, isDirty: true });
    }
  },

  // Redo
  redo: () => {
    const { history, historyIndex } = get();
    if (historyIndex < history.length - 1) {
      const newIndex = historyIndex + 1;
      const { nodes, edges } = history[newIndex];
      set({ nodes, edges, historyIndex: newIndex, isDirty: true });
    }
  },

  // Push current state to history
  pushHistory: () => {
    const { nodes, edges, history, historyIndex } = get();
    const newHistory = history.slice(0, historyIndex + 1);
    newHistory.push({ nodes: [...nodes], edges: [...edges] });

    // Keep history limited to 50 entries
    if (newHistory.length > 50) {
      newHistory.shift();
    }

    set({ history: newHistory, historyIndex: newHistory.length - 1 });
  },

  // Convert to API format
  toWorkflowDefinition: () => {
    const { nodes, edges } = get();

    const workflowNodes: WorkflowNodeDefinition[] = nodes.map((node) => ({
      id: node.id,
      type: node.data.type,
      position: node.position,
      config: node.data.config,
      label: node.data.label,
      inputs: node.data.inputs,
      outputs: node.data.outputs,
    }));

    const workflowEdges: WorkflowEdgeDefinition[] = edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      source_port: edge.sourceHandle || undefined,
      target_port: edge.targetHandle || undefined,
      label: edge.data?.label,
      condition: edge.data?.condition,
    }));

    return { nodes: workflowNodes, edges: workflowEdges };
  },

  // Load from API format
  fromWorkflowDefinition: (apiNodes, apiEdges) => {
    const nodes: WorkflowNode[] = apiNodes.map((node) => ({
      id: node.id,
      type: 'workflowNode',
      position: node.position,
      data: {
        label: node.label || node.type,
        type: node.type,
        config: node.config,
        inputs: node.inputs,
        outputs: node.outputs,
      },
    }));

    const edges: WorkflowEdge[] = apiEdges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      sourceHandle: edge.source_port,
      targetHandle: edge.target_port,
      type: 'smoothstep',
      data: {
        label: edge.label,
        condition: edge.condition,
      },
    }));

    set({ nodes, edges, isDirty: false });
    get().pushHistory();
  },

  // Reset store
  reset: () =>
    set({
      currentWorkflow: null,
      nodes: [],
      edges: [],
      selectedNodeId: null,
      selectedEdgeId: null,
      isDirty: false,
      isSaving: false,
      isLoading: false,
      history: [],
      historyIndex: -1,
      // Reset debug state
      debugMode: false,
      debugState: 'idle',
      debugExecutionId: null,
      currentNodeId: null,
      nodeExecutionResults: {},
      breakpoints: {} as Record<string, boolean>,
      debugLogs: [],
      debugContext: { ...defaultDebugContext },
      watchedVariables: [],
    }),

  // Debug actions
  setDebugMode: (enabled) => set({ debugMode: enabled }),

  setDebugState: (state) => set({ debugState: state }),

  setDebugExecutionId: (executionId) => set({ debugExecutionId: executionId }),

  setCurrentNodeId: (nodeId) => set({ currentNodeId: nodeId }),

  updateNodeExecutionResult: (nodeId, result) => {
    set((state) => ({
      nodeExecutionResults: {
        ...state.nodeExecutionResults,
        [nodeId]: {
          ...(state.nodeExecutionResults[nodeId] || {
            nodeId,
            status: 'pending',
          }),
          ...result,
        },
      },
    }));
  },

  clearNodeExecutionResults: () => set({ nodeExecutionResults: {} }),

  toggleBreakpoint: (nodeId) => {
    set((state) => {
      const newBreakpoints = { ...state.breakpoints };
      if (newBreakpoints[nodeId]) {
        delete newBreakpoints[nodeId];
      } else {
        newBreakpoints[nodeId] = true;
      }
      return { breakpoints: newBreakpoints };
    });
  },

  clearBreakpoints: () => set({ breakpoints: {} as Record<string, boolean> }),

  addDebugLog: (log) => {
    set((state) => ({
      debugLogs: [
        ...state.debugLogs,
        {
          ...log,
          id: generateLogId(),
          timestamp: new Date().toISOString(),
        },
      ].slice(-500), // Keep only last 500 logs
    }));
  },

  clearDebugLogs: () => set({ debugLogs: [] }),

  setDebugContext: (context) => {
    set((state) => ({
      debugContext: { ...state.debugContext, ...context },
    }));
  },

  resetDebugContext: () =>
    set({
      debugContext: {
        messageContent: '',
        senderId: `user_${Date.now().toString(36)}`,
        senderName: '',
        platform: '',
        conversationId: `session_${Date.now().toString(36)}`,
        isGroup: false,
        customVariables: {},
      },
    }),

  addWatchedVariable: (variable) => {
    set((state) => ({
      watchedVariables: state.watchedVariables.includes(variable)
        ? state.watchedVariables
        : [...state.watchedVariables, variable],
    }));
  },

  removeWatchedVariable: (variable) => {
    set((state) => ({
      watchedVariables: state.watchedVariables.filter((v) => v !== variable),
    }));
  },

  clearWatchedVariables: () => set({ watchedVariables: [] }),

  resetDebugState: () =>
    set({
      debugState: 'idle',
      debugExecutionId: null,
      currentNodeId: null,
      nodeExecutionResults: {},
      debugLogs: [],
    }),
}));
