"""Finish SQLite WAL maintenance before application producers start."""

STARTUP_BUSY_TIMEOUT_MS = 60_000


async def checkpoint_after_migration(engine):
    """Require a complete WAL checkpoint, including on a retry at schema head."""
    if engine.dialect.name != 'sqlite':
        return
    async with engine.connect() as connection:
        connection = await connection.execution_options(isolation_level='AUTOCOMMIT')
        if (await connection.exec_driver_sql('PRAGMA journal_mode')).scalar_one().lower() != 'wal':
            return
        timeout = (await connection.exec_driver_sql('PRAGMA busy_timeout')).scalar_one()
        try:
            await connection.exec_driver_sql(f'PRAGMA busy_timeout={STARTUP_BUSY_TIMEOUT_MS}')
            busy, frames, checkpointed = (
                await connection.exec_driver_sql('PRAGMA main.wal_checkpoint(TRUNCATE)')
            ).one()
            if (busy, frames, checkpointed) != (0, 0, 0):
                raise RuntimeError(
                    'SQLite startup WAL checkpoint did not complete: '
                    f'busy={busy}, frames={frames}, checkpointed={checkpointed}. '
                    'Stop other database users and restart LangBot to retry.'
                )
        finally:
            await connection.exec_driver_sql(f'PRAGMA busy_timeout={timeout}')
