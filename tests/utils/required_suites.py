"""Required suites select explicit markers and enforce execution, not case counts."""

import pytest


# These are behavior obligations, independent of file names and parametrization.
REQUIRED_CONTRACTS = {
    'session_summary': {
        'reader_dependencies',
        'reader_sql',
        'reader_http',
        'reader_scale',
        'summary_accounting',
        'summary_fact_equivalence',
        'summary_snapshot',
        'summary_atomicity',
        'summary_backfill',
        'summary_retention',
        'summary_postgres',
        'summary_schema',
    },
    'postgres': {
        'admission_isolation',
        'rag_identity',
        'rag_recovery',
        'migration_history',
        'migration_fresh_schema',
        'runner_timestamps',
        'monitoring_sessions',
    },
    'local_agent': {'agent_ledger', 'agent_tools', 'agent_rag', 'agent_compaction', 'agent_multi_turn', 'agent_box'},
    'security': {'debug_exec_absent', 'debug_route_absent'},
    'compiled_cli': {'cli_http'},
    'plugin_identity': {'dify_identity', 'n8n_identity', 'coze_identity', 'tbox_identity'},
    'seekdb': {'vector_round_trip', 'hybrid_relevance'},
}


def pytest_addoption(parser):
    parser.addoption('--required-suite', choices=tuple(REQUIRED_CONTRACTS), help='Run a mandatory dependency suite')


def pytest_configure(config):
    suite = config.getoption('--required-suite')
    if suite:
        if config.option.markexpr or config.option.keyword or config.option.deselect:
            raise pytest.UsageError('--required-suite cannot be combined with -m, -k or --deselect')
        config.option.markexpr = suite
        config.pluginmanager.register(RequiredSuite(suite), 'required-suite-policy')


class RequiredSuite:
    def __init__(self, suite):
        self.suite = suite
        self.items = {}
        self.passed = set()
        self.unsuccessful = set()

    def pytest_collection_finish(self, session):
        for item in session.items:
            self.items[item.nodeid] = {mark.args[0] for mark in item.iter_markers('contract')}
        covered = set().union(*self.items.values())
        missing = REQUIRED_CONTRACTS[self.suite] - covered
        if missing:
            raise pytest.UsageError(f'Required suite {self.suite} is missing contracts: {sorted(missing)}')

    def pytest_runtest_logreport(self, report):
        if report.nodeid not in self.items:
            return
        if report.failed or report.skipped or hasattr(report, 'wasxfail'):
            self.unsuccessful.add(report.nodeid)
        if report.when == 'call' and report.passed:
            self.passed.add(report.nodeid)

    def pytest_sessionfinish(self, session, exitstatus):
        if session.config.option.collectonly:
            return
        incomplete = set(self.items) - self.passed
        if exitstatus == 0 and (incomplete or self.unsuccessful or not self.items):
            session.exitstatus = pytest.ExitCode.TESTS_FAILED
        reporter = session.config.pluginmanager.get_plugin('terminalreporter')
        if reporter and (incomplete or self.unsuccessful):
            reporter.write_sep('=', f'Required suite {self.suite}: all selected cases must pass without skips/xfails')
            for nodeid in sorted(incomplete | self.unsuccessful):
                reporter.write_line(nodeid)
