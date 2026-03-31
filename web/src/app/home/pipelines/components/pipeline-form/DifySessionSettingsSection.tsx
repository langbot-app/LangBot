import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import DynamicFormComponent from '@/app/home/components/dynamic-form/DynamicFormComponent';
import {
  DifySessionSettingsValues,
  PipelineConfigStage,
} from '@/app/infra/entities/pipeline';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { useTranslation } from 'react-i18next';

export default function DifySessionSettingsSection({
  stage,
  initialValues,
  onSubmit,
}: {
  stage: PipelineConfigStage;
  initialValues: DifySessionSettingsValues;
  onSubmit: (values: DifySessionSettingsValues) => void;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const { t } = useTranslation();

  return (
    <Collapsible
      open={isOpen}
      onOpenChange={setIsOpen}
      className="mb-6 rounded-lg border"
    >
      <CollapsibleTrigger asChild>
        <button
          type="button"
          className="flex w-full items-start justify-between gap-3 px-4 py-3 text-left hover:bg-muted/30"
        >
          <div className="space-y-1">
            <div className="text-lg font-medium">
              {extractI18nObject(stage.label)}
            </div>
            {stage.description && (
              <div className="text-sm text-gray-500">
                {extractI18nObject(stage.description)}
              </div>
            )}
            <div className="text-xs text-muted-foreground">
              {t('pipelines.difySessionSettings.scopeHint')}
            </div>
          </div>
          <div className="mt-1 text-muted-foreground">
            {isOpen ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
          </div>
        </button>
      </CollapsibleTrigger>

      <CollapsibleContent forceMount className="border-t px-4 py-4">
        <DynamicFormComponent
          itemConfigList={stage.config}
          initialValues={initialValues as Record<string, unknown>}
          onSubmit={(values) => {
            onSubmit(values as DifySessionSettingsValues);
          }}
        />
      </CollapsibleContent>
    </Collapsible>
  );
}
