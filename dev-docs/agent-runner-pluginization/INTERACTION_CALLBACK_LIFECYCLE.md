# Interaction Callback Lifecycle: Follow-up Design

## Current Issue

The DingTalk A2UI adapter stores `outTrackId` callback context only in process
memory. The callback is ignored after an adapter restart even though the
interaction request and hashed callback token are persisted. The in-memory
context uses a fixed 30-minute expiry, while a Host interaction may remain
valid for up to 24 hours. Expired contexts are pruned only when another card is
sent, and there is no capacity limit.

The legacy DingTalk Dify form path has separate in-memory `card_state` and
requires its own migration assessment.

## Intended Contract

1. `InteractionStore` remains authoritative for callback token, request,
   delivery target, status, and expiry. An in-memory cache miss must never
   invalidate a pending card.
2. Parse the callback token and `outTrackId` from DingTalk's card callback.
   Resolve the stored request and delivery result, then validate the bot,
   conversation, actor, and card identity before consuming the submission.
   Reconstruct field types and option values from the stored request.
3. If profiling justifies a cache, bound it globally and per bot, cache only
   small derived metadata, and use a short TTL with LRU eviction. Starting
   limits to evaluate: 4,096 entries per process, 512 per bot, and five
   minutes. Cache eviction affects performance only.
4. Waiting cards are database records, not queued in-memory tasks. Bound
   concurrent callback execution separately. Persist callback admission and
   the resume intent atomically before acknowledging delivery; a durable
   worker queue with leases can then resume after process restart. A bounded
   in-memory queue alone cannot close the crash gap after submission commit.
5. Track pending-card count, callback backlog, processing latency, cache
   occupancy, and expired/rejected callbacks. Apply workspace-level admission
   limits and database retention separately from the cache bounds.

## Verification Needed

- A pending card still submits after adapter restart and after cache eviction.
- A card remains usable until its actual persisted expiry, including when
  other cards are sent.
- Replayed callbacks resume the processor once; crashes between admission and
  execution recover the queued work once.
- Forged card, conversation, actor, or option identifiers are rejected.
