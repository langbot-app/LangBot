from __future__ import annotations

import json
import struct
from typing import Any, Dict, List

from langbot.pkg.core import app
from langbot.pkg.vector.vdb import VectorDatabase, SearchType
from langbot.pkg.vector.filter_utils import normalize_filter, strip_unsupported_fields

try:
    from glide import (
        GlideClient,
        GlideClientConfiguration,
        NodeAddress,
        ServerCredentials,
        ft,
        VectorField,
        VectorFieldAttributesHnsw,
        VectorFieldAttributesFlat,
        VectorAlgorithm,
        VectorType,
        DistanceMetricType,
        TagField,
        TextField,
        FtCreateOptions,
        DataType,
        FtSearchOptions,
        FtSearchLimit,
        ReturnField,
    )

    VALKEY_SEARCH_AVAILABLE = True
except ImportError:
    VALKEY_SEARCH_AVAILABLE = False


# Mandatory client name for production observability (CLIENT LIST / dashboards).
VALKEY_CLIENT_NAME = 'langbot_vector_client'

# Fixed, indexed metadata schema.  LangBot's RAG layer stores ``file_id`` on
# every chunk; it is the only metadata field we promote to a first-class
# (filterable) index field.  All other metadata is preserved verbatim inside
# the ``metadata_json`` field so it survives a round-trip, but is NOT
# filterable (the established Milvus / pgvector pragmatism).
_INDEXED_TAG_FIELDS = {'file_id'}
_SUPPORTED_FILTER_FIELDS = set(_INDEXED_TAG_FIELDS)

# Hash field names used for stored documents.
_FIELD_VECTOR = 'vector'
_FIELD_DOCUMENT = 'document'
_FIELD_FILE_ID = 'file_id'
_FIELD_METADATA = 'metadata_json'
_VEC_SCORE_ALIAS = '__vec_score'

# Valkey Search has no bare "match everything" token for non-vector queries
# (a standalone ``*`` is a syntax error).  A negated match on a sentinel tag
# value that can never exist matches every key, which is the canonical
# match-all idiom for FT.SEARCH.
_MATCH_ALL = f'-@{"file_id"}:{{__langbot_match_all_sentinel__}}'

# Page size used when enumerating matching keys for deletion.  Deletes
# paginate through the full result set in batches of this size so that
# files/filters matching more than one page of chunks are fully removed
# (no silent truncation / orphaned vectors).
_DELETE_SCAN_BATCH = 10000


