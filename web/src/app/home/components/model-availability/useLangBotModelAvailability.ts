import { useEffect, useState } from 'react';
import type { LangBotModelAvailability } from '@/app/infra/entities/api';
import { httpClient } from '@/app/infra/http/HttpClient';

const CACHE_TTL_MS = 60_000;

type AvailabilityMap = Record<string, LangBotModelAvailability>;

let cachedAvailability: AvailabilityMap | null = null;
let cacheExpiresAt = 0;
let pendingRequest: Promise<AvailabilityMap> | null = null;

async function loadAvailability(): Promise<AvailabilityMap> {
  if (cachedAvailability && Date.now() < cacheExpiresAt) {
    return cachedAvailability;
  }
  if (pendingRequest) return pendingRequest;

  pendingRequest = httpClient
    .getLangBotModelAvailability()
    .then((response) => {
      const next: AvailabilityMap = {};
      for (const item of response.models) {
        next[item.uuid] = item.availability;
        next[item.model_id] = item.availability;
      }
      cachedAvailability = next;
      cacheExpiresAt = Date.now() + CACHE_TTL_MS;
      return next;
    })
    .finally(() => {
      pendingRequest = null;
    });
  return pendingRequest;
}

export function useLangBotModelAvailability(enabled = true) {
  const [availability, setAvailability] = useState<AvailabilityMap>(
    cachedAvailability ?? {},
  );
  const [loaded, setLoaded] = useState(
    cachedAvailability !== null && Date.now() < cacheExpiresAt,
  );

  useEffect(() => {
    if (!enabled) return;
    let active = true;
    loadAvailability()
      .then((result) => {
        if (!active) return;
        setAvailability(result);
        setLoaded(true);
      })
      .catch(() => {
        // Availability is supplementary; model configuration remains usable.
      });
    return () => {
      active = false;
    };
  }, [enabled]);

  return { availability, loaded };
}
