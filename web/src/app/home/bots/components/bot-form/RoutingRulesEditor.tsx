'use client';

import { useTranslation } from 'react-i18next';
import { UseFormReturn } from 'react-hook-form';
import {
  PipelineRoutingRule,
  RoutingRuleOperator,
} from '@/app/infra/entities/api';
import { Ban, GripVertical, Plus, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { FormLabel } from '@/components/ui/form';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  DndContext,
  DragOverlay,
  closestCenter,
  PointerSensor,
  KeyboardSensor,
  useSensor,
  useSensors,
  DragEndEvent,
  DragStartEvent,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { useRef, useMemo, useState } from 'react';

export const PIPELINE_DISCARD = '__discard__';

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
  message_has_element: [
    { value: 'eq', labelKey: 'bots.operatorHas' },
    { value: 'neq', labelKey: 'bots.operatorNotHas' },
  ],
};

function getValuePlaceholder(
  t: (key: string) => string,
  rule: PipelineRoutingRule,
): string {
  if (rule.type === 'launcher_id')
    return t('bots.ruleValueLauncherIdPlaceholder');
  if (rule.type === 'message_has_element')
    return t('bots.ruleValueElementPlaceholder');
  if (rule.operator === 'regex') return t('bots.ruleValueRegexpPlaceholder');
  return t('bots.ruleValueMessagePlaceholder');
}

/* ── Static rule row (used in DragOverlay) ─────────────────────────── */

interface RuleRowContentProps {
  rule: PipelineRoutingRule;
  index: number;
  pipelineNameList: PipelineOption[];
  updateRule: (index: number, patch: Partial<PipelineRoutingRule>) => void;
  removeRule: (index: number) => void;
  dragHandleProps?: Record<string, unknown>;
  isOverlay?: boolean;
}

function RuleRowContent({
  rule,
  index,
  pipelineNameList,
  updateRule,
  removeRule,
  dragHandleProps,
  isOverlay,
}: RuleRowContentProps) {
  const { t } = useTranslation();
  const operatorsForType =
    OPERATORS_BY_TYPE[rule.type] || OPERATORS_BY_TYPE.message_content;
  const isDiscard = rule.pipeline_uuid === PIPELINE_DISCARD;

  return (
    <div
      className={`flex items-center gap-2 mt-2 p-3 border rounded-md bg-muted/30 ${
        isOverlay ? 'shadow-lg ring-2 ring-primary/20 bg-background' : ''
      }`}
    >
      {/* Drag handle */}
      <button
        type="button"
        className="cursor-grab active:cursor-grabbing shrink-0 text-muted-foreground hover:text-foreground touch-none"
        {...dragHandleProps}
      >
        <GripVertical className="h-4 w-4" />
      </button>

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
          <SelectItem value="message_has_element">
            {t('bots.ruleTypeMessageHasElement')}
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
            <SelectItem value="group">{t('bots.sessionTypeGroup')}</SelectItem>
          </SelectContent>
        </Select>
      ) : rule.type === 'message_has_element' ? (
        <Select
          value={rule.value}
          onValueChange={(val) => updateRule(index, { value: val })}
        >
          <SelectTrigger className="w-[120px]">
            <SelectValue placeholder={t('bots.ruleValueElementPlaceholder')} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="Image">{t('bots.elementImage')}</SelectItem>
            <SelectItem value="Voice">{t('bots.elementVoice')}</SelectItem>
            <SelectItem value="File">{t('bots.elementFile')}</SelectItem>
            <SelectItem value="Forward">{t('bots.elementForward')}</SelectItem>
            <SelectItem value="Face">{t('bots.elementFace')}</SelectItem>
            <SelectItem value="At">{t('bots.elementAt')}</SelectItem>
            <SelectItem value="AtAll">{t('bots.elementAtAll')}</SelectItem>
            <SelectItem value="Quote">{t('bots.elementQuote')}</SelectItem>
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
            isDiscard ? (
              <div className="flex items-center gap-2 text-destructive">
                <Ban className="h-3.5 w-3.5 shrink-0" />
                <span>{t('bots.pipelineDiscard')}</span>
              </div>
            ) : (
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
            )
          ) : (
            <SelectValue placeholder={t('bots.selectPipeline')} />
          )}
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={PIPELINE_DISCARD}>
            <div className="flex items-center gap-2 text-destructive">
              <Ban className="h-3.5 w-3.5 shrink-0" />
              <span>{t('bots.pipelineDiscard')}</span>
            </div>
          </SelectItem>
          <SelectSeparator />
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
}

