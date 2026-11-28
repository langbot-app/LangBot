import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Trash2, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { cn } from '@/lib/utils';
import { STEP_META } from '../lib/catalog';
import {
  pruneBranches,
  removalImpact,
  removeStep,
  stepById,
  updateStep,
} from '../lib/tree';
import { useEditor } from './EditorContext';
import {
  ClassifyForm,
  ConditionForm,
  ExtractForm,
  HandoffForm,
  HttpForm,
  LlmForm,
  OutputsPreview,
  RememberForm,
  ReplyForm,
  SendForm,
  type FormProps,
} from './forms';
import {
  AsrForm,
  Attachments,
  CodeForm,
  HistoryForm,
  KnowledgeForm,
  RandomForm,
  TtsForm,
} from './forms-more';
import { PlatformForm } from './PlatformForm';
import TriggersEditor from './TriggersEditor';

const FORMS: Partial<Record<string, (props: FormProps) => React.ReactNode>> = {
  llm: LlmForm,
  classify: ClassifyForm,
  extract: ExtractForm,
  condition: ConditionForm,
  remember: RememberForm,
  reply: ReplyForm,
  send: SendForm,
  http: HttpForm,
  handoff: HandoffForm,
  knowledge: KnowledgeForm,
  random: RandomForm,
  history: HistoryForm,
  code: CodeForm,
  tts: TtsForm,
  asr: AsrForm,
  platform: PlatformForm,
};

function RunValues({ title, value }: { title: string; value: unknown }) {
  const empty =
    value == null ||
    (typeof value === 'object' && Object.keys(value as object).length === 0);
  if (empty) return null;
  return (
    <div className="space-y-1">
      <p className="text-xs text-muted-foreground">{title}</p>
      <pre className="max-h-48 overflow-auto rounded-md border bg-muted/40 p-2 text-xs whitespace-pre-wrap break-all">
        {JSON.stringify(value, null, 2)}
      </pre>
    </div>
  );
}

export default function StepPanel({ id }: { id: string }) {
  const { t } = useTranslation();
  const { graph, setGraph, select, lastRun, readOnly } = useEditor();
  const [confirm, setConfirm] = useState(false);
  const step = stepById(graph, id);
  if (!step) return null;
  const meta = STEP_META[step.type];
  const Icon = meta?.icon;
  const Form = FORMS[step.type];
  const run = lastRun[id];

  const set = (patch: Record<string, unknown>) =>
    setGraph((current) => {
      const target = stepById(current, id);
      if (!target) return current;
      const config = { ...target.config, ...patch };
      if (
        (target.type === 'reply' || target.type === 'send') &&
        !('content' in patch) &&
        (config.image || config.voice)
      ) {
        // Text edits keep the attached image/voice in the sent message.
        config.content = [
          ...(config.text ? [{ type: 'text', text: config.text }] : []),
          ...(config.image ? [{ type: 'image', ref: config.image }] : []),
          ...(config.voice ? [{ type: 'voice', ref: config.voice }] : []),
        ];
      }
      if (config.content === undefined) delete config.content;
      let next = updateStep(current, id, { config });
      const branching = STEP_META[target.type]?.branching;
      if (branching && branching in patch) {
        const ids = ((config[branching] as { id?: string }[]) ?? [])
          .map((row) => String(row.id ?? ''))
          .concat('else');
        next = pruneBranches(next, id, ids);
      }
      return next;
    });

  const impact = removalImpact(graph, id).length;
  const remove = () => {
    setGraph((current) => removeStep(current, id));
    select(null);
  };

  return (
    <aside
      data-testid="step-panel"
      className="flex h-full w-[400px] flex-col border-l bg-background shadow-xl"
      onClick={(event) => event.stopPropagation()}
    >
      <div className="flex items-start gap-2.5 border-b px-4 py-3">
        {Icon && (
          <span
            className={cn(
              'mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg',
              meta.tone,
            )}
          >
            <Icon className="size-4" />
          </span>
        )}
        <div className="min-w-0 flex-1">
          <Input
            aria-label={t('workflows.form.stepName')}
            value={step.name}
            disabled={readOnly}
            className="h-8 border-transparent px-1 text-sm font-semibold shadow-none hover:border-input focus-visible:border-ring"
            onChange={(event) =>
              setGraph((current) =>
                updateStep(current, id, { name: event.target.value }),
              )
            }
          />
          <p className="px-1 text-xs text-muted-foreground">
            {t(`workflows.steps.${step.type}`)} ·{' '}
            {t(`workflows.stepDesc.${step.type}`)}
          </p>
        </div>
        {step.type !== 'start' && !readOnly && (
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="size-8 text-muted-foreground hover:text-destructive"
            aria-label={t('workflows.form.deleteStep')}
            onClick={() => (impact ? setConfirm(true) : remove())}
          >
            <Trash2 className="size-4" />
          </Button>
        )}
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="size-8 text-muted-foreground"
          aria-label={t('common.close')}
          onClick={() => select(null)}
        >
          <X className="size-4" />
        </Button>
      </div>
      <fieldset
        disabled={readOnly}
        className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4"
      >
        {step.type === 'start' ? (
          <TriggersEditor />
        ) : Form ? (
          <>
            <Form step={step} config={step.config} set={set} />
            {(step.type === 'reply' || step.type === 'send') && (
              <Attachments step={step} config={step.config} set={set} />
            )}
          </>
        ) : (
          <p className="text-sm text-muted-foreground">
            {t('workflows.form.unsupported')}
          </p>
        )}
        <OutputsPreview step={step} />
        {run && (
          <div className="space-y-2 border-t pt-4">
            <p className="text-sm font-medium">{t('workflows.form.lastRun')}</p>
            {run.error && (
              <p className="rounded-md border border-destructive/30 bg-destructive/5 p-2 text-xs text-destructive">
                {run.error}
              </p>
            )}
            <RunValues
              title={t('workflows.form.runInputs')}
              value={run.inputs}
            />
            <RunValues
              title={t('workflows.form.runOutputs')}
              value={run.outputs}
            />
          </div>
        )}
      </fieldset>
      <AlertDialog open={confirm} onOpenChange={setConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {t('workflows.form.deleteStep')}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {t('workflows.form.deleteBranchesConfirm', { count: impact })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={remove}>
              {t('common.delete')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </aside>
  );
}
