

import { useState, useEffect } from 'react';
import { Plus, MessageSquareText, Cpu, Eye, Wrench, Check } from 'lucide-react';
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
import { ExtraArg, ModelType, TestResult } from '../types';
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
  onTestModel,
  isSubmitting,
  isTesting,
  testResult,
  onResetTestResult,
}: AddModelPopoverProps) {
  const { t } = useTranslation();

  const [tab, setTab] = useState<ModelType>('llm');
  const [name, setName] = useState('');
  const [abilities, setAbilities] = useState<string[]>([]);
  const [extraArgs, setExtraArgs] = useState<ExtraArg[]>([]);

  // Reset form when popover opens
  useEffect(() => {
    if (isOpen) {
      setTab('llm');
      setName('');
      setAbilities([]);
      setExtraArgs([]);
      onResetTestResult();
    }
  }, [isOpen]);

  const handleAdd = async () => {
    await onAddModel(tab, name, abilities, extraArgs);
  };

  const handleTest = async () => {
    await onTestModel(name, tab, tab === 'llm' ? abilities : [], extraArgs);
  };

  const toggleAbility = (ability: string, checked: boolean) => {
    if (checked) {
      setAbilities([...abilities, ability]);
    } else {
      setAbilities(abilities.filter((a) => a !== ability));
    }
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
        className="w-80"
        align="end"
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

          <TabsContent value="llm" className="space-y-3 mt-3">
            <div className="space-y-2">
              <Label>{t('models.modelName')}</Label>
              <Input
                placeholder={t('models.modelName')}
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
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
          </TabsContent>

          <TabsContent value="embedding" className="space-y-3 mt-3">
            <div className="space-y-2">
              <Label>{t('models.modelName')}</Label>
              <Input
                placeholder={t('models.modelName')}
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
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
          </TabsContent>
        </Tabs>
      </PopoverContent>
    </Popover>
  );
}
