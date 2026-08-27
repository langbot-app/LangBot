import { useId } from 'react';
import { useTranslation } from 'react-i18next';
import type { AgentKind } from '@/app/infra/entities/api';

const LANGBOT_BLUE = '#2288ee';
const LANGBOT_CYAN = '#19b8c9';

function DiagramMotionStyles() {
  return (
    <style>{`
      @keyframes processor-line-flow {
        to { stroke-dashoffset: -30; }
      }

      @keyframes processor-link-breathe {
        0%, 100% { stroke-opacity: 0.28; }
        50% { stroke-opacity: 0.72; }
      }

      .processor-line-flow {
        animation: processor-line-flow 1.8s linear infinite;
      }

      .processor-link-breathe {
        animation: processor-link-breathe 2.8s ease-in-out infinite;
      }

      @media (prefers-reduced-motion: reduce) {
        .processor-line-flow,
        .processor-link-breathe {
          animation: none;
        }
      }
    `}</style>
  );
}

function ArrowMarker({ id }: { id: string }) {
  return (
    <defs>
      <marker
        id={id}
        markerWidth="8"
        markerHeight="8"
        refX="7"
        refY="4"
        orient="auto"
      >
        <path d="M0 0 8 4 0 8Z" fill={LANGBOT_BLUE} />
      </marker>
    </defs>
  );
}

function CapabilityIcon({
  kind,
  x,
  y,
}: {
  kind: 'model' | 'tool' | 'action';
  x: number;
  y: number;
}) {
  return (
    <g
      transform={`translate(${x - 9} ${y - 9})`}
      fill="none"
      stroke={LANGBOT_CYAN}
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {kind === 'model' && (
        <>
          <path d="m7 1 1.4 4.1L12.5 6.5 8.4 8 7 12 5.6 8 1.5 6.5l4.1-1.4L7 1Z" />
          <path d="m14.5 10 .7 2.3 2.3.7-2.3.8-.7 2.2-.8-2.2-2.2-.8 2.2-.7.8-2.3Z" />
        </>
      )}
      {kind === 'tool' && (
        <path d="M12.8 2.1a4.1 4.1 0 0 0-5.2 5.2L2 12.9a2.1 2.1 0 1 0 3 3l5.6-5.6a4.1 4.1 0 0 0 5.2-5.2l-2.7 2.7-2.8-2.8 2.5-2.9Z" />
      )}
      {kind === 'action' && (
        <path d="M10.5 1 3 10.5h6L8 17l7.5-9.5h-6L10.5 1Z" />
      )}
    </g>
  );
}

