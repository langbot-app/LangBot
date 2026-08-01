import { useEffect, useState } from 'react';
import { httpClient } from '@/app/infra/http/HttpClient';

export function useAuthenticatedPluginIcon(
  author: string,
  name: string,
  enabled = true,
): { url: string; error: boolean } {
  const [url, setURL] = useState('');
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!enabled) {
      setURL('');
      setError(false);
      return;
    }
    let active = true;
    let objectURL = '';
    setURL('');
    setError(false);
    httpClient
      .getAuthenticatedPluginIconURL(author, name)
      .then((nextURL) => {
        objectURL = nextURL;
        if (active) setURL(nextURL);
        else URL.revokeObjectURL(nextURL);
      })
      .catch(() => {
        if (active) setError(true);
      });
    return () => {
      active = false;
      if (objectURL) URL.revokeObjectURL(objectURL);
    };
  }, [author, enabled, name]);

  return { url, error };
}

export function useAuthenticatedPluginAsset(
  author: string,
  name: string,
  filepath: string,
): { url: string; error: boolean } {
  const [url, setURL] = useState('');
  const [error, setError] = useState(false);

  useEffect(() => {
    let active = true;
    let objectURL = '';
    setURL('');
    setError(false);
    httpClient
      .getAuthenticatedPluginAssetURL(author, name, filepath)
      .then((nextURL) => {
        objectURL = nextURL;
        if (active) setURL(nextURL);
        else URL.revokeObjectURL(nextURL);
      })
      .catch(() => {
        if (active) setError(true);
      });
    return () => {
      active = false;
      if (objectURL) URL.revokeObjectURL(objectURL);
    };
  }, [author, name, filepath]);

  return { url, error };
}
