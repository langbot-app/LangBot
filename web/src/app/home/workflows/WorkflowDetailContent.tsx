import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import WorkflowEditorComponent from './components/workflow-editor/WorkflowEditorComponent';
import WorkflowFormComponent from './components/workflow-form/WorkflowFormComponent';
import WorkflowExecutionsTab from './components/workflow-executions/WorkflowExecutionsTab';
import WorkflowDebugDialog from './components/workflow-debug-dialog/WorkflowDebugDialog';
import { useSidebarData } from '@/app/home/components/home-sidebar/SidebarDataContext';
import { useTranslation } from 'react-i18next';
import {
  Settings,
  Play,
  BarChart3,
  GitBranch,
  Download,
  Upload,
  Bug,
} from 'lucide-react';
import { backendClient } from '@/app/infra/http';
import { Workflow } from '@/app/infra/entities/api';
import { useWorkflowStore } from './store/useWorkflowStore';
import { toast } from 'sonner';
import EmojiPicker from '@/components/ui/emoji-picker';

export default function WorkflowDetailContent({ id }: { id: string }) {
  const isCreateMode = id === 'new';
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { refreshWorkflows, workflows, setDetailEntityName } = useSidebarData();

  const {
    currentWorkflow,
    setCurrentWorkflow,
    fromWorkflowDefinition,
    toWorkflowDefinition,
    isDirty,
    setDirty,
    isSaving,
    setSaving,
    setLoading,
    reset,
    nodeTypes,
    setNodeTypes,
  } = useWorkflowStore();

  const [activeTab, setActiveTab] = useState('editor');
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [createStep, setCreateStep] = useState<'basic' | 'editor'>('basic');
  const [basicInfo, setBasicInfo] = useState<{
    name: string;
    description: string;
    emoji: string;
  }>({
    name: '',
    description: '',
    emoji: '🔄',
  });
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isWebSocketConnected, setIsWebSocketConnected] = useState(false);

  // Set breadcrumb entity name
  useEffect(() => {
    if (isCreateMode) {
      setDetailEntityName(t('workflows.createWorkflow'));
    } else {
      const wf = workflows.find((w) => w.id === id);
      setDetailEntityName(wf?.name ?? id);
    }
    return () => setDetailEntityName(null);
  }, [id, isCreateMode, workflows, setDetailEntityName, t]);

  // Load node types
  useEffect(() => {
    if (nodeTypes.length === 0) {
      backendClient
        .getWorkflowNodeTypes()
        .then((resp) => {
          setNodeTypes(resp.node_types, resp.categories);
        })
        .catch((err) => {
          console.error('Failed to load node types:', err);
        });
    }
  }, [nodeTypes.length, setNodeTypes]);

  // Load workflow data
  useEffect(() => {
    if (isCreateMode) {
      reset();
      setWorkflow(null);
      return;
    }

    setLoading(true);
    backendClient
      .getWorkflow(id)
      .then((resp) => {
        setWorkflow(resp.workflow);
        setCurrentWorkflow(resp.workflow);
        fromWorkflowDefinition(
          resp.workflow.nodes || [],
          resp.workflow.edges || [],
        );
      })
      .catch((err) => {
        console.error('Failed to load workflow:', err);
        toast.error(t('workflows.loadError'));
      })
      .finally(() => {
        setLoading(false);
      });

    return () => {
      reset();
    };
  }, [id, isCreateMode]);

  // Save handler
  const handleSave = useCallback(async () => {
    if (isSaving) return;

    setSaving(true);
    try {
      const { nodes, edges } = toWorkflowDefinition();

      if (isCreateMode) {
        const resp = await backendClient.createWorkflow({
          name: basicInfo.name || t('workflows.newWorkflow'),
          description: basicInfo.description,
          emoji: basicInfo.emoji,
          nodes,
          edges,
        });
        refreshWorkflows();
        navigate(`/home/workflows?id=${encodeURIComponent(resp.uuid)}`);
        toast.success(t('workflows.createSuccess'));
      } else {
        await backendClient.updateWorkflow(id, {
          name: workflow?.name,
          emoji: workflow?.emoji,
          description: workflow?.description,
          nodes,
          edges,
          variables: workflow?.variables,
          settings: workflow?.settings,
          triggers: workflow?.triggers,
        });
        setDirty(false);
        refreshWorkflows();
        toast.success(t('workflows.saveSuccess'));
      }
    } catch (err) {
      console.error('Failed to save workflow:', err);
      toast.error(t('workflows.saveError'));
    } finally {
      setSaving(false);
    }
  }, [
    id,
    isCreateMode,
    workflow,
    isSaving,
    toWorkflowDefinition,
    refreshWorkflows,
    navigate,
    t,
    basicInfo,
  ]);

  // Export workflow handler
  const handleExport = useCallback(() => {
    const { nodes, edges } = toWorkflowDefinition();

    const exportData = {
      name: workflow?.name || t('workflows.newWorkflow'),
      description: workflow?.description || '',
      emoji: workflow?.emoji || '🔄',
      nodes,
      edges,
      variables: workflow?.variables || {},
      settings: workflow?.settings || {},
      version: '1.0',
      exportedAt: new Date().toISOString(),
    };

    const blob = new Blob([JSON.stringify(exportData, null, 2)], {
      type: 'application/json',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${workflow?.name || 'workflow'}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    toast.success(t('workflows.exportSuccess'));
  }, [workflow, toWorkflowDefinition, t]);

  // Import workflow handler
  const handleImport = useCallback(
    (file: File) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          const importData = JSON.parse(e.target?.result as string);

          // Validate imported data structure
          if (!importData.nodes || !Array.isArray(importData.nodes)) {
            throw new Error('Invalid workflow file: missing nodes');
          }
          if (!importData.edges || !Array.isArray(importData.edges)) {
            throw new Error('Invalid workflow file: missing edges');
          }

          // Validate each node has required fields
          const nodeIds = new Set<string>();
          for (const node of importData.nodes) {
            if (!node.id || !node.type) {
              throw new Error(`Invalid node: missing id or type`);
            }
            if (
              !node.position ||
              typeof node.position.x !== 'number' ||
              typeof node.position.y !== 'number'
            ) {
              throw new Error(
                `Invalid node "${node.id}": missing or invalid position`,
              );
            }
            nodeIds.add(node.id);
          }

          // Validate each edge has required fields and references existing nodes
          for (const edge of importData.edges) {
            if (!edge.id || !edge.source || !edge.target) {
              throw new Error(`Invalid edge: missing id, source, or target`);
            }
            if (!nodeIds.has(edge.source)) {
              throw new Error(
                `Edge "${edge.id}" references unknown source node "${edge.source}"`,
              );
            }
            if (!nodeIds.has(edge.target)) {
              throw new Error(
                `Edge "${edge.id}" references unknown target node "${edge.target}"`,
              );
            }
          }

          // Load nodes and edges into the store
          fromWorkflowDefinition(importData.nodes, importData.edges);

          // Update workflow metadata if available
          if (
            workflow &&
            (importData.name || importData.description || importData.emoji)
          ) {
            setWorkflow({
              ...workflow,
              name: importData.name || workflow.name,
              description: importData.description || workflow.description,
              emoji: importData.emoji || workflow.emoji,
              variables: importData.variables || workflow.variables,
              settings: importData.settings || workflow.settings,
            });
          }

          setDirty(true);
          toast.success(t('workflows.importSuccess'));
        } catch (error) {
          console.error('Failed to import workflow:', error);
          toast.error(t('workflows.importError'));
        }
      };
      reader.readAsText(file);
    },
    [workflow, fromWorkflowDefinition, setDirty, t],
  );

  // Handle file input change
  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) {
        handleImport(file);
        // Reset file input
        e.target.value = '';
      }
    },
    [handleImport],
  );

  // Publish handler
  const handlePublish = useCallback(async () => {
    if (!workflow?.uuid) return;

    try {
      await backendClient.publishWorkflow(workflow.uuid);
      toast.success(t('workflows.publishSuccess'));
      refreshWorkflows();
    } catch (err) {
      console.error('Failed to publish workflow:', err);
      toast.error(t('workflows.publishError'));
    }
  }, [workflow, refreshWorkflows, t]);

  // Delete handler
  const handleDelete = useCallback(async () => {
    if (!workflow?.uuid) return;

    try {
      await backendClient.deleteWorkflow(workflow.uuid);
      refreshWorkflows();
      navigate('/home/workflows');
      toast.success(t('workflows.deleteSuccess'));
    } catch (err) {
      console.error('Failed to delete workflow:', err);
      toast.error(t('workflows.deleteError'));
    }
  }, [workflow, refreshWorkflows, navigate, t]);

  // ==================== Create Mode ====================
  if (isCreateMode && createStep === 'basic') {
    return (
      <div className="flex h-full flex-col">
        <div className="flex items-center justify-between pb-4 shrink-0">
          <h1 className="text-xl font-semibold">
            {t('workflows.createWorkflow')}
          </h1>
          <div className="flex gap-2">
            <input
              type="file"
              accept=".json"
              onChange={handleFileChange}
              style={{ display: 'none' }}
              ref={fileInputRef}
            />
            <Button
              variant="outline"
              onClick={() => fileInputRef.current?.click()}
            >
              <Upload className="size-4 mr-1" />
              {t('workflows.import')}
            </Button>
            <Button
              onClick={() => setCreateStep('editor')}
              disabled={!basicInfo.name.trim()}
            >
              {t('common.next')}
            </Button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto min-h-0">
          <div className="mx-auto max-w-2xl space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>{t('workflows.basicInfo')}</CardTitle>
                <CardDescription>
                  {t('workflows.basicInfoDesc')}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="workflow-name">{t('workflows.name')}</Label>
                  <div className="flex gap-2">
                    <EmojiPicker
                      value={basicInfo.emoji}
                      onChange={(emoji: string) =>
                        setBasicInfo({ ...basicInfo, emoji })
                      }
                    />
                    <Input
                      id="workflow-name"
                      value={basicInfo.name}
                      onChange={(e) =>
                        setBasicInfo({ ...basicInfo, name: e.target.value })
                      }
                      placeholder={t('workflows.namePlaceholder')}
                      className="flex-1"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="workflow-description">
                    {t('workflows.description')}
                  </Label>
                  <Textarea
                    id="workflow-description"
                    value={basicInfo.description}
                    onChange={(e) =>
                      setBasicInfo({
                        ...basicInfo,
                        description: e.target.value,
                      })
                    }
                    placeholder={t('workflows.descriptionPlaceholder')}
                    rows={3}
                  />
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    );
  }

  if (isCreateMode) {
    return (
      <div className="flex h-full flex-col">
        <div className="flex items-center justify-between pb-4 shrink-0">
          <h1 className="text-xl font-semibold">
            {t('workflows.createWorkflow')}
          </h1>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setCreateStep('basic')}>
              {t('common.back')}
            </Button>
            <Button onClick={handleSave} disabled={isSaving}>
              {isSaving ? t('common.saving') : t('common.create')}
            </Button>
          </div>
        </div>

        <div className="flex-1 min-h-0">
          <WorkflowEditorComponent />
        </div>
      </div>
    );
  }

  // ==================== Edit Mode ====================
  return (
    <div className="flex h-full flex-col">
      {/* Hidden file input for import */}
      <input
        type="file"
        accept=".json"
        onChange={handleFileChange}
        style={{ display: 'none' }}
        ref={fileInputRef}
      />

      {/* Sticky Header: title + save button */}
      <div className="flex items-center justify-between pb-4 shrink-0">
        <h1 className="text-xl font-semibold">{t('workflows.editWorkflow')}</h1>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => fileInputRef.current?.click()}
          >
            <Upload className="size-4 mr-1" />
            {t('workflows.import')}
          </Button>
          <Button variant="outline" onClick={handleExport}>
            <Download className="size-4 mr-1" />
            {t('workflows.export')}
          </Button>
          <Button variant="outline" onClick={handlePublish}>
            <GitBranch className="size-4 mr-1" />
            {t('workflows.publish')}
          </Button>
          <Button onClick={handleSave} disabled={!isDirty || isSaving}>
            {isSaving ? t('common.saving') : t('common.save')}
          </Button>
        </div>
      </div>

      {/* Horizontal Tabs */}
      <Tabs
        key={id}
        value={activeTab}
        onValueChange={setActiveTab}
        className="flex flex-1 flex-col min-h-0"
      >
        <TabsList className="shrink-0">
          <TabsTrigger value="editor" className="gap-1.5">
            <Play className="size-3.5" />
            {t('workflows.editor')}
          </TabsTrigger>
          <TabsTrigger value="debug" className="gap-1.5">
            <Bug className="size-3.5" />
            {t('workflows.debugChat')}
            {activeTab === 'debug' && (
              <span
                className={`inline-block size-2 rounded-full ${
                  isWebSocketConnected ? 'bg-green-500' : 'bg-red-500'
                }`}
              />
            )}
          </TabsTrigger>
          <TabsTrigger value="config" className="gap-1.5">
            <Settings className="size-3.5" />
            {t('workflows.configuration')}
          </TabsTrigger>
          <TabsTrigger value="executions" className="gap-1.5">
            <BarChart3 className="size-3.5" />
            {t('workflows.executions')}
          </TabsTrigger>
        </TabsList>

        {/* Tab: Editor */}
        <TabsContent value="editor" className="flex-1 min-h-0 mt-4">
          <WorkflowEditorComponent />
        </TabsContent>

        {/* Tab: Debug Chat */}
        <TabsContent value="debug" className="flex-1 min-h-0 mt-4">
          <WorkflowDebugDialog
            open={activeTab === 'debug'}
            workflowId={id}
            isEmbedded={true}
            onConnectionStatusChange={setIsWebSocketConnected}
          />
        </TabsContent>

        {/* Tab: Configuration */}
        <TabsContent
          value="config"
          className="flex-1 min-h-0 overflow-y-auto mt-4"
        >
          <WorkflowFormComponent
            workflow={workflow}
            onWorkflowChange={setWorkflow}
            onDelete={handleDelete}
          />
        </TabsContent>

        {/* Tab: Executions */}
        <TabsContent
          value="executions"
          className="flex-1 min-h-0 overflow-y-auto mt-4"
        >
          <WorkflowExecutionsTab workflowId={id} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
