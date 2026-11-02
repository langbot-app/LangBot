import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { httpClient } from '@/app/infra/http/HttpClient';
import { useCurrentWorkspace } from '@/app/infra/http';
import { useSidebarData } from '@/app/home/components/home-sidebar/SidebarDataContext';
import type {
  ScenarioPackage,
  ScenarioReport,
} from '@/app/infra/entities/api/scenario';

export default function ScenarioPacks({ botId }: { botId?: string }) {
  const { t, i18n } = useTranslation();
  const workspace = useCurrentWorkspace();
  const canManage = workspace?.permissions.includes('resource.manage');
  const { refreshBots } = useSidebarData();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [document, setDocument] = useState<ScenarioPackage | null>(null);
  const [mode, setMode] = useState<'export' | 'import'>('import');
  const [reports, setReports] = useState<ScenarioReport[]>([]);
  const requestId = useRef('');
  const fileInput = useRef<HTMLInputElement>(null);
  const refresh = useCallback(async () => {
    const result = await httpClient.listScenarioImports();
    setReports(result.imports);
  }, []);
  useEffect(() => {
    if (canManage)
      void refresh().catch(() => toast.error(t('scenario.failed')));
  }, [canManage, refresh, t, botId]);
  if (!canManage) return null;

  const run = async (operation: () => Promise<void>) => {
    setBusy(true);
    try {
      await operation();
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : t('scenario.failed'),
      );
    } finally {
      setBusy(false);
    }
  };
  const label = (value: string | Record<string, string>) =>
    typeof value === 'string'
      ? value
      : value[i18n.language.replace('-', '_')] ||
        value.en_US ||
        Object.values(value)[0];
  const resourceUrl = (resource: ScenarioReport['resources'][number]) =>
    `/home/${resource.kind === 'bot' ? 'bots' : 'agents'}?id=${encodeURIComponent(resource.uuid)}`;
  const visibleReports = reports.filter(
    (report) =>
      !botId || report.resources.some((resource) => resource.uuid === botId),
  );

  return (
    <section className="space-y-3 rounded-lg border p-4">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="mr-auto font-medium">{t('scenario.title')}</h3>
        {botId && (
          <Button
            variant="outline"
            disabled={busy}
            onClick={() =>
              void run(async () => {
                setDocument(await httpClient.exportScenario(botId));
                setMode('export');
                setOpen(true);
              })
            }
          >
            {t('scenario.export')}
          </Button>
        )}
        <Button
          variant="outline"
          disabled={busy}
          onClick={() => fileInput.current?.click()}
        >
          {t('scenario.import')}
        </Button>
        <Button
          variant="ghost"
          disabled={busy}
          onClick={() => void run(refresh)}
        >
          {t('scenario.check')}
        </Button>
        <input
          ref={fileInput}
          type="file"
          accept=".json,application/json"
          className="hidden"
          onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = '';
            if (!file) return;
            void run(async () => {
              if (file.size > 2 * 1024 * 1024)
                throw new Error(t('scenario.fileTooLarge'));
              const preview = await httpClient.previewScenario(
                JSON.parse(await file.text()),
              );
              setDocument(preview.package);
              setMode('import');
              requestId.current = crypto.randomUUID();
              setOpen(true);
            });
          }}
        />
      </div>
      {visibleReports.map((report) => (
        <div key={report.id} className="space-y-3 border-t pt-3">
          <h4 className="font-medium">{report.metadata.name}</h4>
          <p className="text-sm text-muted-foreground">{t('scenario.setup')}</p>
          {report.metadata.instructions && (
            <p className="whitespace-pre-wrap text-sm">
              {report.metadata.instructions}
            </p>
          )}
          {report.resources.map((resource) => (
            <Link
              key={resource.id}
              className="mr-4 inline-block text-sm underline"
              to={resourceUrl(resource)}
            >
              {resource.name} · {t('scenario.configure')}
            </Link>
          ))}
          <ul className="space-y-2 text-sm">
            {report.inputs.map((item, index) => {
              const resource = report.resources.find(
                (resource) => resource.id === item.resource,
              );
              return (
                <li key={index} className="flex flex-wrap gap-2">
                  <span>
                    {item.status === 'ready' ? '✓' : '○'} {resource?.name} /{' '}
                    {label(item.label)}
                  </span>
                  <span className="text-muted-foreground">
                    {t(`scenario.${item.required ? 'required' : 'optional'}`)} ·{' '}
                    {t(`scenario.${item.status}`)}
                  </span>
                  {resource && (
                    <Link className="underline" to={resourceUrl(resource)}>
                      {t('scenario.configure')}
                    </Link>
                  )}
                </li>
              );
            })}
            {report.dependencies.map((item) => (
              <li key={`${item.kind}:${item.id}`}>
                {item.plugin_id} {item.version} ·{' '}
                {t(
                  `scenario.${item.status === 'ready' ? 'dependencyReady' : item.status === 'configure' ? 'dependencyConfigure' : item.status}`,
                )}{' '}
                <Link className="underline" to="/home/plugins">
                  {t('scenario.plugins')}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ))}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>{t(`scenario.${mode}`)}</DialogTitle>
          </DialogHeader>
          {document && (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                {t(mode === 'export' ? 'scenario.review' : 'scenario.setup')}
              </p>
              <label className="block text-sm">
                {t('scenario.name')}
                <Input
                  value={document.metadata.name}
                  disabled={mode === 'import'}
                  onChange={(event) =>
                    setDocument({
                      ...document,
                      metadata: {
                        ...document.metadata,
                        name: event.target.value,
                      },
                    })
                  }
                />
              </label>
              <label className="block text-sm">
                {t('scenario.instructions')}
                <Textarea
                  value={document.metadata.instructions}
                  disabled={mode === 'import'}
                  onChange={(event) =>
                    setDocument({
                      ...document,
                      metadata: {
                        ...document.metadata,
                        instructions: event.target.value,
                      },
                    })
                  }
                />
              </label>
              <ul className="text-sm">
                {document.inputs.map((item, index) => (
                  <li key={index}>
                    {label(item.label)} ·{' '}
                    {t(`scenario.${item.required ? 'required' : 'optional'}`)}
                  </li>
                ))}
              </ul>
              <details>
                <summary>{t('scenario.preview')}</summary>
                <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-all text-xs">
                  {JSON.stringify(document, null, 2)}
                </pre>
              </details>
              <Button
                disabled={busy || !document.metadata.name.trim()}
                onClick={() =>
                  void run(async () => {
                    if (mode === 'export') {
                      const url = URL.createObjectURL(
                        new Blob([JSON.stringify(document, null, 2)], {
                          type: 'application/json',
                        }),
                      );
                      const anchor = window.document.createElement('a');
                      anchor.href = url;
                      anchor.download = 'scenario.langbot-scene.json';
                      anchor.click();
                      setTimeout(() => URL.revokeObjectURL(url), 1000);
                    } else {
                      await httpClient.importScenario(
                        document,
                        requestId.current,
                      );
                      await refresh();
                      await refreshBots();
                      toast.success(t('scenario.imported'));
                    }
                    setOpen(false);
                  })
                }
              >
                {t(
                  mode === 'export' ? 'scenario.download' : 'scenario.confirm',
                )}
              </Button>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </section>
  );
}
