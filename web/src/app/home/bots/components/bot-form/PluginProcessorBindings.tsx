import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import {
  Check,
  Plus,
  Settings2,
  ScrollText,
  TriangleAlert,
  X,
} from 'lucide-react';
import { toast } from 'sonner';
import { useSidebarData } from '@/app/home/components/home-sidebar/SidebarDataContext';
import type {
  Agent,
  PluginProcessorBinding,
  RunnerDescriptor,
} from '@/app/infra/entities/api';
import { httpClient } from '@/app/infra/http';
import { extractI18nObject } from '@/i18n/I18nProvider';
import {
  eventPatternLabel,
  processorEventCompatibility,
} from '@/app/home/components/event-patterns/event-pattern-groups';
import DynamicFormComponent from '@/app/home/components/dynamic-form/DynamicFormComponent';
import { AuthenticatedPluginIcon } from '@/components/AuthenticatedPluginIcon';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Switch } from '@/components/ui/switch';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';

function ProcessorEvents({
  patterns = [],
  supportedEvents,
}: {
  patterns?: string[];
  supportedEvents: string[];
}) {
  const { t } = useTranslation();
  const { entries, matchingEvents } = processorEventCompatibility(
    patterns,
    supportedEvents,
  );
  const incomplete = entries.some((entry) => !entry.supported);

  return (
    <span className="block text-xs">
      <span
        role="list"
        className="flex flex-wrap gap-x-2 gap-y-1 whitespace-normal"
      >
        {entries.map(({ pattern, supported }) => (
          <span
            role="listitem"
            key={pattern}
            title={pattern}
            className={`inline-flex items-center gap-1 ${supported ? 'text-muted-foreground' : 'text-amber-700 dark:text-amber-400'}`}
          >
            {!supported && (
              <TriangleAlert className="size-3.5 shrink-0" aria-hidden="true" />
            )}
            {eventPatternLabel(pattern, t)}
          </span>
        ))}
      </span>
      {incomplete && (
        <span
          role="status"
          className="mt-2 flex items-start gap-1.5 whitespace-normal text-amber-700 dark:text-amber-400"
        >
          <TriangleAlert
            className="mt-0.5 size-3.5 shrink-0"
            aria-hidden="true"
          />
          <span>
            {t('bots.pluginSubscriptions.incompleteEvents', {
              events:
                matchingEvents
                  .map((pattern) => eventPatternLabel(pattern, t))
                  .join(' · ') || t('common.none'),
            })}
          </span>
        </span>
      )}
    </span>
  );
}

