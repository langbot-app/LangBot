# Valkey Search Vector Database Integration

This document describes how to use **Valkey Search** (the search/vector module bundled in
`valkey/valkey-bundle`) as the vector database backend for LangBot's knowledge base (RAG)
feature.

## What is Valkey Search?

**Valkey Search** is a module that adds vector similarity search and full-text search to
[Valkey](https://valkey.io/), the open-source, BSD-licensed in-memory data store forked from
Redis OSS. It is distributed in the `valkey/valkey-bundle` image alongside other modules
(JSON, Bloom, LDAP).

LangBot talks to Valkey through the official [`valkey-glide`](https://pypi.org/project/valkey-glide/)
client (Rust core + async Python wrapper), using its native `ft` (search) command namespace.

### Key Features

- **Vector search**: ANN via HNSW or exact via FLAT, with COSINE / L2 / IP distance metrics
- **Full-text search**: term, prefix and phrase matching over indexed text fields
- **Hybrid search**: a metadata/text filter pre-selects candidates, then KNN ranks them
- **In-memory speed**: vectors and documents are stored as Valkey HASH keys
- **Auth + TLS**: optional username/password and TLS for production (toB / SaaS) deployments

### Licensing

- Valkey core and the Search module are **BSD-3-Clause**.
- The `valkey-glide` client is **Apache-2.0**.

Both are compatible with LangBot.

## Installation

Valkey Search support is included automatically on Linux and macOS. The official `valkey-glide`
client does not currently publish a Windows package, so LangBot skips this optional dependency on
Windows; LangBot remains usable there, but the Valkey Search backend is unavailable. To install the
client manually on a supported platform:

```bash
pip install 'valkey-glide>=2.4.1,<3.0.0'
```

You also need a running Valkey server with the Search module loaded. The simplest way is the
bundled image:

```bash
# Run valkey-bundle (includes the Search module) on host port 6380
podman run -d --name valkey-test-langbot -p 6380:6379 valkey/valkey-bundle:9.1.0
# (docker run ... works identically)
```

`valkey-bundle` ships multi-arch images (linux/amd64 + linux/arm64), so it runs on both CI
(x86_64) and Apple-silicon dev machines.

## Configuration

Valkey Search is **opt-in and disabled by default** — the default `vdb.use` stays `chroma`,
so existing single-process deployments are unaffected. To enable it, edit your `config.yaml`:

```yaml
vdb:
  use: valkey_search
  valkey_search:
    host: 'localhost'
    port: 6379            # use 6380 if you started the container as shown above
    db: 0
    password: ''          # optional (ACL / requirepass) — never logged
    username: ''          # optional (ACL user)
    tls: false            # optional (toB / SaaS)
    index_algorithm: 'HNSW'   # HNSW | FLAT
    distance_metric: 'COSINE' # COSINE | L2 | IP
    request_timeout: 5000     # per-request timeout in ms
```

| Option | Default | Description |
|--------|---------|-------------|
| `host` | `localhost` | Valkey host |
| `port` | `6379` | Valkey port |
| `db` | `0` | Logical database id |
| `password` | `''` | Optional auth password (empty = no auth). Never logged. |
| `username` | `''` | Optional ACL username. Configuring a username without a password fails closed (raises) rather than connecting unauthenticated. |
| `tls` | `false` | Enable TLS for the connection |
| `index_algorithm` | `HNSW` | `HNSW` (approximate) or `FLAT` (exact) |
| `distance_metric` | `COSINE` | `COSINE`, `L2`, or `IP` |
| `request_timeout` | `5000` | Per-request timeout in milliseconds. The valkey-glide default (250ms) is too low for vector KNN under load; raise it further for remote/cross-AZ Valkey. |

### Connection behavior

The backend uses a **lazy** connection (`lazy_connect=True`): the client is created on first
use and the connection is deferred to the first command. A misconfigured or unreachable Valkey
server therefore does **not** block LangBot from booting — knowledge-base operations will error
at call time instead, and you can recover by switching `vdb.use` back to another backend.

The connection sets a fixed `client_name` of `langbot_vector_client` so it is identifiable in
`CLIENT LIST` and monitoring dashboards.

## Supported search types

| Type | Behavior |
|------|----------|
| `vector` | Pure KNN over the embedding field |
| `full_text` | Term/phrase match over the indexed `document` text field |
| `hybrid` | Metadata/text filter **pre-selects** candidates, then KNN ranks them |

### ⚠️ Important: `vector_weight` is NOT honored

Valkey Search hybrid queries follow a **filter-then-KNN** model: the filter (and/or full-text
clause) narrows the candidate set, and the KNN stage ranks the survivors by vector distance.
There is **no native weighted score fusion** (unlike, e.g., SeekDB's RRF boost).

For interface compatibility the backend still accepts a `vector_weight` argument, but it is
**ignored** — passing different weights does not change result ordering. The first time a
non-default weight is supplied, the backend logs a one-time warning.

If weighted hybrid ranking is needed in the future, it can be added **application-side** (run
vector KNN and full-text search separately and blend the scores). That is intentionally out of
scope for this integration.

## Metadata & filtering

Documents are stored as Valkey HASH keys under the prefix `kb:{collection}:{id}` with fields:

- `vector` — the embedding, packed as little-endian FLOAT32
- `document` — the raw text (indexed as TEXT for full-text/hybrid search)
- `file_id` — promoted to an indexed TAG field so it is filterable
- `metadata_json` — the full metadata dict, preserved verbatim as JSON

Only **indexed** fields are filterable. Currently that is `file_id`. Filters referencing
non-indexed metadata keys are dropped with a warning (the same pragmatism used by the Milvus
and pgvector backends). All other metadata still round-trips intact via `metadata_json`.

Supported filter operators (canonical Chroma-style `where` syntax): `$eq`, `$ne`, `$gt`,
`$gte`, `$lt`, `$lte`, `$in`, `$nin`. Multiple top-level keys are AND-ed.

## Testing

Unit tests (filter mapping, float32 packing, reply parsing, import guard) run in the fast lane
with no server:

```bash
uv run pytest tests/unit_tests/vector/test_valkey_search_filter.py -q
```

Integration tests are **slow-gated** on `TEST_VALKEY_URL` and require a running server:

```bash
podman run -d --name valkey-test-langbot -p 6380:6379 valkey/valkey-bundle:9.1.0
TEST_VALKEY_URL=valkey://localhost:6380 \
    uv run pytest tests/integration/vector/test_valkey_search.py -m slow -q
```

The default upstream fast CI lane (`-m "not slow"`) skips these, matching the existing
PostgreSQL migration-test precedent.

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| Tests skip with "Valkey Search module not available" | The server is plain Valkey without the Search module. Use the `valkey/valkey-bundle` image. |
| `ConnectionError` at call time | Check `host`/`port`/auth; remember `lazy_connect` defers errors to first use. |
| Empty search results right after insert | The Search indexer is asynchronous; results become visible within a short delay. The integration tests poll/retry to account for this. |
| Hybrid ranking ignores `vector_weight` | Expected — see the caveat above. |

## Production considerations

- **Cluster mode**: Valkey Search in cluster mode uses an additional coordination port. This
  integration targets standalone mode; cluster support is a future consideration.
- **Persistence**: configure Valkey RDB/AOF persistence if the knowledge base must survive
  restarts; otherwise an in-memory store is ephemeral.
- **Security**: set `password`/`username` and `tls: true` for any non-local deployment.
  Credentials are never written to logs.
