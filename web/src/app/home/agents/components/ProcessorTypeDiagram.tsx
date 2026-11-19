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
        0%, 100% { stroke-opacity: var(--processor-relation-opacity-min); }
        50% { stroke-opacity: var(--processor-relation-opacity-max); }
      }

      .processor-diagram {
        --processor-blue-node-fill: color-mix(in srgb, ${LANGBOT_BLUE} 7%, var(--card));
        --processor-cyan-node-fill: color-mix(in srgb, ${LANGBOT_CYAN} 7%, var(--card));
        --processor-node-stroke-opacity: 0.18;
        --processor-flow-opacity: 0.34;
        --processor-relation-opacity-min: 0.28;
        --processor-relation-opacity-max: 0.72;
        --processor-capability-fill: color-mix(in srgb, ${LANGBOT_CYAN} 4%, var(--card));
        --processor-capability-stroke-opacity: 0.45;
        --processor-icon-fill: color-mix(in srgb, ${LANGBOT_CYAN} 10%, var(--card));
      }

      .dark .processor-diagram {
        --processor-blue-node-fill: color-mix(in srgb, ${LANGBOT_BLUE} 17%, var(--card));
        --processor-cyan-node-fill: color-mix(in srgb, ${LANGBOT_CYAN} 15%, var(--card));
        --processor-node-stroke-opacity: 0.5;
        --processor-flow-opacity: 0.72;
        --processor-relation-opacity-min: 0.58;
        --processor-relation-opacity-max: 1;
        --processor-capability-fill: color-mix(in srgb, ${LANGBOT_CYAN} 10%, var(--card));
        --processor-capability-stroke-opacity: 0.78;
        --processor-icon-fill: color-mix(in srgb, ${LANGBOT_CYAN} 20%, var(--card));
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
      className="processor-diagram h-full w-full"
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
            opacity="var(--processor-flow-opacity)"
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
            fill="var(--processor-blue-node-fill)"
            stroke={LANGBOT_BLUE}
            strokeOpacity="var(--processor-node-stroke-opacity)"
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
            fill="var(--processor-capability-fill)"
            stroke={LANGBOT_CYAN}
            strokeOpacity="var(--processor-capability-stroke-opacity)"
            strokeWidth="1.5"
          />
          <circle
            cx="565"
            cy={item.y + 29}
            r="11"
            fill="var(--processor-icon-fill)"
            stroke={LANGBOT_CYAN}
            strokeOpacity="var(--processor-capability-stroke-opacity)"
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
      className="processor-diagram h-full w-full"
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
        opacity="var(--processor-flow-opacity)"
        markerEnd={`url(#${arrowId})`}
      />
      <path
        d="M156 310H724"
        fill="none"
        stroke={LANGBOT_BLUE}
        strokeWidth="3"
        strokeDasharray="4 11"
        strokeLinecap="round"
        className="processor-line-flow"
        data-motion="flow"
        data-dash-cycle="15"
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
                  : index === 3
                    ? 'var(--processor-cyan-node-fill)'
                    : 'var(--processor-blue-node-fill)'
              }
              stroke={
                active
                  ? LANGBOT_BLUE
                  : index === 3
                    ? LANGBOT_CYAN
                    : LANGBOT_BLUE
              }
              strokeOpacity={
                active ? 1 : 'var(--processor-node-stroke-opacity)'
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

function RunnerDiagram() {
  const { t } = useTranslation();
  const arrowId = `runner-arrow-${useId().replace(/:/g, '')}`;
  const inputs = [
    { label: t('agents.diagramMessages'), y: 175 },
    { label: t('agents.diagramMembers'), y: 281 },
    { label: t('agents.diagramFeedback'), y: 387 },
  ];
  const outputs = [
    { kind: 'action' as const, label: t('agents.diagramActions'), y: 228 },
    {
      kind: 'tool' as const,
      label: t('agents.eventProcessor.logsTab'),
      y: 334,
    },
  ];
  const mono = 'ui-monospace, SFMono-Regular, Menlo, monospace';
  // Keyword colors follow the code-editor accents used across the console.
  const code: { indent: number; parts: [string, string][] }[] = [
    { indent: 0, parts: [['@handler', '#8b5cf6']] },
    {
      indent: 0,
      parts: [
        ['async def ', LANGBOT_BLUE],
        ['on_event', LANGBOT_CYAN],
        ['(event):', 'var(--foreground)'],
      ],
    },
    {
      indent: 1,
      parts: [
        ['if ', LANGBOT_BLUE],
        ['event.type == ', 'var(--foreground)'],
        ['"joined"', '#f59e0b'],
        [':', 'var(--foreground)'],
      ],
    },
    {
      indent: 2,
      parts: [
        ['await ', LANGBOT_BLUE],
        ['event.reply(...)', 'var(--foreground)'],
      ],
    },
  ];

  return (
    <svg
      viewBox="0 0 760 620"
      role="img"
      aria-label={t('agents.eventProcessor.type')}
      className="processor-diagram h-full w-full"
      data-testid="event-processor-diagram"
    >
      <ArrowMarker id={arrowId} />
      <DiagramMotionStyles />

      <rect width="760" height="620" fill="var(--card)" />

      <text
        x="40"
        y="150"
        fill="var(--muted-foreground)"
        fontSize="13"
        fontWeight="600"
      >
        {t('agents.diagram.eventProcessor.input')}
      </text>
      {inputs.map((item, index) => (
        <g key={item.label}>
          <path
            d={`M178 ${item.y + 26} C214 ${item.y + 26} 214 310 246 310`}
            fill="none"
            stroke={LANGBOT_BLUE}
            strokeWidth="2"
            strokeDasharray="4 11"
            opacity="var(--processor-flow-opacity)"
            markerEnd={`url(#${arrowId})`}
            className="processor-line-flow"
            data-motion="flow"
            style={{ animationDelay: `${index * -0.35}s` }}
          />
          <rect
            x="40"
            y={item.y}
            width="138"
            height="52"
            rx="14"
            fill="var(--processor-blue-node-fill)"
            stroke={LANGBOT_BLUE}
            strokeOpacity="var(--processor-node-stroke-opacity)"
          />
          <circle
            cx="64"
            cy={item.y + 26}
            r="5"
            fill={index === 1 ? LANGBOT_CYAN : LANGBOT_BLUE}
          />
          <text
            x="80"
            y={item.y + 31}
            fill="var(--foreground)"
            fontSize="14"
            fontWeight="550"
          >
            {item.label}
          </text>
        </g>
      ))}

      <rect
        x="250"
        y="208"
        width="270"
        height="204"
        rx="16"
        fill="var(--card)"
        stroke={LANGBOT_BLUE}
        strokeOpacity="0.45"
        strokeWidth="1.5"
      />
      <path
        d="M250 224 a16 16 0 0 1 16 -16 h238 a16 16 0 0 1 16 16 v22 h-270z"
        fill={LANGBOT_BLUE}
      />
      <text
        x="268"
        y="233"
        fill="var(--primary-foreground)"
        fontSize="14"
        fontWeight="700"
      >
        {t('agents.eventProcessor.type')}
      </text>
      <text
        x="502"
        y="233"
        textAnchor="end"
        fill="var(--primary-foreground)"
        fontSize="11"
        fontFamily={mono}
        opacity="0.8"
      >
        processor.py
      </text>
      {code.map((line, index) => (
        <g key={index}>
          <text
            x="268"
            y={280 + index * 30}
            fill="var(--muted-foreground)"
            fontSize="11"
            fontFamily={mono}
            opacity="0.6"
          >
            {index + 1}
          </text>
          <text
            x={288 + line.indent * 14}
            y={280 + index * 30}
            fontSize="12.5"
            fontFamily={mono}
          >
            {line.parts.map(([textPart, color], partIndex) => (
              <tspan key={partIndex} fill={color}>
                {textPart}
              </tspan>
            ))}
          </text>
        </g>
      ))}

      <text
        x="566"
        y="203"
        fill="var(--muted-foreground)"
        fontSize="13"
        fontWeight="600"
      >
        {t('agents.diagram.replyOrAction')}
      </text>
      {outputs.map((item, index) => (
        <g key={item.label}>
          <path
            d={`M520 310 C546 310 544 ${item.y + 26} 566 ${item.y + 26}`}
            fill="none"
            stroke={LANGBOT_CYAN}
            strokeWidth="1.8"
            strokeDasharray="5 6"
            className="processor-link-breathe"
            data-motion="relation"
            style={{ animationDelay: `${index * -0.45}s` }}
          />
          <rect
            x="566"
            y={item.y}
            width="154"
            height="52"
            rx="14"
            fill="var(--processor-capability-fill)"
            stroke={LANGBOT_CYAN}
            strokeOpacity="var(--processor-capability-stroke-opacity)"
            strokeWidth="1.5"
          />
          <circle
            cx="592"
            cy={item.y + 26}
            r="11"
            fill="var(--processor-icon-fill)"
            stroke={LANGBOT_CYAN}
            strokeOpacity="var(--processor-capability-stroke-opacity)"
          />
          <CapabilityIcon kind={item.kind} x={592} y={item.y + 26} />
          <text
            x="611"
            y={item.y + 31}
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

function CommandDiagram() {
  const { t } = useTranslation();
  const arrowId = `command-arrow-${useId().replace(/:/g, '')}`;

  return (
    <svg
      viewBox="0 0 760 620"
      role="img"
      aria-label={t('agents.diagram.commandProcessor.summary')}
      className="processor-diagram h-full w-full"
      data-testid="command-processor-diagram"
    >
      <ArrowMarker id={arrowId} />
      <DiagramMotionStyles />

      <rect width="760" height="620" fill="var(--card)" />
      <text
        x="40"
        y="150"
        fill="var(--muted-foreground)"
        fontSize="13"
        fontWeight="600"
      >
        {t('agents.diagram.commandProcessor.summary')}
      </text>

      <path
        d="M196 310H262"
        fill="none"
        stroke={LANGBOT_BLUE}
        strokeWidth="3"
        strokeDasharray="4 11"
        strokeLinecap="round"
        className="processor-line-flow"
        data-motion="flow"
      />
      <rect
        x="40"
        y="281"
        width="156"
        height="58"
        rx="14"
        fill="var(--processor-blue-node-fill)"
        stroke={LANGBOT_BLUE}
        strokeOpacity="var(--processor-node-stroke-opacity)"
      />
      <circle cx="65" cy="310" r="5" fill={LANGBOT_BLUE} />
      <text
        x="82"
        y="315"
        fill="var(--foreground)"
        fontSize="14"
        fontWeight="600"
        fontFamily="ui-monospace, monospace"
      >
        /draw cat
      </text>

      <rect
        x="262"
        y="278"
        width="176"
        height="64"
        rx="16"
        fill={LANGBOT_BLUE}
      />
      <text
        x="350"
        y="316"
        textAnchor="middle"
        fill="var(--primary-foreground)"
        fontSize="16"
        fontWeight="700"
      >
        {t('agents.commandProcessor.type')}
      </text>
      <text
        x="350"
        y="370"
        textAnchor="middle"
        fill="var(--muted-foreground)"
        fontSize="12"
      >
        {t('agents.diagram.commandProcessor.match')}
      </text>

      <text
        x="512"
        y="182"
        fill="var(--muted-foreground)"
        fontSize="13"
        fontWeight="600"
      >
        {t('agents.diagram.commandProcessor.hit')}
      </text>
      <path
        d="M438 310 C474 310 476 225 512 225"
        fill="none"
        stroke={LANGBOT_BLUE}
        strokeWidth="2"
        strokeDasharray="4 11"
        opacity="var(--processor-flow-opacity)"
        markerEnd={`url(#${arrowId})`}
        className="processor-line-flow"
        data-motion="flow"
      />
      <rect
        x="512"
        y="196"
        width="208"
        height="58"
        rx="14"
        fill="var(--processor-capability-fill)"
        stroke={LANGBOT_CYAN}
        strokeOpacity="var(--processor-capability-stroke-opacity)"
        strokeWidth="1.5"
      />
      <circle
        cx="539"
        cy="225"
        r="11"
        fill="var(--processor-icon-fill)"
        stroke={LANGBOT_CYAN}
        strokeOpacity="var(--processor-capability-stroke-opacity)"
      />
      <CapabilityIcon kind="action" x={539} y={225} />
      <text
        x="558"
        y="230"
        fill="var(--foreground)"
        fontSize="14"
        fontWeight="550"
      >
        {t('agents.diagram.commandProcessor.run')}
      </text>

      <text
        x="512"
        y="356"
        fill="var(--muted-foreground)"
        fontSize="13"
        fontWeight="600"
      >
        {t('agents.diagram.commandProcessor.miss')}
      </text>
      <path
        d="M438 310 C474 310 476 399 512 399"
        fill="none"
        stroke="var(--muted-foreground)"
        strokeWidth="1.6"
        strokeDasharray="5 6"
        opacity="0.5"
      />
      <rect
        x="512"
        y="370"
        width="208"
        height="58"
        rx="14"
        fill="none"
        stroke="var(--muted-foreground)"
        strokeOpacity="0.45"
        strokeDasharray="5 5"
      />
      <text
        x="536"
        y="404"
        fill="var(--muted-foreground)"
        fontSize="14"
        fontWeight="550"
      >
        {t('bots.routingLayers.rules')}
      </text>
    </svg>
  );
}

export default function ProcessorTypeDiagram({ kind }: { kind: AgentKind }) {
  if (kind === 'command_processor') return <CommandDiagram />;
  if (kind === 'event_processor') return <RunnerDiagram />;
  return kind === 'agent' ? <AgentDiagram /> : <PipelineDiagram />;
}
