import { useId, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import type { TFunction } from 'i18next';
import type { AgentKind } from '@/app/infra/entities/api';

const BLUE = '#2288ee';
const CYAN = '#19b8c9';
const VIOLET = '#8b5cf6';
const AMBER = '#f59e0b';
const PINK = '#ec4899';
const GREEN = '#10b981';

function reducedMotion() {
  return (
    typeof window !== 'undefined' &&
    window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  );
}

/** A glowing token that travels along a path; omitted for reduced motion. */
function Token({
  path,
  color = '#fff',
  dur = 2.4,
  begin = 0,
  r = 4,
  opacity = 1,
}: {
  path: string;
  color?: string;
  dur?: number;
  begin?: number;
  r?: number;
  opacity?: number;
}) {
  if (reducedMotion()) return null;
  return (
    <circle r={r} fill={color} opacity={opacity} visibility="hidden">
      {/* Hidden until its motion starts so delayed tokens never flash at the origin. */}
      <set attributeName="visibility" to="visible" begin={`${begin}s`} />
      <animateMotion
        dur={`${dur}s`}
        begin={`${begin}s`}
        repeatCount="indefinite"
        path={path}
      />
    </circle>
  );
}

function Label({
  x,
  y,
  children,
  size = 12,
  weight = 500,
  muted = false,
  anchor = 'middle',
}: {
  x: number;
  y: number;
  children: ReactNode;
  size?: number;
  weight?: number;
  muted?: boolean;
  anchor?: 'start' | 'middle' | 'end';
}) {
  return (
    <text
      x={x}
      y={y}
      textAnchor={anchor}
      fontSize={size}
      fontWeight={weight}
      fill="currentColor"
      opacity={muted ? 0.6 : 0.9}
    >
      {children}
    </text>
  );
}

/** Soft colored blobs that give each scene its atmosphere. */
function Atmosphere({ id, colors }: { id: string; colors: string[] }) {
  const spots = [
    [110, 90, 120],
    [420, 230, 130],
    [300, 60, 90],
  ];
  return (
    <>
      <defs>
        {colors.map((color, index) => (
          <radialGradient key={color} id={`${id}-blob-${index}`}>
            <stop offset="0%" stopColor={color} stopOpacity="0.28" />
            <stop offset="100%" stopColor={color} stopOpacity="0" />
          </radialGradient>
        ))}
      </defs>
      {colors.map((color, index) => (
        <circle
          key={color}
          cx={spots[index][0]}
          cy={spots[index][1]}
          r={spots[index][2]}
          fill={`url(#${id}-blob-${index})`}
        />
      ))}
    </>
  );
}

function Bubble({
  x,
  y,
  w,
  h,
  fill,
  stroke,
  tail = 'left',
  children,
}: {
  x: number;
  y: number;
  w: number;
  h: number;
  fill: string;
  stroke?: string;
  tail?: 'left' | 'right';
  children?: ReactNode;
}) {
  const tailPath =
    tail === 'left'
      ? `M${x + 18} ${y + h - 2} l-12 16 l26 -14z`
      : `M${x + w - 18} ${y + h - 2} l12 16 l-26 -14z`;
  return (
    <g>
      <path d={tailPath} fill={fill} stroke={stroke} strokeWidth="1.2" />
      <rect
        x={x}
        y={y}
        width={w}
        height={h}
        rx="18"
        fill={fill}
        stroke={stroke}
        strokeWidth="1.2"
      />
      {children}
    </g>
  );
}

function PipelineScene({ id, t }: { id: string; t: TFunction }) {
  const stations = [
    { x: 205, label: t('agents.diagram.model'), color: VIOLET, icon: 'spark' },
    {
      x: 265,
      label: t('agents.diagram.knowledge'),
      color: CYAN,
      icon: 'book',
    },
    { x: 325, label: t('agents.diagram.tools'), color: AMBER, icon: 'wrench' },
  ];
  return (
    <>
      <defs>
        <linearGradient id={`${id}-pipe`} x1="0" x2="1">
          <stop offset="0%" stopColor={BLUE} />
          <stop offset="100%" stopColor={CYAN} />
        </linearGradient>
        <linearGradient id={`${id}-reply`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor={BLUE} />
          <stop offset="100%" stopColor={VIOLET} />
        </linearGradient>
      </defs>
      <Atmosphere id={id} colors={[BLUE, VIOLET, CYAN]} />

      <Bubble
        x={28}
        y={128}
        w={112}
        h={60}
        fill="var(--card)"
        stroke={`${BLUE}55`}
      >
        {[0, 1, 2].map((dot) => (
          <circle
            key={dot}
            cx={66 + dot * 18}
            cy={158}
            r="5"
            fill={BLUE}
            opacity={0.35 + dot * 0.25}
          />
        ))}
      </Bubble>
      <Label x={84} y={226}>
        {t('agents.diagram.messageReceived')}
      </Label>

      <rect
        x={150}
        y={160}
        width={232}
        height={34}
        rx={17}
        fill={`url(#${id}-pipe)`}
        opacity="0.92"
      />
      <rect
        x={160}
        y={165}
        width={212}
        height={7}
        rx={3.5}
        fill="#fff"
        opacity="0.35"
      />
      {[0, 0.8, 1.6].map((begin) => (
        <Token key={begin} path="M158 177 H374" begin={begin} r={4.5} />
      ))}
      {stations.map((station) => (
        <g key={station.label}>
          <line
            x1={station.x}
            y1={148}
            x2={station.x}
            y2={160}
            stroke={station.color}
            strokeWidth="3"
            strokeLinecap="round"
          />
          <circle
            cx={station.x}
            cy={124}
            r={24}
            fill="var(--card)"
            stroke={station.color}
            strokeWidth="2"
          />
          {station.icon === 'spark' && (
            <path
              d={`M${station.x} 110 l4 10 10 4 -10 4 -4 10 -4 -10 -10 -4 10 -4z`}
              fill={station.color}
            />
          )}
          {station.icon === 'book' && (
            <path
              d={`M${station.x - 12} 114 h9 a3 3 0 0 1 3 3 v16 a3 3 0 0 0 -3 -3 h-9z M${station.x + 12} 114 h-9 a3 3 0 0 0 -3 3 v16 a3 3 0 0 1 3 -3 h9z`}
              fill="none"
              stroke={station.color}
              strokeWidth="2.2"
              strokeLinejoin="round"
            />
          )}
          {station.icon === 'wrench' && (
            <path
              d={`M${station.x - 9} 135 l12 -12 M${station.x + 3} 123 a7 7 0 1 0 6 -11 l-4 4 -3 -1 -1 -3 4 -4 a7 7 0 0 0 -7 10`}
              fill="none"
              stroke={station.color}
              strokeWidth="2.4"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}
          <Label x={station.x} y={88} size={11} muted>
            {station.label}
          </Label>
        </g>
      ))}
      <Label x={266} y={220} size={11} muted>
        {t('agents.diagram.pipeline.group')}
      </Label>

      <Bubble
        x={392}
        y={128}
        w={104}
        h={60}
        fill={`url(#${id}-reply)`}
        tail="right"
      >
        <rect x={408} y={146} width={70} height={7} rx={3.5} fill="#fff" />
        <rect
          x={408}
          y={162}
          width={48}
          height={7}
          rx={3.5}
          fill="#fff"
          opacity="0.7"
        />
      </Bubble>
      <Label x={444} y={226}>
        {t('agents.diagram.reply')}
      </Label>
    </>
  );
}

function AgentScene({ id, t }: { id: string; t: TFunction }) {
  const motion = !reducedMotion();
  const inputs = [
    { y: 100, color: BLUE, icon: 'chat' },
    { y: 165, color: GREEN, icon: 'user' },
    { y: 230, color: AMBER, icon: 'bell' },
  ];
  return (
    <>
      <defs>
        <linearGradient id={`${id}-robot`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor={VIOLET} />
          <stop offset="100%" stopColor={BLUE} />
        </linearGradient>
        <radialGradient id={`${id}-halo`}>
          <stop offset="60%" stopColor={VIOLET} stopOpacity="0.22" />
          <stop offset="100%" stopColor={VIOLET} stopOpacity="0" />
        </radialGradient>
      </defs>
      <Atmosphere id={id} colors={[VIOLET, BLUE, PINK]} />

      {inputs.map((input, index) => {
        const path = `M96 ${input.y} C 150 ${input.y}, 170 172, 208 172`;
        return (
          <g key={input.icon}>
            <path
              d={path}
              fill="none"
              stroke={input.color}
              strokeOpacity="0.45"
              strokeWidth="2"
              strokeDasharray="5 5"
            />
            <Token path={path} color={input.color} begin={index * 0.7} />
            <rect
              x={46}
              y={input.y - 22}
              width={44}
              height={44}
              rx={14}
              fill="var(--card)"
              stroke={input.color}
              strokeWidth="1.8"
            />
            {input.icon === 'chat' && (
              <path
                d={`M57 ${input.y - 8} h22 a4 4 0 0 1 4 4 v10 a4 4 0 0 1 -4 4 h-12 l-6 5 v-5 h-4 a4 4 0 0 1 -4 -4 v-10 a4 4 0 0 1 4 -4z`}
                fill={input.color}
              />
            )}
            {input.icon === 'user' && (
              <>
                <circle cx={64} cy={input.y - 5} r={6} fill={input.color} />
                <path
                  d={`M53 ${input.y + 12} a11 9 0 0 1 22 0z`}
                  fill={input.color}
                />
                <path
                  d={`M78 ${input.y - 6} v10 M73 ${input.y - 1} h10`}
                  stroke={input.color}
                  strokeWidth="2.4"
                  strokeLinecap="round"
                />
              </>
            )}
            {input.icon === 'bell' && (
              <path
                d={`M68 ${input.y - 12} a9 9 0 0 1 9 9 v7 l4 5 h-26 l4 -5 v-7 a9 9 0 0 1 9 -9z M64 ${input.y + 12} h8`}
                fill={input.color}
                stroke={input.color}
                strokeWidth="1.5"
                strokeLinecap="round"
              />
            )}
          </g>
        );
      })}
      <Label x={68} y={284} size={11} muted>
        {t('agents.diagram.anyEvent')}
      </Label>

      <circle cx={262} cy={172} r={92} fill={`url(#${id}-halo)`} />
      <g>
        <circle
          cx={262}
          cy={172}
          r={74}
          fill="none"
          stroke={VIOLET}
          strokeOpacity="0.35"
          strokeDasharray="3 7"
        />
        {[0, 120, 240].map((angle, index) => (
          <circle
            key={angle}
            cx={262 + 74 * Math.cos((angle * Math.PI) / 180)}
            cy={172 + 74 * Math.sin((angle * Math.PI) / 180)}
            r={6}
            fill={[VIOLET, CYAN, AMBER][index]}
          />
        ))}
        {motion && (
          <animateTransform
            attributeName="transform"
            type="rotate"
            from="0 262 172"
            to="360 262 172"
            dur="18s"
            repeatCount="indefinite"
          />
        )}
      </g>
      <line
        x1={262}
        y1={128}
        x2={262}
        y2={112}
        stroke={VIOLET}
        strokeWidth="3"
        strokeLinecap="round"
      />
      <circle cx={262} cy={108} r={6} fill={PINK}>
        {motion && (
          <animate
            attributeName="opacity"
            values="1;0.35;1"
            dur="1.8s"
            repeatCount="indefinite"
          />
        )}
      </circle>
      <rect
        x={216}
        y={128}
        width={92}
        height={80}
        rx={26}
        fill={`url(#${id}-robot)`}
      />
      <rect
        x={230}
        y={146}
        width={64}
        height={36}
        rx={14}
        fill="#fff"
        opacity="0.92"
      />
      {[248, 276].map((cx) => (
        <ellipse key={cx} cx={cx} cy={164} rx={6} ry={7} fill={VIOLET}>
          {motion && (
            <animate
              attributeName="ry"
              values="7;7;0.8;7"
              keyTimes="0;0.9;0.95;1"
              dur="4s"
              repeatCount="indefinite"
            />
          )}
        </ellipse>
      ))}
      <path
        d="M248 194 q14 8 28 0"
        fill="none"
        stroke="#fff"
        strokeWidth="3"
        strokeLinecap="round"
      />

      <circle cx={318} cy={104} r={5} fill="var(--card)" stroke={VIOLET} />
      <circle cx={332} cy={88} r={8} fill="var(--card)" stroke={VIOLET} />
      <rect
        x={340}
        y={30}
        width={140}
        height={58}
        rx={22}
        fill="var(--card)"
        stroke={VIOLET}
        strokeOpacity="0.6"
      />
      <Label x={410} y={54} size={12}>
        {t('agents.diagram.agent.instructions')}
      </Label>
      <rect
        x={366}
        y={64}
        width={88}
        height={6}
        rx={3}
        fill={VIOLET}
        opacity="0.35"
      />

      <path
        d="M310 172 C 360 172, 380 196, 420 196"
        fill="none"
        stroke={AMBER}
        strokeOpacity="0.55"
        strokeWidth="2"
        strokeDasharray="5 5"
      />
      <Token
        path="M310 172 C 360 172, 380 196, 420 196"
        color={AMBER}
        dur={1.8}
      />
      <circle cx={448} cy={196} r={28} fill={AMBER} opacity="0.18" />
      <circle
        cx={448}
        cy={196}
        r={22}
        fill="var(--card)"
        stroke={AMBER}
        strokeWidth="2"
      />
      <path d="M452 182 l-12 16 h9 l-4 13 l13 -18 h-9z" fill={AMBER} />
      <Label x={448} y={246} size={11} muted>
        {t('agents.diagram.replyOrAction')}
      </Label>
    </>
  );
}

function EventProcessorScene({ id, t }: { id: string; t: TFunction }) {
  const motion = !reducedMotion();
  const cards = [
    { x: 40, y: 70, rotate: -8, color: GREEN },
    { x: 66, y: 140, rotate: 5, color: PINK },
    { x: 40, y: 210, rotate: -4, color: BLUE },
  ];
  const puzzle =
    'M200 110 h36 a18 18 0 1 1 36 0 h36 v38 a18 18 0 1 1 0 36 v38 h-36 a18 18 0 1 0 -36 0 h-36 v-38 a18 18 0 1 0 0 -36z';
  return (
    <>
      <defs>
        <linearGradient id={`${id}-piece`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor={AMBER} />
          <stop offset="100%" stopColor={PINK} />
        </linearGradient>
      </defs>
      <Atmosphere id={id} colors={[AMBER, PINK, GREEN]} />

      {cards.map((card, index) => {
        const path = `M${card.x + 72} ${card.y + 20} C 160 ${card.y + 20}, 170 166, 196 166`;
        return (
          <g key={index}>
            <path
              d={path}
              fill="none"
              stroke={card.color}
              strokeOpacity="0.4"
              strokeWidth="2"
              strokeDasharray="4 6"
            />
            <Token path={path} color={card.color} begin={index * 0.8} />
            <g
              transform={`rotate(${card.rotate} ${card.x + 36} ${card.y + 20})`}
            >
              <rect
                x={card.x}
                y={card.y}
                width={72}
                height={40}
                rx={10}
                fill="var(--card)"
                stroke={card.color}
                strokeWidth="1.8"
              />
              <rect
                x={card.x}
                y={card.y}
                width={10}
                height={40}
                rx={5}
                fill={card.color}
              />
              <rect
                x={card.x + 18}
                y={card.y + 12}
                width={42}
                height={6}
                rx={3}
                fill={card.color}
                opacity="0.6"
              />
              <rect
                x={card.x + 18}
                y={card.y + 24}
                width={28}
                height={6}
                rx={3}
                fill={card.color}
                opacity="0.3"
              />
            </g>
          </g>
        );
      })}
      <Label x={78} y={286} size={11} muted>
        {t('agents.diagram.eventProcessor.input')}
      </Label>

      <path
        d={puzzle}
        fill={`url(#${id}-piece)`}
        transform="translate(4 6)"
        opacity="0.25"
      />
      <path d={puzzle} fill={`url(#${id}-piece)`} />
      {[
        { cx: 240, cy: 160, r: 20, dur: 6, from: 0 },
        { cx: 274, cy: 186, r: 13, dur: 4, from: 360 },
      ].map((gear) => (
        <g key={gear.cx}>
          <circle
            cx={gear.cx}
            cy={gear.cy}
            r={gear.r}
            fill="none"
            stroke="#fff"
            strokeWidth={gear.r / 3}
            strokeDasharray={`${gear.r / 2.2} ${gear.r / 2.2}`}
          />
          <circle cx={gear.cx} cy={gear.cy} r={gear.r / 2.4} fill="#fff" />
          {motion && (
            <animateTransform
              attributeName="transform"
              type="rotate"
              from={`${gear.from} ${gear.cx} ${gear.cy}`}
              to={`${gear.from === 0 ? 360 : 0} ${gear.cx} ${gear.cy}`}
              dur={`${gear.dur}s`}
              repeatCount="indefinite"
            />
          )}
        </g>
      ))}
      <text
        x={254}
        y={232}
        textAnchor="middle"
        fontSize="12"
        fontFamily="ui-monospace, monospace"
        fill="#fff"
      >
        on_event()
      </text>

      <path
        d="M312 166 C 340 166, 350 150, 372 150"
        fill="none"
        stroke={PINK}
        strokeOpacity="0.5"
        strokeWidth="2"
        strokeDasharray="4 6"
      />
      <Token
        path="M312 166 C 340 166, 350 150, 372 150"
        color={PINK}
        dur={1.6}
      />
      <rect
        x={376}
        y={104}
        width={116}
        height={92}
        rx={16}
        fill="var(--card)"
        stroke={PINK}
        strokeOpacity="0.6"
        strokeWidth="1.8"
      />
      {[
        [392, 118, AMBER],
        [470, 122, GREEN],
        [404, 176, BLUE],
        [478, 180, VIOLET],
        [440, 114, PINK],
      ].map(([x, y, color], index) => (
        <rect
          key={index}
          x={x as number}
          y={y as number}
          width={7}
          height={4}
          rx={1}
          fill={color as string}
          transform={`rotate(${index * 37} ${x} ${y})`}
        >
          {motion && (
            <animate
              attributeName="opacity"
              values="1;0.2;1"
              dur={`${1.4 + index * 0.3}s`}
              repeatCount="indefinite"
            />
          )}
        </rect>
      ))}
      <text x={434} y={156} textAnchor="middle" fontSize="26">
        🎉
      </text>
      <rect
        x={404}
        y={168}
        width={60}
        height={6}
        rx={3}
        fill={PINK}
        opacity="0.4"
      />
      <Label x={434} y={226} size={11} muted>
        {t('agents.diagram.replyOrAction')}
      </Label>
    </>
  );
}

function CommandScene({ id, t }: { id: string; t: TFunction }) {
  const hit = 'M168 160 C 200 160, 214 100, 250 100 H300';
  const miss = 'M168 160 C 200 160, 214 252, 250 252 H300';
  return (
    <>
      <defs>
        <linearGradient id={`${id}-gate`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor={CYAN} />
          <stop offset="100%" stopColor={BLUE} />
        </linearGradient>
      </defs>
      <Atmosphere id={id} colors={[CYAN, BLUE, AMBER]} />

      <Bubble
        x={20}
        y={134}
        w={118}
        h={52}
        fill="var(--card)"
        stroke={`${CYAN}88`}
      >
        <text
          x={79}
          y={166}
          textAnchor="middle"
          fontSize="16"
          fontWeight="600"
          fontFamily="ui-monospace, monospace"
          fill="currentColor"
        >
          /draw cat
        </text>
      </Bubble>

      <path
        d={miss}
        fill="none"
        stroke="currentColor"
        strokeOpacity="0.25"
        strokeWidth="2"
        strokeDasharray="4 6"
      />
      <Token path={miss} color="currentColor" opacity={0.25} dur={2.6} />
      <path
        d={hit}
        fill="none"
        stroke={CYAN}
        strokeWidth="3"
        strokeLinecap="round"
      />
      <Token path={hit} color={CYAN} dur={1.8} r={5} />
      <Token path={hit} color={CYAN} dur={1.8} begin={0.9} r={5} />

      <g transform="translate(176 160)">
        <rect
          x={-26}
          y={-26}
          width={52}
          height={52}
          rx={14}
          transform="rotate(45)"
          fill={`url(#${id}-gate)`}
        />
        <text
          x={0}
          y={10}
          textAnchor="middle"
          fontSize="30"
          fontWeight="700"
          fontFamily="ui-monospace, monospace"
          fill="#fff"
        >
          /
        </text>
      </g>
      <Label x={176} y={222} size={11} muted>
        {t('agents.diagram.commandProcessor.match')}
      </Label>

      <rect
        x={304}
        y={36}
        width={192}
        height={128}
        rx={14}
        fill="#16181d"
        stroke={CYAN}
        strokeOpacity="0.5"
      />
      {[320, 334, 348].map((cx, index) => (
        <circle
          key={cx}
          cx={cx}
          cy={52}
          r={4}
          fill={[PINK, AMBER, GREEN][index]}
        />
      ))}
      <text
        x={318}
        y={80}
        fontSize="12"
        fontFamily="ui-monospace, monospace"
        fill={CYAN}
      >
        $ draw cat
      </text>
      <g transform="translate(400 124)">
        <path
          d="M-22 -14 l6 -18 l12 12z M22 -14 l-6 -18 l-12 12z"
          fill={AMBER}
        />
        <circle cx={0} cy={0} r={24} fill={AMBER} />
        <circle cx={-9} cy={-4} r={3.4} fill="#16181d" />
        <circle cx={9} cy={-4} r={3.4} fill="#16181d" />
        <path d="M-3 5 h6 l-3 3z" fill={PINK} />
        <path
          d="M-30 2 h16 M-30 9 h15 M30 2 h-16 M30 9 h-15"
          stroke="#fff"
          strokeOpacity="0.7"
          strokeWidth="1.4"
          strokeLinecap="round"
        />
      </g>
      <Label x={400} y={186} size={11} muted>
        {t('agents.diagram.commandProcessor.run')}
      </Label>

      <rect
        x={304}
        y={230}
        width={150}
        height={44}
        rx={12}
        fill="none"
        stroke="currentColor"
        strokeOpacity="0.3"
        strokeDasharray="5 5"
      />
      <Label x={379} y={257} size={12} muted>
        {t('bots.routingLayers.rules')}
      </Label>
    </>
  );
}

const SCENES: Record<
  AgentKind,
  {
    scene: (props: { id: string; t: TFunction }) => ReactNode;
    title: string;
    summary: string;
    bestFor: string;
    branch?: string;
    accent: string;
  }
> = {
  pipeline: {
    scene: PipelineScene,
    title: 'agents.pipelineType',
    summary: 'agents.diagram.pipeline.summary',
    bestFor: 'agents.diagram.pipeline.bestFor',
    accent: BLUE,
  },
  agent: {
    scene: AgentScene,
    title: 'agents.agentType',
    summary: 'agents.diagram.agent.summary',
    bestFor: 'agents.diagram.agent.bestFor',
    accent: VIOLET,
  },
  event_processor: {
    scene: EventProcessorScene,
    title: 'agents.eventProcessor.type',
    summary: 'agents.diagram.eventProcessor.summary',
    bestFor: 'agents.diagram.eventProcessor.bestFor',
    branch: 'agents.diagram.eventProcessor.branch',
    accent: AMBER,
  },
  command_processor: {
    scene: CommandScene,
    title: 'agents.commandProcessor.type',
    summary: 'agents.diagram.commandProcessor.summary',
    bestFor: 'agents.diagram.commandProcessor.bestFor',
    branch: 'agents.diagram.commandProcessor.branch',
    accent: CYAN,
  },
};

export default function ProcessorTypeDiagram({ kind }: { kind: AgentKind }) {
  const { t } = useTranslation();
  const id = `processor-${useId().replace(/[^a-zA-Z0-9-]/g, '')}`;
  const resolved: AgentKind = SCENES[kind] ? kind : 'pipeline';
  const spec = SCENES[resolved];
  const Scene = spec.scene;
  return (
    <div
      data-testid={`${resolved.replace('_', '-')}-diagram`}
      className="flex h-full w-full flex-col justify-center gap-5 px-6 py-8 sm:px-10"
    >
      <header className="space-y-1.5">
        <h3 className="text-lg font-semibold" style={{ color: spec.accent }}>
          {t(spec.title)}
        </h3>
        <p className="max-w-lg text-sm leading-relaxed text-muted-foreground">
          {t(spec.summary)}
        </p>
      </header>
      <svg
        key={resolved}
        viewBox="0 0 520 300"
        role="img"
        aria-label={t(spec.summary)}
        overflow="visible"
        className="w-full max-w-xl self-center overflow-visible text-foreground"
      >
        <Scene id={id} t={t} />
      </svg>
      <footer className="space-y-1.5 text-xs leading-relaxed">
        {spec.branch && (
          <p className="text-muted-foreground">{t(spec.branch)}</p>
        )}
        <p>
          <span className="font-medium">{t('agents.diagram.bestFor')}</span>
          <span className="text-muted-foreground">{t(spec.bestFor)}</span>
        </p>
      </footer>
    </div>
  );
}