class ValkeySearchVectorDatabase(VectorDatabase):
    """Valkey Search (valkey-bundle) vector database adapter for LangBot.

    Backed by the Valkey Search module shipped in ``valkey/valkey-bundle``,
    accessed through the official ``valkey-glide`` client's native ``ft``
    (search) command namespace.  Documents are stored as Valkey HASH keys
    under a per-collection prefix and indexed by one ``FT.CREATE`` index per
    collection.

    Supported search types: ``VECTOR``, ``FULL_TEXT`` and ``HYBRID``.

    Hybrid search semantics (IMPORTANT)
    -----------------------------------
    Valkey Search hybrid queries follow a *filter-then-KNN* model: the text /
    metadata filter pre-selects candidate keys and the KNN stage ranks them by
    vector distance.  This backend does **NOT** implement application-side
    weighted score fusion.  The ``vector_weight`` argument is therefore
    accepted for interface compatibility but is **not honored** — passing
    different weights does not change result ordering.  A one-time warning is
    emitted the first time a non-default weight is supplied.  App-side score
    fusion can be layered on later if weighted hybrid ranking is required.
    """

    @classmethod
    def supported_search_types(cls) -> list[SearchType]:
        return [SearchType.VECTOR, SearchType.FULL_TEXT, SearchType.HYBRID]

    def __init__(self, ap: app.Application):
        if not VALKEY_SEARCH_AVAILABLE:
            raise ImportError(
                "valkey-glide is not installed. Install it with: pip install 'valkey-glide>=2.4.1,<3.0.0'"
            )

        self.ap = ap
        config = self.ap.instance_config.data['vdb']['valkey_search']

        self._host = config.get('host', 'localhost')
        self._port = int(config.get('port', 6379))
        self._db = int(config.get('db', 0))
        # Auth / TLS are optional (toB / SaaS).  Never logged.
        self._password = config.get('password', '') or None
        self._username = config.get('username', '') or None
        self._tls = bool(config.get('tls', False))

        algorithm = str(config.get('index_algorithm', 'HNSW')).upper()
        self._algorithm = VectorAlgorithm.FLAT if algorithm == 'FLAT' else VectorAlgorithm.HNSW

        metric = str(config.get('distance_metric', 'COSINE')).upper()
        self._distance_metric = {
            'COSINE': DistanceMetricType.COSINE,
            'L2': DistanceMetricType.L2,
            'IP': DistanceMetricType.IP,
        }.get(metric, DistanceMetricType.COSINE)

        # Lazily-created client (created on first use so a down Valkey does not
        # block LangBot boot).
        self._client: GlideClient | None = None
        # Index names we have already ensured this process lifetime.
        self._ensured_indexes: set[str] = set()
        # Whether we have already warned about the non-honored vector_weight.
        self._vector_weight_warned = False

    # ------------------------------------------------------------------ #
    # Client lifecycle
    # ------------------------------------------------------------------ #
    async def _ensure_client(self) -> GlideClient:
        """Create the glide client on first use (lazy, non-blocking boot)."""
        if self._client is None:
            credentials = None
            if self._password is not None:
                # username is optional alongside a password (ACL "user" vs default user).
                credentials = ServerCredentials(password=self._password, username=self._username)
            elif self._username is not None:
                # A username without a password is not a valid credential pair for
                # ServerCredentials (password is required). Skip auth and warn rather than
                # constructing ServerCredentials(password=None, ...) which glide rejects.
                self.ap.logger.warning(
                    'Valkey Search: a username was configured without a password; ignoring auth. '
                    'Set both username and password to use ACL authentication.'
                )

            conf = GlideClientConfiguration(
                addresses=[NodeAddress(self._host, self._port)],
                client_name=VALKEY_CLIENT_NAME,
                database_id=self._db,
                use_tls=self._tls,
                lazy_connect=True,
                credentials=credentials,
            )
            self._client = await GlideClient.create(conf)
            self.ap.logger.info(
                f'Initialized Valkey Search client to {self._host}:{self._port} (db={self._db}, tls={self._tls})'
            )
        return self._client

    async def close(self) -> None:
        """Close the glide client and reset state.

        Safe to call when no client was created. After ``close`` the next
        operation transparently re-creates the client (``_ensure_client``
        guards on ``self._client is None``).
        """
        if self._client is not None:
            try:
                await self._client.close()
            except Exception:
                self.ap.logger.warning('Valkey Search: error while closing client (ignored)')
            finally:
                self._client = None
                self._ensured_indexes.clear()

    # ------------------------------------------------------------------ #
    # Naming helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _index_name(collection: str) -> str:
        return f'idx:{collection}'

    @staticmethod
    def _key_prefix(collection: str) -> str:
        return f'kb:{collection}:'

    @staticmethod
    def _pack_vector(vec: List[float]) -> bytes:
        """Pack a float vector into little-endian float32 bytes.

        Valkey Search stores and queries vectors as FLOAT32 little-endian
        blobs (per the search query-language spec).
        """
        return struct.pack(f'<{len(vec)}f', *[float(x) for x in vec])

    @staticmethod
    def _escape_tag(value: str) -> str:
        """Escape characters that are special inside a TAG ``{...}`` clause.

        The backslash is escaped first so it cannot consume a following
        escape. This neutralises injection-style values (quotes, parens,
        ``|``, ``@``, ``:``, spaces, dashes) so a crafted ``file_id`` cannot
        break out of the clause.

        Note: Valkey Search's TAG query parser does not accept a literal brace
        (``{`` / ``}``) inside the value even when backslash-escaped — such a
        value fails CLOSED (the query raises) rather than widening results.
        Real ``file_id`` values are UUIDs/hashes and never contain braces, so
        this is a safe, defensive edge.
        """
        out = []
        for ch in str(value):
            if ch in '\\,.<>{}[]"\':;!@#$%^&*()-+=~| ':
                out.append('\\')
            out.append(ch)
        return ''.join(out)

    # ------------------------------------------------------------------ #
    # Filter mapping (canonical triples -> FT query fragment)
    # ------------------------------------------------------------------ #
    def _triples_to_ft(self, filter: Dict[str, Any] | None) -> str:
        """Translate a canonical filter dict into an FT filter expression.

        Only indexed fields (``file_id``) are filterable; unsupported fields
        are dropped with a warning (matching the Milvus / pgvector pattern).
        Returns an empty string when there is no usable filter.
        """
        triples = normalize_filter(filter)
        if not triples:
            return ''
        triples = strip_unsupported_fields(triples, _SUPPORTED_FILTER_FIELDS)

        fragments: list[str] = []
        for field, op, value in triples:
            # All currently-indexed fields are TAG fields.
            if op == '$eq':
                fragments.append(f'@{field}:{{{self._escape_tag(value)}}}')
            elif op == '$ne':
                fragments.append(f'-@{field}:{{{self._escape_tag(value)}}}')
            elif op == '$in':
                joined = '|'.join(self._escape_tag(v) for v in value)
                fragments.append(f'@{field}:{{{joined}}}')
            elif op == '$nin':
                joined = '|'.join(self._escape_tag(v) for v in value)
                fragments.append(f'-@{field}:{{{joined}}}')
            elif op == '$gt':
                fragments.append(f'@{field}:[({value} +inf]')
            elif op == '$gte':
                fragments.append(f'@{field}:[{value} +inf]')
            elif op == '$lt':
                fragments.append(f'@{field}:[-inf ({value}]')
            elif op == '$lte':
                fragments.append(f'@{field}:[-inf {value}]')

        return ' '.join(fragments)

    @staticmethod
    def _build_text_clause(text: str) -> str:
        """Build a field-scoped full-text clause for the ``document`` field.

        Each whitespace-delimited word becomes a ``@document:<term>`` term and
        the terms are AND-ed (space separated).  FT special characters in each
        term are escaped.  Returns an empty string when *text* has no words.
        """
        words = [w for w in str(text).split() if w]
        if not words:
            return ''
        terms = [f'@{_FIELD_DOCUMENT}:{ValkeySearchVectorDatabase._escape_text(w)}' for w in words]
        return ' '.join(terms)

    @staticmethod
    def _escape_text(text: str) -> str:
        """Escape FT full-text special characters in a single term."""
        out = []
        for ch in str(text):
            if ch in '@!{}[]()|-"~*:\\':
                out.append('\\')
            out.append(ch)
        return ''.join(out)

    # ------------------------------------------------------------------ #
    # Index management
    # ------------------------------------------------------------------ #
    async def _ensure_index(self, client: GlideClient, collection: str, dim: int) -> None:
        index = self._index_name(collection)
        if index in self._ensured_indexes:
            return

        existing = await ft.list(client)
        existing_names = {self._decode(name) for name in existing}
        if index in existing_names:
            self._ensured_indexes.add(index)
            return

        if self._algorithm == VectorAlgorithm.FLAT:
            vector_attrs = VectorFieldAttributesFlat(
                dimensions=dim,
                distance_metric=self._distance_metric,
                type=VectorType.FLOAT32,
            )
        else:
            vector_attrs = VectorFieldAttributesHnsw(
                dimensions=dim,
                distance_metric=self._distance_metric,
                type=VectorType.FLOAT32,
            )

        schema = [
            VectorField(name=_FIELD_VECTOR, algorithm=self._algorithm, attributes=vector_attrs),
            TagField(name=_FIELD_FILE_ID),
            TextField(name=_FIELD_DOCUMENT),
        ]
        options = FtCreateOptions(data_type=DataType.HASH, prefixes=[self._key_prefix(collection)])
        await ft.create(client, index, schema, options)
        self._ensured_indexes.add(index)
        self.ap.logger.info(
            f"Valkey Search index '{index}' created (dim={dim}, algo={self._algorithm.value}, "
            f'metric={self._distance_metric.value})'
        )

    @staticmethod
    def _decode(value: Any) -> str:
        if isinstance(value, (bytes, bytearray, memoryview)):
            return bytes(value).decode('utf-8', errors='replace')
        return str(value)

    # ------------------------------------------------------------------ #
    # VectorDatabase ABC implementation
    # ------------------------------------------------------------------ #
    async def get_or_create_collection(self, collection: str):
        """Ensure a client exists.

        The index itself requires the vector dimension, which is only known at
        first ``add_embeddings`` (same constraint as Qdrant / SeekDB), so this
        is a best-effort no-op when the index does not yet exist.
        """
        await self._ensure_client()

    async def add_embeddings(
        self,
        collection: str,
        ids: List[str],
        embeddings_list: List[List[float]],
        metadatas: List[Dict[str, Any]],
        documents: List[str] | None = None,
    ) -> None:
        if not embeddings_list:
            return

        client = await self._ensure_client()
        dim = len(embeddings_list[0])
        await self._ensure_index(client, collection, dim)

        prefix = self._key_prefix(collection)

        for i, _id in enumerate(ids):
            key = prefix + str(_id)
            metadata = metadatas[i] if i < len(metadatas) else {}
            mapping: Dict[str, Any] = {
                _FIELD_VECTOR: self._pack_vector(embeddings_list[i]),
                _FIELD_METADATA: json.dumps(metadata, ensure_ascii=False),
            }
            file_id = metadata.get('file_id')
            if file_id is not None:
                mapping[_FIELD_FILE_ID] = str(file_id)
            if documents is not None and i < len(documents) and documents[i] is not None:
                mapping[_FIELD_DOCUMENT] = documents[i]

            await client.hset(key, mapping)

        self.ap.logger.info(f"Added {len(ids)} embeddings to Valkey Search collection '{collection}'")

    async def search(
        self,
        collection: str,
        query_embedding: List[float],
        k: int = 5,
        search_type: str = 'vector',
        query_text: str = '',
        filter: Dict[str, Any] | None = None,
        vector_weight: float | None = None,
    ) -> Dict[str, Any]:
        client = await self._ensure_client()
        index = self._index_name(collection)

        if not await self._index_exists(client, index):
            return {'ids': [[]], 'metadatas': [[]], 'distances': [[]]}

        # vector_weight is accepted for interface parity but NOT honored by this
        # backend (filter-then-KNN, no weighted fusion).  Warn once.
        if vector_weight is not None and not self._vector_weight_warned:
            self.ap.logger.warning(
                'Valkey Search backend does not honor vector_weight: hybrid search uses '
                'filter-then-KNN without weighted score fusion. The vector_weight value '
                'is ignored. See docs/VALKEY_SEARCH_INTEGRATION.md.'
            )
            self._vector_weight_warned = True

        filter_expr = self._triples_to_ft(filter)

        if search_type == SearchType.FULL_TEXT:
            if not query_text:
                return {'ids': [[]], 'metadatas': [[]], 'distances': [[]]}
            text_clause = self._build_text_clause(query_text)
            if not text_clause:
                return {'ids': [[]], 'metadatas': [[]], 'distances': [[]]}
            query = f'{filter_expr} {text_clause}'.strip() if filter_expr else text_clause
            return await self._run_text_search(client, index, query, k)

        if search_type == SearchType.HYBRID:
            # Filter / text pre-selects candidates; KNN ranks. No fusion.
            pre = filter_expr
            if query_text:
                text_clause = self._build_text_clause(query_text)
                if text_clause:
                    pre = f'{pre} {text_clause}'.strip() if pre else text_clause
            pre = pre or '*'
            query = f'{pre}=>[KNN {k} @{_FIELD_VECTOR} $BLOB AS {_VEC_SCORE_ALIAS}]'
            return await self._run_knn_search(client, index, query, query_embedding, k)

        # Default: pure VECTOR search.
        pre = filter_expr or '*'
        query = f'{pre}=>[KNN {k} @{_FIELD_VECTOR} $BLOB AS {_VEC_SCORE_ALIAS}]'
        return await self._run_knn_search(client, index, query, query_embedding, k)

    async def _run_knn_search(
        self,
        client: GlideClient,
        index: str,
        query: str,
        query_embedding: List[float],
        k: int,
    ) -> Dict[str, Any]:
        options = FtSearchOptions(
            params={'BLOB': self._pack_vector(list(query_embedding))},
            return_fields=[
                ReturnField(field_identifier=_VEC_SCORE_ALIAS, alias='distance'),
                ReturnField(field_identifier=_FIELD_DOCUMENT),
                ReturnField(field_identifier=_FIELD_METADATA),
            ],
            limit=FtSearchLimit(0, k),
            dialect=2,
        )
        try:
            reply = await ft.search(client, index, query, options)
        except Exception as exc:
            if self._is_missing_index_error(exc):
                return {'ids': [[]], 'metadatas': [[]], 'distances': [[]]}
            raise
        return self._reply_to_chroma(index, reply, has_distance=True)

    async def _run_text_search(
        self,
        client: GlideClient,
        index: str,
        query: str,
        k: int,
    ) -> Dict[str, Any]:
        options = FtSearchOptions(
            return_fields=[
                ReturnField(field_identifier=_FIELD_DOCUMENT),
                ReturnField(field_identifier=_FIELD_METADATA),
            ],
            limit=FtSearchLimit(0, k),
            dialect=2,
        )
        try:
            reply = await ft.search(client, index, query, options)
        except Exception as exc:
            if self._is_missing_index_error(exc):
                return {'ids': [[]], 'metadatas': [[]], 'distances': [[]]}
            raise
        return self._reply_to_chroma(index, reply, has_distance=False)

    @staticmethod
    def _is_missing_index_error(exc: Exception) -> bool:
        """Return True if *exc* indicates the FT index does not exist.

        ``FT.DROPINDEX`` is applied eventually, so an index can briefly still
        appear in ``FT._LIST`` after being dropped; a follow-up search then
        fails with a "not found" error which we treat as an empty result.
        """
        message = str(exc).lower()
        return 'not found' in message and 'index' in message

    def _reply_to_chroma(self, index: str, reply: Any, has_distance: bool) -> Dict[str, Any]:
        """Convert an FT.SEARCH reply into Chroma-style nested lists.

        glide returns ``[total, {key: {field: value}, ...}]``.  The KNN score
        field (aliased ``distance``) is a COSINE/L2 distance directly, so no
        inversion is needed (unlike Qdrant).
        """
        ids: list[str] = []
        distances: list[float] = []
        metadatas: list[dict[str, Any]] = []

        if not reply or len(reply) < 2:
            return {'ids': [ids], 'metadatas': [metadatas], 'distances': [distances]}

        docs = reply[1]
        prefix = self._key_prefix(index[len('idx:') :]) if index.startswith('idx:') else ''
        if isinstance(docs, dict):
            items = docs.items()
        else:
            items = []

        for key, fields in items:
            key_str = self._decode(key)
            doc_id = key_str[len(prefix) :] if prefix and key_str.startswith(prefix) else key_str
            ids.append(doc_id)

            decoded_fields = {self._decode(fk): fv for fk, fv in fields.items()} if isinstance(fields, dict) else {}

            if has_distance and 'distance' in decoded_fields:
                try:
                    distances.append(float(self._decode(decoded_fields['distance'])))
                except (TypeError, ValueError):
                    distances.append(0.0)
            else:
                distances.append(0.0)

            metadata: dict[str, Any] = {}
            raw_meta = decoded_fields.get(_FIELD_METADATA)
            if raw_meta is not None:
                try:
                    metadata = json.loads(self._decode(raw_meta))
                except (TypeError, ValueError):
                    metadata = {}
            metadatas.append(metadata)

        return {'ids': [ids], 'metadatas': [metadatas], 'distances': [distances]}

    async def delete_by_file_id(self, collection: str, file_id: str) -> None:
        client = await self._ensure_client()
        index = self._index_name(collection)
        if not await self._index_exists(client, index):
            self.ap.logger.warning(f"Valkey Search collection '{collection}' not found for deletion")
            return

        query = f'@{_FIELD_FILE_ID}:{{{self._escape_tag(file_id)}}}'
        keys = await self._search_keys(client, index, query)
        if keys:
            await client.delete(keys)
        self.ap.logger.info(
            f"Deleted {len(keys)} embeddings from Valkey Search collection '{collection}' with file_id: {file_id}"
        )

    async def delete_by_filter(self, collection: str, filter: Dict[str, Any]) -> int:
        client = await self._ensure_client()
        index = self._index_name(collection)
        if not await self._index_exists(client, index):
            self.ap.logger.warning(f"Valkey Search collection '{collection}' not found for deletion")
            return 0

        # Guard against accidental mass deletion: a non-empty filter that maps
        # to no usable (indexed) conditions must NOT fall back to match-all and
        # wipe the whole collection.  Skip instead (matching Milvus / pgvector).
        query = self._triples_to_ft(filter)
        if not query:
            self.ap.logger.warning(
                "Valkey Search delete_by_filter on '%s': filter produced no usable conditions, skipping",
                collection,
            )
            return 0
        keys = await self._search_keys(client, index, query)
        if keys:
            await client.delete(keys)
        self.ap.logger.info(f"Deleted {len(keys)} embeddings from Valkey Search collection '{collection}' by filter")
        return len(keys)

    async def list_by_filter(
        self,
        collection: str,
        filter: Dict[str, Any] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Dict[str, Any]], int]:
        client = await self._ensure_client()
        index = self._index_name(collection)
        if not await self._index_exists(client, index):
            return [], 0

        query = self._triples_to_ft(filter) or _MATCH_ALL
        options = FtSearchOptions(
            return_fields=[
                ReturnField(field_identifier=_FIELD_DOCUMENT),
                ReturnField(field_identifier=_FIELD_METADATA),
            ],
            limit=FtSearchLimit(offset, limit),
            dialect=2,
        )
        try:
            reply = await ft.search(client, index, query, options)
        except Exception as exc:
            if self._is_missing_index_error(exc):
                return [], 0
            raise

        items: list[Dict[str, Any]] = []
        total = 0
        if reply:
            try:
                total = int(reply[0])
            except (TypeError, ValueError):
                total = 0

        prefix = self._key_prefix(collection)
        docs = reply[1] if reply and len(reply) >= 2 and isinstance(reply[1], dict) else {}
        for key, fields in docs.items():
            key_str = self._decode(key)
            doc_id = key_str[len(prefix) :] if key_str.startswith(prefix) else key_str
            decoded_fields = {self._decode(fk): fv for fk, fv in fields.items()} if isinstance(fields, dict) else {}

            document = decoded_fields.get(_FIELD_DOCUMENT)
            metadata: dict[str, Any] = {}
            raw_meta = decoded_fields.get(_FIELD_METADATA)
            if raw_meta is not None:
                try:
                    metadata = json.loads(self._decode(raw_meta))
                except (TypeError, ValueError):
                    metadata = {}

            items.append(
                {
                    'id': doc_id,
                    'document': self._decode(document) if document is not None else None,
                    'metadata': metadata,
                }
            )

        return items, total

    async def delete_collection(self, collection: str):
        client = await self._ensure_client()
        index = self._index_name(collection)
        self._ensured_indexes.discard(index)

        if await self._index_exists(client, index):
            try:
                await ft.dropindex(client, index)
            except Exception:
                self.ap.logger.warning(f"Valkey Search failed to drop index '{index}'")

        # DROPINDEX does not remove the underlying hashes; delete them too.
        prefix = self._key_prefix(collection)
        cursor = b'0'
        deleted = 0
        while True:
            cursor, keys = await client.scan(cursor, match=f'{prefix}*', count=500)
            if keys:
                await client.delete(keys)
                deleted += len(keys)
            if cursor in (b'0', '0', 0):
                break
        self.ap.logger.info(f"Valkey Search collection '{collection}' deleted ({deleted} keys removed)")

    # ------------------------------------------------------------------ #
    # Internal search helpers
    # ------------------------------------------------------------------ #
    async def _index_exists(self, client: GlideClient, index: str) -> bool:
        if index in self._ensured_indexes:
            return True
        existing = await ft.list(client)
        names = {self._decode(name) for name in existing}
        if index in names:
            self._ensured_indexes.add(index)
            return True
        return False

    async def _search_keys(self, client: GlideClient, index: str, query: str) -> list[str]:
        """Return all matching document keys for a query (NOCONTENT).

        Paginates through the full result set in pages of ``_DELETE_SCAN_BATCH``
        so that queries matching more than one page of chunks are fully
        enumerated (avoids silently truncating deletes and leaving orphaned
        vectors).
        """
        keys: list[str] = []
        offset = 0
        while True:
            options = FtSearchOptions(
                nocontent=True,
                limit=FtSearchLimit(offset, _DELETE_SCAN_BATCH),
                dialect=2,
            )
            try:
                reply = await ft.search(client, index, query, options)
            except Exception as exc:
                if self._is_missing_index_error(exc):
                    return keys
                raise

            if not reply or len(reply) < 2:
                break

            # reply[0] is the total match count; reply[1] holds this page.
            total = 0
            try:
                total = int(reply[0])
            except (TypeError, ValueError):
                total = 0

            docs = reply[1]
            if isinstance(docs, dict):
                page = [self._decode(k) for k in docs.keys()]
            elif isinstance(docs, (list, tuple)):
                page = [self._decode(k) for k in docs]
            else:
                page = []

            if not page:
                break
            keys.extend(page)

            offset += len(page)
            if offset >= total or len(page) < _DELETE_SCAN_BATCH:
                break

        return keys
