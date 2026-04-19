import { useState, useEffect, useRef } from 'react';
import {
  Plus,
  MessageSquareText,
  Cpu,
  Eye,
  Wrench,
  Check,
  RefreshCw,
  Search,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useTranslation } from 'react-i18next';
import { ScannedProviderModel } from '@/app/infra/entities/api';
import {
  ExtraArg,
  ModelType,
  ScanModelsResult,
  SelectedScannedModel,
  TestResult,
} from '../types';
import ExtraArgsEditor from './ExtraArgsEditor';

interface AddModelPopoverProps {
  isOpen: boolean;
  onOpen: () => void;
  onClose: () => void;
  onAddModel: (
    modelType: ModelType,
    name: string,
    abilities: string[],
    extraArgs: ExtraArg[],
  ) => Promise<void>;
  onScanModels: (modelType: ModelType) => Promise<ScanModelsResult>;
  onAddScannedModels: (
    modelType: ModelType,
    models: SelectedScannedModel[],
  ) => Promise<void>;
  onTestModel: (
    name: string,
    modelType: ModelType,
    abilities: string[],
    extraArgs: ExtraArg[],
  ) => Promise<void>;
  isSubmitting: boolean;
  isTesting: boolean;
  testResult: TestResult | null;
  onResetTestResult: () => void;
}

