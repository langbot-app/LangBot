"""Exercise the incremental gate with actual commits and the same Ruff used by CI."""

from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from textwrap import dedent


GATE = Path(__file__).with_name('check_traceback_logging.py').resolve()


def main(ruff):
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        path = root / 'sdk/src/langbot_plugin/legacy.py'
        path.parent.mkdir(parents=True)
        path.write_text(
            dedent("""\
            from traceback import print_exc, print_exception as emit
            import traceback as tb

            def historical():
                print_exc()
                emit(ValueError())

            def safe(print_exc):
                pass
        """)
        )

        def git(*args):
            subprocess.run(['git', *args], cwd=root, check=True, capture_output=True)

        def commit(message):
            git('add', '-A')
            git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', message)

        def check(expected, *locations):
            result = subprocess.run([sys.executable, GATE, 'HEAD^', *ruff], cwd=root, capture_output=True, text=True)
            assert result.returncode == expected, (result.stdout, result.stderr)
            diagnostics = result.stdout.splitlines()
            assert len(diagnostics) == len(locations), diagnostics
            for line_number, function in locations:
                assert any(f':{line_number}:' in line and function in line for line in diagnostics), diagnostics

        git('init', '-q')
        commit('Baseline')
        new_path = path.with_name('renamed.py')
        path.rename(new_path)
        commit('Pure rename')
        check(0)
        source = new_path.read_text().replace('    pass', '    print_exc()')
        new_path.write_text(source)
        commit('Shadowing parameter')
        check(0)
        with new_path.open('a') as handle:
            handle.write('\nprint_exc()  # noqa: TID251\nemit(ValueError())\ntb.print_exc()\n')
        commit('New calls via old imports')
        check(1, (11, 'traceback.print_exc'), (12, 'traceback.print_exception'), (13, 'traceback.print_exc'))


if __name__ == '__main__':
    main(sys.argv[1:] or ['ruff'])
