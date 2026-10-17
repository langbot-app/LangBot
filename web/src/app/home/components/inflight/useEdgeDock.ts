import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type PointerEvent,
  type KeyboardEvent,
} from 'react';

const KEY = 'langbot.inflight.dock';
function saved() {
  try {
    return JSON.parse(localStorage.getItem(KEY) || '{}');
  } catch {
    return {};
  }
}

export function useEdgeDock(visible: boolean) {
  const [preference] = useState(saved);
  const [collapsed, setCollapsed] = useState(preference?.collapsed === true);
  const panel = useRef<HTMLElement>(null);
  const position = useRef(
    Number.isFinite(preference?.position)
      ? Math.min(1, Math.max(0, preference.position))
      : 0.55,
  );
  const drag = useRef<{
    id: number;
    y: number;
    top: number;
    moved: boolean;
  } | null>(null);
  const suppressClick = useRef(false);
  // Anchor the top edge to the viewport, never to the changing content height.
  const range = () => Math.max(0, window.innerHeight - 48 - 24);
  const place = (top = 12 + position.current * range()) => {
    const bounded = Math.max(12, Math.min(top, 12 + range()));
    if (panel.current) {
      panel.current.style.transform = `translateY(${bounded}px)`;
      panel.current.style.maxHeight = `${Math.max(48, window.innerHeight - bounded - 12)}px`;
    }
    return bounded;
  };
  const persist = () => {
    try {
      localStorage.setItem(
        KEY,
        JSON.stringify({ collapsed, position: position.current }),
      );
    } catch {
      /* Optional preference. */
    }
  };
  useEffect(() => {
    persist();
  }, [collapsed]);
  useLayoutEffect(() => {
    if (!visible || !panel.current) return;
    const update = () => {
      place();
    };
    window.addEventListener('resize', update);
    update();
    return () => {
      window.removeEventListener('resize', update);
    };
  }, [visible, collapsed]);
  const onPointerDown = (event: PointerEvent<HTMLButtonElement>) => {
    if (event.button !== 0) return;
    if (panel.current) panel.current.dataset.dragging = 'true';
    suppressClick.current = false;
    drag.current = {
      id: event.pointerId,
      y: event.clientY,
      top: panel.current?.getBoundingClientRect().top || 12,
      moved: false,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  };
  const onPointerMove = (event: PointerEvent<HTMLButtonElement>) => {
    const current = drag.current;
    if (!current || current.id !== event.pointerId) return;
    const delta = event.clientY - current.y;
    if (Math.abs(delta) > 5) current.moved = true;
    if (current.moved) {
      const top = place(current.top + delta);
      position.current = range() ? (top - 12) / range() : 0;
    }
  };
  const finish = (event: PointerEvent<HTMLButtonElement>) => {
    if (!drag.current || drag.current.id !== event.pointerId) return;
    suppressClick.current = drag.current.moved;
    drag.current = null;
    if (panel.current) delete panel.current.dataset.dragging;
    if (event.currentTarget.hasPointerCapture(event.pointerId))
      event.currentTarget.releasePointerCapture(event.pointerId);
    persist();
  };
  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (!['ArrowUp', 'ArrowDown', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const top =
      event.key === 'Home'
        ? 12
        : event.key === 'End'
          ? 12 + range()
          : (panel.current?.getBoundingClientRect().top || 12) +
            (event.key === 'ArrowUp' ? -24 : 24);
    const bounded = place(top);
    position.current = range() ? (bounded - 12) / range() : 0;
    persist();
  };
  return {
    panel,
    collapsed,
    setCollapsed,
    suppressClick,
    handle: {
      onPointerDown,
      onPointerMove,
      onPointerUp: finish,
      onPointerCancel: finish,
      onLostPointerCapture: finish,
      onKeyDown,
    },
  };
}
