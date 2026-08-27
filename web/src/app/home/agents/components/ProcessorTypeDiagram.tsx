import { useId } from 'react';
import { useTranslation } from 'react-i18next';
import type { AgentKind } from '@/app/infra/entities/api';

type DiagramIds = {
  accent: string;
  arrow: string;
  glow: string;
  grid: string;
  surface: string;
};

function useDiagramIds(prefix: string): DiagramIds {
  const id = useId().replace(/:/g, '');
  return {
    accent: `${prefix}-accent-${id}`,
    arrow: `${prefix}-arrow-${id}`,
    glow: `${prefix}-glow-${id}`,
    grid: `${prefix}-grid-${id}`,
    surface: `${prefix}-surface-${id}`,
  };
}

function DiagramDefinitions({ ids }: { ids: DiagramIds }) {
  return (
    <defs>
      <linearGradient id={ids.surface} x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stopColor="var(--primary)" stopOpacity="0.12" />
        <stop offset="0.48" stopColor="var(--card)" stopOpacity="0.72" />
        <stop offset="1" stopColor="var(--chart-2)" stopOpacity="0.08" />
      </linearGradient>
      <linearGradient id={ids.accent} x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stopColor="var(--primary)" />
        <stop offset="1" stopColor="var(--chart-2)" />
      </linearGradient>
      <filter id={ids.glow} x="-80%" y="-80%" width="260%" height="260%">
        <feGaussianBlur stdDeviation="9" result="blur" />
        <feComposite in="blur" in2="SourceGraphic" operator="over" />
      </filter>
      <pattern
        id={ids.grid}
        width="28"
        height="28"
        patternUnits="userSpaceOnUse"
      >
        <circle cx="1" cy="1" r="1" fill="var(--border)" opacity="0.72" />
      </pattern>
      <marker
        id={ids.arrow}
        markerWidth="10"
        markerHeight="10"
        refX="8"
        refY="5"
        orient="auto"
        markerUnits="strokeWidth"
      >
        <path d="M0 0 10 5 0 10Z" fill="var(--primary)" />
      </marker>
    </defs>
  );
}

