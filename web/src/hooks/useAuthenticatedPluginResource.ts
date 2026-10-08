import { useEffect, useState } from 'react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { useCurrentWorkspace } from '@/app/infra/http';
import { useInstalledPluginIcon } from '@/app/infra/hooks/useInstalledPluginIcon';

type AuthenticatedResourceState = {
  key: string;
  url: string;
  error: boolean;
};

const EMPTY_RESOURCE: AuthenticatedResourceState = {
  key: '',
  url: '',
  error: false,
};

/**
 * Backwards-compatible wrapper around the shared installed-plugin icon hook.
 * Kept for callers that want a `{ url, error }` shape; the url is '' while
 * loading or when the icon is unavailable.
 */
export function useAuthenticatedPluginIcon(
  author: string,
  name: string,
  enabled = true,
): { url: string; error: boolean } {
  const url = useInstalledPluginIcon(
    enabled ? author : null,
    enabled ? name : null,
  );
  return { url: url ?? '', error: false };
}

export function useAuthenticatedPluginAsset(
  author: string,
  name: string,
  filepath: string,
): { url: string; error: boolean } {
  const [resource, setResource] =
    useState<AuthenticatedResourceState>(EMPTY_RESOURCE);
  const currentWorkspace = useCurrentWorkspace();
  const workspaceUuid = currentWorkspace?.workspace.uuid;
  const resourceKey = `${workspaceUuid ?? ''}:${author}/${name}/${filepath}`;

  useEffect(() => {
    let active = true;
    let objectURL = '';
    setResource({ key: resourceKey, url: '', error: false });
    httpClient
      .getAuthenticatedPluginAssetURL(author, name, filepath)
      .then((nextURL) => {
        objectURL = nextURL;
        if (active) {
          setResource({ key: resourceKey, url: nextURL, error: false });
        } else {
          URL.revokeObjectURL(nextURL);
        }
      })
      .catch(() => {
        if (active) {
          setResource({ key: resourceKey, url: '', error: true });
        }
      });
    return () => {
      active = false;
      if (objectURL) URL.revokeObjectURL(objectURL);
    };
  }, [author, name, filepath, resourceKey]);

  return {
    url: resource.key === resourceKey ? resource.url : '',
    error: resource.key === resourceKey && resource.error,
  };
}