export default function PluginProcessorBindings({
  value,
  onChange,
  agents,
  onCreated,
  supportedEvents,
}: {
  value: PluginProcessorBinding[];
  onChange: (value: PluginProcessorBinding[]) => void;
  agents: Agent[];
  onCreated: (agent: Agent) => void;
  supportedEvents: string[];
}) {
  const { t } = useTranslation();
  const { refreshPipelines } = useSidebarData();
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState('existing');
  const [selected, setSelected] = useState<string[]>([]);
  const [components, setComponents] = useState<RunnerDescriptor[]>([]);
  const [componentRef, setComponentRef] = useState('');
  const [name, setName] = useState('');
  const [parameters, setParameters] = useState<Record<string, unknown>>({});
  const [busy, setBusy] = useState(false);
  const submitting = useRef(false);
  const validate = useRef<(() => Promise<boolean>) | null>(null);
  const component = components.find((item) => item.id === componentRef);
  const available = agents.filter(
    (agent) =>
      agent.kind === 'event_processor' &&
      agent.component_ref &&
      !value.some((item) => item.processor_uuid === agent.uuid),
  );

  async function showDialog() {
    setSelected([]);
    setMode(available.length ? 'existing' : 'new');
    setOpen(true);
    try {
      const metadata = await httpClient.getAgentMetadata();
      setComponents(metadata.event_processors ?? []);
    } catch {
      toast.error(t('agents.eventProcessor.loadError'));
    }
  }

  async function add() {
    if (submitting.current) return;
    if (mode === 'existing') {
      if (!selected.length) return;
      onChange([
        ...value,
        ...selected.map((processor_uuid) => ({
          processor_uuid,
          enabled: true,
        })),
      ]);
      setOpen(false);
      return;
    }
    if (!component || !name.trim()) return;
    submitting.current = true;
    setBusy(true);
    try {
      if (!((await validate.current?.()) ?? true)) return;
      const agent: Agent = {
        name: name.trim(),
        description: '',
        emoji: '🧩',
        kind: 'event_processor',
        component_ref: componentRef,
        config: {
          runner: { id: componentRef },
          runner_config: { [componentRef]: parameters },
        },
      };
      const result = await httpClient.createAgent(agent);
      onCreated({
        ...agent,
        uuid: result.uuid,
        supported_event_patterns: component.supported_event_patterns,
      });
      onChange([...value, { processor_uuid: result.uuid, enabled: true }]);
      void refreshPipelines();
      setOpen(false);
      setName('');
      setComponentRef('');
      setParameters({});
      toast.success(t('bots.pluginSubscriptions.created'));
    } catch (error) {
      toast.error(
        t('agents.createError') +
          ((error as { msg?: string }).msg ??
            t('agents.eventProcessor.loadError')),
      );
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  }

  return (
    <section
      className="mt-6 space-y-3 border-t pt-5"
      aria-labelledby="plugin-subscriptions-title"
    >
      <h3
        id="plugin-subscriptions-title"
        className="text-sm font-semibold text-foreground"
      >
        {t('agents.eventProcessor.type')}
      </h3>
      <p className="text-sm text-muted-foreground">
        {t('bots.pluginSubscriptions.description')}
      </p>
      {value.length === 0 && (
        <div className="flex h-32 items-center justify-center rounded-lg border-2 border-dashed border-border">
          <p className="text-sm text-muted-foreground">
            {t('bots.pluginSubscriptions.empty')}
          </p>
        </div>
      )}
      {value.map((binding) => {
        const agent = agents.find(
          (item) => item.uuid === binding.processor_uuid,
        );
        const title = agent?.name ?? t('agents.eventProcessor.unavailable');
        return (
          <Card
            key={binding.processor_uuid}
            className="gap-0 rounded-lg py-0 shadow-none"
          >
            <CardContent className="flex items-center gap-3 p-3">
              <span
                className="flex size-10 shrink-0 items-center justify-center rounded-lg border bg-muted text-2xl"
                aria-hidden="true"
              >
                {agent?.emoji || '🧩'}
              </span>
              <div className="min-w-0 flex-1">
                <div className="truncate font-medium">{title}</div>
                <p
                  className="truncate text-sm text-muted-foreground"
                  title={agent?.component_ref?.replace('plugin:', '')}
                >
                  {agent?.component_ref?.replace('plugin:', '')}
                </p>
                <ProcessorEvents
                  patterns={agent?.supported_event_patterns}
                  supportedEvents={supportedEvents}
                />
              </div>
              <div className="flex shrink-0 items-center gap-1">
                {agent &&
                  (
                    [
                      ['config', Settings2, 'configure'],
                      ['logs', ScrollText, 'logs'],
                    ] as const
                  ).map(([tab, Icon, key]) => (
                    <Tooltip key={tab}>
                      <TooltipTrigger asChild>
                        <Button
                          asChild
                          variant="ghost"
                          size="icon"
                          className="size-8"
                        >
                          <Link
                            target="_blank"
                            rel="noopener noreferrer"
                            to={`/home/agents?id=${agent.uuid}&tab=${tab}`}
                            aria-label={t(`bots.pluginSubscriptions.${key}`)}
                          >
                            <Icon className="size-4" />
                          </Link>
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>
                        {t(`bots.pluginSubscriptions.${key}`)}
                      </TooltipContent>
                    </Tooltip>
                  ))}
                <Switch
                  aria-label={t('bots.pluginSubscriptions.enable', {
                    name: title,
                  })}
                  checked={binding.enabled}
                  onCheckedChange={(enabled) =>
                    onChange(
                      value.map((item) =>
                        item.processor_uuid === binding.processor_uuid
                          ? { ...item, enabled }
                          : item,
                      ),
                    )
                  }
                />
                <Button
                  type="button"
                  size="icon"
                  variant="ghost"
                  aria-label={t('bots.pluginSubscriptions.remove', {
                    name: title,
                  })}
                  onClick={() =>
                    onChange(
                      value.filter(
                        (item) =>
                          item.processor_uuid !== binding.processor_uuid,
                      ),
                    )
                  }
                >
                  <X className="size-4" />
                </Button>
              </div>
            </CardContent>
          </Card>
        );
      })}
      <Button
        type="button"
        variant="outline"
        className="w-full"
        onClick={showDialog}
      >
        <Plus className="size-4" />
        {t('bots.pluginSubscriptions.add')}
      </Button>
      <Dialog
        open={open}
        onOpenChange={(next) => {
          if (!busy) setOpen(next);
        }}
      >
        <DialogContent className="flex max-h-[80vh] flex-col overflow-hidden sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>{t('bots.pluginSubscriptions.add')}</DialogTitle>
            <DialogDescription>
              {t('bots.pluginSubscriptions.saveHint')}
            </DialogDescription>
          </DialogHeader>
          <Tabs
            value={mode}
            onValueChange={setMode}
            className="min-h-0 overflow-y-auto"
          >
            <TabsList className="w-full">
              <TabsTrigger value="existing" disabled={busy}>
                {t('bots.pluginSubscriptions.existing')}
              </TabsTrigger>
              <TabsTrigger value="new" disabled={busy}>
                {t('bots.pluginSubscriptions.new')}
              </TabsTrigger>
            </TabsList>
            <TabsContent value="existing" className="space-y-3">
              <div className="max-h-80 space-y-2 overflow-y-auto">
                {available.map((agent) => (
                  <label
                    key={agent.uuid}
                    className="flex cursor-pointer items-center gap-3 rounded-lg border p-3 hover:bg-accent"
                  >
                    <Checkbox
                      checked={selected.includes(agent.uuid!)}
                      onCheckedChange={(checked) =>
                        setSelected((current) =>
                          checked
                            ? [...current, agent.uuid!]
                            : current.filter((id) => id !== agent.uuid),
                        )
                      }
                    />
                    <span
                      className="flex size-10 shrink-0 items-center justify-center rounded-lg border bg-muted text-2xl"
                      aria-hidden="true"
                    >
                      {agent.emoji || '🧩'}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium">
                        {agent.name}
                      </span>
                      <span className="block truncate text-sm text-muted-foreground">
                        {agent.component_ref?.replace('plugin:', '')}
                      </span>
                      <ProcessorEvents
                        patterns={agent.supported_event_patterns}
                        supportedEvents={supportedEvents}
                      />
                    </span>
                  </label>
                ))}
              </div>
              {available.length === 0 && (
                <p className="text-sm text-muted-foreground">
                  {t('bots.pluginSubscriptions.noExisting')}
                </p>
              )}
              <p className="text-sm text-muted-foreground">
                {t('bots.pluginSubscriptions.shared')}
              </p>
            </TabsContent>
            <TabsContent value="new">
              <fieldset disabled={busy} className="space-y-4">
                <div
                  className="max-h-60 space-y-2 overflow-y-auto"
                  role="group"
                  aria-label={t('agents.eventProcessor.component')}
                >
                  {components.map((descriptor) => {
                    const label = extractI18nObject({
                      en_US: descriptor.id,
                      zh_Hans: descriptor.id,
                      ...descriptor.label,
                    });
                    return (
                      <Button
                        key={descriptor.id}
                        type="button"
                        variant="outline"
                        aria-pressed={componentRef === descriptor.id}
                        className="h-auto w-full justify-start gap-3 whitespace-normal p-3 text-left font-normal shadow-none aria-pressed:bg-accent"
                        onClick={() => {
                          setComponentRef(descriptor.id);
                          validate.current = null;
                          setParameters(
                            Object.fromEntries(
                              (descriptor.config_schema ?? [])
                                .filter((field) => field.default !== undefined)
                                .map((field) => [field.name, field.default]),
                            ),
                          );
                          if (!name.trim()) setName(label);
                        }}
                      >
                        <AuthenticatedPluginIcon
                          author={descriptor.plugin_author}
                          name={descriptor.plugin_name}
                          className="size-10 shrink-0 rounded-lg border bg-muted object-cover"
                        />
                        <span className="min-w-0 flex-1">
                          <span className="block truncate font-medium">
                            {label}
                          </span>
                          <span className="block truncate text-sm text-muted-foreground">
                            {descriptor.plugin_author}/{descriptor.plugin_name}
                          </span>
                          <ProcessorEvents
                            patterns={descriptor.supported_event_patterns}
                            supportedEvents={supportedEvents}
                          />
                        </span>
                        {componentRef === descriptor.id && (
                          <Check className="size-4 shrink-0" />
                        )}
                      </Button>
                    );
                  })}
                  {components.length === 0 && (
                    <p className="py-6 text-center text-sm text-muted-foreground">
                      {t('agents.eventProcessor.noComponents')}
                    </p>
                  )}
                </div>
                {component && (
                  <div className="space-y-2">
                    <Label htmlFor="new-plugin-processor-name">
                      {t('common.name')}
                    </Label>
                    <Input
                      id="new-plugin-processor-name"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                    />
                  </div>
                )}
                {component && (
                  <DynamicFormComponent
                    key={componentRef}
                    itemConfigList={component.config_schema}
                    initialValues={parameters}
                    onSubmit={(values) =>
                      setParameters(values as Record<string, unknown>)
                    }
                    onValidate={(fn) => {
                      validate.current = fn;
                    }}
                  />
                )}
              </fieldset>
            </TabsContent>
          </Tabs>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              disabled={busy}
              onClick={() => setOpen(false)}
            >
              {t('common.cancel')}
            </Button>
            <Button
              type="button"
              disabled={
                busy ||
                (mode === 'existing'
                  ? !selected.length
                  : !component || !name.trim())
              }
              onClick={add}
            >
              {t(
                mode === 'existing'
                  ? 'bots.pluginSubscriptions.add'
                  : 'bots.pluginSubscriptions.createAndBind',
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}
