"""F-01 evidence: PDF parsing must run inside a dedicated process boundary.

PyMuPDF is documented as not thread safe and its table finder keeps module-level
page state (``EDGES`` / ``CHARS``), so driving it from the shared worker's thread
pool made concurrent parses from different installations re-enter the dependency
and let a cancelled parse keep working after its caller was gone.  These tests
pin the replacement contract:

* a parse runs in its own short-lived process, never in the shared one,
* PyMuPDF's module state only ever exists inside that process,
* the worker is reaped before the caller resumes on success, timeout and
  cancellation, so a later request can never overlap the previous one's work.

The tests fail against the pre-fix code: there the parse ran through
``asyncio.to_thread`` inside the shared process, so PyMuPDF modules (including
``pymupdf.table`` and its page state) appeared in the shared interpreter and no
process boundary existed to observe or tear down.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from importlib import import_module, util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

BOUNDARY_MODULE = 'components.general_parsers.isolated_process'
PDF_MODULE = 'components.general_parsers.parsers.pdf'
PYMUPDF_AVAILABLE = util.find_spec('pymupdf') is not None or util.find_spec('fitz') is not None


def _pymupdf_modules() -> set[str]:
    """PyMuPDF modules currently imported in *this* process."""
    return {
        name for name in list(sys.modules)
        if name == 'fitz' or name.startswith(('fitz.', 'pymupdf'))
    }


def _worker_dependency_state() -> dict:
    """Runs inside the worker: does the dependency keep module-level page state?"""
    table = None
    for module_name in ('pymupdf.table', 'fitz.table'):
        try:
            table = import_module(module_name)
            break
        except ImportError:
            continue
    if table is None:
        return {'modules': [], 'page_state': False}
    return {
        'modules': sorted(_pymupdf_modules()),
        'page_state': hasattr(table, 'CHARS') or hasattr(table, 'EDGES'),
    }


def _probe_worker(payload: dict) -> dict:
    """Fake worker target: reports its process and holds the boundary open."""
    marker_dir = Path(payload['marker_dir'])
    (marker_dir / 'started').write_text(str(os.getpid()), encoding='utf-8')
    dependency = _worker_dependency_state()
    deadline = time.monotonic() + float(payload.get('hold_seconds', 0.0))
    while time.monotonic() < deadline:
        time.sleep(0.02)
    (marker_dir / 'finished').write_text('done', encoding='utf-8')
    return {'pid': os.getpid(), 'dependency': dependency}


def _crashing_worker(payload: dict) -> dict:
    """Fake worker target: dies like a native PyMuPDF fault would."""
    os._exit(int(payload.get('exit_code', 7)))


def _pid_is_alive(pid: int) -> bool:
    if os.name == 'nt':
        import ctypes

        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel32.OpenProcess.restype = ctypes.c_void_p
        kernel32.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        kernel32.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return False
            return exit_code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _build_pdf(page_texts: list[str]) -> bytes:
    """Build a minimal valid multi-page PDF without third-party helpers."""
    first_page_object = 3
    font_object = first_page_object + 2 * len(page_texts)
    page_objects = [first_page_object + 2 * index for index in range(len(page_texts))]

    objects: list[bytes] = [
        b'<< /Type /Catalog /Pages 2 0 R >>',
        (
            '<< /Type /Pages /Kids ['
            + ' '.join(f'{number} 0 R' for number in page_objects)
            + f'] /Count {len(page_texts)} >>'
        ).encode(),
    ]
    for index, page_text in enumerate(page_texts):
        content_object = first_page_object + 2 * index + 1
        objects.append(
            (
                f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] '
                f'/Resources << /Font << /F1 {font_object} 0 R >> >> '
                f'/Contents {content_object} 0 R >>'
            ).encode()
        )
        escaped = page_text.replace('\\', r'\\').replace('(', r'\(').replace(')', r'\)')
        stream = f'BT /F1 24 Tf 72 700 Td ({escaped}) Tj ET'.encode()
        objects.append(
            b'<< /Length ' + str(len(stream)).encode() + b' >>\nstream\n' + stream + b'\nendstream'
        )
    objects.append(b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>')

    document = bytearray(b'%PDF-1.4\n')
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(document))
        document += f'{number} 0 obj\n'.encode() + body + b'\nendobj\n'
    xref_offset = len(document)
    document += f'xref\n0 {len(objects) + 1}\n'.encode()
    document += b'0000000000 65535 f \n'
    for offset in offsets:
        document += f'{offset:010d} 00000 n \n'.encode()
    document += (
        f'trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n'
        f'startxref\n{xref_offset}\n%%EOF\n'
    ).encode()
    return bytes(document)


class BoundaryProcessTests(unittest.IsolatedAsyncioTestCase):
    """The process boundary itself: identity, reaping, timeout, cancellation."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.marker_root = Path(self._tmp.name)

    def _marker_dir(self, name: str) -> Path:
        path = self.marker_root / name
        path.mkdir()
        return path

    def _boundary(self):
        return import_module(BOUNDARY_MODULE)

    async def _wait_for_pid(self, marker: Path, timeout: float = 30.0) -> int:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if marker.exists():
                content = marker.read_text(encoding='utf-8').strip()
                if content:
                    return int(content)
            await asyncio.sleep(0.02)
        raise AssertionError(f'the worker never reported itself through {marker}')

    async def test_target_runs_in_its_own_process_and_is_reaped_before_returning(self) -> None:
        boundary = self._boundary()
        markers = self._marker_dir('single')
        modules_before = _pymupdf_modules()

        result = await boundary.run_isolated(
            f'{__name__}:_probe_worker',
            {'marker_dir': str(markers), 'hold_seconds': 0.0},
            timeout=60,
            name='probe',
        )

        self.assertNotEqual(result['pid'], os.getpid(), 'the parse ran inside the shared process')
        self.assertFalse(_pid_is_alive(result['pid']), 'the worker outlived the boundary')
        self.assertEqual(boundary.active_worker_count(), 0)
        self.assertTrue((markers / 'finished').exists())
        self.assertEqual(
            _pymupdf_modules(),
            modules_before,
            'the shared process gained PyMuPDF module state',
        )
        if PYMUPDF_AVAILABLE:
            self.assertTrue(
                result['dependency']['modules'],
                'the worker did not exercise the dependency',
            )
            self.assertTrue(
                result['dependency']['page_state'],
                'the dependency no longer keeps module-level page state',
            )

    async def test_worker_crash_does_not_take_down_the_shared_process(self) -> None:
        boundary = self._boundary()

        with self.assertRaises(boundary.IsolatedWorkerError) as caught:
            await boundary.run_isolated(
                f'{__name__}:_crashing_worker',
                {'exit_code': 7},
                timeout=60,
                name='crash probe',
            )

        self.assertNotIsInstance(caught.exception, boundary.IsolatedWorkerTimeout)
        self.assertIn('7', str(caught.exception))
        self.assertEqual(boundary.active_worker_count(), 0)

    async def test_hard_timeout_terminates_the_worker(self) -> None:
        boundary = self._boundary()
        markers = self._marker_dir('timeout')
        started = markers / 'started'

        started_at = time.monotonic()
        task = asyncio.create_task(
            boundary.run_isolated(
                f'{__name__}:_probe_worker',
                {'marker_dir': str(markers), 'hold_seconds': 30.0},
                timeout=1.5,
                name='timeout probe',
            )
        )
        pid = await self._wait_for_pid(started)
        with self.assertRaises(boundary.IsolatedWorkerTimeout):
            await task
        elapsed = time.monotonic() - started_at

        self.assertLess(elapsed, 15.0, 'the worker was not stopped by its hard timeout')
        self.assertFalse(_pid_is_alive(pid), 'the timed out worker is still running')
        self.assertEqual(boundary.active_worker_count(), 0)
        self.assertFalse((markers / 'finished').exists(), 'timed out work continued')

    async def test_cancellation_tears_the_worker_down_before_the_caller_resumes(self) -> None:
        boundary = self._boundary()
        markers = self._marker_dir('cancelled')
        started = markers / 'started'

        task = asyncio.create_task(
            boundary.run_isolated(
                f'{__name__}:_probe_worker',
                {'marker_dir': str(markers), 'hold_seconds': 30.0},
                timeout=120,
                name='cancel probe',
            )
        )
        cancelled_pid = await self._wait_for_pid(started)
        self.assertEqual(boundary.active_worker_count(), 1)
        self.assertTrue(_pid_is_alive(cancelled_pid), 'the worker was not running before the cancel')

        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task

        # The caller only regains control once the worker is gone.
        self.assertEqual(boundary.active_worker_count(), 0)
        self.assertFalse(_pid_is_alive(cancelled_pid), 'the cancelled worker is still running')
        self.assertFalse((markers / 'finished').exists(), 'cancelled work continued')

        # Another installation can start immediately, in a fresh process.
        next_markers = self._marker_dir('after-cancel')
        follow_up = await boundary.run_isolated(
            f'{__name__}:_probe_worker',
            {'marker_dir': str(next_markers), 'hold_seconds': 0.0},
            timeout=60,
            name='follow up',
        )
        self.assertNotEqual(follow_up['pid'], cancelled_pid)
        self.assertFalse(_pid_is_alive(follow_up['pid']))

    async def test_concurrent_parses_never_share_a_process(self) -> None:
        boundary = self._boundary()
        first_markers = self._marker_dir('first')
        second_markers = self._marker_dir('second')

        first = asyncio.create_task(
            boundary.run_isolated(
                f'{__name__}:_probe_worker',
                {'marker_dir': str(first_markers), 'hold_seconds': 3.0},
                timeout=60,
                name='first probe',
            )
        )
        second = asyncio.create_task(
            boundary.run_isolated(
                f'{__name__}:_probe_worker',
                {'marker_dir': str(second_markers), 'hold_seconds': 3.0},
                timeout=60,
                name='second probe',
            )
        )
        first_pid = await self._wait_for_pid(first_markers / 'started')
        second_pid = await self._wait_for_pid(second_markers / 'started')

        self.assertNotEqual(first_pid, second_pid, 'two parses shared one worker process')
        self.assertEqual(boundary.active_worker_count(), 2)

        first_result, second_result = await asyncio.gather(first, second)
        self.assertEqual(first_result['pid'], first_pid)
        self.assertEqual(second_result['pid'], second_pid)
        self.assertEqual(boundary.active_worker_count(), 0)
        self.assertFalse(_pid_is_alive(first_pid))
        self.assertFalse(_pid_is_alive(second_pid))


