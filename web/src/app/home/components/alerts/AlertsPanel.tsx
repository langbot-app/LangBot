import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import {
  ArrowRight,
  BellRing,
  Check,
  CheckCircle2,
  CircleAlert,
  Loader2,
  Mail,
  RefreshCw,
  Send,
  Webhook as WebhookIcon,
} from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { cn } from '@/lib/utils';
import langbotIcon from '@/app/assets/langbot-logo.webp';
import { httpClient } from '@/app/infra/http/HttpClient';
import { rememberSpaceBindReturnPath } from '@/app/infra/space-bind-return';
import { backendClient, useCurrentWorkspace } from '@/app/infra/http';
import type {
  AlertDelivery,
  AlertEmailChannel,
  AlertIncident,
  AlertRuleName,
  AlertSettings,
  AlertSettingsResponse,
} from '@/app/infra/entities/alerts';
import {
  PanelBody,
  PanelToolbar,
} from '@/app/home/components/settings-dialog/panel-layout';

interface AlertsPanelProps {
  active: boolean;
}

const RULE_ORDER: AlertRuleName[] = [
  'pipeline_failures',
  'model_failures',
  'bot_offline',
];

function Section({
  title,
  description,
  icon,
  children,
}: {
  title: string;
  description?: string;
  icon?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-lg border bg-background">
      <div className="flex items-start gap-2.5 border-b px-4 py-3">
        {icon && <div className="mt-0.5 text-muted-foreground">{icon}</div>}
        <div className="min-w-0">
          <h3 className="text-sm font-medium">{title}</h3>
          {description && (
            <p className="mt-0.5 text-xs text-muted-foreground">
              {description}
            </p>
          )}
        </div>
      </div>
      <div className="px-4 py-3">{children}</div>
    </section>
  );
}

/**
 * Shown when neither the instance mail service nor a LangBot Account can send
 * alert emails: signing in with a LangBot Account is the zero-config path.
 */
function SignInCta() {
  const { t, i18n } = useTranslation();
  const [busy, setBusy] = useState(false);
  const docsLanguage = i18n.language?.startsWith('zh')
    ? 'zh'
    : i18n.language?.startsWith('ja')
      ? 'ja'
      : 'en';

  const signIn = async () => {
    setBusy(true);
    try {
      rememberSpaceBindReturnPath(
        `${window.location.pathname}?action=showAlerts`,
      );
      const response = await httpClient.getSpaceBindAuthorizeUrl(
        `${window.location.origin}/auth/space/callback?mode=bind`,
      );
      window.location.href = response.authorize_url;
    } catch {
      toast.error(t('common.spaceLoginFailed'));
      setBusy(false);
    }
  };

  const points = [
    t('alerts.cta.pointFree'),
    t('alerts.cta.pointNoSetup'),
    t('alerts.cta.pointPrivate'),
  ];

  return (
    <div className="mb-4 overflow-hidden rounded-lg border border-primary/25 bg-primary/[0.03]">
      <div className="flex flex-col gap-4 p-4 sm:flex-row sm:items-center sm:gap-5">
        <img
          src={langbotIcon}
          alt=""
          className="size-11 shrink-0 rounded-xl shadow-sm"
        />
        <div className="min-w-0 flex-1 space-y-1.5">
          <p className="text-sm font-semibold">{t('alerts.cta.title')}</p>
          <ul className="space-y-1">
            {points.map((point) => (
              <li
                key={point}
                className="flex items-center gap-1.5 text-xs text-muted-foreground"
              >
                <Check className="size-3.5 shrink-0 text-primary" />
                {point}
              </li>
            ))}
          </ul>
        </div>
        <Button
          className="shrink-0"
          onClick={() => void signIn()}
          disabled={busy}
        >
          {busy && <Loader2 className="size-4 animate-spin" />}
          {t('common.loginWithSpace')}
          {!busy && <ArrowRight className="size-4" />}
        </Button>
      </div>
      <div className="border-t border-primary/15 bg-background/60 px-4 py-2 text-xs text-muted-foreground">
        {t('alerts.cta.selfHosted')}{' '}
        <a
          href={`https://langbot.app/docs/${docsLanguage}/deploy/alerts`}
          target="_blank"
          rel="noreferrer"
          className="font-medium text-primary hover:underline"
        >
          {t('alerts.cta.selfHostedLink')}
        </a>
      </div>
    </div>
  );
}

