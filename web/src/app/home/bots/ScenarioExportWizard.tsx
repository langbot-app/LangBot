import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  ArrowLeft,
  ArrowRight,
  Check,
  Download,
  Loader2,
  Package,
} from 'lucide-react';
import { toast } from 'sonner';
import { httpClient } from '@/app/infra/http/HttpClient';
import type {
  Bot,
  Pipeline,
  Agent,
  KnowledgeBase,
  MCPServer,
} from '@/app/infra/entities/api';
import type { Plugin } from '@/app/infra/entities/plugin';
import type { ScenarioPackage } from '@/app/infra/entities/api/scenario';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from '@/components/ui/card';
import { cn } from '@/lib/utils';

type Selection = Record<
  | 'pipeline_uuids'
  | 'agent_uuids'
  | 'event_processor_uuids'
  | 'plugin_ids'
  | 'mcp_server_uuids'
  | 'knowledge_base_uuids',
  string[]
>;
const emptySelection = (): Selection => ({
  pipeline_uuids: [],
  agent_uuids: [],
  event_processor_uuids: [],
  plugin_ids: [],
  mcp_server_uuids: [],
  knowledge_base_uuids: [],
});
type Choice = {
  id: string;
  name: string;
  description?: string;
  group: keyof Selection;
};

export default function ScenarioExportWizard({
  open,
  onOpenChange,
  botId,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  botId?: string;
}) {
  const { t } = useTranslation();
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState(false);
  const [bots, setBots] = useState<Bot[]>([]);
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [plugins, setPlugins] = useState<Plugin[]>([]);
  const [servers, setServers] = useState<MCPServer[]>([]);
  const [bases, setBases] = useState<KnowledgeBase[]>([]);
  const [selectedBot, setSelectedBot] = useState('');
  const [selection, setSelection] = useState<Selection>(emptySelection);
  const [name, setName] = useState('');
  const [instructions, setInstructions] = useState('');
  const [preview, setPreview] = useState<ScenarioPackage | null>(null);
  const [publishOpen, setPublishOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setStep(0);
    setLoading(true);
    setError(false);
    setPreview(null);
    setSelection(emptySelection());
    setSelectedBot('');
    setName('');
    setInstructions('');
    // All choices come from the authenticated Workspace, never Marketplace.
    void Promise.all([
      httpClient.getBots(),
      httpClient.getPipelines(),
      httpClient.getAgents(),
      httpClient.getPlugins(),
      httpClient.getMCPServers(),
      httpClient.getKnowledgeBases(),
    ])
      .then(([b, p, a, plugins, mcp, kb]) => {
        if (cancelled) return;
        setBots(b.bots);
        setPipelines(p.pipelines);
        setAgents(a.agents);
        setPlugins(plugins.plugins);
        setServers(mcp.servers);
        setBases(kb.bases);
        const initial = b.bots.find((item) => item.uuid === botId);
        if (initial?.uuid) {
          setSelectedBot(initial.uuid);
          setName(initial.name);
          setSelection({
            ...emptySelection(),
            pipeline_uuids: (initial.event_bindings || [])
              .filter((route) => route.target_type === 'pipeline')
              .map((route) => route.target_uuid),
            agent_uuids: (initial.event_bindings || [])
              .filter((route) => route.target_type === 'agent')
              .map((route) => route.target_uuid),
            event_processor_uuids: (initial.plugin_processors || []).map(
              (item) => item.processor_uuid,
            ),
          });
        }
      })
      .catch(() => {
        if (!cancelled) setError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, botId]);

  const steps = [
    'platformStep',
    'pipelineStep',
    'agentStep',
    'extensionStep',
    'knowledgeStep',
  ];
  const toggle = (group: keyof Selection, id: string) => {
    setPreview(null);
    setSelection((current) => ({
      ...current,
      [group]: current[group].includes(id)
        ? current[group].filter((value) => value !== id)
        : [...current[group], id],
    }));
  };
  const chooseBot = (bot: Bot) => {
    if (!bot.uuid) return;
    setSelectedBot(bot.uuid);
    setName(bot.name);
    setPreview(null);
    setSelection({
      ...emptySelection(),
      pipeline_uuids: (bot.event_bindings || [])
        .filter((route) => route.target_type === 'pipeline')
        .map((route) => route.target_uuid),
      agent_uuids: (bot.event_bindings || [])
        .filter((route) => route.target_type === 'agent')
        .map((route) => route.target_uuid),
      event_processor_uuids: (bot.plugin_processors || []).map(
        (item) => item.processor_uuid,
      ),
    });
  };
  const choices: Choice[] =
    step === 1
      ? pipelines
          .filter((item) => item.uuid)
          .map((item) => ({
            id: item.uuid!,
            name: item.name,
            description: item.description,
            group: 'pipeline_uuids',
          }))
      : step === 2
        ? agents
            .filter((item) => item.uuid && item.kind === 'agent')
            .map((item) => ({
              id: item.uuid!,
              name: item.name,
              description: item.description,
              group: 'agent_uuids',
            }))
        : step === 3
          ? [
              ...plugins.map((item): Choice => {
                const meta = item.manifest.manifest.metadata;
                return {
                  id: `${meta.author}/${meta.name}`,
                  name: `${meta.author}/${meta.name}`,
                  description: meta.version,
                  group: 'plugin_ids',
                };
              }),
              ...agents
                .filter((item) => item.uuid && item.kind === 'event_processor')
                .map((item): Choice => ({
                  id: item.uuid!,
                  name: item.name,
                  description: t('scenario.processor'),
                  group: 'event_processor_uuids',
                })),
              ...servers
                .filter((item) => item.uuid)
                .map((item): Choice => ({
                  id: item.uuid!,
                  name: item.name,
                  description: `MCP · ${item.mode}`,
                  group: 'mcp_server_uuids',
                })),
            ]
          : bases
              .filter((item) => item.uuid)
              .map((item) => ({
                id: item.uuid!,
                name: item.name,
                description: item.description,
                group: 'knowledge_base_uuids',
              }));

  const makePreview = async () => {
    setBusy(true);
    try {
      setPreview(
        await httpClient.exportScenario(
          selectedBot,
          { name, instructions },
          selection,
        ),
      );
    } catch (error) {
      toast.error(
        error instanceof Error
          ? error.message
          : (error as { msg?: string })?.msg || t('scenario.failed'),
      );
    } finally {
      setBusy(false);
    }
  };
  const download = () => {
    if (!preview) return;
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(preview, null, 2)], {
        type: 'application/json',
      }),
    );
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = 'scenario.langbot-scene.json';
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    onOpenChange(false);
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(value) => {
        if (!busy) onOpenChange(value);
      }}
    >
      <DialogContent
        className="flex max-h-[85dvh] w-[calc(100%-2rem)] flex-col gap-0 overflow-hidden rounded-xl p-0 sm:max-w-3xl"
        aria-describedby="scenario-export-description"
        data-suspend-guided-tours
      >
        <div className="flex shrink-0 items-center gap-2 border-b px-4 py-4 sm:px-6">
          <Package className="size-5 text-primary" />
          <DialogTitle className="text-base sm:text-lg">
            {t('scenario.createPack')}
          </DialogTitle>
        </div>
        <div className="shrink-0 overflow-x-auto px-4 py-4 sm:px-6">
          <div className="flex items-center justify-center gap-1.5 sm:gap-2">
            {steps.map((key, index) => (
              <div key={key} className="flex items-center gap-1.5 sm:gap-2">
                <div
                  className={cn(
                    'flex size-7 items-center justify-center rounded-full text-xs font-medium transition-colors',
                    index <= step
                      ? 'bg-blue-600 text-white'
                      : 'bg-muted text-muted-foreground',
                  )}
                  aria-current={index === step ? 'step' : undefined}
                >
                  {index < step ? <Check className="size-3.5" /> : index + 1}
                </div>
                <span
                  className={cn(
                    'hidden text-sm sm:inline',
                    index === step
                      ? 'font-medium text-blue-600'
                      : 'text-muted-foreground',
                  )}
                >
                  {t(`scenario.${key}`)}
                </span>
                {index < 4 && (
                  <div
                    className={cn(
                      'h-px w-4 sm:w-8',
                      index < step ? 'bg-blue-600' : 'bg-border',
                    )}
                  />
                )}
              </div>
            ))}
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-6 sm:px-6">
          <div className="mx-auto max-w-4xl space-y-5">
            <div className="py-3">
              <h2 className="text-xl font-semibold">
                {t(`scenario.${steps[step]}`)}
              </h2>
              <DialogDescription
                id="scenario-export-description"
                className="mt-2"
              >
                {t('scenario.workspaceOnly')}
              </DialogDescription>
            </div>
            {loading ? (
              <div className="flex justify-center py-20">
                <Loader2 className="size-6 animate-spin text-muted-foreground" />
              </div>
            ) : error ? (
              <p role="alert" className="py-8 text-destructive">
                {t('scenario.failed')}
              </p>
            ) : (
              <>
                <p className="text-sm text-muted-foreground">
                  {t(
                    step === 0
                      ? 'scenario.platformHint'
                      : step === 4
                        ? 'scenario.knowledgeHint'
                        : step === 3
                          ? 'scenario.extensionHint'
                          : 'scenario.selectionHint',
                  )}
                </p>
                <div className="grid gap-3 sm:grid-cols-2">
                  {step === 0
                    ? bots.map((bot) => (
                        <button
                          type="button"
                          key={bot.uuid}
                          aria-pressed={selectedBot === bot.uuid}
                          onClick={() => chooseBot(bot)}
                          className={cn(
                            'rounded-xl border p-4 text-left transition-all hover:border-primary/50',
                            selectedBot === bot.uuid
                              ? 'border-primary bg-primary/5 ring-1 ring-primary'
                              : 'border-border',
                          )}
                        >
                          <div className="flex items-center justify-between gap-3">
                            <span className="font-medium">{bot.name}</span>
                            {selectedBot === bot.uuid && (
                              <Check className="size-4 text-primary" />
                            )}
                          </div>
                          <p className="mt-1 text-sm text-muted-foreground">
                            {bot.adapter}
                          </p>
                        </button>
                      ))
                    : choices.map((item) => (
                        <button
                          type="button"
                          key={`${item.group}:${item.id}`}
                          aria-pressed={selection[item.group].includes(item.id)}
                          onClick={() => toggle(item.group, item.id)}
                          className={cn(
                            'rounded-xl border p-4 text-left transition-all hover:border-primary/50',
                            selection[item.group].includes(item.id)
                              ? 'border-primary bg-primary/5 ring-1 ring-primary'
                              : 'border-border',
                          )}
                        >
                          <div className="flex items-center justify-between gap-3">
                            <span className="break-all font-medium">
                              {item.name}
                            </span>
                            {selection[item.group].includes(item.id) && (
                              <Check className="size-4 shrink-0 text-primary" />
                            )}
                          </div>
                          {item.description && (
                            <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">
                              {item.description}
                            </p>
                          )}
                        </button>
                      ))}
                </div>
                {(step === 0 ? bots.length === 0 : choices.length === 0) && (
                  <div className="rounded-xl border border-dashed p-10 text-center text-sm text-muted-foreground">
                    {t('scenario.noResources')}
                  </div>
                )}
                {step === 4 && (
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-base">
                        {t('scenario.exportReview')}
                      </CardTitle>
                      <CardDescription>{t('scenario.review')}</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <label className="block space-y-2 text-sm">
                        <span>{t('scenario.name')}</span>
                        <Input
                          value={name}
                          onChange={(event) => {
                            setName(event.target.value);
                            setPreview(null);
                          }}
                        />
                      </label>
                      <label className="block space-y-2 text-sm">
                        <span>{t('scenario.instructions')}</span>
                        <Textarea
                          value={instructions}
                          onChange={(event) => {
                            setInstructions(event.target.value);
                            setPreview(null);
                          }}
                        />
                      </label>
                      <p className="text-sm text-muted-foreground">
                        {t('scenario.selectionCount', {
                          count:
                            Object.values(selection).reduce(
                              (sum, items) => sum + items.length,
                              0,
                            ) + 1,
                        })}
                      </p>
                      {preview && (
                        <>
                          <p className="text-sm">
                            {t('scenario.previewReady', {
                              count: preview.resources.length,
                            })}
                          </p>
                          <ul className="space-y-1 text-sm">
                            {preview.resources.map((resource) => (
                              <li key={resource.id}>
                                {String(resource.data.name)} · {resource.kind}
                              </li>
                            ))}
                          </ul>
                          <details>
                            <summary className="cursor-pointer text-sm">
                              {t('scenario.preview')}
                            </summary>
                            <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap break-all rounded-lg bg-muted p-3 text-xs">
                              {JSON.stringify(preview, null, 2)}
                            </pre>
                          </details>
                        </>
                      )}
                    </CardContent>
                  </Card>
                )}
              </>
            )}
          </div>
        </div>
        <div className="flex shrink-0 items-center justify-between border-t px-4 py-4 sm:px-6">
          <Button
            variant="outline"
            disabled={busy}
            onClick={() =>
              step === 0 ? onOpenChange(false) : setStep(step - 1)
            }
          >
            <ArrowLeft className="mr-2 size-4" />
            {t(step === 0 ? 'scenario.cancel' : 'scenario.previous')}
          </Button>
          {step === 4 && preview && (
            <Button
              variant="outline"
              disabled={busy}
              onClick={() => setPublishOpen(true)}
            >
              {t('scenario.publishSpace')}
            </Button>
          )}
          {step < 4 ? (
            <Button
              disabled={loading || error || !selectedBot}
              onClick={() => setStep(step + 1)}
            >
              {t('scenario.next')}
              <ArrowRight className="ml-2 size-4" />
            </Button>
          ) : (
            <Button
              disabled={busy || !name.trim()}
              onClick={() => (preview ? download() : void makePreview())}
            >
              {busy ? (
                <Loader2 className="mr-2 size-4 animate-spin" />
              ) : preview ? (
                <Download className="mr-2 size-4" />
              ) : null}
              {t(preview ? 'scenario.download' : 'scenario.exportReview')}
            </Button>
          )}
        </div>
        <Dialog open={publishOpen} onOpenChange={setPublishOpen}>
          <DialogContent>
            <DialogTitle>{t('scenario.publishTitle')}</DialogTitle>
            <DialogDescription>
              {t('scenario.publishDescription')}
            </DialogDescription>
            <div className="rounded-lg border p-4">
              <p className="font-medium">{name}</p>
              <p className="mt-2 whitespace-pre-wrap text-sm text-muted-foreground">
                {instructions}
              </p>
            </div>
            <Button
              onClick={() => {
                toast.info(t('scenario.publishDone'));
                setPublishOpen(false);
              }}
            >
              {t('scenario.publishConfirm')}
            </Button>
          </DialogContent>
        </Dialog>
      </DialogContent>
    </Dialog>
  );
}
