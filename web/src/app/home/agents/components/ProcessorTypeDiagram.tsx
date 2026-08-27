import { useId } from 'react';
import { useTranslation } from 'react-i18next';
import type { AgentKind } from '@/app/infra/entities/api';

function DiagramArrow({ id }: { id: string }) {
  return (
    <marker
      id={id}
      markerWidth="8"
      markerHeight="8"
      refX="7"
      refY="4"
      orient="auto"
      markerUnits="strokeWidth"
    >
      <path d="M0,0 L8,4 L0,8 Z" fill="var(--muted-foreground)" />
    </marker>
  );
}

function AgentDiagram() {
  const { t } = useTranslation();
  const arrowId = `agent-arrow-${useId().replace(/:/g, '')}`;

  return (
    <svg
      viewBox="0 0 720 340"
      role="img"
      aria-label={t('agents.agentDiagramTitle')}
      className="h-auto w-full"
      data-testid="agent-diagram"
    >
      <title>{t('agents.agentDiagramTitle')}</title>
      <desc>{t('agents.agentDiagramDescription')}</desc>
      <defs>
        <linearGradient id="agent-core" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="var(--primary)" stopOpacity="0.22" />
          <stop offset="1" stopColor="var(--primary)" stopOpacity="0.06" />
        </linearGradient>
        <DiagramArrow id={arrowId} />
      </defs>

      <rect
        x="24"
        y="42"
        width="184"
        height="256"
        rx="22"
        fill="var(--muted)"
        fillOpacity="0.48"
        stroke="var(--border)"
      />
      <text
        x="116"
        y="76"
        textAnchor="middle"
        fill="var(--foreground)"
        fontSize="16"
        fontWeight="600"
      >
        {t('agents.diagramEvents')}
      </text>

      {[
        {
          y: 98,
          label: t('agents.diagramMessages'),
          icon: 'M44 116h12l8 8v-8h28v-24H44z',
        },
        {
          y: 160,
          label: t('agents.diagramMembers'),
          icon: 'M51 167a7 7 0 1 0 0-14 7 7 0 0 0 0 14zm-11 14c1-8 6-12 11-12s10 4 11 12m8-22a6 6 0 1 0 0-12m5 28c-1-6-4-9-9-10',
        },
        {
          y: 222,
          label: t('agents.diagramFeedback'),
          icon: 'M52 213l4 9 10 1-7 7 2 10-9-5-9 5 2-10-7-7 10-1z',
        },
      ].map((item) => (
        <g key={item.label}>
          <rect
            x="38"
            y={item.y}
            width="156"
            height="48"
            rx="13"
            fill="var(--card)"
            stroke="var(--border)"
          />
          <path
            d={item.icon}
            transform={`translate(0 ${item.y - 92})`}
            fill="none"
            stroke="var(--primary)"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <text
            x="120"
            y={item.y + 30}
            textAnchor="middle"
            fill="var(--foreground)"
            fontSize="14"
            fontWeight="500"
          >
            {item.label}
          </text>
        </g>
      ))}

      <path
        d="M208 170H270"
        fill="none"
        stroke="var(--muted-foreground)"
        strokeWidth="2"
        markerEnd={`url(#${arrowId})`}
      />

      <rect
        x="284"
        y="82"
        width="164"
        height="176"
        rx="30"
        fill="url(#agent-core)"
        stroke="var(--primary)"
        strokeWidth="2"
      />
      <rect
        x="331"
        y="112"
        width="70"
        height="54"
        rx="16"
        fill="var(--card)"
        stroke="var(--primary)"
        strokeWidth="2"
      />
      <circle cx="350" cy="139" r="5" fill="var(--primary)" />
      <circle cx="382" cy="139" r="5" fill="var(--primary)" />
      <path
        d="M350 153c8 7 24 7 32 0M366 112V99m-8 0h16"
        fill="none"
        stroke="var(--primary)"
        strokeWidth="2"
        strokeLinecap="round"
      />
      <text
        x="366"
        y="202"
        textAnchor="middle"
        fill="var(--foreground)"
        fontSize="18"
        fontWeight="700"
      >
        {t('agents.agentType')}
      </text>
      <text
        x="366"
        y="228"
        textAnchor="middle"
        fill="var(--muted-foreground)"
        fontSize="13"
      >
        {t('agents.diagramDecide')}
      </text>

      <path
        d="M448 170H506"
        fill="none"
        stroke="var(--muted-foreground)"
        strokeWidth="2"
        markerEnd={`url(#${arrowId})`}
      />
      {[
        { y: 70, label: t('agents.diagramModel') },
        { y: 145, label: t('agents.diagramTools') },
        { y: 220, label: t('agents.diagramActions') },
      ].map((item, index) => (
        <g key={item.label}>
          <path
            d={`M476 170 C500 170 492 ${item.y + 26} 516 ${item.y + 26}`}
            fill="none"
            stroke="var(--border)"
            strokeWidth="2"
          />
          <rect
            x="516"
            y={item.y}
            width="176"
            height="52"
            rx="15"
            fill="var(--card)"
            stroke={index === 1 ? 'var(--primary)' : 'var(--border)'}
          />
          <circle
            cx="544"
            cy={item.y + 26}
            r="10"
            fill="var(--primary)"
            fillOpacity={index === 1 ? 0.22 : 0.1}
          />
          <text
            x="608"
            y={item.y + 31}
            textAnchor="middle"
            fill="var(--foreground)"
            fontSize="14"
            fontWeight="500"
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
      viewBox="0 0 720 340"
      role="img"
      aria-label={t('agents.pipelineDiagramTitle')}
      className="h-auto w-full"
      data-testid="pipeline-diagram"
    >
      <title>{t('agents.pipelineDiagramTitle')}</title>
      <desc>{t('agents.pipelineDiagramDescription')}</desc>
      <defs>
        <linearGradient id="pipeline-flow" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="var(--primary)" stopOpacity="0.06" />
          <stop offset="0.5" stopColor="var(--primary)" stopOpacity="0.18" />
          <stop offset="1" stopColor="var(--primary)" stopOpacity="0.06" />
        </linearGradient>
        <DiagramArrow id={arrowId} />
      </defs>

      <rect
        x="24"
        y="65"
        width="672"
        height="210"
        rx="28"
        fill="url(#pipeline-flow)"
        stroke="var(--border)"
      />
      <text
        x="360"
        y="104"
        textAnchor="middle"
        fill="var(--muted-foreground)"
        fontSize="14"
        fontWeight="500"
      >
        {t('agents.pipelineDiagramFlow')}
      </text>

      <rect
        x="40"
        y="137"
        width="104"
        height="68"
        rx="18"
        fill="var(--card)"
        stroke="var(--border)"
      />
      <path
        d="M63 156h38v25H76l-9 8v-8h-4z"
        fill="none"
        stroke="var(--primary)"
        strokeWidth="2"
        strokeLinejoin="round"
      />
      <text
        x="92"
        y="228"
        textAnchor="middle"
        fill="var(--foreground)"
        fontSize="13"
        fontWeight="500"
      >
        {t('agents.diagramMessage')}
      </text>

      <path
        d="M144 171H168"
        fill="none"
        stroke="var(--muted-foreground)"
        strokeWidth="2"
        markerEnd={`url(#${arrowId})`}
      />

      {stages.map((stage, index) => {
        const x = 178 + index * 128;
        return (
          <g key={stage}>
            <rect
              x={x}
              y="127"
              width="104"
              height="88"
              rx="18"
              fill="var(--card)"
              stroke={index === 1 ? 'var(--primary)' : 'var(--border)'}
              strokeWidth={index === 1 ? 2 : 1}
            />
            <circle
              cx={x + 52}
              cy="154"
              r="14"
              fill="var(--primary)"
              fillOpacity={index === 1 ? 0.22 : 0.1}
            />
            <text
              x={x + 52}
              y="159"
              textAnchor="middle"
              fill="var(--primary)"
              fontSize="13"
              fontWeight="700"
            >
              {index + 1}
            </text>
            <text
              x={x + 52}
              y="190"
              textAnchor="middle"
              fill="var(--foreground)"
              fontSize="13"
              fontWeight="600"
            >
              {stage}
            </text>
            {index < stages.length - 1 && (
              <path
                d={`M${x + 104} 171H${x + 122}`}
                fill="none"
                stroke="var(--muted-foreground)"
                strokeWidth="2"
                markerEnd={`url(#${arrowId})`}
              />
            )}
          </g>
        );
      })}
    </svg>
  );
}

export default function ProcessorTypeDiagram({ kind }: { kind: AgentKind }) {
  return kind === 'agent' ? <AgentDiagram /> : <PipelineDiagram />;
}