function formatTime(value: string | null): string {
  if (!value) return '—';
  const date = new Date(value.endsWith('Z') ? value : `${value}Z`);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export default function AlertsPanel({ active }: AlertsPanelProps) {
  const { t } = useTranslation();
  const currentWorkspace = useCurrentWorkspace();
  const canEdit = (currentWorkspace?.permissions ?? []).includes(
    'workspace.update',
  );

  const [data, setData] = useState<AlertSettingsResponse | null>(null);
  const [draft, setDraft] = useState<AlertSettings | null>(null);
  const [extraInput, setExtraInput] = useState('');
  const [incidents, setIncidents] = useState<AlertIncident[]>([]);
  const [deliveries, setDeliveries] = useState<AlertDelivery[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [settings, incidentResponse, deliveryResponse] = await Promise.all([
        backendClient.getAlertSettings(),
        backendClient.getAlertIncidents(),
        backendClient.getAlertDeliveries(),
      ]);
      setData(settings);
      setDraft(settings.settings);
      setExtraInput(settings.settings.extra_recipients.join(', '));
      setIncidents(incidentResponse.incidents);
      setDeliveries(deliveryResponse.deliveries);
    } catch (error) {
      toast.error(t('alerts.loadFailed', { error: String(error) }));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    if (active) void load();
  }, [active, load]);

  const extraRecipients = useMemo(
    () =>
      extraInput
        .split(/[\s,;]+/)
        .map((item) => item.trim())
        .filter(Boolean),
    [extraInput],
  );

  const dirty = useMemo(() => {
    if (!data || !draft) return false;
    return (
      JSON.stringify({ ...draft, extra_recipients: extraRecipients }) !==
      JSON.stringify(data.settings)
    );
  }, [data, draft, extraRecipients]);

  const update = (patch: Partial<AlertSettings>) =>
    setDraft((current) => (current ? { ...current, ...patch } : current));

  const updateRule = (
    name: AlertRuleName,
    patch: Partial<AlertSettings['rules'][AlertRuleName]>,
  ) =>
    setDraft((current) =>
      current
        ? {
            ...current,
            rules: {
              ...current.rules,
              [name]: { ...current.rules[name], ...patch },
            },
          }
        : current,
    );

  const save = async () => {
    if (!draft) return;
    setSaving(true);
    try {
      await backendClient.updateAlertSettings({
        ...draft,
        extra_recipients: extraRecipients,
      });
      toast.success(t('alerts.saved'));
      await load();
    } catch (error) {
      toast.error(t('alerts.saveFailed', { error: String(error) }));
    } finally {
      setSaving(false);
    }
  };

  const sendTest = async () => {
    setTesting(true);
    try {
      const result = await backendClient.sendTestAlert();
      if (result.deliveries.length === 0) {
        toast.warning(t('alerts.testNoChannel'));
      } else if (result.deliveries.every((item) => item.status === 'sent')) {
        toast.success(
          t('alerts.testSent', { count: result.deliveries.length }),
        );
      } else {
        toast.warning(t('alerts.testPartial'));
      }
      const deliveryResponse = await backendClient.getAlertDeliveries();
      setDeliveries(deliveryResponse.deliveries);
    } catch (error) {
      toast.error(t('alerts.testFailed', { error: String(error) }));
    } finally {
      setTesting(false);
    }
  };

  if (!data || !draft) {
    return (
      <PanelBody className="flex items-center justify-center">
        <Loader2 className="size-5 animate-spin text-muted-foreground" />
      </PanelBody>
    );
  }

  const { channels } = data;
  const channelOptions: {
    value: AlertEmailChannel;
    label: string;
    description: string;
    available: boolean;
  }[] = [
    {
      value: 'auto',
      label: t('alerts.channel.auto'),
      description: t('alerts.channel.autoDescription'),
      available: true,
    },
    {
      value: 'instance',
      label: t('alerts.channel.instance'),
      description: channels.instance.configured
        ? t('alerts.channel.instanceConfigured', {
            provider:
              channels.instance.provider === 'resend' ? 'Resend' : 'SMTP',
          })
        : t('alerts.channel.instanceMissing'),
      available: channels.instance.configured,
    },
    {
      value: 'space',
      label: t('alerts.channel.space'),
      description: channels.space.available
        ? t('alerts.channel.spaceAvailable', {
            accounts: channels.space.accounts.join(', '),
          })
        : t('alerts.channel.spaceMissing'),
      available: channels.space.available,
    },
    {
      value: 'off',
      label: t('alerts.channel.off'),
      description: t('alerts.channel.offDescription'),
      available: true,
    },
  ];
  const effectiveLabel =
    data.channels.effective_email_channel === 'instance'
      ? t('alerts.channel.instance')
      : data.channels.effective_email_channel === 'space'
        ? t('alerts.channel.space')
        : t('alerts.channel.none');
  const firing = incidents.filter((item) => item.state === 'firing');
  const usesInstance =
    draft.email_channel === 'instance' ||
    (draft.email_channel === 'auto' && channels.instance.configured);

  return (
    <>
      <PanelToolbar>
        <div className="flex min-w-0 items-center gap-3">
          <Switch
            id="alerts-enabled"
            checked={draft.enabled}
            disabled={!canEdit}
            onCheckedChange={(checked) => update({ enabled: checked })}
          />
          <Label htmlFor="alerts-enabled" className="text-sm">
            {t('alerts.enabled')}
          </Label>
          {firing.length > 0 ? (
            <Badge variant="destructive">
              {t('alerts.firingCount', { count: firing.length })}
            </Badge>
          ) : (
            <Badge variant="secondary" className="gap-1">
              <CheckCircle2 className="size-3" />
              {t('alerts.allClear')}
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => void load()}
            disabled={loading}
          >
            <RefreshCw className={cn('size-4', loading && 'animate-spin')} />
          </Button>
          {canEdit && (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={() => void sendTest()}
                disabled={testing || dirty}
                title={dirty ? t('alerts.saveBeforeTest') : undefined}
              >
                {testing ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <Send className="size-4" />
                )}
                {t('alerts.sendTest')}
              </Button>
              <Button
                size="sm"
                onClick={() => void save()}
                disabled={!dirty || saving}
              >
                {saving && <Loader2 className="size-4 animate-spin" />}
                {t('common.save')}
              </Button>
            </>
          )}
        </div>
      </PanelToolbar>
      <PanelBody className="space-y-4">
        {!data.enabled_instance_wide && (
          <div className="flex items-center gap-2 rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-xs text-muted-foreground">
            <CircleAlert className="size-4 text-amber-500" />
            {t('alerts.disabledInstanceWide')}
          </div>
        )}

        <Section
          title={t('alerts.emailTitle')}
          description={t('alerts.emailDescription', {
            channel: effectiveLabel,
          })}
          icon={<Mail className="size-4" />}
        >
          {!channels.instance.configured &&
            !channels.space.available &&
            channels.space.supported && <SignInCta />}
          <div className="grid gap-2 sm:grid-cols-2">
            {channelOptions.map((option) => {
              const selected = draft.email_channel === option.value;
              const disabled =
                !canEdit ||
                (!option.available && option.value !== draft.email_channel);
              return (
                <button
                  key={option.value}
                  type="button"
                  disabled={disabled}
                  onClick={() => update({ email_channel: option.value })}
                  className={cn(
                    'rounded-md border px-3 py-2.5 text-left transition-colors',
                    selected
                      ? 'border-primary bg-primary/5 ring-1 ring-primary'
                      : 'hover:bg-muted/50',
                    disabled && 'cursor-not-allowed opacity-50',
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium">{option.label}</span>
                    {option.value !== 'auto' && option.value !== 'off' && (
                      <Badge
                        variant={option.available ? 'secondary' : 'outline'}
                        className="text-[10px]"
                      >
                        {option.available
                          ? t('alerts.channel.ready')
                          : t('alerts.channel.unavailable')}
                      </Badge>
                    )}
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {option.description}
                  </p>
                </button>
              );
            })}
          </div>

          <div className="mt-4 space-y-2">
            <p className="text-xs font-medium text-muted-foreground">
              {t('alerts.recipients')}
            </p>
            {data.recipients.length === 0 && (
              <p className="text-xs text-muted-foreground">
                {t('alerts.noRecipients')}
              </p>
            )}
            {data.recipients.map((recipient) => {
              const muted = draft.muted_account_uuids.includes(
                recipient.account_uuid,
              );
              return (
                <label
                  key={recipient.account_uuid}
                  className="flex items-center gap-2 text-sm"
                >
                  <Checkbox
                    checked={!muted}
                    disabled={!canEdit}
                    onCheckedChange={(checked) =>
                      update({
                        muted_account_uuids: checked
                          ? draft.muted_account_uuids.filter(
                              (item) => item !== recipient.account_uuid,
                            )
                          : [
                              ...draft.muted_account_uuids,
                              recipient.account_uuid,
                            ],
                      })
                    }
                  />
                  <span className="truncate">{recipient.email}</span>
                  <Badge variant="outline" className="text-[10px]">
                    {t(`workspace.roles.${recipient.role}`, recipient.role)}
                  </Badge>
                  {recipient.space_linked && (
                    <Badge variant="secondary" className="text-[10px]">
                      LangBot Space
                    </Badge>
                  )}
                </label>
              );
            })}
            {usesInstance && (
              <div className="pt-2">
                <Label htmlFor="alerts-extra" className="text-xs">
                  {t('alerts.extraRecipients')}
                </Label>
                <Input
                  id="alerts-extra"
                  className="mt-1"
                  placeholder="oncall@example.com, ops@example.com"
                  value={extraInput}
                  disabled={!canEdit}
                  onChange={(event) => setExtraInput(event.target.value)}
                />
              </div>
            )}
            {channels.space.available &&
            (draft.email_channel === 'space' ||
              (draft.email_channel === 'auto' &&
                !channels.instance.configured)) ? (
              <p className="text-xs text-muted-foreground">
                {t('alerts.spaceRecipientsHint')}
              </p>
            ) : null}
          </div>
        </Section>

        <Section
          title={t('alerts.rulesTitle')}
          description={t('alerts.rulesDescription')}
          icon={<BellRing className="size-4" />}
        >
          <div className="divide-y">
            {RULE_ORDER.map((name) => {
              const rule = draft.rules[name];
              const spec = data.rule_catalog.find((item) => item.name === name);
              if (!rule || !spec) return null;
              const fixed = spec.min_threshold === spec.max_threshold;
              return (
                <div
                  key={name}
                  className="flex flex-col gap-2 py-2.5 first:pt-0 last:pb-0 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="flex min-w-0 items-start gap-3">
                    <Switch
                      checked={rule.enabled}
                      disabled={!canEdit}
                      onCheckedChange={(checked) =>
                        updateRule(name, { enabled: checked })
                      }
                    />
                    <div className="min-w-0">
                      <p className="text-sm font-medium">
                        {t(`alerts.rule.${name}`)}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {t(`alerts.rule.${name}Description`)}
                      </p>
                    </div>
                  </div>
                  {!fixed && (
                    <div className="flex shrink-0 items-center gap-1.5 pl-12 text-xs text-muted-foreground sm:pl-0">
                      <Input
                        type="number"
                        className="h-8 w-16"
                        min={spec.min_window_minutes}
                        max={spec.max_window_minutes}
                        value={rule.window_minutes}
                        disabled={!canEdit || !rule.enabled}
                        onChange={(event) =>
                          updateRule(name, {
                            window_minutes: Number(event.target.value),
                          })
                        }
                      />
                      <span>{t('alerts.minutesWithin')}</span>
                      <Input
                        type="number"
                        className="h-8 w-16"
                        min={spec.min_threshold}
                        max={spec.max_threshold}
                        value={rule.threshold}
                        disabled={!canEdit || !rule.enabled}
                        onChange={(event) =>
                          updateRule(name, {
                            threshold: Number(event.target.value),
                          })
                        }
                      />
                      <span>{t('alerts.failuresOrMore')}</span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
          <div className="mt-3 flex items-center gap-2 border-t pt-3">
            <Switch
              id="alerts-resolved"
              checked={draft.notify_resolved}
              disabled={!canEdit}
              onCheckedChange={(checked) =>
                update({ notify_resolved: checked })
              }
            />
            <Label htmlFor="alerts-resolved" className="text-sm">
              {t('alerts.notifyResolved')}
            </Label>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            {t('alerts.throttleHint')}
          </p>
        </Section>

        <Section
          title={t('alerts.webhooksTitle')}
          description={t('alerts.webhooksDescription')}
          icon={<WebhookIcon className="size-4" />}
        >
          {data.webhooks.length === 0 ? (
            <p className="text-xs text-muted-foreground">
              {t('alerts.noWebhooks')}
            </p>
          ) : (
            <div className="space-y-2">
              {data.webhooks.map((webhook) => (
                <label
                  key={webhook.id}
                  className="flex items-center gap-2 text-sm"
                >
                  <Checkbox
                    checked={draft.webhook_ids.includes(webhook.id)}
                    disabled={!canEdit}
                    onCheckedChange={(checked) =>
                      update({
                        webhook_ids: checked
                          ? [...draft.webhook_ids, webhook.id]
                          : draft.webhook_ids.filter(
                              (item) => item !== webhook.id,
                            ),
                      })
                    }
                  />
                  <span>{webhook.name}</span>
                  {!webhook.enabled && (
                    <Badge variant="outline" className="text-[10px]">
                      {t('alerts.webhookDisabled')}
                    </Badge>
                  )}
                </label>
              ))}
            </div>
          )}
        </Section>

        <Section title={t('alerts.incidentsTitle')}>
          {incidents.length === 0 ? (
            <p className="text-xs text-muted-foreground">
              {t('alerts.noIncidents')}
            </p>
          ) : (
            <div className="divide-y">
              {incidents.slice(0, 20).map((incident) => (
                <div key={incident.id} className="py-2 first:pt-0 last:pb-0">
                  <div className="flex items-center gap-2">
                    <Badge
                      variant={
                        incident.state === 'firing'
                          ? 'destructive'
                          : 'secondary'
                      }
                      className="text-[10px]"
                    >
                      {t(`alerts.state.${incident.state}`)}
                    </Badge>
                    <span className="truncate text-sm font-medium">
                      {t(`alerts.rule.${incident.rule}`)} ·{' '}
                      {incident.subject_name}
                    </span>
                  </div>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {t('alerts.incidentMeta', {
                      count: incident.event_count,
                      time: formatTime(incident.opened_at),
                    })}
                  </p>
                  {incident.error_summary && (
                    <p className="mt-0.5 break-all font-mono text-xs text-muted-foreground">
                      {incident.error_summary}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </Section>

        <Section title={t('alerts.deliveriesTitle')}>
          {deliveries.length === 0 ? (
            <p className="text-xs text-muted-foreground">
              {t('alerts.noDeliveries')}
            </p>
          ) : (
            <div className="divide-y text-xs">
              {deliveries.slice(0, 20).map((delivery) => (
                <div
                  key={delivery.id}
                  className="flex flex-wrap items-center gap-x-3 gap-y-1 py-1.5"
                >
                  <span className="w-36 shrink-0 text-muted-foreground">
                    {formatTime(delivery.created_at)}
                  </span>
                  <span className="w-20 shrink-0">
                    {t(`alerts.kind.${delivery.kind}`)}
                  </span>
                  <span className="w-24 shrink-0">
                    {t(`alerts.via.${delivery.channel}`)}
                  </span>
                  <span className="min-w-0 flex-1 truncate">
                    {delivery.target}
                  </span>
                  <Badge
                    variant={
                      delivery.status === 'sent' ? 'secondary' : 'destructive'
                    }
                    className="text-[10px]"
                    title={delivery.error ?? undefined}
                  >
                    {t(`alerts.status.${delivery.status}`)}
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </Section>
      </PanelBody>
    </>
  );
}