export default function AddModelPopover({
  isOpen,
  onOpen,
  onClose,
  onAddModel,
  onScanModels,
  onAddScannedModels,
  onTestModel,
  isSubmitting,
  isTesting,
  testResult,
  onResetTestResult,
}: AddModelPopoverProps) {
  const { t } = useTranslation();
  const scannedListRef = useRef<HTMLDivElement | null>(null);
  const prevIsOpenRef = useRef(false);

  const [tab, setTab] = useState<ModelType>('llm');
  const [mode, setMode] = useState<'manual' | 'scan'>('manual');
  const [name, setName] = useState('');
  const [abilities, setAbilities] = useState<string[]>([]);
  const [extraArgs, setExtraArgs] = useState<ExtraArg[]>([]);
  const [scanLoading, setScanLoading] = useState(false);
  const [scannedModels, setScannedModels] = useState<ScannedProviderModel[]>(
    [],
  );
  const [selectedScannedModels, setSelectedScannedModels] = useState<
    Record<string, SelectedScannedModel>
  >({});
  const [scanQuery, setScanQuery] = useState('');

  useEffect(() => {
    const wasOpen = prevIsOpenRef.current;
    if (isOpen && !wasOpen) {
      setTab('llm');
      setMode('manual');
      setName('');
      setAbilities([]);
      setExtraArgs([]);
      setScanLoading(false);
      setScannedModels([]);
      setSelectedScannedModels({});
      setScanQuery('');
      onResetTestResult();
    }
    prevIsOpenRef.current = isOpen;
  }, [isOpen, onResetTestResult]);

  useEffect(() => {
    setScannedModels([]);
    setSelectedScannedModels({});
    setScanQuery('');
  }, [tab, mode]);

  const handleAdd = async () => {
    await onAddModel(tab, name, abilities, extraArgs);
  };

  const handleTest = async () => {
    await onTestModel(name, tab, tab === 'llm' ? abilities : [], extraArgs);
  };

  const handleScan = async () => {
    setScanLoading(true);
    try {
      const result = await onScanModels(tab);
      setScannedModels(result.models);
      setSelectedScannedModels({});
    } finally {
      setScanLoading(false);
    }
  };

  const handleAddScanned = async () => {
    const selectedModels = Object.values(selectedScannedModels);
    if (selectedModels.length === 0) return;
    await onAddScannedModels(tab, selectedModels);
  };

  const toggleAbility = (ability: string, checked: boolean) => {
    if (checked) {
      setAbilities([...abilities, ability]);
    } else {
      setAbilities(abilities.filter((a) => a !== ability));
    }
  };

  const toggleScannedModel = (
    model: ScannedProviderModel,
    checked: boolean,
  ) => {
    setSelectedScannedModels((prev) => {
      const next = { ...prev };
      if (checked) {
        next[model.id] = {
          model,
          abilities:
            model.type === 'llm'
              ? prev[model.id]?.abilities || model.abilities || []
              : [],
        };
      } else {
        delete next[model.id];
      }
      return next;
    });
  };

  const toggleScannedModelAbility = (
    modelId: string,
    ability: string,
    checked: boolean,
  ) => {
    setSelectedScannedModels((prev) => {
      const current = prev[modelId];
      if (!current) return prev;

      const nextAbilities = checked
        ? [...current.abilities, ability]
        : current.abilities.filter((item) => item !== ability);

      return {
        ...prev,
        [modelId]: {
          ...current,
          abilities: nextAbilities,
        },
      };
    });
  };

  const filteredScannedModels = scannedModels.filter((model) =>
    model.name.toLowerCase().includes(scanQuery.trim().toLowerCase()),
  );

  const handleScannedListWheel = (e: React.WheelEvent<HTMLDivElement>) => {
    const container = scannedListRef.current;
    if (!container) return;

    container.scrollTop += e.deltaY;
    e.preventDefault();
    e.stopPropagation();
  };

  return (
    <Popover
      open={isOpen}
      onOpenChange={(open) => (open ? onOpen() : onClose())}
    >
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="h-6 text-xs"
          onClick={(e) => e.stopPropagation()}
        >
          <Plus className="h-3 w-3 mr-1" />
          {t('models.addModel')}
        </Button>
      </PopoverTrigger>
      <PopoverContent
        className="w-[min(24rem,calc(100vw-2rem))] max-h-[calc(100vh-8rem)] overflow-y-auto"
        align="end"
        side="left"
        sideOffset={8}
        collisionPadding={16}
        onClick={(e) => e.stopPropagation()}
      >
        <Tabs value={tab} onValueChange={(v) => setTab(v as ModelType)}>
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="llm">
              <MessageSquareText className="h-4 w-4 mr-1" />
              {t('models.chat')}
            </TabsTrigger>
            <TabsTrigger value="embedding">
              <Cpu className="h-4 w-4 mr-1" />
              {t('models.embedding')}
            </TabsTrigger>
          </TabsList>

          <Tabs
            value={mode}
            onValueChange={(v) => setMode(v as 'manual' | 'scan')}
          >
            <TabsList className="grid w-full grid-cols-2 mt-3">
              <TabsTrigger value="manual">{t('models.manualAdd')}</TabsTrigger>
              <TabsTrigger value="scan">{t('models.scanAdd')}</TabsTrigger>
            </TabsList>

            <TabsContent value="manual" className="mt-3">
              <div className="space-y-3">
                <div className="space-y-2">
                  <Label>{t('models.modelName')}</Label>
                  <Input
                    placeholder={t('models.modelName')}
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                  />
                </div>

                {tab === 'llm' && (
                  <div className="space-y-2">
                    <Label>{t('models.abilities')}</Label>
                    <div className="flex gap-4">
                      <div className="flex items-center gap-2">
                        <Checkbox
                          id="add-vision"
                          checked={abilities.includes('vision')}
                          onCheckedChange={(checked) =>
                            toggleAbility('vision', checked as boolean)
                          }
                        />
                        <Label htmlFor="add-vision" className="text-sm">
                          <Eye className="h-3 w-3 inline mr-1" />
                          {t('models.visionAbility')}
                        </Label>
                      </div>
                      <div className="flex items-center gap-2">
                        <Checkbox
                          id="add-func-call"
                          checked={abilities.includes('func_call')}
                          onCheckedChange={(checked) =>
                            toggleAbility('func_call', checked as boolean)
                          }
                        />
                        <Label htmlFor="add-func-call" className="text-sm">
                          <Wrench className="h-3 w-3 inline mr-1" />
                          {t('models.functionCallAbility')}
                        </Label>
                      </div>
                    </div>
                  </div>
                )}

                <ExtraArgsEditor args={extraArgs} onChange={setExtraArgs} />
                <div className="flex gap-2">
                  <Button
                    className="flex-1"
                    size="sm"
                    onClick={handleAdd}
                    disabled={isSubmitting || isTesting}
                  >
                    {isSubmitting ? t('common.saving') : t('common.add')}
                  </Button>
                  <Button
                    className="flex-1"
                    size="sm"
                    variant="outline"
                    onClick={handleTest}
                    disabled={isSubmitting || isTesting}
                  >
                    {isTesting ? (
                      t('common.loading')
                    ) : testResult?.success ? (
                      <>
                        <Check className="h-4 w-4 mr-1 text-green-500" />
                        {(testResult.duration / 1000).toFixed(1)}s
                      </>
                    ) : (
                      t('common.test')
                    )}
                  </Button>
                </div>
              </div>
            </TabsContent>

            <TabsContent value="scan" className="space-y-3 mt-3">
              <div className="text-xs text-muted-foreground">
                {t('models.scanModelsHint')}
              </div>

              <div className="flex gap-2">
                <Button
                  className="flex-1"
                  size="sm"
                  variant="outline"
                  onClick={handleScan}
                  disabled={scanLoading || isSubmitting}
                >
                  {scanLoading ? (
                    <RefreshCw className="h-4 w-4 mr-1 animate-spin" />
                  ) : (
                    <Search className="h-4 w-4 mr-1" />
                  )}
                  {t('models.scanModels')}
                </Button>
                <Button
                  className="flex-1"
                  size="sm"
                  onClick={handleAddScanned}
                  disabled={
                    isSubmitting ||
                    scanLoading ||
                    Object.keys(selectedScannedModels).length === 0
                  }
                >
                  {isSubmitting
                    ? t('common.saving')
                    : t('models.addSelectedModels')}
                </Button>
              </div>

              <div className="space-y-2">
                <Label>{t('models.scannedModels')}</Label>
                <Input
                  placeholder={t('models.searchScannedModels')}
                  value={scanQuery}
                  onChange={(e) => setScanQuery(e.target.value)}
                  disabled={scannedModels.length === 0}
                />
              </div>

              <div
                ref={scannedListRef}
                className="h-64 overflow-y-auto overscroll-contain rounded-md border"
                onWheel={handleScannedListWheel}
              >
                <div className="p-3 space-y-2">
                  {filteredScannedModels.length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      {scannedModels.length === 0
                        ? t('models.noScannedModels')
                        : t('models.noScannedModelsMatch')}
                    </p>
                  ) : (
                    filteredScannedModels.map((model) => {
                      const isSelected = Boolean(
                        selectedScannedModels[model.id],
                      );
                      const selectedAbilities =
                        selectedScannedModels[model.id]?.abilities || [];
                      return (
                        <div
                          key={model.id}
                          className="rounded-md border p-3 space-y-2"
                        >
                          <div className="flex items-start gap-3">
                            <Checkbox
                              checked={isSelected || model.already_added}
                              disabled={model.already_added}
                              onCheckedChange={(checked) =>
                                toggleScannedModel(model, checked as boolean)
                              }
                            />
                            <div className="min-w-0 flex-1">
                              <div className="text-sm font-medium break-all">
                                {model.name}
                              </div>
                              <div className="text-xs text-muted-foreground">
                                {model.already_added
                                  ? t('models.alreadyAdded')
                                  : model.type === 'llm'
                                    ? t('models.chat')
                                    : t('models.embedding')}
                              </div>
                            </div>
                          </div>

                          {tab === 'llm' &&
                            isSelected &&
                            !model.already_added && (
                              <div className="flex gap-4 pl-7">
                                <div className="flex items-center gap-2">
                                  <Checkbox
                                    id={`scan-vision-${model.id}`}
                                    checked={selectedAbilities.includes(
                                      'vision',
                                    )}
                                    onCheckedChange={(checked) =>
                                      toggleScannedModelAbility(
                                        model.id,
                                        'vision',
                                        checked as boolean,
                                      )
                                    }
                                  />
                                  <Label
                                    htmlFor={`scan-vision-${model.id}`}
                                    className="text-sm"
                                  >
                                    <Eye className="h-3 w-3 inline mr-1" />
                                    {t('models.visionAbility')}
                                  </Label>
                                </div>
                                <div className="flex items-center gap-2">
                                  <Checkbox
                                    id={`scan-func-${model.id}`}
                                    checked={selectedAbilities.includes(
                                      'func_call',
                                    )}
                                    onCheckedChange={(checked) =>
                                      toggleScannedModelAbility(
                                        model.id,
                                        'func_call',
                                        checked as boolean,
                                      )
                                    }
                                  />
                                  <Label
                                    htmlFor={`scan-func-${model.id}`}
                                    className="text-sm"
                                  >
                                    <Wrench className="h-3 w-3 inline mr-1" />
                                    {t('models.functionCallAbility')}
                                  </Label>
                                </div>
                              </div>
                            )}
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            </TabsContent>
          </Tabs>
        </Tabs>
      </PopoverContent>
    </Popover>
  );
}
