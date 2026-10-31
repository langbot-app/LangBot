import { useEffect, useState } from 'react';
import type { LangBotModelAvailabilityItem } from '@/app/infra/entities/api';
import { httpClient } from '@/app/infra/http/HttpClient';

const CACHE_TTL_MS = 60_000;

type ModelMetadataMap = Record<string, LangBotModelAvailabilityItem>;

let cachedMetadata: ModelMetadataMap | null = null;
let cacheExpiresAt = 0;
let pendingRequest: Promise<ModelMetadataMap> | null = null;

async function loadMetadata(): Promise<ModelMetadataMap> {
  if (cachedMetadata && Date.now() < cacheExpiresAt) {
    return cachedMetadata;
  }
  if (pendingRequest) return pendingRequest;

  pendingRequest = httpClient
    .getLangBotModelAvailability()
    .then((response) => {
      const next: ModelMetadataMap = {};
      for (const item of response.models) {
        next[item.uuid] = item;
        next[item.model_id] = item;
      }
      cachedMetadata = next;
      cacheExpiresAt = Date.now() + CACHE_TTL_MS;
      return next;
    })
    .finally(() => {
      pendingRequest = null;
    });
  return pendingRequest;
}

export function useLangBotModelAvailability(enabled = true) {
  const [metadata, setMetadata] = useState<ModelMetadataMap>(
    cachedMetadata ?? {},
  );
  const [loaded, setLoaded] = useState(
    cachedMetadata !== null && Date.now() < cacheExpiresAt,
  );

  useEffect(() => {
    if (!enabled) return;
    let active = true;
    loadMetadata()
      .then((result) => {
        if (!active) return;
        setMetadata(result);
        setLoaded(true);
      })
      .catch(() => {
        // Catalog metadata is supplementary; model configuration remains usable.
      });
    return () => {
      active = false;
    };
  }, [enabled]);

  return { metadata, loaded };
}
