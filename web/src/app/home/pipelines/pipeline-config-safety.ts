function record(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}

/** Only unambiguous current containers may hydrate editor defaults. */
export function isCurrentPipelineConfig(config: unknown): boolean {
  if (!record(config) || !record(config.ai) || !record(config.ai.runner))
    return false;
  const ai = config.ai;
  const runner = ai.runner as Record<string, unknown>;
  if (
    Object.keys(ai).some((key) => !['runner', 'runner_config'].includes(key)) ||
    Object.keys(runner).some((key) => !['id', 'expire-time'].includes(key)) ||
    typeof runner.id !== 'string'
  )
    return false;

  // The canonical current default has no selected runner yet. Do not confuse
  // it with a legacy selector or an orphaned configuration needing review.
  if (runner.id === '')
    return (
      record(ai.runner_config) && Object.keys(ai.runner_config).length === 0
    );

  return runner.id.startsWith('plugin:');
}
