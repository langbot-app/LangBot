import i18n from 'i18next';

/**
 * All known adapter category IDs.
 */
export const ADAPTER_CATEGORIES = [
  'popular',
  'china',
  'global',
  'protocol',
] as const;

export type AdapterCategoryId = (typeof ADAPTER_CATEGORIES)[number];

/**
 * Returns the ordered list of category IDs based on the current locale.
 *
 * - zh-Hans: popular -> china -> global -> protocol
 * - All other locales: popular -> global -> china -> protocol
 *
 * `popular` is always first.
 */
export function getOrderedCategories(): AdapterCategoryId[] {
  const lang = i18n.language;
  if (lang === 'zh-Hans') {
    return ['popular', 'china', 'global', 'protocol'];
  }
  return ['popular', 'global', 'china', 'protocol'];
}

/**
 * Groups items that have a `categories` string array into ordered category
 * buckets. An item can appear in multiple groups if it belongs to multiple
 * categories. Items without any recognised category are collected into a
 * trailing "uncategorized" group (null key).
 */
export function groupByCategory<T extends { categories?: string[] }>(
  items: T[],
): { categoryId: AdapterCategoryId | null; items: T[] }[] {
  const ordered = getOrderedCategories();
  const buckets = new Map<AdapterCategoryId | null, T[]>();

  // Initialise buckets in display order
  for (const cat of ordered) {
    buckets.set(cat, []);
  }
  buckets.set(null, []);

  for (const item of items) {
    const cats = item.categories;
    if (!cats || cats.length === 0) {
      buckets.get(null)!.push(item);
      continue;
    }

    let placed = false;
    for (const cat of cats) {
      if (ordered.includes(cat as AdapterCategoryId)) {
        buckets.get(cat as AdapterCategoryId)!.push(item);
        placed = true;
      }
    }
    if (!placed) {
      buckets.get(null)!.push(item);
    }
  }

  // Build result, skipping empty buckets
  const result: { categoryId: AdapterCategoryId | null; items: T[] }[] = [];
  for (const [categoryId, groupItems] of buckets) {
    if (groupItems.length > 0) {
      result.push({ categoryId, items: groupItems });
    }
  }
  return result;
}

/**
 * Resolve the i18n display name for a category ID using the
 * `bots.adapterCategory.*` translation keys.
 */
export function getCategoryLabel(
  t: (key: string) => string,
  categoryId: AdapterCategoryId | null,
): string {
  if (categoryId === null) return '';
  return t(`bots.adapterCategory.${categoryId}`);
}
