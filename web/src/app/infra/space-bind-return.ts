// Where to land after the LangBot Account bind redirect. Only in-app /home
// paths are accepted so a stored value can never become an open redirect.
const KEY = 'langbot_space_bind_return';

function isSafe(path: string): boolean {
  return path.startsWith('/home') && !path.startsWith('//');
}

export function rememberSpaceBindReturnPath(path: string): void {
  if (!isSafe(path)) return;
  try {
    sessionStorage.setItem(KEY, path);
  } catch {
    // Storage may be unavailable (private mode); fall back to /home.
  }
}

export function consumeSpaceBindReturnPath(): string | null {
  try {
    const path = sessionStorage.getItem(KEY);
    sessionStorage.removeItem(KEY);
    return path && isSafe(path) ? path : null;
  } catch {
    return null;
  }
}
