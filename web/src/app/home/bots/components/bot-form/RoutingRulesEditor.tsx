'use client';

import { useTranslation } from 'react-i18next';
import { UseFormReturn } from 'react-hook-form';
import {
  PipelineRoutingRule,
  RoutingRuleOperator,
} from '@/app/infra/entities/api';
import { Plus, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { FormLabel } from '@/components/ui/form';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

interface PipelineOption {
  value: string;
  label: string;
  emoji?: string;
}

interface RoutingRulesEditorProps {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  form: UseFormReturn<any>;
  pipelineNameList: PipelineOption[];
}

const OPERATORS_BY_TYPE: Record<
  PipelineRoutingRule['type'],
  { value: RoutingRuleOperator; labelKey: string }[]
> = {
  launcher_type: [
    { value: 'eq', labelKey: 'bots.operatorEq' },
    { value: 'neq', labelKey: 'bots.operatorNeq' },
  ],
  launcher_id: [
    { value: 'eq', labelKey: 'bots.operatorEq' },
    { value: 'neq', labelKey: 'bots.operatorNeq' },
    { value: 'contains', labelKey: 'bots.operatorContains' },
    { value: 'not_contains', labelKey: 'bots.operatorNotContains' },
    { value: 'regex', labelKey: 'bots.operatorRegex' },
  ],
  message_content: [
    { value: 'eq', labelKey: 'bots.operatorEq' },
    { value: 'neq', labelKey: 'bots.operatorNeq' },
    { value: 'contains', labelKey: 'bots.operatorContains' },
    { value: 'not_contains', labelKey: 'bots.operatorNotContains' },
    { value: 'starts_with', labelKey: 'bots.operatorStartsWith' },
    { value: 'regex', labelKey: 'bots.operatorRegex' },
  ],
};

function getValuePlaceholder(
  t: (key: string) => string,
  rule: PipelineRoutingRule,
): string {
  if (rule.type === 'launcher_id')
    return t('bots.ruleValueLauncherIdPlaceholder');
  if (rule.operator === 'regex') return t('bots.ruleValueRegexpPlaceholder');
  return t('bots.ruleValueMessagePlaceholder');
}

export default function RoutingRulesEditor({
  form,
  pipelineNameList,
}: RoutingRulesEditorProps) {
  const { t } = useTranslation();

  const rules: PipelineRoutingRule[] =
    form.watch('pipeline_routing_rules') || [];

  const updateRules = (newRules: PipelineRoutingRule[]) => {
    form.setValue('pipeline_routing_rules', newRules, { shouldDirty: true });
  };

  const addRule = () => {
    updateRules([
      ...rules,
      {
        type: 'launcher_type',
        operator: 'eq',
        value: '',
        pipeline_uuid: '',
      },
    ]);
  };

  const updateRule = (index: number, patch: Partial<PipelineRoutingRule>) => {
    const updated = [...rules];
    updated[index] = { ...updated[index], ...patch };
    updateRules(updated);
  };

  const removeRule = (index: number) => {
    const updated = [...rules];
    updated.splice(index, 1);
    updateRules(updated);
  };

  return (
    <div className="mt-6">
      <div className="flex items-center justify-between mb-2">
        <div>
          <FormLabel>{t('bots.routingRules')}</FormLabel>
          <p className="text-sm text-muted-foreground mt-1">
            {t('bots.routingRulesDescription')}
          </p>
        </div>
        <Button type="button" variant="outline" size="sm" onClick={addRule}>
          <Plus className="h-4 w-4 mr-1" />
          {t('bots.addRoutingRule')}
        </Button>
      </div>

      {rules.map((rule, index) => {
        const operatorsForType =
          OPERATORS_BY_TYPE[rule.type] || OPERATORS_BY_TYPE.message_content;

        return (
          <div
            key={index}
            className="flex items-center gap-2 mt-2 p-3 border rounded-md bg-muted/30"
          >
            {/* Field selector */}
            <Select
              value={rule.type}
              onValueChange={(val) => {
                updateRule(index, {
                  type: val as PipelineRoutingRule['type'],
                  operator: 'eq',
                  value: '',
                });
              }}
            >
              <SelectTrigger className="w-[130px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="launcher_type">
                  {t('bots.ruleTypeLauncherType')}
                </SelectItem>
                <SelectItem value="launcher_id">
                  {t('bots.ruleTypeLauncherId')}
                </SelectItem>
                <SelectItem value="message_content">
                  {t('bots.ruleTypeMessageContent')}
                </SelectItem>
              </SelectContent>
            </Select>

            {/* Operator selector */}
            <Select
              value={rule.operator || 'eq'}
              onValueChange={(val) => {
                updateRule(index, { operator: val as RoutingRuleOperator });
              }}
            >
              <SelectTrigger className="w-[120px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {operatorsForType.map((op) => (
                  <SelectItem key={op.value} value={op.value}>
                    {t(op.labelKey)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {/* Value input */}
            {rule.type === 'launcher_type' ? (
              <Select
                value={rule.value}
                onValueChange={(val) => updateRule(index, { value: val })}
              >
                <SelectTrigger className="w-[100px]">
                  <SelectValue placeholder={t('bots.ruleValuePlaceholder')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="person">
                    {t('bots.sessionTypePerson')}
                  </SelectItem>
                  <SelectItem value="group">
                    {t('bots.sessionTypeGroup')}
                  </SelectItem>
                </SelectContent>
              </Select>
            ) : (
              <Input
                className="flex-1"
                placeholder={getValuePlaceholder(t, rule)}
                value={rule.value}
                onChange={(e) => updateRule(index, { value: e.target.value })}
              />
            )}

            <span className="text-sm text-muted-foreground shrink-0">→</span>

            {/* Pipeline selector */}
            <Select
              value={rule.pipeline_uuid}
              onValueChange={(val) => updateRule(index, { pipeline_uuid: val })}
            >
              <SelectTrigger className="w-[200px]">
                {rule.pipeline_uuid ? (
                  (() => {
                    const p = pipelineNameList.find(
                      (p) => p.value === rule.pipeline_uuid,
                    );
                    return (
                      <div className="flex items-center gap-2">
                        {p?.emoji && (
                          <span className="text-sm shrink-0">{p.emoji}</span>
                        )}
                        <span>{p?.label ?? rule.pipeline_uuid}</span>
                      </div>
                    );
                  })()
                ) : (
                  <SelectValue placeholder={t('bots.selectPipeline')} />
                )}
              </SelectTrigger>
              <SelectContent>
                {pipelineNameList.map((item) => (
                  <SelectItem key={item.value} value={item.value}>
                    <div className="flex items-center gap-2">
                      {item.emoji && (
                        <span className="text-sm shrink-0">{item.emoji}</span>
                      )}
                      <span>{item.label}</span>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="shrink-0"
              onClick={() => removeRule(index)}
            >
              <Trash2 className="h-4 w-4 text-destructive" />
            </Button>
          </div>
        );
      })}
    </div>
  );
}
