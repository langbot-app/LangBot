from __future__ import annotations

import unittest

from components.report_core.sheet_snapshot import render_sheet_snapshot


class SheetSnapshotTest(unittest.TestCase):
    def test_render_sheet_snapshot_returns_png_data_url(self) -> None:
        values = [
            ["表头A", "表头B", "表头C"],
            ["说明A", "说明B", "说明C"],
            ["规格A", "规格B", "规格C"],
            ["2026-03-01", "DA2603-001", "1.23"],
            ["2026-03-02", "DA2603-002", "1.24"],
            ["2026-03-03", "DA2603-003", "1.25"],
        ]

        result = render_sheet_snapshot(sheet_title="S18-A线", values=values, header_rows=3, tail_nonempty_rows=2, chunk_size=2)

        self.assertTrue(result.data_url.startswith("data:image/png;base64,"))
        self.assertEqual(result.selected_rows, [1, 2, 3, 5, 6])
        self.assertEqual(result.max_col, 3)


if __name__ == "__main__":
    unittest.main()
