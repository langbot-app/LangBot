"""Keep subprocess coverage pointed at the generated E2E configuration."""

from pathlib import Path
from unittest.mock import Mock, patch

from tests.e2e.utils.process_manager import LangBotProcess


def test_e2e_coverage_environment_uses_generated_config(tmp_path):
    process = Mock()
    process.poll.return_value = None
    project = tmp_path / 'project'
    project.mkdir()
    manager = LangBotProcess(project, tmp_path, collect_coverage=True)
    # start() opens real log files even when the child process is mocked.
    # Pair it with cleanup, without signalling any real operating-system PID.
    with (
        patch('subprocess.Popen', return_value=process) as popen,
        patch('httpx.get') as get,
        patch('os.getpgid', return_value=1),
        patch('os.killpg'),
    ):
        get.return_value.status_code = 200
        try:
            assert manager.start()
            config = Path(popen.call_args.kwargs['env']['COVERAGE_PROCESS_START'])
            assert config.is_file()
            assert f'--rcfile={config}' in popen.call_args.args[0]
        finally:
            manager.stop()
        assert manager._stdout_file is None
        assert manager._stderr_file is None