/* ── Sortable rule row ─────────────────────────────────────────────── */

interface SortableRuleRowProps {
  id: string;
  rule: PipelineRoutingRule;
  index: number;
  pipelineNameList: PipelineOption[];
  updateRule: (index: number, patch: Partial<PipelineRoutingRule>) => void;
  removeRule: (index: number) => void;
}

function SortableRuleRow({
  id,
  rule,
  index,
  pipelineNameList,
  updateRule,
  removeRule,
}: SortableRuleRowProps) {
  const { attributes, listeners, setNodeRef, transform, isDragging } =
    useSortable({ id });

  const style = {
    transform: CSS.Transform.toString(transform),
    // No transition — items reorder visually during drag via transform;
    // on drop the data updates and transform resets, so animating would
    // cause a redundant "swap" flicker.
    opacity: isDragging ? 0.3 : undefined,
  };

  return (
    <div ref={setNodeRef} style={style}>
      <RuleRowContent
        rule={rule}
        index={index}
        pipelineNameList={pipelineNameList}
        updateRule={updateRule}
        removeRule={removeRule}
        dragHandleProps={{ ...attributes, ...listeners }}
      />
    </div>
  );
}

/* ── Main editor ───────────────────────────────────────────────────── */

export default function RoutingRulesEditor({
  form,
  pipelineNameList,
}: RoutingRulesEditorProps) {
  const { t } = useTranslation();
  const [activeId, setActiveId] = useState<string | null>(null);

  const rules: PipelineRoutingRule[] =
    form.watch('pipeline_routing_rules') || [];

  // Stable unique ids for sortable items.
  // We keep a running counter so newly added rules always get fresh ids.
  const nextId = useRef(0);
  const idsRef = useRef<string[]>([]);

  const sortableIds = useMemo(() => {
    // Grow the id list to match rules length (newly added items get new ids).
    while (idsRef.current.length < rules.length) {
      idsRef.current.push(`rule-${nextId.current++}`);
    }
    // Shrink if rules were removed from the end.
    if (idsRef.current.length > rules.length) {
      idsRef.current = idsRef.current.slice(0, rules.length);
    }
    return idsRef.current;
  }, [rules.length]);

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
    // Also remove the corresponding sortable id so indices stay in sync.
    idsRef.current.splice(index, 1);
    updateRules(updated);
  };

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  );

  const handleDragStart = (event: DragStartEvent) => {
    setActiveId(event.active.id as string);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    setActiveId(null);
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    const oldIndex = sortableIds.indexOf(active.id as string);
    const newIndex = sortableIds.indexOf(over.id as string);
    if (oldIndex === -1 || newIndex === -1) return;

    idsRef.current = arrayMove(idsRef.current, oldIndex, newIndex);
    updateRules(arrayMove(rules, oldIndex, newIndex));
  };

  const activeIndex = activeId ? sortableIds.indexOf(activeId) : -1;
  const activeRule = activeIndex >= 0 ? rules[activeIndex] : null;

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

      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
      >
        <SortableContext
          items={sortableIds}
          strategy={verticalListSortingStrategy}
        >
          {rules.map((rule, index) => (
            <SortableRuleRow
              key={sortableIds[index]}
              id={sortableIds[index]}
              rule={rule}
              index={index}
              pipelineNameList={pipelineNameList}
              updateRule={updateRule}
              removeRule={removeRule}
            />
          ))}
        </SortableContext>
        <DragOverlay dropAnimation={null}>
          {activeRule ? (
            <RuleRowContent
              rule={activeRule}
              index={activeIndex}
              pipelineNameList={pipelineNameList}
              updateRule={updateRule}
              removeRule={removeRule}
              isOverlay
            />
          ) : null}
        </DragOverlay>
      </DndContext>
    </div>
  );
}