class PdfParsingIsolationTests(unittest.IsolatedAsyncioTestCase):
    """The real PDF path: out-of-process parsing, no PyMuPDF in the shared process."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def _tmp_pdf(self) -> str:
        path = Path(self._tmp.name) / 'fresh-process.pdf'
        path.write_bytes(_build_pdf(['Boundary page one', 'Boundary page two', 'Boundary page three']))
        return str(path)

    def _tmp_probe(self) -> str:
        path = Path(self._tmp.name) / 'fresh_process_probe.py'
        path.write_text(
            'import asyncio\n'
            'import json\n'
            'import os\n'
            'import sys\n'
            '\n'
            'plugin_root, pdf_path = sys.argv[1], sys.argv[2]\n'
            'sys.path.insert(0, plugin_root)\n'
            '\n'
            'from components.general_parsers.parsers.pdf import parse_pdf\n'
            '\n'
            'with open(pdf_path, "rb") as handle:\n'
            '    payload = handle.read()\n'
            '\n'
            'text, metadata = asyncio.run(parse_pdf(payload, "probe.pdf"))\n'
            'modules = sorted(\n'
            '    name for name in sys.modules\n'
            '    if name == "fitz" or name.startswith(("fitz.", "pymupdf"))\n'
            ')\n'
            'print(json.dumps({\n'
            '    "text": text,\n'
            '    "page_count": metadata.get("page_count"),\n'
            '    "modules": modules,\n'
            '    "pid": os.getpid(),\n'
            '}))\n',
            encoding='utf-8',
        )
        return str(path)

    async def test_pdf_parse_runs_out_of_process_and_reaps_its_worker(self) -> None:
        if not PYMUPDF_AVAILABLE:
            self.skipTest('PyMuPDF is not installed')
        parse_pdf = getattr(import_module(PDF_MODULE), 'parse_pdf')
        boundary = import_module(BOUNDARY_MODULE)
        pdf_bytes = _build_pdf(['Boundary page one', 'Boundary page two', 'Boundary page three'])
        modules_before = _pymupdf_modules()

        task = asyncio.create_task(parse_pdf(pdf_bytes, 'boundary.pdf'))
        observed: set[int] = set()
        for _ in range(2000):
            observed |= set(boundary.active_worker_pids())
            if task.done():
                break
            await asyncio.sleep(0.005)

        text, metadata = await task

        self.assertIn('Boundary page one', text)
        self.assertEqual(metadata['page_count'], 3)
        self.assertTrue(observed, 'the parse never appeared in a worker process')
        self.assertNotIn(os.getpid(), observed, 'the parse ran inside the shared process')
        self.assertEqual(boundary.active_worker_count(), 0)
        self.assertEqual(
            _pymupdf_modules(),
            modules_before,
            'the shared process gained PyMuPDF module state',
        )

    @unittest.skipUnless(PYMUPDF_AVAILABLE, 'PyMuPDF is not installed')
    async def test_fresh_process_ends_a_pdf_parse_without_pymupdf_state(self) -> None:
        pdf_path = self._tmp_pdf()
        probe_path = self._tmp_probe()
        modules_before = _pymupdf_modules()

        completed = await asyncio.to_thread(
            subprocess.run,
            [sys.executable, probe_path, str(REPO_ROOT), pdf_path],
            capture_output=True,
            text=True,
            timeout=180,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout.strip().splitlines()[-1])
        self.assertEqual(
            report['modules'],
            [],
            'PyMuPDF state is reachable in the process that ran the parse',
        )
        self.assertIn('Boundary page one', report['text'])
        self.assertEqual(report['page_count'], 3)
        self.assertEqual(_pymupdf_modules(), modules_before)


class TwoInstallationPdfTests(unittest.IsolatedAsyncioTestCase):
    """Two installations parsing at once must not see each other's document."""

    def setUp(self) -> None:
        if not PYMUPDF_AVAILABLE:
            self.skipTest('PyMuPDF is not installed')
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def _binding(self, installation: str):
        from langbot_plugin.entities.io.context import InstallationBinding

        return InstallationBinding(
            instance_uuid='instance-1',
            workspace_uuid='workspace-1',
            installation_uuid=installation,
            runtime_revision=1,
            artifact_digest='a' * 64,
        )

    async def test_concurrent_parses_keep_their_own_document_text(self) -> None:
        from langbot_plugin.api.entities.builtin.rag.models import ParseContext
        from langbot_plugin.api.proxies.invocation import bind_invocation
        from components.observability.telemetry import get_telemetry, release_telemetry

        parser_class = getattr(import_module('components.general_parsers.general_parsers'), 'GeneralParsers')
        handler = object()

        class Plugin:
            plugin_runtime_handler = handler

            def get_config(self) -> dict:
                return {'enable_vision': False}

        parser = parser_class()
        parser.plugin = Plugin()

        first_binding = self._binding('installation-a')
        second_binding = self._binding('installation-b')
        first_pdf = _build_pdf(['Tenant A page one', 'Tenant A page two'])
        second_pdf = _build_pdf(['Tenant B page one', 'Tenant B page two'])

        async def _parse_for(binding, pdf_bytes: bytes, filename: str):
            # Each task carries its own context, so its invocation binding stays
            # active for the whole parse and never overlaps the other one.
            with bind_invocation(handler, config={'enable_vision': False}, binding=binding):
                return await parser.parse(ParseContext(
                    file_content=pdf_bytes,
                    filename=filename,
                    mime_type='application/pdf',
                ))

        for _ in range(2):
            first_task = asyncio.create_task(_parse_for(first_binding, first_pdf, 'tenant-a.pdf'))
            second_task = asyncio.create_task(_parse_for(second_binding, second_pdf, 'tenant-b.pdf'))
            first_result, second_result = await asyncio.gather(first_task, second_task)

            self.assertIn('Tenant A page one', first_result.text)
            self.assertNotIn('Tenant B', first_result.text)
            self.assertEqual(first_result.metadata['page_count'], 2)
            self.assertIn('Tenant B page one', second_result.text)
            self.assertNotIn('Tenant A', second_result.text)
            self.assertEqual(second_result.metadata['page_count'], 2)

        first_snapshot = get_telemetry(first_binding).snapshot()
        second_snapshot = get_telemetry(second_binding).snapshot()
        self.assertEqual(
            {entry['filename'] for entry in first_snapshot['recent_parses']},
            {'tenant-a.pdf'},
        )
        self.assertEqual(
            {entry['filename'] for entry in second_snapshot['recent_parses']},
            {'tenant-b.pdf'},
        )
        release_telemetry(first_binding)
        release_telemetry(second_binding)


if __name__ == '__main__':
    unittest.main()
