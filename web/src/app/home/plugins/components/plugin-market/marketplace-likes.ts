import FingerprintJS, { type LoadOptions } from '@fingerprintjs/fingerprintjs';
import { getCloudServiceClient } from '@/app/infra/http';

const MARKETPLACE_LIKE_CHANGED_EVENT = 'langbot-marketplace-like-changed';

export interface MarketplaceLikeChange {
  key: string;
  liked: boolean;
  likeCount: number;
}

let fingerprintPromise: Promise<string> | undefined;
let likedKeysPromise: Promise<Set<string>> | undefined;

export function marketplaceExtensionKey(
  type: string | undefined,
  author: string,
  name: string,
): string {
  return `${type || 'plugin'}:${author}/${name}`;
}

export function getMarketplaceFingerprint(): Promise<string> {
  if (!fingerprintPromise) {
    fingerprintPromise = FingerprintJS.load({
      monitoring: false,
    } as LoadOptions & { monitoring: boolean })
      .then((agent) => agent.get())
      .then((result) => result.visitorId)
      .catch((error) => {
        fingerprintPromise = undefined;
        throw error;
      });
  }
  return fingerprintPromise;
}

async function loadLikedKeys(): Promise<Set<string>> {
  if (!likedKeysPromise) {
    likedKeysPromise = Promise.all([
      getMarketplaceFingerprint(),
      getCloudServiceClient(),
    ])
      .then(([fingerprint, client]) =>
        client.getMarketplaceLikedExtensions(fingerprint),
      )
      .then((data) => {
        const keys = new Set<string>();
        for (const ref of data.extensions || []) {
          keys.add(`${ref.type}:${ref.extension_id}`);
        }
        return keys;
      })
      .catch((error) => {
        likedKeysPromise = undefined;
        throw error;
      });
  }
  return likedKeysPromise;
}

export async function getMarketplaceExtensionLiked(
  type: string | undefined,
  author: string,
  name: string,
): Promise<boolean> {
  const likedKeys = await loadLikedKeys();
  return likedKeys.has(marketplaceExtensionKey(type, author, name));
}

export async function toggleMarketplaceExtensionLike(
  type: string | undefined,
  author: string,
  name: string,
  liked: boolean,
): Promise<MarketplaceLikeChange> {
  const extensionType = type || 'plugin';
  const [fingerprint, likedKeys, client] = await Promise.all([
    getMarketplaceFingerprint(),
    loadLikedKeys(),
    getCloudServiceClient(),
  ]);
  const result = await client.setMarketplaceExtensionLike(
    extensionType,
    author,
    name,
    fingerprint,
    liked,
  );
  const key = marketplaceExtensionKey(extensionType, author, name);
  if (result.liked) {
    likedKeys.add(key);
  } else {
    likedKeys.delete(key);
  }
  const change: MarketplaceLikeChange = {
    key,
    liked: result.liked,
    likeCount: result.like_count,
  };
  window.dispatchEvent(
    new CustomEvent<MarketplaceLikeChange>(MARKETPLACE_LIKE_CHANGED_EVENT, {
      detail: change,
    }),
  );
  return change;
}

export function subscribeMarketplaceLikeChanges(
  listener: (change: MarketplaceLikeChange) => void,
): () => void {
  const handler = (event: Event) => {
    listener((event as CustomEvent<MarketplaceLikeChange>).detail);
  };
  window.addEventListener(MARKETPLACE_LIKE_CHANGED_EVENT, handler);
  return () =>
    window.removeEventListener(MARKETPLACE_LIKE_CHANGED_EVENT, handler);
}
