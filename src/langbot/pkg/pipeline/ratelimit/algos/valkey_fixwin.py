from __future__ import annotations

import asyncio
import time
import typing

from .. import algo
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query

# Import guard for the optional valkey-glide dependency. The algorithm is only
# usable when valkey-glide is installed; otherwise constructing the algorithm
# raises an ImportError with an install hint (mirrors the sibling Valkey
# backends). VALKEY_AVAILABLE lets tests toggle the guard without uninstalling.
try:
    from glide import (
        GlideClient,
        GlideClientConfiguration,
        GlideError,
        NodeAddress,
        ServerCredentials,
        Script,
    )

    VALKEY_AVAILABLE = True
except ImportError:
    GlideClient = None  # type: ignore[assignment,misc]
    GlideClientConfiguration = None  # type: ignore[assignment,misc]
    # Fallback so the narrowed ``except (GlideError, OSError)`` clause in
    # ``require_access`` is always a valid exception type. Unreachable in
    # practice: the constructor raises ImportError when valkey-glide is absent,
    # so ``require_access`` never runs in that case.
    GlideError = Exception  # type: ignore[assignment,misc]
    NodeAddress = None  # type: ignore[assignment,misc]
    ServerCredentials = None  # type: ignore[assignment,misc]
    Script = None  # type: ignore[assignment,misc]
    VALKEY_AVAILABLE = False


# Key prefix for every fixed-window counter. The full key embeds the launcher
# identity and the window start so each window is a distinct, TTL-reaped key.
_KEY_PREFIX = 'langbot:ratelimit:fixwin'

# Default Valkey port used when the top-level `valkey:` config block omits it.
_DEFAULT_PORT = 6379

# Throttle window (seconds) for fail-open warning logs so a Valkey outage does
# not flood the log on every request.
_WARN_THROTTLE_SECONDS = 60

# Atomic check-then-increment fixed-window script.
#
# KEYS[1] = window key
# ARGV[1] = limit (max requests allowed in the window)
# ARGV[2] = ttl seconds (window length; used to expire the counter)
#
# Returns -1 when the request is over the limit (denied); otherwise returns the
# post-increment counter value (>= 1, allowed). Performing the GET/INCR/EXPIRE
# inside a single script makes the check-and-increment atomic across workers, so
# concurrent processes cannot both pass the limit boundary. `redis.call` is used
# (rather than the native `server.call` alias) for broad compatibility with
# valkey-bundle 9.1.0, which keeps the `redis.*` scripting API.
_LUA_FIXWIN = """
local current = tonumber(redis.call('GET', KEYS[1]) or '0')
if current >= tonumber(ARGV[1]) then
    return -1
end
current = redis.call('INCR', KEYS[1])
if current == 1 then
    redis.call('EXPIRE', KEYS[1], tonumber(ARGV[2]))
end
return current
"""


