"""Share Workspace content to LangBot Space for review (LANG-439).

Skills, remote MCP servers and prompts are packaged here, credentials are
removed before anything leaves the instance, and the submission is sent with
the LangBot Account bound to the requesting member or the Workspace owner.
Space re-validates everything; this module is the first line, not the only
one.
"""

from __future__ import annotations

import io
import math
import re
import typing
import zipfile
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

if typing.TYPE_CHECKING:
    from ....core import app
    from ..context import RequestContext

PROMPT_KINDS = ('messaging', 'agent')
NAME_PATTERN = re.compile(r'^[a-z0-9][a-z0-9_-]{1,63}$')
VAR_PATTERN = re.compile(r'^[A-Z][A-Z0-9_]{0,63}$')
PLACEHOLDER = re.compile(r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}')
SENSITIVE_KEY = re.compile(r'(auth|token|key|secret|password|passwd|cookie|session|credential|signature|sig$)', re.I)
MAX_PROMPT_BYTES = 32 * 1024
MAX_PROMPT_MESSAGES = 20
MAX_SKILL_BYTES = 10 * 1024 * 1024

# High-confidence credential formats. A match blocks sharing until removed.
_SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ('openai_key', re.compile(r'\bsk-[A-Za-z0-9_-]{20,}')),
    ('anthropic_key', re.compile(r'\bsk-ant-[A-Za-z0-9_-]{20,}')),
    ('github_token', re.compile(r'\b(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})')),
    ('slack_token', re.compile(r'\bxox[abpors]-[A-Za-z0-9-]{10,}')),
    ('aws_access_key', re.compile(r'\b(AKIA|ASIA)[A-Z0-9]{16}\b')),
    ('google_api_key', re.compile(r'\bAIza[0-9A-Za-z_-]{35}\b')),
    ('private_key', re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----')),
    ('jwt', re.compile(r'\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}')),
    ('langbot_key', re.compile(r'\b(lbk|lbpat)_[A-Za-z0-9_-]{16,}')),
]
# Personal data: a warning the user must acknowledge, not a block.
_PII_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ('email', re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')),
    ('phone', re.compile(r'(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)')),
    ('private_url', re.compile(r'https?://(?:localhost|127\.|10\.|192\.168\.|172\.(?:1[6-9]|2\d|3[01])\.)[^\s"\']*')),
]


