"""Backfill raw artifact digests for legacy shared certificates.

Revision ID: 0032_cert_artifact_digest
Revises: 0031_merge_totp_assistant

Older certified-plugin rows persisted every shared-admission fact except the raw
archive digest.  Placement now requires that digest to match the installation's
immutable artifact digest, so this migration fills only records whose remaining
facts already prove the exact legacy shared-admission shape.
"""

from __future__ import annotations

from collections.abc import Mapping

import sqlalchemy as sa
from alembic import op

revision = '0032_cert_artifact_digest'
down_revision = '0031_merge_totp_assistant'
branch_labels = None
depends_on = None

_TABLE = 'plugin_settings'
_SHARED_RUNTIME = 'shared-runtime-v1'
_SHARED_ADMISSION_CODE = 'CERTIFIED_PLUGIN_SHARED_ELIGIBLE'
_LOWER_HEX = frozenset('0123456789abcdef')
_HEX = frozenset('0123456789abcdefABCDEF')


def _is_digest(value: object, *, lowercase: bool) -> bool:
    allowed = _LOWER_HEX if lowercase else _HEX
    return isinstance(value, str) and len(value) == 64 and all(character in allowed for character in value)


def _eligible_certification(install_info: object, artifact_digest: object) -> Mapping[object, object] | None:
    if not _is_digest(artifact_digest, lowercase=True) or not isinstance(install_info, Mapping):
        return None
    certification = install_info.get('_certification')
    if not isinstance(certification, Mapping) or 'artifact_digest' in certification:
        return None
    certificate_id = certification.get('certificate_id')
    if not isinstance(certificate_id, str) or not certificate_id.strip():
        return None
    if not _is_digest(certification.get('normalized_digest'), lowercase=False):
        return None
    required_facts = {
        'verification': 'valid',
        'certificate_runtime_profile': _SHARED_RUNTIME,
        'runtime_profile': _SHARED_RUNTIME,
        'admission_code': _SHARED_ADMISSION_CODE,
    }
    if not all(certification.get(key) == value for key, value in required_facts.items()):
        return None
    return certification


def _suspend_postgres_rls(conn: sa.Connection) -> tuple[bool, bool]:
    if conn.dialect.name != 'postgresql':
        return False, False
    state = conn.execute(
        sa.text('SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE oid = to_regclass(:table_name)'),
        {'table_name': _TABLE},
    ).one()
    rls_enabled, rls_forced = bool(state.relrowsecurity), bool(state.relforcerowsecurity)
    if rls_forced:
        conn.execute(sa.text(f'ALTER TABLE {_TABLE} NO FORCE ROW LEVEL SECURITY'))
    if rls_enabled:
        conn.execute(sa.text(f'ALTER TABLE {_TABLE} DISABLE ROW LEVEL SECURITY'))
    return rls_enabled, rls_forced


def _restore_postgres_rls(conn: sa.Connection, state: tuple[bool, bool]) -> None:
    if conn.dialect.name != 'postgresql':
        return
    rls_enabled, rls_forced = state
    if rls_enabled:
        conn.execute(sa.text(f'ALTER TABLE {_TABLE} ENABLE ROW LEVEL SECURITY'))
    if rls_forced:
        conn.execute(sa.text(f'ALTER TABLE {_TABLE} FORCE ROW LEVEL SECURITY'))


def backfill_certification_artifact_digests(conn: sa.Connection) -> None:
    inspector = sa.inspect(conn)
    if _TABLE not in inspector.get_table_names():
        return
    columns = {column['name'] for column in inspector.get_columns(_TABLE)}
    required_columns = {
        'workspace_uuid',
        'plugin_author',
        'plugin_name',
        'artifact_digest',
        'install_info',
    }
    if not required_columns <= columns:
        return

    plugin_settings = sa.table(
        _TABLE,
        sa.column('workspace_uuid', sa.String(36)),
        sa.column('plugin_author', sa.String(255)),
        sa.column('plugin_name', sa.String(255)),
        sa.column('artifact_digest', sa.String(64)),
        sa.column('install_info', sa.JSON()),
    )
    rows = conn.execute(sa.select(plugin_settings)).mappings().all()
    for row in rows:
        certification = _eligible_certification(row['install_info'], row['artifact_digest'])
        if certification is None:
            continue
        updated_certification = dict(certification)
        updated_certification['artifact_digest'] = row['artifact_digest']
        updated_install_info = dict(row['install_info'])
        updated_install_info['_certification'] = updated_certification
        conn.execute(
            plugin_settings.update()
            .where(plugin_settings.c.workspace_uuid == row['workspace_uuid'])
            .where(plugin_settings.c.plugin_author == row['plugin_author'])
            .where(plugin_settings.c.plugin_name == row['plugin_name'])
            .values(install_info=updated_install_info)
        )


def upgrade() -> None:
    conn = op.get_bind()
    if _TABLE not in sa.inspect(conn).get_table_names():
        return
    rls_state = _suspend_postgres_rls(conn)
    try:
        backfill_certification_artifact_digests(conn)
    finally:
        _restore_postgres_rls(conn, rls_state)


def downgrade() -> None:
    # The source digest cannot be distinguished from a digest persisted by
    # current Core, so downgrade intentionally preserves the safe enrichment.
    pass
