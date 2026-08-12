import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const webRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '../..',
);
const read = (relativePath) =>
  fs.readFileSync(path.join(webRoot, relativePath), 'utf8');

test('marketplace defaults to shared hot sorting and cards support fingerprint likes', () => {
  const market = read(
    'src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx',
  );
  const card = read(
    'src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx',
  );
  const cardVO = read(
    'src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardVO.ts',
  );
  const entity = read('src/app/infra/entities/plugin/index.ts');
  const client = read('src/app/infra/http/CloudServiceClient.ts');
  const likes = read(
    'src/app/home/plugins/components/plugin-market/marketplace-likes.ts',
  );

  assert.match(
    market,
    /hot_score_desc/,
    'market must expose and default to hot-score sorting',
  );
  assert.match(
    market,
    /sortBy:\s*['"]hot_score['"]/,
    'hot option must use the shared API field',
  );
  assert.match(
    entity,
    /like_count\??:\s*number/,
    'marketplace extension responses must carry like counts',
  );
  assert.match(
    cardVO,
    /likeCount:\s*number/,
    'market cards must carry like counts',
  );
  assert.match(card, /\bHeart\b/, 'market cards must render a like affordance');
  assert.match(
    card,
    /toggleMarketplaceExtensionLike/,
    'market cards must support liking and unliking',
  );
  assert.match(
    client,
    /marketplace\/extensions\/likes/,
    'client must load browser likes',
  );
  assert.match(
    client,
    /setMarketplaceExtensionLike\(/,
    'client must update likes through the shared API',
  );
  assert.match(
    client,
    /data\.sort_by === ['"]hot_score['"] \? ['"]install_count['"] : data\.sort_by/,
    'older Space servers must fall back from hot score to install sorting',
  );
  assert.match(
    likes,
    /@fingerprintjs\/fingerprintjs/,
    'anonymous likes must use browser fingerprinting',
  );
  assert.match(
    likes,
    /FingerprintJS\.load\(\{/,
    'fingerprint agent must be initialized with options',
  );
  assert.match(
    likes,
    /monitoring:\s*false/,
    'fingerprinting must not send vendor monitoring requests',
  );
});
