import type { LangBotModelAvailabilityItem } from '@/app/infra/entities/api';

type CatalogModel = { uuid: string; name: string };
type MetadataMap = Record<string, LangBotModelAvailabilityItem>;

function listingDay(value?: string | null): number {
  const timestamp = value ? Date.parse(value) : NaN;
  // Use UTC calendar days so list order is consistent across user time zones.
  return Number.isFinite(timestamp) ? Math.floor(timestamp / 86_400_000) : -1;
}

function availabilityRank(up?: boolean | null): number {
  return up === true ? 0 : up == null ? 1 : 2;
}

function price(value?: number | null): number {
  return value != null && Number.isFinite(value) && value >= 0
    ? value
    : Infinity;
}

/** Sort one LangBot Models group without changing the source array. */
export function sortModelsByCatalog<T extends CatalogModel>(
  models: readonly T[],
  metadata: MetadataMap,
): T[] {
  // Keep the existing order until catalog metadata is available.
  if (Object.keys(metadata).length === 0) return [...models];

  return [...models].sort((left, right) => {
    const a = metadata[left.uuid] ?? metadata[left.name];
    const b = metadata[right.uuid] ?? metadata[right.name];
    const dateOrder = listingDay(b?.listed_at) - listingDay(a?.listed_at);
    if (dateOrder) return dateOrder;

    const statusOrder =
      availabilityRank(a?.availability?.up) -
      availabilityRank(b?.availability?.up);
    if (statusOrder) return statusOrder;

    for (const key of ['input_credits', 'output_credits'] as const) {
      const aPrice = price(a?.[key]);
      const bPrice = price(b?.[key]);
      if (aPrice !== bPrice) return aPrice < bPrice ? -1 : 1;
    }
    return left.name < right.name ? -1 : left.name > right.name ? 1 : 0;
  });
}
