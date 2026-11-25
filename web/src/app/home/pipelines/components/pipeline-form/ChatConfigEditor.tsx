import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { useTranslation } from 'react-i18next';
import { useWatch, type Control } from 'react-hook-form';
import {
  BookOpen,
  Bot,
  Box,
  Copy,
  Cpu,
  FileOutput,
  Gauge,
  MessageSquareText,
  MessagesSquare,
  Mic,
  ScrollText,
  Settings2,
  SlidersHorizontal,
  Trash2,
  Volume2,
  Wrench,
  type LucideIcon,
} from 'lucide-react';
import type { IDynamicFormItemSchema } from '@/app/infra/entities/form/dynamic';
import type {
  PipelineConfigStage,
  PipelineConfigTab,
} from '@/app/infra/entities/pipeline';
import { backendClient } from '@/app/infra/http';
import { extractI18nObject } from '@/i18n/I18nProvider';
import DynamicFormComponent from '@/app/home/components/dynamic-form/DynamicFormComponent';
import { collectSensitiveTools } from '@/app/home/components/sensitive-tools/SensitiveToolsWarning';
import {
  SettingGroup,
  SettingRow,
} from '@/app/home/components/setting-row/SettingRow';
import PipelineExtension from '@/app/home/pipelines/components/pipeline-extensions/PipelineExtension';
import { Button } from '@/components/ui/button';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { Skeleton } from '@/components/ui/skeleton';
import { preserveRunnerConfig } from './RunnerConfigPreservation';

type Values = Record<string, unknown>;
type FormName = 'ai' | 'speech' | 'output';

const k = (key: string) => `pipelines.chatConfig.${key}`;

// --- Field classification -------------------------------------------------
// Runners describe their settings as one flat schema. These rules place the
// fields a bot owner touches most (model, prompt, knowledge) up front and
// fold the rest into named rows. Unknown fields fall back to the runner's
// own settings block, or "other advanced" when the runner marks them as such.

const MODEL_TYPES = new Set(['model-fallback-selector', 'llm-model-selector']);
const PROMPT_TYPES = new Set(['prompt-editor']);
const KNOWLEDGE_TYPES = new Set([
  'knowledge-base-multi-selector',
  'knowledge-base-selector',
]);
const RETRIEVAL_FIELDS = new Set([
  'retrieval-top-k',
  'rerank-model',
  'rerank-top-k',
]);
const RUNTIME_FIELDS = new Set([
  'timeout',
  'max-tool-iterations',
  'tool-execution-mode',
  'max-tool-result-chars',
  'workspace-direct-threshold',
]);
/** Display-only toggle that used to reveal advanced fields; rows replace it. */
const ADVANCED_TOGGLE = 'advanced-settings';
/** Mirrored by the reply-content row (`output.misc.remove-think`). */
const MIRRORED_FIELDS = new Set(['remove-think']);

function isAdvanced(item: IDynamicFormItemSchema) {
  return item.show_if?.field === ADVANCED_TOGGLE;
}

interface RunnerFieldGroups {
  model: IDynamicFormItemSchema[];
  prompt: IDynamicFormItemSchema[];
  knowledge: IDynamicFormItemSchema[];
  retrieval: IDynamicFormItemSchema[];
  context: IDynamicFormItemSchema[];
  runtime: IDynamicFormItemSchema[];
  sandbox: IDynamicFormItemSchema[];
  basic: IDynamicFormItemSchema[];
  advanced: IDynamicFormItemSchema[];
}

