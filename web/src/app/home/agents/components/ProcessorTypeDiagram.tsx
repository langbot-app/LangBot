import type { ComponentType } from 'react';
import { useTranslation } from 'react-i18next';
import {
  ArrowRightLeft,
  BookOpen,
  Bot,
  BrainCircuit,
  CornerDownRight,
  Filter,
  Hash,
  MessageSquare,
  MessageSquareReply,
  Puzzle,
  Radio,
  ScrollText,
  Sparkles,
  SquareTerminal,
  Workflow,
  Wrench,
  Zap,
} from 'lucide-react';
import type { AgentKind } from '@/app/infra/entities/api';
import { cn } from '@/lib/utils';

type Icon = ComponentType<{ className?: string }>;

interface FlowNode {
  icon: Icon;
  title: string;
  caption?: string;
  code?: string;
}

interface DiagramSpec {
  icon: Icon;
  title: string;
  summary: string;
  input: FlowNode;
  group: string;
  steps: FlowNode[];
  capabilities?: { icon: Icon; label: string }[];
  output: FlowNode;
  branch?: string;
  bestFor: string;
}

function Connector() {
  return (
    <svg
      className="mx-auto block h-7 w-3 text-[#2288ee]"
      viewBox="0 0 12 28"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M6 0v21"
        stroke="currentColor"
        strokeOpacity="0.55"
        strokeWidth="1.5"
        strokeDasharray="3 3"
        className="motion-safe:animate-[processor-flow_1.2s_linear_infinite]"
      />
      <path d="M2 20l4 6 4-6" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

function Node({
  node,
  tone = 'plain',
}: {
  node: FlowNode;
  tone?: 'plain' | 'accent';
}) {
  const Icon = node.icon;
  return (
    <div
      className={cn(
        'flex items-center gap-3 rounded-lg border px-3 py-2.5 shadow-xs',
        tone === 'accent'
          ? 'border-[#2288ee]/30 bg-[#2288ee]/[0.06] dark:bg-[#2288ee]/15'
          : 'bg-card',
      )}
    >
      <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-[#2288ee]/10 text-[#2288ee]">
        <Icon className="size-4" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-medium leading-5">
          {node.title}
        </span>
        {node.caption && (
          <span className="block text-xs leading-4 text-muted-foreground">
            {node.caption}
          </span>
        )}
      </span>
      {node.code && (
        <code className="shrink-0 rounded bg-muted px-1.5 py-0.5 font-mono text-[11px] text-muted-foreground">
          {node.code}
        </code>
      )}
    </div>
  );
}

function FlowDiagram({ spec, testId }: { spec: DiagramSpec; testId: string }) {
  const { t } = useTranslation();
  const KindIcon = spec.icon;
  return (
    <div
      data-testid={testId}
      className="flex h-full w-full flex-col justify-center gap-6 px-6 py-8 sm:px-10"
    >
      <style>{`@keyframes processor-flow { to { stroke-dashoffset: -12; } }`}</style>
      <header className="space-y-2">
        <span className="inline-flex items-center gap-1.5 rounded-full border bg-background px-2.5 py-1 text-xs font-medium text-[#2288ee]">
          <KindIcon className="size-3.5" />
          {spec.title}
        </span>
        <p className="max-w-md text-sm leading-relaxed text-muted-foreground">
          {spec.summary}
        </p>
      </header>

      <div className="mx-auto w-full max-w-md">
        <Node node={spec.input} />
        <Connector />
        <div className="relative rounded-xl border border-dashed border-[#2288ee]/40 bg-muted/20 p-3 pt-5">
          <span className="absolute -top-2.5 left-3 rounded-full border bg-background px-2 text-[11px] font-medium text-[#2288ee]">
            {spec.group}
          </span>
          {spec.steps.map((step, index) => (
            <div key={step.title}>
              {index > 0 && <Connector />}
              <Node node={step} tone="accent" />
            </div>
          ))}
          {spec.capabilities && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {spec.capabilities.map(({ icon: CapabilityIcon, label }) => (
                <span
                  key={label}
                  className="inline-flex items-center gap-1 rounded-md border bg-background px-2 py-0.5 text-[11px] text-muted-foreground"
                >
                  <CapabilityIcon className="size-3" />
                  {label}
                </span>
              ))}
            </div>
          )}
        </div>
        <Connector />
        <Node node={spec.output} />
        {spec.branch && (
          <p className="mt-3 flex items-start gap-1.5 text-xs leading-relaxed text-muted-foreground">
            <CornerDownRight className="mt-0.5 size-3.5 shrink-0" />
            {spec.branch}
          </p>
        )}
      </div>

      <footer className="mx-auto w-full max-w-md rounded-lg bg-muted/40 px-3 py-2 text-xs leading-relaxed">
        <span className="font-medium">{t('agents.diagram.bestFor')}</span>
        <span className="text-muted-foreground">{spec.bestFor}</span>
      </footer>
    </div>
  );
}

export default function ProcessorTypeDiagram({ kind }: { kind: AgentKind }) {
  const { t } = useTranslation();
  const specs: Record<AgentKind, DiagramSpec> = {
    pipeline: {
      icon: Workflow,
      title: t('agents.pipelineType'),
      summary: t('agents.diagram.pipeline.summary'),
      input: {
        icon: MessageSquare,
        title: t('agents.diagram.messageReceived'),
        code: 'message.received',
      },
      group: t('agents.diagram.pipeline.group'),
      steps: [
        { icon: Filter, title: t('agents.diagram.pipeline.trigger') },
        {
          icon: BrainCircuit,
          title: t('agents.diagram.pipeline.generate'),
          caption: t('agents.diagram.pipeline.generateCaption'),
        },
      ],
      capabilities: [
        { icon: Sparkles, label: t('agents.diagram.model') },
        { icon: BookOpen, label: t('agents.diagram.knowledge') },
        { icon: Wrench, label: t('agents.diagram.tools') },
      ],
      output: {
        icon: MessageSquareReply,
        title: t('agents.diagram.reply'),
      },
      bestFor: t('agents.diagram.pipeline.bestFor'),
    },
    agent: {
      icon: Bot,
      title: t('agents.agentType'),
      summary: t('agents.diagram.agent.summary'),
      input: {
        icon: Radio,
        title: t('agents.diagram.anyEvent'),
        caption: t('agents.diagram.anyEventCaption'),
      },
      group: t('agents.diagram.agent.group'),
      steps: [
        {
          icon: ScrollText,
          title: t('agents.diagram.agent.instructions'),
          caption: t('agents.diagram.agent.instructionsCaption'),
        },
        {
          icon: BrainCircuit,
          title: t('agents.diagram.agent.decide'),
          caption: t('agents.diagram.agent.decideCaption'),
        },
      ],
      capabilities: [
        { icon: Sparkles, label: t('agents.diagram.model') },
        { icon: Wrench, label: t('agents.diagram.tools') },
        { icon: ArrowRightLeft, label: t('agents.diagram.externalAgent') },
      ],
      output: {
        icon: Zap,
        title: t('agents.diagram.replyOrAction'),
      },
      bestFor: t('agents.diagram.agent.bestFor'),
    },
    event_processor: {
      icon: Puzzle,
      title: t('agents.eventProcessor.type'),
      summary: t('agents.diagram.eventProcessor.summary'),
      input: {
        icon: Radio,
        title: t('agents.diagram.eventProcessor.input'),
        caption: t('agents.diagram.eventProcessor.inputCaption'),
      },
      group: t('agents.diagram.eventProcessor.group'),
      steps: [
        {
          icon: Puzzle,
          title: t('agents.diagram.eventProcessor.handle'),
          code: 'on_event()',
        },
      ],
      output: {
        icon: Zap,
        title: t('agents.diagram.replyOrAction'),
        caption: t('agents.diagram.eventProcessor.outputCaption'),
      },
      branch: t('agents.diagram.eventProcessor.branch'),
      bestFor: t('agents.diagram.eventProcessor.bestFor'),
    },
    command_processor: {
      icon: SquareTerminal,
      title: t('agents.commandProcessor.type'),
      summary: t('agents.diagram.commandProcessor.summary'),
      input: {
        icon: MessageSquare,
        title: t('agents.diagram.messageReceived'),
        code: '/draw cat',
      },
      group: t('agents.diagram.commandProcessor.group'),
      steps: [
        {
          icon: Hash,
          title: t('agents.diagram.commandProcessor.match'),
          caption: t('agents.diagram.commandProcessor.matchCaption'),
        },
        {
          icon: SquareTerminal,
          title: t('agents.diagram.commandProcessor.run'),
          caption: t('agents.diagram.commandProcessor.runCaption'),
        },
      ],
      output: {
        icon: MessageSquareReply,
        title: t('agents.diagram.reply'),
      },
      branch: t('agents.diagram.commandProcessor.branch'),
      bestFor: t('agents.diagram.commandProcessor.bestFor'),
    },
  };
  const resolved = specs[kind] ? kind : 'pipeline';
  return (
    <FlowDiagram
      spec={specs[resolved]}
      testId={`${resolved.replace('_', '-')}-diagram`}
    />
  );
}