@algo.algo_class('valkey_fixwin')
class ValkeyFixedWindowAlgo(algo.ReteLimitAlgo):
    """Distributed fixed-window rate-limit algorithm backed by Valkey.

    This mirrors the in-memory :class:`FixedWindowAlgo` window semantics
    (per ``launcher_type`` + ``launcher_id``, per fixed time window) but stores
    the counter in Valkey so the limit is shared across multiple worker
    processes. The atomic check-then-increment is performed with a Lua
    ``Script`` (``GET`` / ``INCR`` / ``EXPIRE``) so concurrent workers cannot
    both pass the limit boundary.

    Fail-open posture (default): if Valkey is unreachable or the script
    invocation fails, ``require_access`` logs a throttled warning and returns
    ``True`` (allows the request). A rate limiter is a safety throttle, not an
    authentication gate; dropping legitimate user messages because the optional
    Valkey backend is down is worse than briefly not enforcing the cap.
    Operators who rely on the limiter for abuse prevention can opt into a
    fail-closed posture by setting ``valkey.fail_strategy: closed``, which denies
    requests when Valkey errors.

    Connection settings are read from the top-level ``valkey:`` config block
    (``ap.instance_config.data['valkey']``). The glide client is owned by this
    component and created lazily on first use via :meth:`_ensure_client`. The
    counter key namespace (``valkey.key_prefix``) is configurable so multiple
    LangBot deployments can share one Valkey instance without colliding.
    """

    def __init__(self, ap):
        super().__init__(ap)
        if not VALKEY_AVAILABLE:
            raise ImportError(
                "valkey-glide is not installed. Install it with: pip install 'valkey-glide>=2.4.1,<3.0.0'"
            )
        self._client: typing.Optional['GlideClient'] = None
        self._client_lock = asyncio.Lock()
        self._script: typing.Optional['Script'] = None
        self._last_warn_ts: float = 0.0
        # Static (non-connection) config read in initialize().
        self._key_prefix: str = _KEY_PREFIX
        self._fail_strategy: str = 'open'

    async def initialize(self):
        # The glide client is created lazily on first require_access so that
        # LangBot still boots when Valkey is unreachable (lazy_connect=True also
        # defers the underlying connection to the first command).
        self._script = Script(_LUA_FIXWIN)

        # Read static, non-connection config. Connection settings are read
        # lazily in _ensure_client; these two drive request-path behavior and
        # the key namespace, so cache them here.
        cfg = self.ap.instance_config.data.get('valkey', {})
        self._key_prefix = cfg.get('key_prefix') or _KEY_PREFIX
        fail_strategy = (cfg.get('fail_strategy') or 'open').lower()
        if fail_strategy not in ('open', 'closed'):
            raise ValueError(f"valkey.fail_strategy must be 'open' or 'closed', got {fail_strategy!r}")
        self._fail_strategy = fail_strategy

    async def _ensure_client(self) -> 'GlideClient':
        """Create the component-owned glide client lazily on first use."""
        if self._client is not None:
            return self._client

        async with self._client_lock:
            if self._client is not None:
                return self._client

            cfg = self.ap.instance_config.data.get('valkey', {})
            host = cfg.get('host', 'localhost')
            use_tls = bool(cfg.get('tls', False))
            password = cfg.get('password') or ''
            credentials = None
            if password:
                # Only attach credentials when a password is configured; never
                # log the password value.
                credentials = ServerCredentials(
                    password=password,
                    username=cfg.get('username') or None,
                )
                # Warn (but do not block) when a password would be sent in
                # plaintext to a non-local host. Only the host is logged.
                if not use_tls and host not in ('localhost', '127.0.0.1', '::1'):
                    self.ap.logger.warning(
                        'valkey_fixwin: sending Valkey credentials to non-local host %s with TLS '
                        'disabled; the password will be transmitted in plaintext. Set valkey.tls: true.',
                        host,
                    )

            conf = GlideClientConfiguration(
                addresses=[
                    NodeAddress(
                        host,
                        int(cfg.get('port', _DEFAULT_PORT)),
                    )
                ],
                client_name='langbot_ratelimit_client',
                database_id=int(cfg.get('db', 0)),
                lazy_connect=True,
                credentials=credentials,
                use_tls=use_tls,
                # Explicit timeout (GLIDE defaults to 250ms) so behavior is
                # stable across client versions and fails fast for a real-time
                # chat pipeline rather than relying on a library default.
                request_timeout=500,
            )
            self._client = await GlideClient.create(conf)
            return self._client

    def _build_key(self, launcher_type: str, launcher_id: typing.Union[int, str], window_start: int) -> str:
        return f'{self._key_prefix}:{launcher_type}:{launcher_id}:{window_start}'

    @staticmethod
    def _window_start(now: int, window_size: int) -> int:
        return now - now % window_size

    async def _run_script(self, key: str, limitation: int, window_size: int) -> int:
        """Invoke the fixed-window Lua script and return its integer result."""
        client = await self._ensure_client()
        result = await client.invoke_script(
            self._script,
            keys=[key],
            args=[str(limitation), str(window_size)],
        )
        # glide returns the Lua integer reply as an int; coerce defensively in
        # case a bytes/str reply is produced by a future client version.
        if isinstance(result, (bytes, bytearray)):
            return int(result)
        return int(result)

    def _warn_throttled(self, message: str, err: Exception) -> None:
        """Log a fail-open warning at most once per throttle window."""
        now = time.time()
        if now - self._last_warn_ts >= _WARN_THROTTLE_SECONDS:
            self._last_warn_ts = now
            # Lazy %s formatting; never logs credentials.
            self.ap.logger.warning(message, err)

    async def require_access(
        self,
        query: pipeline_query.Query,
        launcher_type: str,
        launcher_id: typing.Union[int, str],
    ) -> bool:
        window_size = query.pipeline_config['safety']['rate-limit']['window-length']
        limitation = query.pipeline_config['safety']['rate-limit']['limitation']
        strategy = query.pipeline_config['safety']['rate-limit']['strategy']

        # Validate configuration outside the try/except below so misconfiguration
        # surfaces as a loud error instead of being swallowed by the fail-open
        # handler (which is reserved for Valkey/infra errors, not config bugs).
        if window_size <= 0:
            raise ValueError(f'rate-limit window-length must be a positive integer, got {window_size!r}')

        try:
            now = int(time.time())
            window_start = self._window_start(now, window_size)
            key = self._build_key(launcher_type, launcher_id, window_start)

            result = await self._run_script(key, limitation, window_size)

            if result >= 1:
                # Allowed (post-increment counter within limit).
                return True

            # result == -1 -> over the limit for this window.
            if strategy == 'drop':
                return False
            elif strategy == 'wait':
                # Wait until the next window boundary, then retry once (mirrors
                # the in-memory fixwin single-wait behavior).
                await asyncio.sleep(window_size - time.time() % window_size)

                now = int(time.time())
                window_start = self._window_start(now, window_size)
                key = self._build_key(launcher_type, launcher_id, window_start)
                result = await self._run_script(key, limitation, window_size)
                return result >= 1

            # Unknown strategy. 'strategy' is a select limited to 'drop'/'wait'
            # in the metadata, so this is unreachable via valid config; raise
            # loudly rather than silently denying so a metadata/handler mismatch
            # is debuggable. ValueError is not caught by the handler below.
            raise ValueError(f'unsupported rate-limit strategy: {strategy!r}')
        except (GlideError, OSError) as err:
            # Fail open (default) on infrastructure errors only: a rate limiter
            # is a throttle, not an auth gate. Programming bugs (TypeError,
            # KeyError, ValueError, ...) are NOT caught here and propagate so
            # regressions fail loudly. Operators can opt into fail-closed via
            # valkey.fail_strategy.
            posture = 'closed' if self._fail_strategy == 'closed' else 'open'
            self._warn_throttled(f'valkey_fixwin: Valkey error, applying fail-{posture} posture: %s', err)
            return self._fail_strategy != 'closed'

    async def release_access(
        self,
        query: pipeline_query.Query,
        launcher_type: str,
        launcher_id: typing.Union[int, str],
    ):
        # Fixed-window does not track occupancy, so release is a no-op
        # (identical to the in-memory FixedWindowAlgo).
        pass
