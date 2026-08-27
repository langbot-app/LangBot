import { useId } from 'react';
import { useTranslation } from 'react-i18next';
import type { AgentKind } from '@/app/infra/entities/api';

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
        <path d="M0 0 8 4 0 8Z" fill="var(--muted-foreground)" />
      </marker>
    </defs>
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
    { label: t('agents.diagramModel'), y: 155 },
    { label: t('agents.diagramTools'), y: 275 },
    { label: t('agents.diagramActions'), y: 395 },
  ];

  return (
    <svg
      viewBox="0 0 760 620"
      role="img"
      aria-label={t('agents.agentDiagramTitle')}
      className="h-full w-full"
      data-testid="agent-diagram"
    >
      <title>{t('agents.agentDiagramTitle')}</title>
      <desc>{t('agents.agentDiagramDescription')}</desc>
      <ArrowMarker id={arrowId} />

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

      {inputs.map((item) => (
        <g key={item.label}>
          <path
            d={`M222 ${item.y + 29} C286 ${item.y + 29} 282 310 314 310`}
            fill="none"
            stroke="var(--border)"
            strokeWidth="2"
          />
          <rect
            x="64"
            y={item.y}
            width="158"
            height="58"
            rx="14"
            fill="var(--muted)"
            fillOpacity="0.55"
          />
          <circle cx="91" cy={item.y + 29} r="5" fill="var(--primary)" />
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

      <circle
        cx="380"
        cy="310"
        r="100"
        fill="none"
        stroke="var(--border)"
        strokeDasharray="5 8"
      />
      <circle cx="380" cy="310" r="72" fill="var(--primary)" />
      <rect
        x="351"
        y="269"
        width="58"
        height="43"
        rx="14"
        fill="var(--primary-foreground)"
      />
      <circle cx="367" cy="290" r="3.5" fill="var(--primary)" />
      <circle cx="393" cy="290" r="3.5" fill="var(--primary)" />
      <path
        d="M367 301c7 6 19 6 26 0M380 269v-10m-6 0h12"
        fill="none"
        stroke="var(--primary)"
        strokeWidth="2"
        strokeLinecap="round"
      />
      <text
        x="380"
        y="340"
        textAnchor="middle"
        fill="var(--primary-foreground)"
        fontSize="18"
        fontWeight="700"
      >
        {t('agents.agentType')}
      </text>
      <text
        x="380"
        y="365"
        textAnchor="middle"
        fill="var(--primary-foreground)"
        fontSize="11"
        opacity="0.78"
      >
        {t('agents.diagramDecide')}
      </text>

      {outputs.map((item, index) => (
        <g key={item.label}>
          <path
            d={`M446 310 C478 310 474 ${item.y + 29} 538 ${item.y + 29}`}
            fill="none"
            stroke="var(--border)"
            strokeWidth="2"
            markerEnd={index === 2 ? `url(#${arrowId})` : undefined}
          />
          <rect
            x="538"
            y={item.y}
            width="158"
            height="58"
            rx="14"
            fill="var(--muted)"
            fillOpacity="0.55"
          />
          <circle
            cx="565"
            cy={item.y + 29}
            r="5"
            fill="var(--primary)"
            opacity={index === 1 ? 1 : 0.48}
          />
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
  const stages = [
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
      <title>{t('agents.pipelineDiagramTitle')}</title>
      <desc>{t('agents.pipelineDiagramDescription')}</desc>
      <ArrowMarker id={arrowId} />

      <rect width="760" height="620" fill="var(--card)" />
      <path
        d="M86 310H718"
        fill="none"
        stroke="var(--border)"
        strokeWidth="2"
        markerEnd={`url(#${arrowId})`}
      />

      <g>
        <circle
          cx="82"
          cy="310"
          r="42"
          fill="var(--muted)"
          stroke="var(--border)"
        />
        <path
          d="M64 299h36v23H77l-9 8v-8h-4z"
          fill="none"
          stroke="var(--foreground)"
          strokeWidth="2"
          strokeLinejoin="round"
        />
        <text
          x="82"
          y="382"
          textAnchor="middle"
          fill="var(--muted-foreground)"
          fontSize="13"
          fontWeight="550"
        >
          {t('agents.diagramMessage')}
        </text>
      </g>

      {stages.map((stage, index) => {
        const x = 198 + index * 146;
        const active = index === 1;
        return (
          <g key={stage}>
            <rect
              x={x - 55}
              y="260"
              width="110"
              height="100"
              rx="18"
              fill={active ? 'var(--primary)' : 'var(--card)'}
              stroke={active ? 'var(--primary)' : 'var(--border)'}
              strokeWidth={active ? 2 : 1}
            />
            <circle
              cx={x}
              cy="289"
              r="14"
              fill={active ? 'var(--primary-foreground)' : 'var(--muted)'}
            />
            <text
              x={x}
              y="294"
              textAnchor="middle"
              fill={active ? 'var(--primary)' : 'var(--foreground)'}
              fontSize="12"
              fontWeight="700"
            >
              {index + 1}
            </text>
            <text
              x={x}
              y="330"
              textAnchor="middle"
              fill={active ? 'var(--primary-foreground)' : 'var(--foreground)'}
              fontSize="13"
              fontWeight="600"
            >
              {stage}
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
