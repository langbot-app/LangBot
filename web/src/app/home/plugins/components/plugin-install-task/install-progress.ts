/**
 * Pure install-stage model shared by the install-task UI.
 *
 * Kept free of React imports so the mapping and progress maths can be
 * exercised directly in unit tests.
 */

/**
 * Installation stages mapped from backend current_action strings.
 */
export enum InstallStage {
  CHECKING = 'checking',
  VALIDATING = 'validating',
  DOWNLOADING = 'downloading',
  INSTALLING_DEPS = 'installing_deps',
  INITIALIZING = 'initializing',
  LAUNCHING = 'launching',
  DONE = 'done',
  ERROR = 'error',
}

/**
 * Map the backend `current_action` string to an InstallStage.
 *
 * The runtime connector emits human-readable stage strings; each branch here
 * matches the wording produced by the connector so newly added stages show up
 * in the UI without a protocol change.
 */
export function mapActionToStage(action: string): InstallStage {
  const lower = (action || '').toLowerCase();

  // Terminal wording first: "installed" would otherwise also match the
  // in-progress "installing" branch below.
  if (
    lower.includes('installed') ||
    lower.includes('updated') ||
    lower.includes('complete')
  ) {
    return InstallStage.DONE;
  }
  // "waiting for plugin to become ready" is the post-install readiness wait,
  // checked before the stage branches so "ready" is not read as "done".
  if (lower.includes('waiting') || lower.includes('ready')) {
    return InstallStage.LAUNCHING;
  }
  if (lower.includes('checking')) return InstallStage.CHECKING;
  if (lower.includes('validat')) return InstallStage.VALIDATING;
  if (lower.includes('refresh')) return InstallStage.LAUNCHING;
  if (lower.includes('applying')) return InstallStage.INSTALLING_DEPS;

  // Pre-download wording, checked before the "install" branches because
  // "preparing plugin install" also contains "install".
  if (lower.includes('prepar') || lower.includes('checking')) {
    return InstallStage.DOWNLOADING;
  }
  if (lower.includes('download')) return InstallStage.DOWNLOADING;

  // The runtime installs the plugin's dependencies and starts it in a single
  // step ("installing or starting plugin"), and persisting the installation
  // precedes it. None of these stream finer-grained progress, so they all map
  // to one honest stage rather than pretending to be a separate dependency
  // step. This is checked before the generic "launch"/"start" branch, which
  // would otherwise catch the "...or starting..." wording.
  if (
    lower.includes('installing') ||
    lower.includes('starting') ||
    lower.includes('persisting') ||
    lower.includes('storing') ||
    lower.includes('inspect')
  ) {
    return InstallStage.INSTALLING_DEPS;
  }
  if (lower.includes('launch')) return InstallStage.LAUNCHING;
  if (lower.includes('initializ') || lower.includes('configur')) {
    return InstallStage.INITIALIZING;
  }

  return InstallStage.DOWNLOADING;
}

/**
 * Progress range (start → end) attributed to each stage, used to build a
 * smooth determinate bar that never goes backwards. The ranges are contiguous
 * and non-overlapping, so progress never has to move backwards when the stage
 * advances.
 */
export const STAGE_PROGRESS_RANGE: Record<InstallStage, [number, number]> = {
  [InstallStage.CHECKING]: [3, 5],
  [InstallStage.VALIDATING]: [45, 45],
  [InstallStage.DOWNLOADING]: [5, 45],
  [InstallStage.INSTALLING_DEPS]: [45, 85],
  [InstallStage.INITIALIZING]: [85, 88],
  [InstallStage.LAUNCHING]: [88, 97],
  [InstallStage.DONE]: [100, 100],
  [InstallStage.ERROR]: [0, 0],
};

/** Progress never reaches 100 until the backend reports the task as done. */
export const INSTALL_PROGRESS_CAP = 99;

function clampToRange(value: number, start: number, end: number): number {
  return Math.min(end, Math.max(start, value));
}

export interface StageProgressInput {
  stage: InstallStage;
  downloadCurrent?: number;
  downloadTotal?: number;
  /** Host coarse stage progress, used only when measured bytes are absent. */
  reportedProgress?: number;
  /** Seconds spent in the current stage, used to bound fallback drift. */
  stageElapsedSeconds: number;
}

/**
 * Progress contributed by a single stage, always inside that stage's range.
 *
 * Real byte counts take priority: when the backend has reported a download
 * size, the measured ratio is authoritative and no time-based drift is added
 * on top of it. Drift is only a fallback for stages that report no measurable
 * progress, and it is clamped to the current stage so it can never spill into
 * a later stage's range.
 */
export function computeStageProgress(input: StageProgressInput): number {
  const [start, end] = STAGE_PROGRESS_RANGE[input.stage] ?? [0, 0];

  const hasMeasuredBytes =
    input.stage === InstallStage.DOWNLOADING &&
    input.downloadTotal != null &&
    input.downloadTotal > 0 &&
    input.downloadCurrent != null;

  if (hasMeasuredBytes) {
    const ratio = Math.min(
      1,
      (input.downloadCurrent as number) / (input.downloadTotal as number),
    );
    return clampToRange(Math.round(start + (end - start) * ratio), start, end);
  }

  if (
    input.reportedProgress != null &&
    Number.isFinite(input.reportedProgress)
  ) {
    return clampToRange(input.reportedProgress, start, end);
  }

  // Nothing measurable to show yet: drift slowly, but never past this stage's
  // own ceiling (hence `end - start - 1`, leaving the final point to the real
  // stage transition).
  const maxDrift = Math.max(0, end - start - 1);
  const drift = Math.min(
    maxDrift,
    Math.floor(Math.max(0, input.stageElapsedSeconds) / 2),
  );
  return clampToRange(start + drift, start, end);
}