function groupRunnerFields(items: IDynamicFormItemSchema[]): RunnerFieldGroups {
  const groups: RunnerFieldGroups = {
    model: [],
    prompt: [],
    knowledge: [],
    retrieval: [],
    context: [],
    runtime: [],
    sandbox: [],
    basic: [],
    advanced: [],
  };
  for (const item of items) {
    if (item.name === ADVANCED_TOGGLE || MIRRORED_FIELDS.has(item.name))
      continue;
    if (MODEL_TYPES.has(item.type)) groups.model.push(item);
    else if (PROMPT_TYPES.has(item.type)) groups.prompt.push(item);
    else if (KNOWLEDGE_TYPES.has(item.type)) groups.knowledge.push(item);
    else if (RETRIEVAL_FIELDS.has(item.name)) groups.retrieval.push(item);
    else if (item.name.startsWith('context-') || item.name === 'date-grounding')
      groups.context.push(item);
    else if (RUNTIME_FIELDS.has(item.name)) groups.runtime.push(item);
    else if (item.name.startsWith('box-')) groups.sandbox.push(item);
    else if (isAdvanced(item)) groups.advanced.push(item);
    else groups.basic.push(item);
  }
  return groups;
}

/** Fields whose value differs from their schema default. */
function modifiedCount(items: IDynamicFormItemSchema[], values: Values) {
  return items.filter((item) => {
    const value = values[item.name];
    if (value === undefined) return false;
    return JSON.stringify(value) !== JSON.stringify(item.default ?? null);
  }).length;
}

/**
 * Edits a subset of one stored object. The latest stored object is read at
 * write time, so several subsets of the same object never overwrite each
 * other, and untouched keys (including ones no form shows) are preserved.
 */
function SubsetForm({
  items,
  read,
  write,
  systemContext,
  renderItem,
}: {
  items: IDynamicFormItemSchema[];
  read: () => Values;
  write: (next: Values) => void;
  systemContext?: Values;
  renderItem?: Parameters<typeof DynamicFormComponent>[0]['renderItem'];
}) {
  const previous = useRef<Values | undefined>(undefined);
  if (items.length === 0) return null;
  return (
    <DynamicFormComponent
      itemConfigList={items}
      // Always the latest stored object: re-syncing from it never discards
      // an edit made through this or a sibling subset.
      initialValues={read()}
      systemContext={systemContext}
      // Fields in other subsets (and the retired advanced toggle) still
      // drive show_if conditions here.
      externalDependentValues={{ ...read(), [ADVANCED_TOGGLE]: true }}
      renderItem={renderItem}
      onSubmit={(emitted) => {
        const values = emitted as Values;
        const current = read();
        const next = preserveRunnerConfig(current, previous.current, values);
        previous.current = structuredClone(values);
        if (JSON.stringify(next) !== JSON.stringify(current)) write(next);
      }}
    />
  );
}

/** Re-renders only its own summary text when the watched value changes. */
function Watch<T>({
  control,
  name,
  children,
}: {
  control: Control<any>;
  name: string;
  children: (value: T) => ReactNode;
}) {
  const value = useWatch({ control, name }) as T;
  return <>{children(value)}</>;
}

