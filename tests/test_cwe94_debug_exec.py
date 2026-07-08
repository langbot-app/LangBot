"""
PoC test for CWE-94: Authenticated RCE via exec() on user-supplied Python code.

The /api/v1/system/debug/exec endpoint passes raw HTTP body to exec(),
allowing arbitrary code execution when debug_mode is True.

This test verifies that:
1. The exec() endpoint is removed from the codebase entirely.
2. No route matches /api/v1/system/debug/exec.
"""

import ast
import pathlib

# Resolve project root (one level up from tests/)
_PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent

VULN_FILE = _PROJECT_ROOT / 'src' / 'langbot' / 'pkg' / 'api' / 'http' / 'controller' / 'groups' / 'system.py'


def test_no_exec_call_in_system_controller():
    """Verify there is no exec() call in system.py that takes user input."""
    with open(VULN_FILE, 'r') as f:
        source = f.read()

    tree = ast.parse(source)

    exec_calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            # Match bare exec() call
            if isinstance(func, ast.Name) and func.id == 'exec':
                exec_calls.append(node.lineno)

    assert len(exec_calls) == 0, (
        f'Found exec() call(s) at line(s) {exec_calls} in system.py. User-supplied code must never be passed to exec().'
    )


def test_no_debug_exec_route():
    """Verify the /debug/exec route is not registered."""
    with open(VULN_FILE, 'r') as f:
        source = f.read()

    assert 'debug/exec' not in source, (
        'The /debug/exec route still exists in system.py. '
        'This endpoint allows arbitrary code execution and must be removed.'
    )


if __name__ == '__main__':
    test_no_exec_call_in_system_controller()
    test_no_debug_exec_route()
    print('All tests passed!')
