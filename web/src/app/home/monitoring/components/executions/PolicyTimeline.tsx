import { useTranslation } from 'react-i18next';
import type { TFunction } from 'i18next';
import { Cpu, LogIn, Puzzle, Send } from 'lucide-react';
import type {
  ExecutionDetailItem,
  ExecutionRow,
} from '@/app/infra/entities/api/monitoring-executions';
import { cn } from '@/lib/utils';
import { pluginHandlerName, policyItemLabel } from './ExecutionTable';

type StepState = 'ok' | 'blocked' | 'denied' | 'failed' | 'skipped';

interface PolicyRoute {
  status?: string | null;
  target_type?: string | null;
  target_uuid?: string | null;
  failure_code?: string | null;
  policy_layer?: string | null;
  policy_item?: string | null;
  hook?: string | null;
  denied_reply?: string | null;
  command_kind?: string | null;
}

interface OutputAction {
  kind: string;
  strategy?: string;
  ms?: number;
}

interface PolicyEvent {
  type: string;
  actions?: OutputAction[];
  policy_layer?: string;
  policy_item?: string;
}

interface Step {
  key: 'admission' | 'hooks' | 'processor' | 'output';
  state: StepState;
  text: string;
  chips?: { label: string; warn?: boolean }[];
}

const ICONS = {
  admission: LogIn,
  hooks: Puzzle,
  processor: Cpu,
  output: Send,
};

const DOT: Record<StepState, string> = {
  ok: 'border-emerald-500 bg-emerald-500',
  blocked: 'border-amber-500 bg-amber-500',
  denied: 'border-red-500 bg-red-500',
  failed: 'border-red-500 bg-red-500',
  skipped: 'border-muted-foreground/40 bg-background',
};

/** The ingress `message.received` record carrying routes and policy events. */
export function policyIngress(
  items: ExecutionDetailItem[] | undefined,
): ExecutionDetailItem | null {
  return (
    items?.find(
      (item) =>
        item.event_type === 'message.received' &&
        item.metadata &&
        (Array.isArray(item.metadata.routes) ||
          Array.isArray(item.metadata.policy_events)),
    ) ?? null
  );
}

function layerLabel(layer: string | null | undefined, t: TFunction) {
  return layer
    ? t(`monitoring.execution.policyLayer.${layer}`, { defaultValue: layer })
    : t('monitoring.execution.timeline.unknownLayer');
}

function actionLabel(action: OutputAction, t: TFunction) {
  if (action.kind === 'long_text')
    return t('monitoring.execution.timeline.actions.long_text', {
      strategy: t(
        `monitoring.execution.timeline.actions.strategy.${action.strategy}`,
        { defaultValue: action.strategy ?? '' },
      ),
    });
  if (action.kind === 'delay')
    return t('monitoring.execution.timeline.actions.delay', {
      ms: action.ms ?? 0,
    });
  return t(`monitoring.execution.timeline.actions.${action.kind}`, {
    defaultValue: action.kind,
  });
}