function AgentDiagram() {
  const { t } = useTranslation();
  const arrowId = `agent-arrow-${useId().replace(/:/g, '')}`;
  const inputs = [
    { label: t('agents.diagramMessages'), y: 155 },
    { label: t('agents.diagramMembers'), y: 275 },
    { label: t('agents.diagramFeedback'), y: 395 },
  ];
  const outputs = [
    { kind: 'model' as const, label: t('agents.diagramModel'), y: 155 },
    { kind: 'tool' as const, label: t('agents.diagramTools'), y: 275 },
    { kind: 'action' as const, label: t('agents.diagramActions'), y: 395 },
  ];

  return (
    <svg
      viewBox="0 0 760 620"
      role="img"
      aria-label={t('agents.agentDiagramTitle')}
      className="h-full w-full"
      data-testid="agent-diagram"
    >
      <desc>{t('agents.agentDiagramDescription')}</desc>
      <ArrowMarker id={arrowId} />
      <DiagramMotionStyles />

      <rect width="760" height="620" fill="var(--card)" />

      <text
        x="74"
        y="112"
        fill="var(--muted-foreground)"
        fontSize="13"
        fontWeight="600"
      >
        {t('agents.diagramEvents')}
      </text>

      {inputs.map((item, index) => (
        <g key={item.label}>
          <path
            d={`M222 ${item.y + 29} C286 ${item.y + 29} 292 310 324 310`}
            fill="none"
            stroke={LANGBOT_BLUE}
            strokeWidth="2"
            strokeDasharray="4 11"
            opacity="0.32"
            markerEnd={`url(#${arrowId})`}
            className="processor-line-flow"
            data-motion="flow"
            style={{ animationDelay: `${index * -0.35}s` }}
          />
          <rect
            x="64"
            y={item.y}
            width="158"
            height="58"
            rx="14"
            fill={`color-mix(in srgb, ${LANGBOT_BLUE} 7%, var(--card))`}
          />
          <circle
            cx="91"
            cy={item.y + 29}
            r="5"
            fill={index === 1 ? LANGBOT_CYAN : LANGBOT_BLUE}
          />
          <text
            x="110"
            y={item.y + 34}
            fill="var(--foreground)"
            fontSize="14"
            fontWeight="550"
          >
            {item.label}
          </text>
        </g>
      ))}

      <rect
        x="324"
        y="278"
        width="112"
        height="64"
        rx="16"
        fill={LANGBOT_BLUE}
      />
      <text
        x="380"
        y="317"
        textAnchor="middle"
        fill="var(--primary-foreground)"
        fontSize="18"
        fontWeight="700"
      >
        {t('agents.agentType')}
      </text>

      <text
        x="538"
        y="112"
        fill="var(--muted-foreground)"
        fontSize="13"
        fontWeight="600"
      >
        {t('agents.diagramAgentCanUse')}
      </text>

      {outputs.map((item, index) => (
        <g key={item.label}>
          <path
            d={`M436 310 C468 310 474 ${item.y + 29} 538 ${item.y + 29}`}
            fill="none"
            stroke={LANGBOT_CYAN}
            strokeWidth="1.8"
            strokeDasharray="5 6"
            opacity="0.48"
            className="processor-link-breathe"
            data-motion="relation"
            style={{ animationDelay: `${index * -0.45}s` }}
          />
          <rect
            x="538"
            y={item.y}
            width="158"
            height="58"
            rx="14"
            fill="var(--card)"
            stroke={LANGBOT_CYAN}
            strokeOpacity="0.45"
            strokeWidth="1.5"
          />
          <circle
            cx="565"
            cy={item.y + 29}
            r="11"
            fill={`color-mix(in srgb, ${LANGBOT_CYAN} 10%, var(--card))`}
            stroke={LANGBOT_CYAN}
            strokeOpacity="0.5"
          />
          <CapabilityIcon kind={item.kind} x={565} y={item.y + 29} />
          <text
            x="584"
            y={item.y + 34}
            fill="var(--foreground)"
            fontSize="14"
            fontWeight="550"
          >
            {item.label}
          </text>
        </g>
      ))}
    </svg>
  );
}

function PipelineDiagram() {
  const { t } = useTranslation();
  const arrowId = `pipeline-arrow-${useId().replace(/:/g, '')}`;
  const steps = [
    t('agents.diagramMessage'),
    t('agents.diagramPreprocess'),
    t('agents.diagramAI'),
    t('agents.diagramPostprocess'),
    t('agents.diagramOutput'),
  ];

  return (
    <svg
      viewBox="0 0 760 620"
      role="img"
      aria-label={t('agents.pipelineDiagramTitle')}
      className="h-full w-full"
      data-testid="pipeline-diagram"
    >
      <desc>{t('agents.pipelineDiagramDescription')}</desc>
      <ArrowMarker id={arrowId} />
      <DiagramMotionStyles />

      <rect width="760" height="620" fill="var(--card)" />
      <text
        x="40"
        y="238"
        fill="var(--muted-foreground)"
        fontSize="13"
        fontWeight="600"
      >
        {t('agents.pipelineDiagramFlow')}
      </text>
      <path
        d="M156 310H738"
        fill="none"
        stroke={LANGBOT_BLUE}
        strokeWidth="2"
        opacity="0.32"
        markerEnd={`url(#${arrowId})`}
      />
      <path
        d="M156 310H724"
        fill="none"
        stroke={LANGBOT_BLUE}
        strokeWidth="3"
        strokeDasharray="4 14"
        strokeLinecap="round"
        className="processor-line-flow"
        data-motion="flow"
      />

      {steps.map((step, index) => {
        const x = 40 + index * 142;
        const active = index === 2;
        return (
          <g key={step}>
            <rect
              x={x}
              y="281"
              width="116"
              height="58"
              rx="14"
              fill={
                active
                  ? LANGBOT_BLUE
                  : `color-mix(in srgb, ${index === 3 ? LANGBOT_CYAN : LANGBOT_BLUE} 7%, var(--card))`
              }
            />
            {!active && (
              <circle
                cx={x + 25}
                cy="310"
                r="5"
                fill={index === 3 ? LANGBOT_CYAN : LANGBOT_BLUE}
              />
            )}
            <text
              x={active ? x + 58 : x + 44}
              y="315"
              textAnchor={active ? 'middle' : 'start'}
              fill={active ? 'var(--primary-foreground)' : 'var(--foreground)'}
              fontSize="13"
              fontWeight="600"
            >
              {step}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export default function ProcessorTypeDiagram({ kind }: { kind: AgentKind }) {
  return kind === 'agent' ? <AgentDiagram /> : <PipelineDiagram />;
}
