import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import type {
  Agent,
  CommandProcessorDescriptor,
} from '@/app/infra/entities/api';
import { httpClient } from '@/app/infra/http/HttpClient';
import { extractI18nObject } from '@/i18n/I18nProvider';
import DynamicFormComponent from '@/app/home/components/dynamic-form/DynamicFormComponent';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { ScrollArea } from '@/components/ui/scroll-area';
import { commandSchemaDefaults } from './command-processors';

type CommandParameters = Record<string, Record<string, unknown>>;

/**
 * Per-bot settings of one plugin's commands.
 *
 * Saving the first time creates a command processor instance and binds it to
 * the bot; later saves update that instance. "Use defaults" unbinds it, so the
 * commands fall back to their schema defaults.
 */
export default function CommandConfigDialog({
  open,
  onOpenChange,
  descriptor,
  pluginLabel,
  instance,
  prefix,
  onBind,
  onUnbind,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  descriptor: CommandProcessorDescriptor;
  pluginLabel: string;
  instance?: Agent;
  prefix: string;
  onBind: (agent: Agent) => void;
  onUnbind: () => void;
}) {
  const { t } = useTranslation();
  const [parameters, setParameters] = useState<CommandParameters>({});
  const [saving, setSaving] = useState(false);
  const validators = useRef<Record<string, () => Promise<boolean>>>({});

  useEffect(() => {
    if (!open) return;
    validators.current = {};
    const stored = instance?.config?.command_config;
    setParameters(
      stored && typeof stored === 'object'
        ? (stored as CommandParameters)
        : commandSchemaDefaults(descriptor),
    );
  }, [open, instance, descriptor]);

  const commands = descriptor.commands.filter(
    (command) => command.config_schema.length > 0,
  );

  async function save() {
    if (saving) return;
    for (const validate of Object.values(validators.current)) {
      if (!(await validate())) return;
    }
    setSaving(true);
    const config = {
      plugin: { id: descriptor.plugin_id },
      command_config: parameters,
    };
    try {
      if (instance?.uuid) {
        await httpClient.updateAgent(instance.uuid, {
          component_ref: descriptor.id,
          config,
        });
        onBind({ ...instance, component_ref: descriptor.id, config });
        toast.success(t('bots.pluginHooks.commandConfig.saved'));
      } else {
        const agent: Agent = {
          name: pluginLabel,
          description: '',
          emoji: '⌨️',
          kind: 'command_processor',
          component_ref: descriptor.id,
          config,
        };
        const result = await httpClient.createAgent(agent);
        onBind({ ...agent, uuid: result.uuid });
        toast.success(t('bots.pluginHooks.commandConfig.created'));
      }
      onOpenChange(false);
    } catch {
      toast.error(t('agents.saveError'));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="sm:max-w-lg"
        data-testid="command-config-dialog"
      >
        <DialogHeader>
          <DialogTitle className="text-base">
            {t('bots.pluginHooks.commandConfig.title', { plugin: pluginLabel })}
          </DialogTitle>
          <DialogDescription className="text-xs">
            {t('bots.pluginHooks.commandConfig.description')}
          </DialogDescription>
        </DialogHeader>
        <ScrollArea className="max-h-[60vh]">
          <div className="space-y-5 pr-3">
            {commands.map((command) => {
              const label =
                extractI18nObject({
                  en_US: command.name,
                  zh_Hans: command.name,
                  ...command.label,
                }) || command.name;
              return (
                <section key={command.name} className="space-y-2">
                  <h4 className="flex items-baseline gap-2 text-sm font-medium">
                    <code className="font-mono">
                      {prefix}
                      {command.name}
                    </code>
                    {label !== command.name && (
                      <span className="text-xs font-normal text-muted-foreground">
                        {label}
                      </span>
                    )}
                  </h4>
                  <DynamicFormComponent
                    key={`${instance?.uuid ?? 'new'}:${command.name}`}
                    itemConfigList={command.config_schema}
                    initialValues={parameters[command.name] ?? {}}
                    onSubmit={(values) =>
                      setParameters((current) => ({
                        ...current,
                        [command.name]: values as Record<string, unknown>,
                      }))
                    }
                    onValidate={(fn) => {
                      validators.current[command.name] = fn;
                    }}
                  />
                </section>
              );
            })}
          </div>
        </ScrollArea>
        <DialogFooter className="gap-2 sm:justify-between">
          {instance ? (
            <Button
              type="button"
              variant="ghost"
              onClick={() => {
                onUnbind();
                onOpenChange(false);
              }}
            >
              {t('bots.pluginHooks.commandConfig.useDefaults')}
            </Button>
          ) : (
            <span />
          )}
          <Button type="button" onClick={() => void save()} disabled={saving}>
            {t('common.save')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