function AgentDiagram() {
  const { t } = useTranslation();
  const ids = useDiagramIds('agent');
  const events = [
    { label: t('agents.diagramMessages'), y: 154 },
    { label: t('agents.diagramMembers'), y: 270 },
    { label: t('agents.diagramFeedback'), y: 386 },
  ];
  const capabilities = [
    { label: t('agents.diagramModel'), y: 154 },
    { label: t('agents.diagramTools'), y: 270 },
    { label: t('agents.diagramActions'), y: 386 },
  ];

  return (
    <svg
      viewBox="0 0 760 600"
      role="img"
      aria-label={t('agents.agentDiagramTitle')}
      className="h-auto w-full"
      data-testid="agent-diagram"
    >
      <title>{t('agents.agentDiagramTitle')}</title>
      <desc>{t('agents.agentDiagramDescription')}</desc>
      <DiagramDefinitions ids={ids} />

      <rect
        x="10"
        y="16"
        width="740"
        height="568"
        rx="34"
        fill={`url(#${ids.surface})`}
        stroke="var(--border)"
      />
      <rect
        x="10"
        y="16"
        width="740"
        height="568"
        rx="34"
        fill={`url(#${ids.grid})`}
        opacity="0.48"
      />
      <circle cx="650" cy="94" r="80" fill="var(--primary)" opacity="0.035" />
      <circle cx="105" cy="510" r="104" fill="var(--chart-2)" opacity="0.045" />

      <g fill="none" stroke="var(--primary)" strokeWidth="2">
        {events.map((event) => (
          <path
            key={event.label}
            d={`M226 ${event.y + 30} C286 ${event.y + 30}, 280 300, 323 300`}
            opacity="0.42"
          />
        ))}
        {capabilities.map((capability) => (
          <path
            key={capability.label}
            d={`M437 300 C480 300, 474 ${capability.y + 30}, 534 ${capability.y + 30}`}
            opacity="0.42"
          />
        ))}
      </g>

      <text
        x="54"
        y="112"
        fill="var(--muted-foreground)"
        fontSize="13"
        fontWeight="600"
        letterSpacing="1.8"
      >
        {t('agents.diagramEvents')}
      </text>

      {events.map((event, index) => (
        <g key={event.label}>
          <rect
            x="46"
            y={event.y}
            width="180"
            height="60"
            rx="18"
            fill="var(--card)"
            stroke="var(--border)"
          />
          <circle
            cx="78"
            cy={event.y + 30}
            r="13"
            fill="var(--primary)"
            opacity={0.09 + index * 0.045}
          />
          {index === 0 && (
            <path
              d={`M69 ${event.y + 24}h18v12H76l-5 4v-4h-2z`}
              fill="none"
              stroke="var(--primary)"
              strokeWidth="1.8"
              strokeLinejoin="round"
            />
          )}
          {index === 1 && (
            <g fill="none" stroke="var(--primary)" strokeWidth="1.8">
              <circle cx="75" cy={event.y + 26} r="4" />
              <circle cx="83" cy={event.y + 29} r="3.5" />
              <path d={`M68 ${event.y + 40}c1-6 4-9 8-9s7 3 8 9`} />
            </g>
          )}
          {index === 2 && (
            <path
              d={`m78 ${event.y + 20} 3 6 7 1-5 5 1 7-6-3-6 3 1-7-5-5 7-1z`}
              fill="none"
              stroke="var(--primary)"
              strokeWidth="1.8"
              strokeLinejoin="round"
            />
          )}
          <text
            x="104"
            y={event.y + 35}
            fill="var(--foreground)"
            fontSize="14"
            fontWeight="600"
          >
            {event.label}
          </text>
          <circle cx="226" cy={event.y + 30} r="3.5" fill="var(--primary)" />
        </g>
      ))}

      <g>
        <circle
          cx="380"
          cy="300"
          r="122"
          fill="none"
          stroke="var(--primary)"
          strokeDasharray="4 12"
          opacity="0.22"
        />
        <circle
          cx="380"
          cy="300"
          r="96"
          fill="var(--primary)"
          opacity="0.08"
          filter={`url(#${ids.glow})`}
        />
        <circle
          cx="380"
          cy="300"
          r="82"
          fill={`url(#${ids.accent})`}
          opacity="0.96"
        />
        <circle cx="347" cy="193" r="7" fill="var(--chart-2)" />
        <circle cx="466" cy="329" r="5" fill="var(--primary)" />
        <circle cx="314" cy="385" r="4" fill="var(--chart-4)" />
        <rect
          x="348"
          y="250"
          width="64"
          height="48"
          rx="16"
          fill="var(--primary-foreground)"
          opacity="0.96"
        />
        <circle cx="365" cy="273" r="4" fill="var(--primary)" />
        <circle cx="395" cy="273" r="4" fill="var(--primary)" />
        <path
          d="M364 285c8 7 24 7 32 0M380 250v-12m-7 0h14"
          fill="none"
          stroke="var(--primary)"
          strokeWidth="2"
          strokeLinecap="round"
        />
        <text
          x="380"
          y="329"
          textAnchor="middle"
          fill="var(--primary-foreground)"
          fontSize="20"
          fontWeight="750"
        >
          {t('agents.agentType')}
        </text>
        <text
          x="380"
          y="352"
          textAnchor="middle"
          fill="var(--primary-foreground)"
          fontSize="11"
          opacity="0.82"
        >
          {t('agents.diagramDecide')}
        </text>
      </g>

      {capabilities.map((capability, index) => (
        <g key={capability.label}>
          <circle
            cx="534"
            cy={capability.y + 30}
            r="3.5"
            fill="var(--primary)"
          />
          <rect
            x="534"
            y={capability.y}
            width="180"
            height="60"
            rx="18"
            fill="var(--card)"
            stroke={index === 1 ? 'var(--primary)' : 'var(--border)'}
            strokeWidth={index === 1 ? 1.5 : 1}
          />
          <circle
            cx="566"
            cy={capability.y + 30}
            r="13"
            fill="var(--primary)"
            opacity={index === 1 ? 0.18 : 0.09}
          />
          <path
            d={
              index === 0
                ? `M560 ${capability.y + 30}h12m-6-6v12`
                : index === 1
                  ? `M560 ${capability.y + 35}l12-12m-8 0h8v8`
                  : `M560 ${capability.y + 30}h12m-4-5 5 5-5 5`
            }
            fill="none"
            stroke="var(--primary)"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <text
            x="592"
            y={capability.y + 35}
            fill="var(--foreground)"
            fontSize="14"
            fontWeight="600"
          >
            {capability.label}
          </text>
        </g>
      ))}

      <path
        d="M704 494c-88 46-246 63-388 31"
        fill="none"
        stroke="var(--primary)"
        strokeWidth="1.5"
        strokeDasharray="2 8"
        opacity="0.24"
        markerEnd={`url(#${ids.arrow})`}
      />
    </svg>
  );
}

