import { useCallback, useRef, useState } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Panel,
  ReactFlowProvider,
  useReactFlow,
  BackgroundVariant,
  SelectionMode,
} from '@xyflow/react';
import type { Node, NodeTypes, OnSelectionChangeParams } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {
  useWorkflowStore,
  WorkflowNode,
  WorkflowEdge,
} from '../../store/useWorkflowStore';
import WorkflowNodeComponent from './WorkflowNodeComponent';
import NodePalette from './NodePalette';
import PropertyPanel from './PropertyPanel';
import { useTranslation } from 'react-i18next';
import {
  Undo2,
  Redo2,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Copy,
  ClipboardPaste,
  Trash2,
  Keyboard,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

// Custom node types - use type assertion to satisfy NodeTypes
const nodeTypes: NodeTypes = {
  workflowNode: WorkflowNodeComponent,
};

// Clipboard storage for copy/paste
interface ClipboardData {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
}

// Generate unique ID for pasted nodes
const generatePastedNodeId = () =>
  `node_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
const generatePastedEdgeId = () =>
  `edge_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

function WorkflowEditorInner() {
  const { t } = useTranslation();
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const { screenToFlowPosition, fitView, zoomIn, zoomOut } = useReactFlow();

  // Clipboard state
  const [clipboard, setClipboard] = useState<ClipboardData | null>(null);
  // Multi-selection state
  const [selectedNodes, setSelectedNodes] = useState<string[]>([]);
  const [selectedEdges, setSelectedEdges] = useState<string[]>([]);
  // Property panel visibility state
  const [showPropertyPanel, setShowPropertyPanel] = useState(false);

  const {
    nodes,
    edges,
    onNodesChange,
    onEdgesChange,
    onConnect,
    addNode,
    selectNode,
    selectEdge,
    clearSelection,
    selectedNodeId,
    selectedEdgeId,
    deleteNode,
    deleteEdge,
    undo,
    redo,
    history,
    historyIndex,
    isDirty,
    setNodes,
    setEdges,
    pushHistory,
    nodeExecutionResults,
  } = useWorkflowStore();

  // Handle node click
  const handleNodeClick = useCallback(
    (_: React.MouseEvent, node: WorkflowNode) => {
      selectNode(node.id);
      setShowPropertyPanel(true);
    },
    [selectNode],
  );

  // Handle edge click
  const handleEdgeClick = useCallback(
    (_: React.MouseEvent, edge: WorkflowEdge) => {
      selectEdge(edge.id);
    },
    [selectEdge],
  );

  // Handle pane click (deselect)
  const handlePaneClick = useCallback(() => {
    clearSelection();
    setSelectedNodes([]);
    setSelectedEdges([]);
    setShowPropertyPanel(false);
  }, [clearSelection]);

  // Handle selection change for multi-select
  const handleSelectionChange = useCallback(
    ({
      nodes: selectedNodesArr,
      edges: selectedEdgesArr,
    }: OnSelectionChangeParams) => {
      const nodeIds = selectedNodesArr.map((n) => n.id);
      const edgeIds = selectedEdgesArr.map((e) => e.id);
      setSelectedNodes(nodeIds);
      setSelectedEdges(edgeIds);

      // Update single selection for property panel
      if (nodeIds.length === 1) {
        selectNode(nodeIds[0]);
      } else if (edgeIds.length === 1 && nodeIds.length === 0) {
        selectEdge(edgeIds[0]);
      } else if (nodeIds.length === 0 && edgeIds.length === 0) {
        clearSelection();
      }
    },
    [selectNode, selectEdge, clearSelection],
  );

  // Handle drop from palette
  const onDrop = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault();

      const type = event.dataTransfer.getData('application/reactflow');
      if (!type || !reactFlowWrapper.current) return;

      const position = screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });

      addNode(type, position);
    },
    [screenToFlowPosition, addNode],
  );

  const onDragOver = useCallback((event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  // Copy selected nodes
  const handleCopy = useCallback(() => {
    const nodesToCopy = nodes.filter(
      (n) => selectedNodes.includes(n.id) || n.id === selectedNodeId,
    );

    if (nodesToCopy.length === 0) {
      toast.error(t('workflows.nothingToCopy'));
      return;
    }

    // Get edges between selected nodes
    const nodeIds = new Set(nodesToCopy.map((n) => n.id));
    const edgesToCopy = edges.filter(
      (e) => nodeIds.has(e.source) && nodeIds.has(e.target),
    );

    setClipboard({
      nodes: nodesToCopy,
      edges: edgesToCopy,
    });

    toast.success(t('workflows.copied', { count: nodesToCopy.length }));
  }, [nodes, edges, selectedNodes, selectedNodeId, t]);

  // Paste nodes from clipboard
  const handlePaste = useCallback(() => {
    if (!clipboard || clipboard.nodes.length === 0) {
      toast.error(t('workflows.nothingToPaste'));
      return;
    }

    // Create ID mapping for pasted nodes
    const idMapping: Record<string, string> = {};
    clipboard.nodes.forEach((node) => {
      idMapping[node.id] = generatePastedNodeId();
    });

    // Offset position for pasted nodes
    const offset = { x: 50, y: 50 };

    // Create new nodes with new IDs and offset positions
    const newNodes: WorkflowNode[] = clipboard.nodes.map((node) => ({
      ...node,
      id: idMapping[node.id],
      position: {
        x: node.position.x + offset.x,
        y: node.position.y + offset.y,
      },
      selected: true,
      data: {
        ...node.data,
        label: `${node.data.label} (copy)`,
      },
    }));

    // Create new edges with updated source/target IDs
    const newEdges: WorkflowEdge[] = clipboard.edges.map((edge) => ({
      ...edge,
      id: generatePastedEdgeId(),
      source: idMapping[edge.source],
      target: idMapping[edge.target],
    }));

    // Add new nodes and edges
    setNodes([...nodes.map((n) => ({ ...n, selected: false })), ...newNodes]);
    setEdges([...edges, ...newEdges]);
    pushHistory();

    // Select pasted nodes
    setSelectedNodes(newNodes.map((n) => n.id));

    toast.success(t('workflows.pasted', { count: newNodes.length }));
  }, [clipboard, nodes, edges, setNodes, setEdges, pushHistory, t]);

  // Delete selected nodes/edges
  const handleDelete = useCallback(() => {
    const nodesToDelete =
      selectedNodes.length > 0
        ? selectedNodes
        : selectedNodeId
          ? [selectedNodeId]
          : [];
    const edgesToDelete =
      selectedEdges.length > 0
        ? selectedEdges
        : selectedEdgeId
          ? [selectedEdgeId]
          : [];

    if (nodesToDelete.length === 0 && edgesToDelete.length === 0) {
      return;
    }

    // Delete nodes (this will also delete connected edges)
    nodesToDelete.forEach((nodeId) => {
      deleteNode(nodeId);
    });

    // Delete edges
    edgesToDelete.forEach((edgeId) => {
      deleteEdge(edgeId);
    });

    setSelectedNodes([]);
    setSelectedEdges([]);
    clearSelection();

    toast.success(t('workflows.deleted'));
  }, [
    selectedNodes,
    selectedEdges,
    selectedNodeId,
    selectedEdgeId,
    deleteNode,
    deleteEdge,
    clearSelection,
    t,
  ]);

  // Select all nodes
  const handleSelectAll = useCallback(() => {
    const allNodeIds = nodes.map((n) => n.id);
    setSelectedNodes(allNodeIds);
    setNodes(nodes.map((n) => ({ ...n, selected: true })));
  }, [nodes, setNodes]);

  // Keyboard shortcuts
  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      // Prevent shortcuts when typing in input fields
      if (
        event.target instanceof HTMLInputElement ||
        event.target instanceof HTMLTextAreaElement
      ) {
        return;
      }

      const isCtrlOrCmd = event.ctrlKey || event.metaKey;

      // Ctrl/Cmd + Z: Undo
      if (isCtrlOrCmd && event.key === 'z' && !event.shiftKey) {
        event.preventDefault();
        undo();
        return;
      }

      // Ctrl/Cmd + Shift + Z or Ctrl/Cmd + Y: Redo
      if (
        (isCtrlOrCmd && event.shiftKey && event.key === 'z') ||
        (isCtrlOrCmd && event.key === 'y')
      ) {
        event.preventDefault();
        redo();
        return;
      }

      // Ctrl/Cmd + C: Copy
      if (isCtrlOrCmd && event.key === 'c') {
        event.preventDefault();
        handleCopy();
        return;
      }

      // Ctrl/Cmd + V: Paste
      if (isCtrlOrCmd && event.key === 'v') {
        event.preventDefault();
        handlePaste();
        return;
      }

      // Ctrl/Cmd + A: Select All
      if (isCtrlOrCmd && event.key === 'a') {
        event.preventDefault();
        handleSelectAll();
        return;
      }

      // Delete or Backspace: Delete selected
      if (event.key === 'Delete' || event.key === 'Backspace') {
        event.preventDefault();
        handleDelete();
        return;
      }

      // Escape: Clear selection
      if (event.key === 'Escape') {
        event.preventDefault();
        clearSelection();
        setSelectedNodes([]);
        setSelectedEdges([]);
        return;
      }
    },
    [
      undo,
      redo,
      handleCopy,
      handlePaste,
      handleSelectAll,
      handleDelete,
      clearSelection,
    ],
  );

  // Memoize mini map node color
  const minimapNodeColor = useCallback((node: Node) => {
    const workflowNode = node as WorkflowNode;
    const categoryColors: Record<string, string> = {
      trigger: '#22c55e',
      process: '#3b82f6',
      control: '#f59e0b',
      action: '#8b5cf6',
      integration: '#ec4899',
    };
    // Extract category from node type (e.g., 'trigger.message' -> 'trigger')
    const category = workflowNode.data?.type?.split('.')[0] || 'process';
    return categoryColors[category] || '#6b7280';
  }, []);

  const displayNodes = nodes.map((node) => {
    const executionResult = nodeExecutionResults[node.id];

    if (!executionResult) {
      return node;
    }

    return {
      ...node,
      data: {
        ...node.data,
        executionStatus: executionResult.status,
        executionError: executionResult.error,
        executionDuration: executionResult.duration,
      },
    };
  });

  const canUndo = historyIndex > 0;
  const canRedo = historyIndex < history.length - 1;
  const hasSelection = selectedNodes.length > 0 || selectedNodeId !== null;
  const hasClipboard = clipboard !== null && clipboard.nodes.length > 0;

  return (
    <TooltipProvider>
      <div
        ref={reactFlowWrapper}
        className="h-full w-full flex"
        onKeyDown={handleKeyDown}
        tabIndex={0}
      >
        {/* Left: Node Palette */}
        <div className="w-64 border-r bg-muted/30 overflow-y-auto flex-shrink-0">
          <NodePalette />
        </div>

        {/* Center: Flow Canvas */}
        <div className="flex-1 relative">
          <ReactFlow
            nodes={displayNodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={handleNodeClick}
            onEdgeClick={handleEdgeClick}
            onPaneClick={handlePaneClick}
            onSelectionChange={handleSelectionChange}
            onDrop={onDrop}
            onDragOver={onDragOver}
            nodeTypes={nodeTypes}
            fitView
            snapToGrid
            snapGrid={[15, 15]}
            selectionMode={SelectionMode.Partial}
            selectionOnDrag
            panOnDrag={[1, 2]} // Middle click and right click to pan
            selectNodesOnDrag={false}
            defaultEdgeOptions={{
              type: 'smoothstep',
              animated: true,
            }}
            deleteKeyCode={null} // We handle delete manually
          >
            <Background
              gap={15}
              size={1}
              variant={BackgroundVariant.Dots}
              color="hsl(var(--muted-foreground) / 0.3)"
            />
            <Controls
              showInteractive={false}
              className="!bg-background !border-border !shadow-md [&_button]:!bg-background [&_button]:!border-border [&_button]:!fill-foreground [&_button:hover]:!bg-muted"
            />
            <MiniMap
              nodeColor={minimapNodeColor}
              maskColor="rgba(0, 0, 0, 0.1)"
              className="!bg-background/80"
              pannable
              zoomable
            />

            {/* Main Toolbar Panel */}
            <Panel
              position="top-right"
              className="flex gap-1 bg-background/80 backdrop-blur-sm rounded-lg p-1 shadow-md border"
            >
              {/* Undo/Redo */}
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => undo()}
                    disabled={!canUndo}
                    className="size-8"
                  >
                    <Undo2 className="size-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="bottom">
                  <p>{t('common.undo')} (Ctrl+Z)</p>
                </TooltipContent>
              </Tooltip>

              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => redo()}
                    disabled={!canRedo}
                    className="size-8"
                  >
                    <Redo2 className="size-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="bottom">
                  <p>{t('common.redo')} (Ctrl+Shift+Z)</p>
                </TooltipContent>
              </Tooltip>

              <div className="w-px bg-border mx-0.5" />

              {/* Copy/Paste */}
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={handleCopy}
                    disabled={!hasSelection}
                    className="size-8"
                  >
                    <Copy className="size-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="bottom">
                  <p>{t('common.copy')} (Ctrl+C)</p>
                </TooltipContent>
              </Tooltip>

              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={handlePaste}
                    disabled={!hasClipboard}
                    className="size-8"
                  >
                    <ClipboardPaste className="size-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="bottom">
                  <p>{t('workflows.paste')} (Ctrl+V)</p>
                </TooltipContent>
              </Tooltip>

              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={handleDelete}
                    disabled={!hasSelection && selectedEdgeId === null}
                    className="size-8 text-destructive hover:text-destructive"
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="bottom">
                  <p>{t('common.delete')} (Delete)</p>
                </TooltipContent>
              </Tooltip>

              <div className="w-px bg-border mx-0.5" />

              {/* Zoom controls */}
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => zoomIn()}
                    className="size-8 text-muted-foreground hover:text-foreground dark:text-muted-foreground dark:hover:text-foreground"
                  >
                    <ZoomIn className="size-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="bottom">
                  <p>{t('workflows.zoomIn')}</p>
                </TooltipContent>
              </Tooltip>

              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => zoomOut()}
                    className="size-8 text-muted-foreground hover:text-foreground dark:text-muted-foreground dark:hover:text-foreground"
                  >
                    <ZoomOut className="size-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="bottom">
                  <p>{t('workflows.zoomOut')}</p>
                </TooltipContent>
              </Tooltip>

              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => fitView()}
                    className="size-8 text-muted-foreground hover:text-foreground dark:text-muted-foreground dark:hover:text-foreground"
                  >
                    <Maximize2 className="size-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="bottom">
                  <p>{t('workflows.fitView')}</p>
                </TooltipContent>
              </Tooltip>
            </Panel>

            {/* Keyboard shortcuts hint */}
            <Panel
              position="bottom-center"
              className="text-xs text-muted-foreground bg-background/60 backdrop-blur-sm rounded px-2 py-1"
            >
              <div className="flex items-center gap-2">
                <Keyboard className="size-3" />
                <span>
                  Ctrl+Z/Y: {t('common.undo')}/{t('common.redo')} | Ctrl+C/V:{' '}
                  {t('common.copy')}/{t('workflows.paste')} | Del:{' '}
                  {t('common.delete')}
                </span>
              </div>
            </Panel>

            {/* Dirty indicator */}
            {isDirty && (
              <Panel position="top-left" className="ml-2">
                <div className="text-xs text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/50 border border-amber-200 dark:border-amber-800 px-2 py-1 rounded flex items-center gap-1">
                  <div className="size-1.5 rounded-full bg-amber-500 animate-pulse" />
                  {t('workflows.unsavedChanges')}
                </div>
              </Panel>
            )}

            {/* Selection info */}
            {(selectedNodes.length > 1 || selectedEdges.length > 0) && (
              <Panel
                position="bottom-right"
                className="text-xs text-muted-foreground bg-background/80 backdrop-blur-sm rounded px-2 py-1 mr-2 mb-2"
              >
                {selectedNodes.length > 0 && (
                  <span>
                    {t('workflows.nodesSelected', {
                      count: selectedNodes.length,
                    })}
                  </span>
                )}
                {selectedNodes.length > 0 && selectedEdges.length > 0 && (
                  <span> | </span>
                )}
                {selectedEdges.length > 0 && (
                  <span>
                    {t('workflows.edgesSelected', {
                      count: selectedEdges.length,
                    })}
                  </span>
                )}
              </Panel>
            )}
          </ReactFlow>
        </div>

        {/* Right: Property Panel (conditionally rendered) */}
        {showPropertyPanel && (
          <div className="w-[28rem] xl:w-[32rem] min-w-[24rem] border-l bg-muted/30 overflow-hidden flex-shrink-0 h-full">
            <PropertyPanel
              selectedNodeId={selectedNodeId}
              selectedEdgeId={selectedEdgeId}
            />
          </div>
        )}
      </div>
    </TooltipProvider>
  );
}

export default function WorkflowEditorComponent() {
  return (
    <ReactFlowProvider>
      <WorkflowEditorInner />
    </ReactFlowProvider>
  );
}
