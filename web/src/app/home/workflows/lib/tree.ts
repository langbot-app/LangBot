import type {
  WorkflowEdge,
  WorkflowGraph,
  WorkflowStep,
  WorkflowStepType,
} from '@/app/infra/entities/api';
import { STEP_META } from './catalog';

/** The slot under a step where the next step goes (`branch` for branching steps). */
export interface Slot {
  from: string;
  branch?: string;
}

const sameSlot = (edge: WorkflowEdge, slot: Slot) =>
  edge.from === slot.from && (edge.branch ?? undefined) === slot.branch;

export function stepById(graph: WorkflowGraph, id: string) {
  return graph.nodes.find((node) => node.id === id);
}

export function childAt(graph: WorkflowGraph, slot: Slot): string | undefined {
  return graph.edges.find((edge) => sameSlot(edge, slot))?.to;
}

export function parentOf(graph: WorkflowGraph, id: string) {
  return graph.edges.find((edge) => edge.to === id);
}

/** Ancestors of a step from `start` down to its parent. */
export function ancestorsOf(graph: WorkflowGraph, id: string): WorkflowStep[] {
  const chain: WorkflowStep[] = [];
  const seen = new Set<string>([id]);
  let edge = parentOf(graph, id);
  while (edge && !seen.has(edge.from)) {
    seen.add(edge.from);
    const step = stepById(graph, edge.from);
    if (step) chain.unshift(step);
    edge = parentOf(graph, edge.from);
  }
  return chain;
}

export function subtreeIds(graph: WorkflowGraph, id: string): string[] {
  const result: string[] = [];
  const queue = [id];
  while (queue.length) {
    const current = queue.shift()!;
    if (result.includes(current)) continue;
    result.push(current);
    for (const edge of graph.edges) {
      if (edge.from === current) queue.push(edge.to);
    }
  }
  return result;
}

export function newStepId(graph: WorkflowGraph, type: WorkflowStepType) {
  const taken = new Set(graph.nodes.map((node) => node.id));
  let index = 1;
  while (taken.has(`${type}_${index}`)) index += 1;
  return `${type}_${index}`;
}

/**
 * Insert a step into a slot. A step already in the slot moves under the new
 * step (under its "other" branch when the new step branches).
 */
export function insertStep(
  graph: WorkflowGraph,
  slot: Slot,
  type: WorkflowStepType,
  name: string,
): { graph: WorkflowGraph; id: string } {
  const meta = STEP_META[type];
  const id = newStepId(graph, type);
  const step: WorkflowStep = { id, type, name, config: meta.defaults() };
  const existing = childAt(graph, slot);
  const edges = graph.edges.filter((edge) => !sameSlot(edge, slot));
  edges.push({
    from: slot.from,
    to: id,
    ...(slot.branch ? { branch: slot.branch } : {}),
  });
  let nodes = [...graph.nodes, step];
  if (existing) {
    if (meta.terminal) {
      const removed = new Set(subtreeIds(graph, existing));
      nodes = nodes.filter((node) => !removed.has(node.id));
      return {
        id,
        graph: {
          nodes,
          edges: edges.filter(
            (edge) => !removed.has(edge.from) && !removed.has(edge.to),
          ),
        },
      };
    }
    edges.push({
      from: id,
      to: existing,
      ...(meta.branching ? { branch: 'else' } : {}),
    });
  }
  return { id, graph: { nodes, edges } };
}

/** Steps that removing `id` would also remove (its branches' subtrees). */
export function removalImpact(graph: WorkflowGraph, id: string): string[] {
  const step = stepById(graph, id);
  if (!step) return [];
  const outgoing = graph.edges.filter((edge) => edge.from === id);
  if (STEP_META[step.type]?.branching || outgoing.length > 1) {
    return subtreeIds(graph, id).filter((node) => node !== id);
  }
  return [];
}

/**
 * Remove a step. A linear step is spliced out (its next step moves up);
 * a branching step takes its branches with it.
 */
export function removeStep(graph: WorkflowGraph, id: string): WorkflowGraph {
  const step = stepById(graph, id);
  if (!step || step.type === 'start') return graph;
  const incoming = parentOf(graph, id);
  const dropped = new Set([id, ...removalImpact(graph, id)]);
  const next =
    dropped.size === 1
      ? graph.edges.find((edge) => edge.from === id)?.to
      : undefined;
  const edges = graph.edges.filter(
    (edge) => !dropped.has(edge.from) && !dropped.has(edge.to),
  );
  if (incoming && next) {
    edges.push({
      from: incoming.from,
      to: next,
      ...(incoming.branch ? { branch: incoming.branch } : {}),
    });
  }
  return {
    nodes: graph.nodes.filter((node) => !dropped.has(node.id)),
    edges,
  };
}

/** Drop the subtrees under branches that no longer exist on a step. */
export function pruneBranches(
  graph: WorkflowGraph,
  id: string,
  branchIds: string[],
): WorkflowGraph {
  const stale = graph.edges.filter(
    (edge) =>
      edge.from === id && edge.branch && !branchIds.includes(edge.branch),
  );
  if (!stale.length) return graph;
  const dropped = new Set(stale.flatMap((edge) => subtreeIds(graph, edge.to)));
  return {
    nodes: graph.nodes.filter((node) => !dropped.has(node.id)),
    edges: graph.edges.filter(
      (edge) => !dropped.has(edge.to) && !dropped.has(edge.from),
    ),
  };
}

export function updateStep(
  graph: WorkflowGraph,
  id: string,
  patch: Partial<Pick<WorkflowStep, 'name' | 'config'>>,
): WorkflowGraph {
  return {
    ...graph,
    nodes: graph.nodes.map((node) =>
      node.id === id ? { ...node, ...patch } : node,
    ),
  };
}

export function emptyGraph(startName: string): WorkflowGraph {
  return {
    nodes: [{ id: 'start', type: 'start', name: startName, config: {} }],
    edges: [],
  };
}