function PipelineDiagram() {
  const { t } = useTranslation();
  const ids = useDiagramIds('pipeline');
  const stations = [
    { x: 198, y: 312, label: t('agents.diagramPreprocess') },
    { x: 338, y: 242, label: t('agents.diagramAI') },
    { x: 478, y: 312, label: t('agents.diagramPostprocess') },
    { x: 618, y: 242, label: t('agents.diagramOutput') },
  ];

  return (
    <svg
      viewBox="0 0 760 600"
      role="img"
      aria-label={t('agents.pipelineDiagramTitle')}
      className="h-auto w-full"
      data-testid="pipeline-diagram"
    >
      <title>{t('agents.pipelineDiagramTitle')}</title>
      <desc>{t('agents.pipelineDiagramDescription')}</desc>
      <DiagramDefinitions ids={ids} />

      <rect
        x="10"
        y="16"
        width="740"
        height="568"
        rx="34"
        fill={`url(#${ids.surface})`}
        stroke="var(--border)"
      />
      <rect
        x="10"
        y="16"
        width="740"
        height="568"
        rx="34"
        fill={`url(#${ids.grid})`}
        opacity="0.48"
      />
      <circle cx="640" cy="110" r="112" fill="var(--chart-2)" opacity="0.045" />
      <circle cx="105" cy="500" r="96" fill="var(--primary)" opacity="0.045" />

      <text
        x="380"
        y="105"
        textAnchor="middle"
        fill="var(--muted-foreground)"
        fontSize="13"
        fontWeight="600"
        letterSpacing="1.5"
      >
        {t('agents.pipelineDiagramFlow')}
      </text>

      <path
        d="M72 360 C128 360 146 312 198 312 S286 242 338 242 S426 312 478 312 S566 242 618 242 S674 286 704 286"
        fill="none"
        stroke="var(--primary)"
        strokeWidth="28"
        strokeLinecap="round"
        opacity="0.06"
      />
      <path
        d="M72 360 C128 360 146 312 198 312 S286 242 338 242 S426 312 478 312 S566 242 618 242 S674 286 704 286"
        fill="none"
        stroke={`url(#${ids.accent})`}
        strokeWidth="3"
        strokeLinecap="round"
        markerEnd={`url(#${ids.arrow})`}
      />
      <path
        d="M92 405 C180 486 314 478 380 430 S548 388 678 430"
        fill="none"
        stroke="var(--chart-2)"
        strokeWidth="1.5"
        strokeDasharray="3 10"
        opacity="0.22"
      />

      <g>
        <circle
          cx="72"
          cy="360"
          r="42"
          fill="var(--card)"
          stroke="var(--border)"
        />
        <path
          d="M54 348h36v24H67l-9 8v-8h-4z"
          fill="none"
          stroke="var(--primary)"
          strokeWidth="2.5"
          strokeLinejoin="round"
        />
        <text
          x="72"
          y="424"
          textAnchor="middle"
          fill="var(--foreground)"
          fontSize="13"
          fontWeight="600"
        >
          {t('agents.diagramMessage')}
        </text>
      </g>

      {stations.map((station, index) => (
        <g key={station.label}>
          <circle
            cx={station.x}
            cy={station.y}
            r={index === 1 ? 58 : 50}
            fill="var(--primary)"
            opacity={index === 1 ? 0.12 : 0.07}
            filter={index === 1 ? `url(#${ids.glow})` : undefined}
          />
          <circle
            cx={station.x}
            cy={station.y}
            r={index === 1 ? 45 : 39}
            fill={index === 1 ? `url(#${ids.accent})` : 'var(--card)'}
            stroke={index === 1 ? 'var(--primary)' : 'var(--border)'}
            strokeWidth={index === 1 ? 2 : 1}
          />
          <text
            x={station.x}
            y={station.y + 6}
            textAnchor="middle"
            fill={index === 1 ? 'var(--primary-foreground)' : 'var(--primary)'}
            fontSize="17"
            fontWeight="750"
          >
            {index + 1}
          </text>
          <rect
            x={station.x - 61}
            y={station.y + (index % 2 === 0 ? 66 : -91)}
            width="122"
            height="38"
            rx="14"
            fill="var(--card)"
            stroke="var(--border)"
          />
          <text
            x={station.x}
            y={station.y + (index % 2 === 0 ? 90 : -67)}
            textAnchor="middle"
            fill="var(--foreground)"
            fontSize="13"
            fontWeight="600"
          >
            {station.label}
          </text>
        </g>
      ))}

      <g opacity="0.7">
        <circle cx="704" cy="286" r="12" fill="var(--primary)" opacity="0.14" />
        <circle cx="704" cy="286" r="4" fill="var(--primary)" />
      </g>

      <g transform="translate(178 494)">
        {[0, 1, 2, 3].map((step) => (
          <g key={step} transform={`translate(${step * 106} 0)`}>
            <circle
              cx="0"
              cy="0"
              r="5"
              fill={step === 1 ? 'var(--primary)' : 'var(--border)'}
            />
            {step < 3 && (
              <path
                d="M10 0h86"
                stroke="var(--border)"
                strokeWidth="2"
                strokeLinecap="round"
              />
            )}
          </g>
        ))}
      </g>
    </svg>
  );
}

export default function ProcessorTypeDiagram({ kind }: { kind: AgentKind }) {
  return kind === 'agent' ? <AgentDiagram /> : <PipelineDiagram />;
}