class ShareError(ValueError):
    def __init__(self, message: str, *, status: int = 400, findings: list[dict] | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.findings = findings or []


def _entropy(value: str) -> float:
    if not value:
        return 0.0
    counts: dict[str, int] = {}
    for ch in value:
        counts[ch] = counts.get(ch, 0) + 1
    return -sum((n / len(value)) * math.log2(n / len(value)) for n in counts.values())


def looks_like_secret(value: str) -> bool:
    value = value.strip()
    if not value or PLACEHOLDER.fullmatch(value):
        return False
    if any(p.search(value) for _, p in _SECRET_PATTERNS):
        return True
    token = value.split(' ', 1)[1] if value.lower().startswith(('bearer ', 'basic ', 'token ')) else value
    return (
        len(token) >= 20
        and re.fullmatch(r'[A-Za-z0-9_\-.=+/:]+', token) is not None
        and any(c.isdigit() for c in token)
        and any(c.isalpha() for c in token)
        and _entropy(token) >= 3.5
    )


def scan_text(text: str, *, where: str = '') -> list[dict]:
    """Return credential (``severity=block``) and PII (``warn``) findings."""
    findings: list[dict] = []
    for kind, pattern in _SECRET_PATTERNS:
        for m in pattern.finditer(text):
            findings.append({'kind': kind, 'severity': 'block', 'where': where, 'excerpt': _mask(m.group(0))})
    for kind, pattern in _PII_PATTERNS:
        for m in pattern.finditer(text):
            findings.append({'kind': kind, 'severity': 'warn', 'where': where, 'excerpt': _mask(m.group(0))})
    return findings[:50]


def _mask(value: str) -> str:
    if len(value) <= 8:
        return value[:2] + '…'
    return value[:4] + '…' + value[-2:]


def _var_name(raw: str, used: set[str]) -> str:
    base = re.sub(r'[^A-Za-z0-9]+', '_', raw).strip('_').upper() or 'SECRET'
    if not base[0].isalpha():
        base = 'V_' + base
    base = base[:48]
    name, i = base, 2
    while name in used:
        name, i = f'{base}_{i}', i + 1
    used.add(name)
    return name


async def resolve_space_access_token(ap: 'app.Application', request_context: 'RequestContext') -> str | None:
    """The requesting member's LangBot Account token, else the Workspace owner's."""
    try:
        user_service = getattr(ap, 'user_service', None)
        space_service = getattr(ap, 'space_service', None)
        if user_service is None or space_service is None:
            return None
        if request_context.account_uuid:
            account = await user_service.get_user_by_uuid(request_context.account_uuid)
            if account and account.account_type == 'space':
                token = await space_service.get_valid_access_token(account.user)
                if token:
                    return token
        owner = await user_service.get_workspace_owner(request_context.workspace_uuid)
        if owner is None:
            return None
        return await space_service.get_valid_access_token(owner.user)
    except Exception:
        return None


async def share_context(ap: 'app.Application', request_context: 'RequestContext') -> dict:
    space_cfg = ap.instance_config.data.get('space', {}) or {}
    web_url = space_cfg.get('web_url') or space_cfg.get('url') or 'https://space.langbot.app'
    token = await resolve_space_access_token(ap, request_context)
    ctx = {
        'space_connected': False,
        'has_creator_profile': False,
        'creator_slug': None,
        'space_web_url': web_url.rstrip('/'),
    }
    if not token:
        return ctx
    valid, creator = await ap.space_service.get_creator_profile(token)
    ctx['space_connected'] = bool(valid)
    if valid and creator and creator.get('slug'):
        ctx['has_creator_profile'] = True
        ctx['creator_slug'] = creator['slug']
    return ctx


async def require_creator_token(ap: 'app.Application', request_context: 'RequestContext') -> tuple[str, str]:
    token = await resolve_space_access_token(ap, request_context)
    if not token:
        raise ShareError('Connect a LangBot Account before sharing to LangBot Space', status=400)
    valid, creator = await ap.space_service.get_creator_profile(token)
    if not valid:
        raise ShareError('The LangBot Account session has expired. Sign in again.', status=401)
    if not creator or not creator.get('slug'):
        raise ShareError('Set up a creator profile on LangBot Space before sharing', status=400)
    return token, creator['slug']


def build_prompt_payload(data: dict) -> tuple[dict, list[dict]]:
    """Validate a prompt share request; returns (payload, findings)."""
    kind = str(data.get('kind') or '')
    if kind not in PROMPT_KINDS:
        raise ShareError('kind must be messaging or agent')
    raw_messages = data.get('messages')
    if not isinstance(raw_messages, list) or not raw_messages or len(raw_messages) > MAX_PROMPT_MESSAGES:
        raise ShareError(f'A prompt needs 1-{MAX_PROMPT_MESSAGES} messages')
    messages = []
    total = 0
    for i, m in enumerate(raw_messages):
        if not isinstance(m, dict):
            raise ShareError('Invalid prompt message')
        role = str(m.get('role') or '')
        content = str(m.get('content') or '')
        if (i == 0 and role != 'system') or (i > 0 and role not in ('user', 'assistant')):
            raise ShareError('The first message must be system; later ones user or assistant')
        total += len(content.encode())
        messages.append({'role': role, 'content': content})
    if not messages[0]['content'].strip():
        raise ShareError('The system prompt is empty')
    if total > MAX_PROMPT_BYTES:
        raise ShareError('The prompt is larger than 32 KB')
    found_vars = []
    for m in messages:
        for v in re.findall(r'\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}', m['content']):
            if v not in found_vars:
                found_vars.append(v)
    described = {
        str(v.get('name')): str(v.get('description') or '')[:200]
        for v in (data.get('variables') or [])
        if isinstance(v, dict) and v.get('name')
    }
    variables = [{'name': v, 'description': described.get(v, '')} for v in found_vars[:32]]
    findings: list[dict] = []
    for i, m in enumerate(messages):
        findings.extend(scan_text(m['content'], where=f'messages[{i}]'))
    payload = {
        'kind': kind,
        'language': str(data.get('language') or '')[:16],
        'messages': messages,
        'variables': variables,
    }
    return payload, findings


def sanitize_mcp_server(server: dict, runtime_info: dict | None, overrides: dict | None = None) -> dict:
    """Turn a stored MCP server into a credential-free, publishable config.

    Every header / query parameter whose name looks sensitive or whose value
    looks like a credential becomes a ``${VAR}`` placeholder declared in
    ``required_inputs``. URL userinfo is refused. Returns the payload plus a
    ``redactions`` list describing each replacement for the preview UI.
    """
    overrides = overrides or {}
    mode = str(server.get('mode') or '')
    if mode not in ('remote', 'http', 'sse'):
        raise ShareError('Only remote MCP servers can be shared for now; stdio servers stay private.')
    extra = server.get('extra_args') or {}
    url = str(extra.get('url') or '').strip()
    parts = urlsplit(url)
    if parts.scheme != 'https' or not parts.hostname:
        raise ShareError('Only https MCP servers with a public address can be shared')
    host = parts.hostname.lower()
    if (
        re.fullmatch(r'[\d.]+|\[?[0-9a-f:]+\]?', host)
        or host == 'localhost'
        or '.' not in host
        or host.endswith(('.local', '.internal', '.lan', '.localhost'))
    ):
        raise ShareError('The MCP server URL must be a public domain name')
    if parts.username or parts.password:
        raise ShareError('Remove the username/password from the MCP server URL before sharing')

    used: set[str] = set(PLACEHOLDER.findall(url))
    inputs: dict[str, dict] = {}
    redactions: list[dict] = []
    input_meta = overrides.get('inputs') or {}

    def declare(name: str, label: str, secret: bool = True) -> None:
        meta = input_meta.get(name) or {}
        inputs[name] = {
            'name': name,
            'label': str(meta.get('label') or label)[:120],
            'description': str(meta.get('description') or '')[:500],
            'secret': secret,
            'required': True,
        }

    # Existing placeholders the user typed themselves.
    for name in list(used):
        declare(name, name)

    query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if PLACEHOLDER.fullmatch(value.strip()):
            query.append((key, value))
            continue
        if SENSITIVE_KEY.search(key) or looks_like_secret(value):
            var = _var_name(key, used)
            declare(var, key)
            query.append((key, '${' + var + '}'))
            redactions.append({'where': f'url?{key}', 'placeholder': var})
        else:
            query.append((key, value))
    path_segments = []
    for seg in parts.path.split('/'):
        if seg and looks_like_secret(seg):
            var = _var_name('URL_TOKEN', used)
            declare(var, 'URL token')
            path_segments.append('${' + var + '}')
            redactions.append({'where': 'url path', 'placeholder': var})
        else:
            path_segments.append(seg)
    clean_url = urlunsplit((parts.scheme, parts.netloc, '/'.join(path_segments), urlencode(query, safe='${}'), ''))

    headers: dict[str, str] = {}
    for key, value in (extra.get('headers') or {}).items():
        key, value = str(key), str(value)
        stripped = value.strip()
        if PLACEHOLDER.search(stripped) and not looks_like_secret(PLACEHOLDER.sub('', stripped)):
            for name in PLACEHOLDER.findall(stripped):
                if name not in inputs:
                    used.add(name)
                    declare(name, name)
            headers[key] = stripped
            continue
        if SENSITIVE_KEY.search(key) or looks_like_secret(stripped):
            var = _var_name(key, used)
            declare(var, key)
            scheme = ''
            m = re.match(r'^(Bearer|Basic|Token)\s+', stripped, re.I)
            if m:
                scheme = m.group(0)
            headers[key] = scheme + '${' + var + '}'
            redactions.append({'where': f'header {key}', 'placeholder': var})
        else:
            headers[key] = value

    tools = []
    for tool in (runtime_info or {}).get('tools') or []:
        tools.append(
            {
                'name': str(tool.get('name') or ''),
                'description': str(tool.get('description') or '')[:2000],
                'parameters': tool.get('parameters') or {},
            }
        )
    readme = overrides.get('readme')
    if readme is None:
        readme = server.get('readme') or ''
    payload: dict[str, typing.Any] = {
        'mode': 'remote',
        'url': clean_url,
        'headers': headers,
        'required_inputs': list(inputs.values()),
        'tools': tools[:200],
        'readme': str(readme)[: 64 * 1024],
    }
    timeout = extra.get('timeout')
    if isinstance(timeout, (int, float)) and 0 < timeout <= 600:
        payload['timeout'] = int(timeout)
    repository = str(overrides.get('repository') or '').strip()
    if repository:
        payload['repository'] = repository[:300]
    # Final guard: nothing that still looks like a credential may leave.
    leftovers = scan_text(clean_url + '\n' + '\n'.join(headers.values()), where='config')
    blocking = [f for f in leftovers if f['severity'] == 'block']
    if blocking:
        raise ShareError('The MCP configuration still contains a credential', findings=blocking)
    return {'payload': payload, 'redactions': redactions}


def inspect_skill_zip(package: bytes) -> dict:
    """List files and scan text files of a skill package for credentials."""
    if len(package) > MAX_SKILL_BYTES:
        raise ShareError('The skill package is larger than 10 MB')
    files = []
    findings: list[dict] = []
    with zipfile.ZipFile(io.BytesIO(package)) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            files.append({'path': info.filename, 'size': info.file_size})
            if info.file_size <= 512 * 1024:
                try:
                    text = zf.read(info).decode('utf-8')
                except (UnicodeDecodeError, KeyError):
                    continue
                findings.extend(scan_text(text, where=info.filename))
    return {'files': files, 'findings': findings[:50]}


def validate_share_metadata(data: dict, *, require_name: bool = True) -> dict:
    name = str(data.get('name') or '').strip().lower()
    if require_name and not NAME_PATTERN.match(name):
        raise ShareError("Name must be 2-64 lowercase letters, digits, '-' or '_'")

    def i18n(value: typing.Any) -> dict:
        if isinstance(value, str):
            return {'en_US': value} if value.strip() else {}
        if isinstance(value, dict):
            return {str(k): str(v)[:500] for k, v in value.items() if isinstance(v, str) and v.strip()}
        return {}

    label = i18n(data.get('label'))
    description = i18n(data.get('description'))
    if require_name and not label:
        raise ShareError('A display name is required')
    if require_name and not description:
        raise ShareError('A description is required')
    tags = [str(t).strip()[:32] for t in (data.get('tags') or []) if str(t).strip()][:8]
    return {
        'name': name,
        'label': label,
        'description': description,
        'tags': tags,
        'changelog': str(data.get('changelog') or '')[:4000],
    }
