"""Exercise generated shell/Python syntax without installing dependencies."""

import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

from langbot.pkg.utils.python_workspace import wrap_python_command_with_env


class TestPythonWorkspaceCommand(unittest.TestCase):
    def test_generated_command_contains_no_null_bytes(self):
        command = wrap_python_command_with_env('python main.py')
        self.assertNotIn('\0', command)

    @unittest.skipUnless(shutil.which('sh'), 'POSIX shell required')
    def test_generated_command_has_valid_shell_syntax(self):
        command = wrap_python_command_with_env('python main.py')
        result = subprocess.run(['sh', '-n', '-c', command], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(shutil.which('sh'), 'POSIX shell required')
    def test_cached_environment_executes_command_and_hashes_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mount = root / 'project'
            state = root / 'state'
            bin_dir = root / 'bin'
            venv_bin = state / '.venv' / 'bin'
            meta_dir = state / '.langbot'
            for path in (mount, bin_dir, venv_bin, meta_dir):
                path.mkdir(parents=True)

            manifest = b'# local fixture\nexample==1.0\n'
            (mount / 'requirements.txt').write_bytes(manifest)
            # Run the real metadata interpreter, but fail closed if bootstrap is attempted.
            system_python = bin_dir / 'python3'
            system_python.write_text(
                '#!/bin/sh\n'
                '[ "$#" -eq 1 ] && [ "$1" = "-" ] || exit 99\n'
                f'exec {shlex.quote(sys.executable)} "$@"\n',
                encoding='utf-8',
            )
            system_python.chmod(0o755)
            venv_python = venv_bin / 'python'
            venv_python.write_text('#!/bin/sh\nprintf "%s\\n" "$VIRTUAL_ENV"\n', encoding='utf-8')
            venv_python.chmod(0o755)
            metadata = json.dumps(
                {
                    'python_executable': sys.executable,
                    'python_version': list(sys.version_info[:3]),
                    'manifest_files': ['requirements.txt'],
                    'manifest_sha256': hashlib.sha256(b'requirements.txt\0' + manifest + b'\0').hexdigest(),
                },
                sort_keys=True,
            )
            meta_file = meta_dir / 'python-env.json'
            meta_file.write_text(metadata, encoding='utf-8')

            command = wrap_python_command_with_env('python', mount_path=str(mount), state_path=str(state))
            result = subprocess.run(
                ['sh', '-c', command],
                env={**os.environ, 'PATH': f'{bin_dir}{os.pathsep}{os.environ.get("PATH", "")}'},
                capture_output=True,
                text=True,
                timeout=10,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, f'{state / ".venv"}\n')
            self.assertEqual(meta_file.read_text(encoding='utf-8'), metadata)
            self.assertFalse((meta_dir / 'python-env.lock').exists())
