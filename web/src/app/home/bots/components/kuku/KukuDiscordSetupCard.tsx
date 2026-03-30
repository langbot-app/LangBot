'use client';

import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';

import { KukuGroupSettings, KukuPersona } from '@/app/infra/entities/api';
import { httpClient } from '@/app/infra/http/HttpClient';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { CustomApiError } from '@/app/infra/entities/common';

import {
  buildKukuGroupSettingsPayload,
  createDefaultKukuSettingsFormValues,
  mapGroupSettingsToFormValues,
  type KukuSettingsFormValues,
} from './kuku-settings-helpers';

type LoadState = 'idle' | 'loaded' | 'missing';
type ApiErrorWithCode = CustomApiError & { code?: number };

export default function KukuDiscordSetupCard({ botId }: { botId: string }) {
  const { t } = useTranslation();
  const [isDiscordBot, setIsDiscordBot] = useState(false);
  const [isLoadingBot, setIsLoadingBot] = useState(true);
  const [isLoadingSettings, setIsLoadingSettings] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [loadState, setLoadState] = useState<LoadState>('idle');
  const [personas, setPersonas] = useState<KukuPersona[]>([]);
  const [formValues, setFormValues] = useState<KukuSettingsFormValues>(
    createDefaultKukuSettingsFormValues(),
  );

  useEffect(() => {
    let cancelled = false;

    async function loadInitialData() {
      try {
        const [botResp, personasResp] = await Promise.all([
          httpClient.getBot(botId),
          httpClient.getKukuPersonas(),
        ]);
        if (cancelled) return;

        const personaList = personasResp.personas ?? [];
        setIsDiscordBot(botResp.bot.adapter === 'discord');
        setPersonas(personaList);
        setFormValues((current) => ({
          ...current,
          personaId: personaList[0]?.id ?? current.personaId,
        }));
      } catch (err) {
        if (!cancelled) {
          toast.error(
            t('bots.kuku.loadBootstrapError') +
              ((err as CustomApiError).msg ?? ''),
          );
        }
      } finally {
        if (!cancelled) {
          setIsLoadingBot(false);
        }
      }
    }

    loadInitialData();
    return () => {
      cancelled = true;
    };
  }, [botId, t]);

  function updateField<K extends keyof KukuSettingsFormValues>(
    key: K,
    value: KukuSettingsFormValues[K],
  ) {
    setFormValues((current) => ({ ...current, [key]: value }));
  }

  async function handleLoadSettings() {
    const groupId = formValues.groupId.trim();
    if (!groupId) {
      toast.error(t('bots.kuku.groupIdRequired'));
      return;
    }

    setIsLoadingSettings(true);
    try {
      const response = await httpClient.getKukuGroupSettings(
        botId,
        'discord',
        groupId,
      );
      applyServerSettings(response.group);
      setLoadState('loaded');
      toast.success(t('bots.kuku.loadSuccess'));
    } catch (err) {
      const apiErr = err as ApiErrorWithCode;
      if (apiErr.code === 404) {
        setFormValues({
          ...createDefaultKukuSettingsFormValues(),
          groupId,
          personaId: personas[0]?.id ?? 'kuku-sunny',
        });
        setLoadState('missing');
        toast(t('bots.kuku.notConfiguredYet'));
      } else {
        toast.error(t('bots.kuku.loadError') + (apiErr.msg ?? ''));
      }
    } finally {
      setIsLoadingSettings(false);
    }
  }

  async function handleSaveSettings() {
    let request: ReturnType<typeof buildKukuGroupSettingsPayload>;
    try {
      request = buildKukuGroupSettingsPayload(formValues);
    } catch (err) {
      toast.error((err as Error).message);
      return;
    }

    setIsSaving(true);
    try {
      const response = await httpClient.updateKukuGroupSettings(
        botId,
        'discord',
        request.groupId,
        request.payload,
      );
      applyServerSettings(response.group);
      setLoadState('loaded');
      toast.success(t('bots.kuku.saveSuccess'));
    } catch (err) {
      toast.error(
        t('bots.kuku.saveError') + ((err as CustomApiError).msg ?? ''),
      );
    } finally {
      setIsSaving(false);
    }
  }

  function applyServerSettings(group: KukuGroupSettings) {
    const mapped = mapGroupSettingsToFormValues(group);
    setFormValues({
      ...mapped,
      personaId: mapped.personaId || personas[0]?.id || 'kuku-sunny',
    });
  }

  if (isLoadingBot || !isDiscordBot) {
    return null;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('bots.kuku.title')}</CardTitle>
        <CardDescription>{t('bots.kuku.description')}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="rounded-lg border bg-muted/30 p-4 text-sm text-muted-foreground">
          {t('bots.kuku.channelHint')}
        </div>

        <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto]">
          <div className="space-y-2">
            <Label htmlFor="kuku-group-id">{t('bots.kuku.groupId')}</Label>
            <Input
              id="kuku-group-id"
              value={formValues.groupId}
              placeholder={t('bots.kuku.groupIdPlaceholder')}
              onChange={(e) => updateField('groupId', e.target.value)}
            />
          </div>
          <div className="flex items-end">
            <Button
              type="button"
              variant="outline"
              onClick={handleLoadSettings}
              disabled={isLoadingSettings}
            >
              {isLoadingSettings
                ? t('bots.kuku.loadingSettings')
                : t('bots.kuku.loadSettings')}
            </Button>
          </div>
        </div>

        <p className="text-sm text-muted-foreground">
          {loadState === 'loaded'
            ? t('bots.kuku.loadedState')
            : loadState === 'missing'
              ? t('bots.kuku.missingState')
              : t('bots.kuku.idleState')}
        </p>

        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="kuku-persona">{t('bots.kuku.persona')}</Label>
            <Select
              value={formValues.personaId}
              onValueChange={(value) => updateField('personaId', value)}
            >
              <SelectTrigger id="kuku-persona">
                <SelectValue placeholder={t('bots.kuku.persona')} />
              </SelectTrigger>
              <SelectContent>
                {personas.map((persona) => (
                  <SelectItem key={persona.id} value={persona.id}>
                    {persona.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center justify-between rounded-lg border px-4 py-3">
            <div className="space-y-1">
              <p className="text-sm font-medium">{t('bots.kuku.enabled')}</p>
              <p className="text-sm text-muted-foreground">
                {t('bots.kuku.enabledHint')}
              </p>
            </div>
            <Switch
              checked={formValues.enabled}
              onCheckedChange={(checked) => updateField('enabled', checked)}
            />
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="kuku-silence-minutes">
              {t('bots.kuku.silenceMinutes')}
            </Label>
            <Input
              id="kuku-silence-minutes"
              type="number"
              min="0"
              value={formValues.silenceMinutes}
              onChange={(e) => updateField('silenceMinutes', e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="kuku-cooldown-minutes">
              {t('bots.kuku.cooldownMinutes')}
            </Label>
            <Input
              id="kuku-cooldown-minutes"
              type="number"
              min="0"
              value={formValues.cooldownMinutes}
              onChange={(e) => updateField('cooldownMinutes', e.target.value)}
            />
          </div>
        </div>

        <div className="space-y-4">
          <div>
            <p className="text-sm font-medium">{t('bots.kuku.quietHours')}</p>
            <p className="text-sm text-muted-foreground">
              {t('bots.kuku.quietHoursHint')}
            </p>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            <div className="space-y-2">
              <Label htmlFor="kuku-quiet-start">
                {t('bots.kuku.quietStart')}
              </Label>
              <Input
                id="kuku-quiet-start"
                type="time"
                value={formValues.quietHoursStart}
                onChange={(e) => updateField('quietHoursStart', e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="kuku-quiet-end">{t('bots.kuku.quietEnd')}</Label>
              <Input
                id="kuku-quiet-end"
                type="time"
                value={formValues.quietHoursEnd}
                onChange={(e) => updateField('quietHoursEnd', e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="kuku-quiet-timezone">
                {t('bots.kuku.timezone')}
              </Label>
              <Input
                id="kuku-quiet-timezone"
                value={formValues.quietHoursTimezone}
                placeholder="UTC"
                onChange={(e) =>
                  updateField('quietHoursTimezone', e.target.value)
                }
              />
            </div>
          </div>
        </div>

        <div className="flex justify-end">
          <Button
            type="button"
            onClick={handleSaveSettings}
            disabled={isSaving}
          >
            {isSaving ? t('common.saving') : t('bots.kuku.saveSettings')}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
