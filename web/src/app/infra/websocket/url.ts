/** Match the HTTP backend base, including reverse-proxy path prefixes. */
export function backendWebSocketURL(
  base: string | undefined,
  pageURL: string,
  path: string,
): URL {
  const url = new URL(base || '/', pageURL);
  url.protocol =
    url.protocol === 'https:' || url.protocol === 'wss:' ? 'wss:' : 'ws:';
  url.pathname =
    url.pathname.replace(/\/$/, '') + '/' + path.replace(/^\//, '');
  url.search = '';
  url.hash = '';
  return url;
}
