# Shared runtime source candidate (SDK >=0.7.4)

This source declares `shared-runtime-v1` and `stateless-v1`. It is not certified
and makes no claim of live vendor acceptance. Certification additionally requires
independent review, signer approval, and two-Workspace invocation acceptance.

- `spec.config` is empty; the tool derives everything from its arguments. No
  configuration is read, cached, or retained on the component object.
- The whole `mux.process` call runs in a worker thread, so the blocking
  fetch/parse cannot stall the shared event loop. At most
  `MAX_CONCURRENT_FETCHES` fetches are in flight per event loop, a call waits at
  most `FETCH_SLOT_WAIT_SECONDS` for a free slot, and cancelling the invocation
  sets a stop flag that ends the I/O. The slot has a single owner: the caller
  releases it if the executor submission itself fails, and the worker thread
  releases it in its own `finally` once it has really exited. An
  await-cancellation cannot cancel the queued executor future (it is awaited
  under `asyncio.shield`), so a worker that has not started yet still runs and
  releases the slot exactly once; a worker that is still running is never
  released early.
- No binding-keyed caches or detached tasks exist, so
  `on_installation_revoked()` has nothing to release.

## Site adapters

`components/tools/sites/model.py` keeps the module-level `__site_adapters__`
registry. It holds only artifact-level data registered by the `@site(...)`
decorator at import time: each entry is a URL regex plus a class reference. It
contains no tenant, Workspace, or installation data, which the stateless
component contract permits for a process-level cache.

All adapters remain synchronous — they fetch through
`SiteAdapterBase.get_html`, which delegates to `components/tools/sites/safe_fetch.py`.
That is acceptable here because the entire `mux.process` adapter dispatch
(registry lookup, fetch, and parse) is executed in a worker thread by the tool;
no adapter code runs on the event loop. The adapters:

- `SiteAdapterBase` — generic fallback used for every URL in this revision.
- `GithubRepoSiteAdapter`, `GithubUserSiteAdapter` — defined under `sites/github/`
  with `@site(...)`, but that package is not imported by the current registry, so
  they are not registered at runtime (unchanged pre-existing behaviour).

## Outbound target and size policy (`safe_fetch.py`)

Fetching is not a bare `requests.get` any more; the module enforces the
certification requirements in the plugin request layer:

- only `http`/`https` URLs are accepted;
- the host is resolved by the plugin, every resolved address must be globally
  routable (loopback, link-local, private, multicast, reserved, unspecified,
  NAT64/IPv4-mapped forms are refused), and the connection is made to the
  validated IP so a later DNS answer cannot rebind it;
- redirects are followed manually, with the same validation applied to every hop;
- the body is read in bounded chunks: a declared or streamed body above
  `MAX_RESPONSE_BYTES`, and a body that inflates beyond it, abort the fetch
  without being buffered; the HTML handed to BeautifulSoup is capped at
  `MAX_PARSE_CHARS` and the extracted title/brief lengths are clamped;
- the *encoded* bytes read are bounded too: a cumulative `MAX_RESPONSE_BYTES +
  64 KiB` budget stops a chunked or length-less peer that keeps streaming
  bytes after the first compressed member, and the decoder tracks the zlib
  stream's end explicitly — exactly one gzip/deflate member is supported, bytes
  after it raise `TrailingDataError` instead of sitting in `unused_data`, an
  EOF'd decompressor is never fed again, and a stream that stops before its end
  marker raises `IncompleteCompressedStreamError` so gzip CRC32 / zlib Adler-32
  is validated before any body becomes a document;
- the whole operation has an absolute deadline plus a cooperative stop flag that
  cover DNS, connect, the TLS handshake, status/header parsing and the body: a
  watchdog thread shuts the socket down when either fires, because a socket
  timeout only bounds the idle time between two reads. The socket is closed on
  every exit path;
- every deadline-bounded DNS lookup runs on a fixed resolver worker pool with a
  fixed in-flight budget (`MAX_DNS_WORKERS` threads, `MAX_DNS_OUTSTANDING`
  lookups running + queued): a lookup whose waiter timed out or was cancelled
  keeps its budget slot until `getaddrinfo` really returns, so it can never
  free budget early or accumulate off the pool, and once the budget is
  exhausted a further lookup is refused with `ResolverBusyError` instead of
  starting another thread or queueing without limit;
- an aborted, timed-out or truncated response is never returned as a document:
  every exit path re-checks the stop flag and the deadline (a shut-down socket
  can read as a clean EOF), and a body shorter than its declared
  `Content-Length` fails with `TruncatedResponseError` instead of being parsed;
- the socket is opened directly, so no proxy environment variables or netrc
  credentials are consulted, and TLS keeps the default verification context;
- userinfo, query string and fragment are stripped from every URL before it
  reaches an error result, an exception (including chained causes) or a log
  line.

## Limits

- A DNS lookup that the resolver never answers cannot be killed, so the fetch
  returns at its deadline while the lookup is still running. It runs inside the
  fixed resolver pool above and holds its budget slot until the resolver really
  returns, so repeated deadline/cancel timeouts fill the pool's fixed budget
  instead of growing the process thread count; further lookups are then refused
  with `ResolverBusyError` until a slot frees. Lookups the resolver does answer
  reuse the same bounded workers (an idle pool is at most `MAX_DNS_WORKERS`
  threads).
- A cancelled invocation still cannot un-do I/O that has already been issued,
  but the stop flag and the absolute deadline shut the socket down, so an
  abandoned worker ends at the next blocking-socket return (bounded by the
  watchdog poll interval) instead of waiting for the peer to finish.
- Fetch concurrency is bounded by the plugin's own slot pool, so a tenant cannot
  occupy the default executor without limit.
- Tests drive the real fetch path against a local HTTP server (target refusals,
  redirect re-validation, DNS pinning, TLS context, byte/parse caps, deadline,
  cancellation, a peer that never completes its response headers, the slot
  ownership cases and the redaction of error results/logs); they also prove the
  resolver budget is independent of the waiter (a timed-out lookup does not free
  it, a further lookup is refused while it is exhausted, it comes back only when
  the lookup really ends, and the pool stays within its fixed worker/queue caps
  under repeated timeouts). They do not fetch the public internet.
