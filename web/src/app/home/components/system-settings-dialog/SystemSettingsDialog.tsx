'use client';

import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Loader2, Settings2 } from 'lucide-react';
import { toast } from 'sonner';

import { httpClient, systemInfo } from '@/app/infra/http';
import { SystemAutoCleanupSettings } from '@/app/infra/entities/api';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';

interface SystemSettingsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const defaultSettings: SystemAutoCleanupSettings = {
  enabled: false,
  interval_hours: 24,
  log_retention_days: 7,
  monitoring_retention_days: 30,
  runtime_session_idle_hours: 24,
};

export default function SystemSettingsDialog({
  open,
  onOpenChange,
}: SystemSettingsDialogProps) {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [settings, setSettings] =
    useState<SystemAutoCleanupSettings>(defaultSettings);

  useEffect(() => {
    if (!open) {
      return;
    }

    void loadSettings();
  }, [open]);

  async function loadSettings() {
    setLoading(true);
    try {
      const info = await httpClient.getSystemInfo();
      setSettings(info.auto_cleanup || defaultSettings);
    } catch {
      toast.error(t('systemSettings.loadFailed'));
    } finally {
      setLoading(false);
    }
  }

  function updateNumericField(
    field: keyof Omit<SystemAutoCleanupSettings, 'enabled'>,
    value: string,
  ) {
    setSettings((current) => ({
      ...current,
      [field]: value === '' ? 0 : Number.parseInt(value, 10) || 0,
    }));
  }

  function validateSettings() {
    if (!Number.isInteger(settings.interval_hours) || settings.interval_hours <= 0) {
      toast.error(t('systemSettings.validation.intervalHours'));
      return false;
    }

    const numericFields: Array<keyof Omit<SystemAutoCleanupSettings, 'enabled'>> =
      [
        'log_retention_days',
        'monitoring_retention_days',
        'runtime_session_idle_hours',
      ];

    for (const field of numericFields) {
      const value = settings[field];
      if (!Number.isInteger(value) || value < 0) {
        toast.error(t('systemSettings.validation.nonNegativeInteger'));
        return false;
      }
    }

    return true;
  }

  async function handleSave() {
    if (!validateSettings()) {
      return;
    }

    setSaving(true);
    try {
      const response = await httpClient.updateAutoCleanupSettings(settings);
      setSettings(response.auto_cleanup);
      systemInfo.auto_cleanup = response.auto_cleanup;
      toast.success(t('systemSettings.saved'));
      onOpenChange(false);
    } catch (error) {
      console.error('Failed to update auto cleanup settings:', error);
      toast.error(t('systemSettings.saveFailed'));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Settings2 className="h-5 w-5" />
            {t('systemSettings.title')}
          </DialogTitle>
          <DialogDescription>
            {t('systemSettings.description')}
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="flex justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin" />
          </div>
        ) : (
          <div className="space-y-6">
            <div className="flex items-start justify-between rounded-lg border p-4">
              <div className="space-y-1 pr-4">
                <Label htmlFor="auto-cleanup-enabled">
                  {t('systemSettings.autoCleanupEnabled')}
                </Label>
                <p className="text-sm text-muted-foreground">
                  {t('systemSettings.autoCleanupEnabledDescription')}
                </p>
              </div>
              <Switch
                id="auto-cleanup-enabled"
                checked={settings.enabled}
                onCheckedChange={(checked) =>
                  setSettings((current) => ({
                    ...current,
                    enabled: checked,
                  }))
                }
              />
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="interval-hours">
                  {t('systemSettings.intervalHours')}
                </Label>
                <Input
                  id="interval-hours"
                  type="number"
                  min={1}
                  value={settings.interval_hours}
                  onChange={(event) =>
                    updateNumericField('interval_hours', event.target.value)
                  }
                />
                <p className="text-xs text-muted-foreground">
                  {t('systemSettings.intervalHoursDescription')}
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="log-retention-days">
                  {t('systemSettings.logRetentionDays')}
                </Label>
                <Input
                  id="log-retention-days"
                  type="number"
                  min={0}
                  value={settings.log_retention_days}
                  onChange={(event) =>
                    updateNumericField(
                      'log_retention_days',
                      event.target.value,
                    )
                  }
                />
                <p className="text-xs text-muted-foreground">
                  {t('systemSettings.zeroDisables')}
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="monitoring-retention-days">
                  {t('systemSettings.monitoringRetentionDays')}
                </Label>
                <Input
                  id="monitoring-retention-days"
                  type="number"
                  min={0}
                  value={settings.monitoring_retention_days}
                  onChange={(event) =>
                    updateNumericField(
                      'monitoring_retention_days',
                      event.target.value,
                    )
                  }
                />
                <p className="text-xs text-muted-foreground">
                  {t('systemSettings.monitoringRetentionDaysDescription')}
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="runtime-session-idle-hours">
                  {t('systemSettings.runtimeSessionIdleHours')}
                </Label>
                <Input
                  id="runtime-session-idle-hours"
                  type="number"
                  min={0}
                  value={settings.runtime_session_idle_hours}
                  onChange={(event) =>
                    updateNumericField(
                      'runtime_session_idle_hours',
                      event.target.value,
                    )
                  }
                />
                <p className="text-xs text-muted-foreground">
                  {t('systemSettings.runtimeSessionIdleHoursDescription')}
                </p>
              </div>
            </div>

            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
              {t('systemSettings.notice')}
            </div>

            <div className="flex justify-end gap-2">
              <Button
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={saving}
              >
                {t('common.cancel')}
              </Button>
              <Button onClick={handleSave} disabled={saving}>
                {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {t('common.save')}
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
