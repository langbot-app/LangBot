import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ArrowLeft,
  Check,
  Eye,
  Loader2,
  Pencil,
  RefreshCw,
  Wrench,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';

import ProviderForm from '@/app/home/components/models-dialog/component/provider-form/ProviderForm';
import type { ScannedProviderModel } from '@/app/infra/entities/api';
import { httpClient } from '@/app/infra/http/HttpClient';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { cn } from '@/lib/utils';

type ModelSetupMode = 'scan' | 'manual';
type ScanFallbackReason = 'failed' | 'empty' | null;

export interface OwnModelSelection {
  source: ModelSetupMode;
  providerUuid: string;
  model: ScannedProviderModel;
}

interface OwnModelSetupProps {
  onBack: () => void;
  onSelectionChange: (selection: OwnModelSelection | null) => void;
}

export default function OwnModelSetup({
  onBack,
  onSelectionChange,
}: OwnModelSetupProps) {
  const { t } = useTranslation();
  const [providerUuid, setProviderUuid] = useState<string | null>(null);
  const [showProviderForm, setShowProviderForm] = useState(true);
  const [mode, setMode] = useState<ModelSetupMode>('scan');
  const [models, setModels] = useState<ScannedProviderModel[]>([]);
  const [selectedModelId, setSelectedModelId] = useState<string | null>(null);
  const [isScanning, setIsScanning] = useState(false);
  const [scanFallbackReason, setScanFallbackReason] =
    useState<ScanFallbackReason>(null);
  const [manualModelName, setManualModelName] = useState('');
  const [manualContextLength, setManualContextLength] = useState('');
  const [manualVision, setManualVision] = useState(false);
  const [manualFunctionCall, setManualFunctionCall] = useState(false);

  const parsedManualContextLength = useMemo(() => {
    if (!manualContextLength.trim()) return null;
    const value = Number(manualContextLength);
    return Number.isInteger(value) && value > 0 ? value : undefined;
  }, [manualContextLength]);

  useEffect(() => {
    if (mode !== 'manual' || !providerUuid) return;
    if (!manualModelName.trim() || parsedManualContextLength === undefined) {
      onSelectionChange(null);
      return;
    }

    const abilities = [
      ...(manualVision ? ['vision'] : []),
      ...(manualFunctionCall ? ['func_call'] : []),
    ];
    const modelName = manualModelName.trim();
    onSelectionChange({
      source: 'manual',
      providerUuid,
      model: {
        id: modelName,
        name: modelName,
        type: 'llm',
        abilities,
        context_length: parsedManualContextLength,
        already_added: false,
      },
    });
  }, [
    manualFunctionCall,
    manualModelName,
    manualVision,
    mode,
    onSelectionChange,
    parsedManualContextLength,
    providerUuid,
  ]);

  const scanModels = useCallback(
    async (uuid: string) => {
      setMode('scan');
      setIsScanning(true);
      setScanFallbackReason(null);
      setModels([]);
      setSelectedModelId(null);
      onSelectionChange(null);

      try {
        const response = await httpClient.scanProviderModels(uuid, 'llm');
        const availableModels = response.models.filter(
          (model) => model.type === 'llm' && !model.already_added,
        );
        setModels(availableModels);
        if (availableModels.length === 0) {
          setScanFallbackReason('empty');
          setMode('manual');
        }
      } catch {
        setScanFallbackReason('failed');
        setMode('manual');
      } finally {
        setIsScanning(false);
      }
    },
    [onSelectionChange],
  );

  const handleProviderSaved = useCallback(
    async (uuid: string) => {
      setProviderUuid(uuid);
      setShowProviderForm(false);
      await scanModels(uuid);
    },
    [scanModels],
  );

  const handleSelectModel = useCallback(
    (model: ScannedProviderModel) => {
      if (!providerUuid) return;
      setSelectedModelId(model.id);
      onSelectionChange({ source: 'scan', providerUuid, model });
    },
    [onSelectionChange, providerUuid],
  );

  const handleModeChange = useCallback(
    (value: string) => {
      setMode(value as ModelSetupMode);
      setSelectedModelId(null);
      onSelectionChange(null);
    },
    [onSelectionChange],
  );

  const handleBack = useCallback(() => {
    onSelectionChange(null);
    onBack();
  }, [onBack, onSelectionChange]);

  const handleEditProvider = useCallback(() => {
    setSelectedModelId(null);
    onSelectionChange(null);
    setShowProviderForm(true);
  }, [onSelectionChange]);

  return (
    <div className="mx-auto w-full max-w-4xl space-y-6">
      <div className="text-center">
        <h2 className="text-xl font-semibold">
          {t('wizard.aiEngine.ownModelSetupTitle')}
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {t('wizard.aiEngine.ownModelSetupDescription')}
        </p>
      </div>

      <div>
        <Button variant="ghost" size="sm" onClick={handleBack}>
          <ArrowLeft className="mr-1.5 size-4" />
          {t('wizard.aiEngine.backToChoices')}
        </Button>
      </div>

      {showProviderForm ? (
        <Card className="mx-auto w-full max-w-3xl">
          <CardHeader>
            <CardTitle className="text-base">
              {t('wizard.aiEngine.addProviderTitle')}
            </CardTitle>
            <CardDescription>
              {t('wizard.aiEngine.addProviderDescription')}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ProviderForm
              providerId={providerUuid ?? undefined}
              onFormSubmit={handleProviderSaved}
              onFormCancel={() =>
                providerUuid ? setShowProviderForm(false) : handleBack()
              }
            />
          </CardContent>
        </Card>
      ) : (
        <div className="mx-auto w-full max-w-3xl space-y-4">
          <div className="flex flex-wrap items-start justify-between gap-3 border-b pb-3">
            <div>
              <h3 className="text-base font-semibold">
                {t('wizard.aiEngine.selectModelTitle')}
              </h3>
              <p className="text-sm text-muted-foreground">
                {t('wizard.aiEngine.selectScannedModelDescription')}
              </p>
            </div>
            <Button
              variant="outline"
              size="icon"
              title={t('wizard.aiEngine.editProvider')}
              onClick={handleEditProvider}
            >
              <Pencil className="size-4" />
            </Button>
          </div>

          <Tabs value={mode} onValueChange={handleModeChange}>
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="scan">
                {t('wizard.aiEngine.scanModelMode')}
              </TabsTrigger>
              <TabsTrigger value="manual">
                {t('wizard.aiEngine.manualModelMode')}
              </TabsTrigger>
            </TabsList>

            <TabsContent value="scan" className="mt-4">
              {isScanning ? (
                <div className="flex min-h-48 items-center justify-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="size-4 animate-spin" />
                  {t('wizard.aiEngine.scanningModels')}
                </div>
              ) : models.length > 0 ? (
                <div className="space-y-3">
                  <div className="grid gap-2 sm:grid-cols-2">
                    {models.map((model) => {
                      const selected = selectedModelId === model.id;
                      return (
                        <button
                          key={model.id}
                          type="button"
                          className={cn(
                            'flex min-h-20 items-center gap-3 rounded-md border p-3 text-left transition-colors hover:border-primary/60 hover:bg-accent/40',
                            selected &&
                              'border-primary bg-accent ring-1 ring-primary',
                          )}
                          onClick={() => handleSelectModel(model)}
                        >
                          <span
                            className={cn(
                              'flex size-5 shrink-0 items-center justify-center rounded-full border',
                              selected &&
                                'border-primary bg-primary text-primary-foreground',
                            )}
                          >
                            {selected && <Check className="size-3" />}
                          </span>
                          <span className="min-w-0">
                            <span className="block truncate text-sm font-medium">
                              {model.display_name || model.name}
                            </span>
                            <span className="block truncate text-xs text-muted-foreground">
                              {model.name}
                            </span>
                          </span>
                        </button>
                      );
                    })}
                  </div>
                  <div className="flex justify-end">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={isScanning || !providerUuid}
                      onClick={() => providerUuid && scanModels(providerUuid)}
                    >
                      <RefreshCw className="mr-1.5 size-4" />
                      {t('wizard.aiEngine.rescanModels')}
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="flex min-h-48 flex-col items-center justify-center gap-3 border border-dashed p-6 text-center">
                  <p className="text-sm text-muted-foreground">
                    {t(
                      scanFallbackReason === 'failed'
                        ? 'wizard.aiEngine.scanModelsFailed'
                        : 'wizard.aiEngine.noScannedModels',
                    )}
                  </p>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={!providerUuid}
                    onClick={() => providerUuid && scanModels(providerUuid)}
                  >
                    <RefreshCw className="mr-1.5 size-4" />
                    {t('wizard.aiEngine.rescanModels')}
                  </Button>
                </div>
              )}
            </TabsContent>

            <TabsContent value="manual" className="mt-4 space-y-5">
              {scanFallbackReason && (
                <div className="border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-200">
                  {t(
                    scanFallbackReason === 'failed'
                      ? 'wizard.aiEngine.manualFallbackFailed'
                      : 'wizard.aiEngine.manualFallbackEmpty',
                  )}
                </div>
              )}

              <div className="space-y-2">
                <Label htmlFor="wizard-manual-model-name">
                  {t('wizard.aiEngine.manualModelId')}
                  <span className="text-red-500">*</span>
                </Label>
                <Input
                  id="wizard-manual-model-name"
                  value={manualModelName}
                  onChange={(event) => setManualModelName(event.target.value)}
                  placeholder={t('wizard.aiEngine.manualModelIdPlaceholder')}
                />
                <p className="text-xs text-muted-foreground">
                  {t('wizard.aiEngine.manualModelIdDescription')}
                </p>
              </div>

              <div className="space-y-3 border-t pt-4">
                <p className="text-sm font-medium">
                  {t('wizard.aiEngine.manualModelOptions')}
                </p>
                <div className="space-y-2">
                  <Label htmlFor="wizard-manual-context-length">
                    {t('models.contextLength')}
                  </Label>
                  <Input
                    id="wizard-manual-context-length"
                    type="number"
                    min={1}
                    step={1}
                    value={manualContextLength}
                    onChange={(event) =>
                      setManualContextLength(event.target.value)
                    }
                    placeholder={t('models.contextLengthPlaceholder')}
                  />
                  {parsedManualContextLength === undefined && (
                    <p className="text-xs text-destructive">
                      {t('models.contextLengthInvalid')}
                    </p>
                  )}
                </div>

                <div className="flex flex-wrap gap-5">
                  <div className="flex items-center gap-2">
                    <Checkbox
                      id="wizard-manual-vision"
                      checked={manualVision}
                      onCheckedChange={(checked) =>
                        setManualVision(checked === true)
                      }
                    />
                    <Label
                      htmlFor="wizard-manual-vision"
                      className="flex items-center gap-1.5"
                    >
                      <Eye className="size-4" />
                      {t('models.visionAbility')}
                    </Label>
                  </div>
                  <div className="flex items-center gap-2">
                    <Checkbox
                      id="wizard-manual-function-call"
                      checked={manualFunctionCall}
                      onCheckedChange={(checked) =>
                        setManualFunctionCall(checked === true)
                      }
                    />
                    <Label
                      htmlFor="wizard-manual-function-call"
                      className="flex items-center gap-1.5"
                    >
                      <Wrench className="size-4" />
                      {t('models.functionCallAbility')}
                    </Label>
                  </div>
                </div>
              </div>
            </TabsContent>
          </Tabs>
        </div>
      )}
    </div>
  );
}
