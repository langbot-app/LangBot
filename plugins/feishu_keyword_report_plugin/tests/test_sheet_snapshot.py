from __future__ import annotations

import unittest

from components.report_core.sheet_snapshot import _cell_to_text, render_sheet_snapshot


class SheetSnapshotTest(unittest.TestCase):
    def test_cell_to_text_should_extract_rich_text_segments(self) -> None:
        rich_value = [
            {
                "segmentStyle": {
                    "bold": True,
                    "fontSize": 8,
                    "foreColor": "FF0000",
                    "italic": False,
                    "strikeThrough": False,
                    "underline": False,
                },
                "text": "161±2.5",
                "type": "text",
            },
            {
                "segmentStyle": {
                    "bold": True,
                    "fontSize": 8,
                    "foreColor": "FF0000",
                    "italic": False,
                    "strikeThrough": False,
                    "underline": False,
                },
                "text": "\nmAh/g",
                "type": "text",
            },
        ]

        self.assertEqual(_cell_to_text(rich_value), "161±2.5\nmAh/g")

    def test_cell_to_text_should_extract_rich_text_from_json_string(self) -> None:
        raw = (
            '[{"segmentStyle":{"bold":true,"fontSize":8,"foreColor":"FF0000"},'
            '"text":"161\\u00b12.5","type":"text"},{"segmentStyle":{"bold":true},'
            '"text":"\\nmAh/g","type":"text"}]'
        )

        self.assertEqual(_cell_to_text(raw), "161±2.5\nmAh/g")

    def test_render_sheet_snapshot_returns_png_data_url(self) -> None:
        values = [
            ["headerA", "headerB", "headerC"],
            ["descA", "descB", "descC"],
            ["specA", "specB", "specC"],
            ["2026-03-01", "DA2603-001", "1.23"],
            ["2026-03-02", "DA2603-002", "1.24"],
            ["2026-03-03", "DA2603-003", "1.25"],
        ]

        result = render_sheet_snapshot(
            sheet_title="S18-A",
            values=values,
            header_rows=3,
            tail_nonempty_rows=2,
            chunk_size=2,
        )

        self.assertTrue(result.data_url.startswith("data:image/png;base64,"))
        self.assertEqual(result.selected_rows, [1, 2, 3, 5, 6])
        self.assertEqual(result.max_col, 3)


if __name__ == "__main__":
    unittest.main()