function buildSteps(
  record: ExecutionRow,
  ingress: ExecutionDetailItem,
  t: TFunction,
): Step[] {
  const metadata = ingress.metadata ?? {};
  const routes = (
    Array.isArray(metadata.routes) ? metadata.routes : []
  ) as PolicyRoute[];
  const events = (
    Array.isArray(metadata.policy_events) ? metadata.policy_events : []
  ) as PolicyEvent[];
  const primary = routes[0] ?? {};
  const T = (key: string, options?: Record<string, unknown>) =>
    t(`monitoring.execution.timeline.${key}`, options);

  // 1. Admission: message policy of the bot default or the route override.
  const policyItem =
    (metadata.policy_item as string | undefined) ??
    (primary.failure_code === 'message_policy'
      ? primary.policy_item
      : undefined) ??
    (record.handling === 'policy' ? record.policy_item : undefined);
  const policyLayer =
    (metadata.policy_layer as string | undefined) ??
    primary.policy_layer ??
    record.policy_layer;
  const blocked = Boolean(
    policyItem ||
    primary.failure_code === 'message_policy' ||
    record.handling === 'policy',
  );
  // `*MessageReceived` runs before admission, so its interception skips it.
  const hookRoute = routes.find((route) => route.hook);
  const earlyHook = hookRoute?.hook === 'MessageReceived';
  const admission: Step = blocked
    ? {
        key: 'admission',
        state: 'blocked',
        text: policyItem
          ? T('blockedBy', {
              layer: layerLabel(policyLayer, t),
              item: policyItemLabel(policyItem, t),
            })
          : T('blocked'),
      }
    : earlyHook
      ? { key: 'admission', state: 'skipped', text: T('notReached') }
      : { key: 'admission', state: 'ok', text: T('admitted') };

  // 2. Lifecycle hooks: a plugin may intercept MessageReceived, CommandSent
  //    or NormalMessageReceived.
  const chatPlugin =
    record.source === 'pipeline' ? pluginHandlerName(record.handled_by) : null;
  const hookPlugin = hookRoute
    ? (pluginHandlerName(hookRoute.target_uuid) ?? hookRoute.target_uuid)
    : chatPlugin;
  const intercepted = Boolean(hookRoute || chatPlugin);
  const hooks: Step = intercepted
    ? {
        key: 'hooks',
        state: 'blocked',
        text: T('hookBy', {
          plugin: hookPlugin || '?',
          hook: hookRoute?.hook ?? 'NormalMessageReceived',
        }),
      }
    : blocked && !earlyHook
      ? // MessageReceived runs before admission, so it has already run here;
        // only the hooks after admission were skipped.
        { key: 'hooks', state: 'skipped', text: T('earlyHookOnly') }
      : { key: 'hooks', state: 'ok', text: T('noHook') };

  // 3. Processor: system command, plugin command, Chat or Agent.
  const denied = routes.find((route) => route.status === 'denied');
  let processor: Step;
  if (blocked || intercepted) {
    processor = { key: 'processor', state: 'skipped', text: T('notReached') };
  } else if (denied && routes.length === 1) {
    processor = {
      key: 'processor',
      state: 'denied',
      text: T('denied', {
        name: denied.target_uuid ?? '',
        reply: T(
          denied.denied_reply === 'notice' ? 'deniedNotice' : 'deniedSilent',
        ),
      }),
    };
  } else {
    const target = primary.target_type;
    const name = String(primary.target_uuid ?? '');
    const failed = primary.status === 'failed' || record.has_error;
    const text =
      target === 'builtin_command'
        ? T('builtin', { name })
        : target === 'plugin_command'
          ? T('pluginCommand', { name: name.split('/').pop() })
          : target === 'discard'
            ? T('discarded')
            : T('handledBy', {
                target:
                  record.target_name ||
                  record.pipeline_name ||
                  record.runner_id ||
                  name ||
                  '—',
              });
    processor = {
      key: 'processor',
      state: failed ? 'failed' : 'ok',
      text: denied
        ? `${T('denied', {
            name: denied.target_uuid ?? '',
            reply: T('deniedSilent'),
          })} → ${text}`
        : text,
    };
  }

  // 4. Output: long text, delay, @, quote and outbound content filter.
  const actions = events
    .filter((event) => event.type === 'output')
    .flatMap((event) => event.actions ?? []);
  const output: Step =
    processor.state === 'skipped' && actions.length === 0
      ? { key: 'output', state: 'skipped', text: T('notReached') }
      : actions.length === 0
        ? { key: 'output', state: 'ok', text: T('noOutput') }
        : {
            key: 'output',
            state: actions.some((action) => action.kind === 'outbound_block')
              ? 'blocked'
              : 'ok',
            text: T('outputApplied'),
            // One output event is recorded per sent message; show each
            // distinct action once.
            chips: [
              ...new Map(
                actions.map((action) => [
                  actionLabel(action, t),
                  {
                    label: actionLabel(action, t),
                    warn: action.kind === 'outbound_block',
                  },
                ]),
              ).values(),
            ],
          };
  return [admission, hooks, processor, output];
}

/**
 * "Why did / didn't the bot reply": admission → lifecycle hooks → processor →
 * output, read from the ingress event's route records and policy events.
 */
export default function PolicyTimeline({
  record,
  inputs,
}: {
  record: ExecutionRow;
  inputs: ExecutionDetailItem[] | undefined;
}) {
  const { t } = useTranslation();
  const ingress = policyIngress(inputs);
  if (!ingress) return null;
  const steps = buildSteps(record, ingress, t);
  return (
    <section
      className="space-y-2 rounded-lg border p-3"
      data-testid="policy-timeline"
    >
      <h3 className="text-sm font-semibold">
        {t('monitoring.execution.timeline.title')}
      </h3>
      <ol className="relative space-y-3">
        {steps.map((step, index) => {
          const Icon = ICONS[step.key];
          return (
            <li
              key={step.key}
              className="relative grid grid-cols-[1.25rem_1fr] gap-x-3"
              data-step={step.key}
              data-state={step.state}
            >
              {index < steps.length - 1 && (
                <span
                  aria-hidden="true"
                  className="absolute left-[0.6rem] top-5 h-[calc(100%-0.25rem)] w-px bg-border"
                />
              )}
              <span
                aria-hidden="true"
                className={cn(
                  'relative mt-1 size-3 justify-self-center rounded-full border-2',
                  DOT[step.state],
                )}
              />
              <div className="min-w-0 space-y-1">
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Icon className="size-3.5" />
                  {t(`monitoring.execution.timeline.steps.${step.key}`)}
                </div>
                <p
                  className={cn(
                    'text-sm break-words',
                    step.state === 'skipped' && 'text-muted-foreground',
                    step.state === 'blocked' &&
                      'text-amber-700 dark:text-amber-300',
                    (step.state === 'denied' || step.state === 'failed') &&
                      'text-destructive',
                  )}
                >
                  {step.text}
                </p>
                {step.chips && (
                  <div className="flex flex-wrap gap-1.5">
                    {step.chips.map((chip, chipIndex) => (
                      <span
                        key={`${chip.label}-${chipIndex}`}
                        className={cn(
                          'rounded-md border px-1.5 py-0.5 text-xs',
                          chip.warn
                            ? 'border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200'
                            : 'bg-muted/40',
                        )}
                      >
                        {chip.label}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
