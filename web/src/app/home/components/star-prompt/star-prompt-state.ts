/** Executions a Workspace must have handled before the Star prompt appears. */
export const STAR_PROMPT_THRESHOLD = 100;

const STORAGE_KEY = 'langbot_github_star_prompt';

export type StarPromptState =
  | { state: 'starred' }
  | { state: 'dismissed' }
  | { state: 'snoozed'; until: number };

export function readStarPromptState(): StarPromptState | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as StarPromptState;
    return parsed && typeof parsed.state === 'string' ? parsed : null;
  } catch {
    return null;
  }
}

export function writeStarPromptState(state: StarPromptState): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // Storage may be unavailable (private mode); the prompt then simply
    // reappears in a later session.
  }
}

/** Starred and dismissed are final; a snooze expires. */
export function shouldOfferStarPrompt(
  state: StarPromptState | null,
  now: number,
): boolean {
  if (!state) return true;
  if (state.state === 'snoozed') return !(Number(state.until) > now);
  return false;
}

/** Same compact format as the sidebar's Star menu item (56.3k). */
export function formatStarCount(count: number): string {
  return count >= 1000 ? `${(count / 1000).toFixed(1)}k` : String(count);
}