function PrimaryBlock({
  icon: Icon,
  guide,
  title,
  hint,
  action,
  children,
}: {
  icon: LucideIcon;
  guide?: string;
  title?: string;
  hint?: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section
      data-guide={guide}
      className="flex gap-3 rounded-lg border bg-card p-4"
    >
      <span className="flex size-8 shrink-0 items-center justify-center rounded-md border bg-background text-primary">
        <Icon className="size-4" />
      </span>
      <div className="min-w-0 flex-1 space-y-3">
        {(title || action) && (
          <div className="flex items-start justify-between gap-3">
            <div>
              {title && <h3 className="text-sm font-semibold">{title}</h3>}
              {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
            </div>
            {action}
          </div>
        )}
        {children}
      </div>
    </section>
  );
}

type Extensions = Awaited<
  ReturnType<typeof backendClient.getPipelineExtensions>
>;

function ToolsBlock({
  pipelineId,
  onSensitiveToolsChange,
}: {
  pipelineId: string;
  onSensitiveToolsChange?: (tools: string[]) => void;
}) {
  const { t } = useTranslation();
  const [data, setData] = useState<Extensions | null>(null);
  const [open, setOpen] = useState(false);

  const load = useCallback(() => {
    backendClient
      .getPipelineExtensions(pipelineId)
      .then((next) => {
        setData(next);
        onSensitiveToolsChange?.(
          collectSensitiveTools(
            next.available_platform_tools ?? [],
            next.allowed_platform_tools ?? [],
            next.available_workspace_operations ?? [],
            next.workspace_operations ?? [],
          ),
        );
      })
      .catch(() => setData(null));
  }, [pipelineId, onSensitiveToolsChange]);

  useEffect(() => {
    load();
  }, [load]);

  const count = (all: boolean, bound: number) =>
    all
      ? t(k('all'))
      : bound > 0
        ? t(k('countItems'), { count: bound })
        : t(k('none'));
  const stats = data
    ? [
        {
          label: t(k('plugins')),
          value: count(data.enable_all_plugins, data.bound_plugins.length),
        },
        {
          label: t(k('mcp')),
          value: count(
            data.enable_all_mcp_servers,
            data.bound_mcp_servers.length,
          ),
        },
        {
          label: t(k('skills')),
          value: count(data.enable_all_skills, data.bound_skills.length),
        },
        {
          label: t(k('operations')),
          value: count(
            false,
            (data.allowed_platform_tools?.length ?? 0) +
              (data.workspace_operations?.length ?? 0),
          ),
        },
      ]
    : [];

  return (
    <PrimaryBlock
      icon={Wrench}
      guide="pipeline-section-extensions"
      title={t(k('tools'))}
      hint={t(k('toolsHint'))}
      action={
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => setOpen(true)}
          data-testid="chat-manage-tools"
        >
          {t(k('manageTools'))}
        </Button>
      }
    >
      {data ? (
        <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {stats.map((stat) => (
            <div key={stat.label} className="rounded-md bg-muted/40 px-3 py-2">
              <dt className="text-xs text-muted-foreground">{stat.label}</dt>
              <dd className="text-sm font-medium">{stat.value}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <Skeleton className="h-12 w-full" />
      )}
      <Sheet
        open={open}
        onOpenChange={(next) => {
          setOpen(next);
          if (!next) load();
        }}
      >
        <SheetContent className="w-full overflow-y-auto sm:max-w-2xl">
          <SheetHeader>
            <SheetTitle>{t(k('tools'))}</SheetTitle>
            <SheetDescription>{t(k('toolsSheetDescription'))}</SheetDescription>
          </SheetHeader>
          <div className="px-4 pb-6">
            <PipelineExtension
              pipelineId={pipelineId}
              onSensitiveToolsChange={onSensitiveToolsChange}
            />
          </div>
        </SheetContent>
      </Sheet>
    </PrimaryBlock>
  );
}

/**
 * Chat (pipeline) settings, arranged by importance: who answers, then the
 * model, prompt, tools and knowledge the answer is built from, then
 * everything else as collapsed rows with a one-line summary.
 */
export default function ChatConfigEditor({
  control,
  getValues,
  aiTab,
  speechTab,
  outputTab,
  runnerId,
  onStage,
  onRunnerConfig,
  renderRunnerSelect,
  systemContext,
  pipelineId,
  onSensitiveToolsChange,
  onCopy,
  onDelete,
  isDefaultPipeline,
}: {
  control: Control<any>;
  getValues: (path: string) => unknown;
  aiTab: PipelineConfigTab;
  speechTab?: PipelineConfigTab;
  outputTab?: PipelineConfigTab;
  runnerId: string;
  /** Write one stage. `fromEdit` marks a user edit (not a mount emission). */
  onStage: (
    formName: FormName,
    stage: string,
    values: Values,
    fromEdit?: boolean,
  ) => void;
  onRunnerConfig: (stage: string, values: Values) => void;
  renderRunnerSelect: Parameters<typeof DynamicFormComponent>[0]['renderItem'];
  systemContext: Values;
  pipelineId: string;
  onSensitiveToolsChange?: (tools: string[]) => void;
  onCopy: () => void;
  onDelete: () => void;
  isDefaultPipeline: boolean;
}) {
  const { t } = useTranslation();
  const runnerStage = aiTab.stages.find((stage) => stage.name === 'runner');
  const runnerConfigStage = aiTab.stages.find(
    (stage) => stage.name === runnerId,
  );
  // Stable field lists: a new list identity makes the form re-sync.
  const groups = useMemo(
    () => groupRunnerFields(runnerConfigStage?.config ?? []),
    [runnerConfigStage],
  );
  const runnerIdItems = useMemo(
    () => (runnerStage?.config ?? []).filter((item) => item.name === 'id'),
    [runnerStage],
  );
  const runnerContextItems = useMemo(
    () => (runnerStage?.config ?? []).filter((item) => item.name !== 'id'),
    [runnerStage],
  );

  const readRunner = () => (getValues('ai.runner') as Values) ?? {};
  const writeRunner = (next: Values) => onStage('ai', 'runner', next, true);
  const readRunnerConfig = () =>
    ((getValues('ai.runner_config') as Record<string, Values>) ?? {})[
      runnerId
    ] ?? {};
  const writeRunnerConfig = (next: Values) => onRunnerConfig(runnerId, next);
  const outputMisc = outputTab?.stages.find((stage) => stage.name === 'misc');
  const readOutputMisc = () =>
    ((getValues('output') as Record<string, Values>) ?? {}).misc ?? {};
  const writeOutputMisc = (next: Values) =>
    onStage('output', 'misc', next, true);
  const replyItems = useMemo(
    () => (outputMisc?.config ?? []).filter((item) => item.type === 'boolean'),
    [outputMisc],
  );
  const hintItems = useMemo(
    () => (outputMisc?.config ?? []).filter((item) => item.type !== 'boolean'),
    [outputMisc],
  );

  const runnerForm = (items: IDynamicFormItemSchema[]) => (
    <SubsetForm
      key={`${runnerId}:${items.map((item) => item.name).join(',')}`}
      items={items}
      read={readRunnerConfig}
      write={writeRunnerConfig}
      systemContext={systemContext}
    />
  );
  const runnerLabel = runnerConfigStage
    ? extractI18nObject(runnerConfigStage.label)
    : '';
  const configPath = `ai.runner_config`;

  function speechRow(stage: PipelineConfigStage, icon: LucideIcon) {
    return (
      <Watch<Values>
        key={stage.name}
        control={control}
        name={`speech.${stage.name}`}
      >
        {(value) => (
          <SettingRow
            id={stage.name}
            icon={icon}
            guide={
              stage.name === 'speech-recognition'
                ? 'pipeline-section-speech'
                : undefined
            }
            title={extractI18nObject(stage.label)}
            summary={value?.enable ? t(k('on')) : t(k('off'))}
          >
            {stage.description && (
              <p className="text-xs text-muted-foreground">
                {extractI18nObject(stage.description)}
              </p>
            )}
            <DynamicFormComponent
              itemConfigList={stage.config}
              initialValues={
                (getValues(`speech.${stage.name}`) as Values) ?? {}
              }
              systemContext={systemContext}
              onSubmit={(values) =>
                onStage('speech', stage.name, values as Values)
              }
            />
          </SettingRow>
        )}
      </Watch>
    );
  }

  return (
    <div className="space-y-6" data-testid="chat-config">
      {/* Who answers */}
      <PrimaryBlock icon={Bot} guide="pipeline-section-ai">
        <SubsetForm
          items={runnerIdItems}
          read={readRunner}
          write={writeRunner}
          systemContext={systemContext}
          renderItem={renderRunnerSelect}
        />
        <p className="text-xs text-muted-foreground">
          {t('pipelines.extensions.runnerScopeHint')}
        </p>
        {runnerConfigStage?.description && (
          <p className="text-xs text-muted-foreground">
            {extractI18nObject(runnerConfigStage.description)}
          </p>
        )}
      </PrimaryBlock>

      {/* What the answer is built from */}
      {groups.model.length > 0 && (
        <PrimaryBlock icon={Cpu}>{runnerForm(groups.model)}</PrimaryBlock>
      )}
      {groups.prompt.length > 0 && (
        <PrimaryBlock icon={ScrollText}>
          {runnerForm(groups.prompt)}
        </PrimaryBlock>
      )}
      <ToolsBlock
        pipelineId={pipelineId}
        onSensitiveToolsChange={onSensitiveToolsChange}
      />
      {groups.knowledge.length > 0 && (
        <PrimaryBlock icon={BookOpen}>
          {runnerForm(groups.knowledge)}
          {groups.retrieval.length > 0 && (
            <Collapsible>
              <CollapsibleTrigger asChild>
                <Button
                  type="button"
                  variant="link"
                  size="sm"
                  className="h-auto p-0 text-xs text-muted-foreground"
                >
                  {t(k('retrieval'))}
                </Button>
              </CollapsibleTrigger>
              <CollapsibleContent forceMount className="pt-3">
                {runnerForm(groups.retrieval)}
              </CollapsibleContent>
            </Collapsible>
          )}
        </PrimaryBlock>
      )}
      {groups.basic.length > 0 && (
        <PrimaryBlock
          icon={Settings2}
          title={t(k('runnerSettings'), { runner: runnerLabel })}
        >
          {runnerForm(groups.basic)}
        </PrimaryBlock>
      )}

      {/* Everything else, folded. Tour steps for speech and replies point
          at their rows, or at this group when the runner has none. */}
      <div
        data-guide={
          speechTab?.stages.length ? undefined : 'pipeline-section-speech'
        }
      >
        <div
          data-guide={replyItems.length ? undefined : 'pipeline-section-output'}
        >
          <SettingGroup title={t(k('more'))}>
            {(runnerContextItems.length > 0 || groups.context.length > 0) && (
              <Watch<Values> control={control} name="ai.runner">
                {(runner) => (
                  <SettingRow
                    id="context"
                    icon={MessagesSquare}
                    title={t(k('context'))}
                    summary={[
                      runner?.['group-context'] === 'group'
                        ? t(k('scopeGroup'))
                        : t(k('scopeMember')),
                      Number(runner?.['expire-time'] ?? 0) > 0
                        ? t(k('expireAfter'), {
                            seconds: Number(runner?.['expire-time']),
                          })
                        : t(k('expireNever')),
                    ].join(' · ')}
                  >
                    <SubsetForm
                      items={runnerContextItems}
                      read={readRunner}
                      write={writeRunner}
                      systemContext={systemContext}
                    />
                    {runnerForm(groups.context)}
                  </SettingRow>
                )}
              </Watch>
            )}
            {groups.runtime.length > 0 && (
              <Watch<Record<string, Values>>
                control={control}
                name={configPath}
              >
                {(configs) => {
                  const changed = modifiedCount(
                    groups.runtime,
                    configs?.[runnerId] ?? {},
                  );
                  return (
                    <SettingRow
                      id="runtime"
                      icon={Gauge}
                      title={t(k('runtime'))}
                      summary={
                        changed
                          ? t(k('modified'), { count: changed })
                          : t(k('default'))
                      }
                    >
                      {runnerForm(groups.runtime)}
                    </SettingRow>
                  );
                }}
              </Watch>
            )}
            {groups.sandbox.length > 0 && (
              <Watch<Record<string, Values>>
                control={control}
                name={configPath}
              >
                {(configs) => (
                  <SettingRow
                    id="sandbox"
                    icon={Box}
                    title={t(k('sandbox'))}
                    summary={
                      configs?.[runnerId]?.['box-enabled'] === false
                        ? t(k('off'))
                        : t(k('on'))
                    }
                  >
                    {runnerForm(groups.sandbox)}
                  </SettingRow>
                )}
              </Watch>
            )}
            {speechTab?.stages.map((stage) =>
              speechRow(stage, stage.name === 'text-to-speech' ? Volume2 : Mic),
            )}
            {replyItems.length > 0 && (
              <Watch<Values> control={control} name="output.misc">
                {(misc) => {
                  const on = replyItems.filter((item) => misc?.[item.name]);
                  return (
                    <SettingRow
                      id="reply"
                      icon={FileOutput}
                      guide="pipeline-section-output"
                      title={t(k('reply'))}
                      summary={
                        on.length
                          ? on
                              .map((item) => extractI18nObject(item.label))
                              .join(' · ')
                          : t(k('default'))
                      }
                    >
                      <p className="text-xs text-muted-foreground">
                        {t('pipelines.outputMovedToPolicy')}
                      </p>
                      <SubsetForm
                        items={replyItems}
                        read={readOutputMisc}
                        write={writeOutputMisc}
                        systemContext={systemContext}
                      />
                    </SettingRow>
                  );
                }}
              </Watch>
            )}
            {hintItems.length > 0 && (
              <Watch<Values> control={control} name="output.misc">
                {(misc) => {
                  const custom = hintItems.filter((item) =>
                    String(misc?.[item.name] ?? '').trim(),
                  ).length;
                  return (
                    <SettingRow
                      id="hints"
                      icon={MessageSquareText}
                      title={t(k('hints'))}
                      summary={
                        custom
                          ? t(k('hintsCustom'), { count: custom })
                          : t(k('default'))
                      }
                    >
                      <SubsetForm
                        items={hintItems}
                        read={readOutputMisc}
                        write={writeOutputMisc}
                        systemContext={systemContext}
                      />
                    </SettingRow>
                  );
                }}
              </Watch>
            )}
            {groups.advanced.length > 0 && (
              <Watch<Record<string, Values>>
                control={control}
                name={configPath}
              >
                {(configs) => {
                  const changed = modifiedCount(
                    groups.advanced,
                    configs?.[runnerId] ?? {},
                  );
                  return (
                    <SettingRow
                      id="advanced"
                      icon={SlidersHorizontal}
                      title={t(k('advanced'))}
                      summary={
                        changed
                          ? t(k('modified'), { count: changed })
                          : t(k('default'))
                      }
                    >
                      {runnerForm(groups.advanced)}
                    </SettingRow>
                  );
                }}
              </Watch>
            )}
            <SettingRow
              id="manage"
              icon={Settings2}
              guide="pipeline-section-basic"
              title={t(k('manage'))}
              summary={t(k('manageSummary'))}
            >
              <div className="flex items-center justify-between gap-4">
                <div className="space-y-0.5">
                  <p className="text-sm font-medium">
                    {t('pipelines.copyPipelineAction')}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {t('pipelines.copyPipelineHint')}
                  </p>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={onCopy}
                >
                  <Copy className="size-4" />
                  {t('common.copy')}
                </Button>
              </div>
              <div className="flex items-center justify-between gap-4">
                <div className="space-y-0.5">
                  <p className="text-sm font-medium text-destructive">
                    {t('pipelines.deletePipelineAction')}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {isDefaultPipeline
                      ? t('pipelines.defaultPipelineCannotDelete')
                      : t('pipelines.deletePipelineHint')}
                  </p>
                </div>
                <Button
                  type="button"
                  variant="destructive"
                  size="sm"
                  disabled={isDefaultPipeline}
                  onClick={onDelete}
                >
                  <Trash2 className="size-4" />
                  {t('common.delete')}
                </Button>
              </div>
            </SettingRow>
          </SettingGroup>
        </div>
      </div>
    </div>
  );
}
