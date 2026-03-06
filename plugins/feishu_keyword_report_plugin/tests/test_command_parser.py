from __future__ import annotations

import unittest

from components.command_parser import parse_report_command, parse_touch_material_command


class CommandParserTest(unittest.TestCase):
    def test_parse_basic_report_command(self) -> None:
        result = parse_report_command("日报", {"日报"})
        self.assertTrue(result.triggered)
        self.assertEqual(result.error, "")
        assert result.value is not None
        self.assertIsNone(result.value.date_arg)
        self.assertEqual(result.value.sheet_names, [])

    def test_parse_report_date_and_sheets(self) -> None:
        result = parse_report_command("日报 2026-03-03 S18-A线,S006-B线", {"日报"})
        self.assertTrue(result.triggered)
        self.assertEqual(result.error, "")
        assert result.value is not None
        self.assertEqual(result.value.date_arg, "2026-03-03")
        self.assertEqual(result.value.sheet_names, ["S18-A线", "S006-B线"])

    def test_parse_report_mixed_token(self) -> None:
        result = parse_report_command("日报 2026-03-03,S18-A线", {"日报"})
        self.assertTrue(result.triggered)
        self.assertEqual(result.error, "")
        assert result.value is not None
        self.assertEqual(result.value.date_arg, "2026-03-03")
        self.assertEqual(result.value.sheet_names, ["S18-A线"])

    def test_parse_report_duplicate_date_should_fail(self) -> None:
        result = parse_report_command("日报 2026-03-03 2026-03-04", {"日报"})
        self.assertTrue(result.triggered)
        self.assertIn("日期参数重复", result.error)

    def test_non_report_command_should_not_trigger(self) -> None:
        result = parse_report_command("hello", {"日报"})
        self.assertFalse(result.triggered)

    def test_parse_touch_material_basic(self) -> None:
        result = parse_touch_material_command("摸料 A2", {"摸料"})
        self.assertTrue(result.triggered)
        self.assertEqual(result.error, "")
        assert result.value is not None
        self.assertEqual(result.value.segment, "A2")

    def test_parse_touch_material_with_punctuation(self) -> None:
        result = parse_touch_material_command("摸料，A2", {"摸料"})
        self.assertTrue(result.triggered)
        self.assertEqual(result.error, "")
        assert result.value is not None
        self.assertEqual(result.value.segment, "A2")

    def test_parse_touch_material_without_segment(self) -> None:
        result = parse_touch_material_command("摸料", {"摸料"})
        self.assertTrue(result.triggered)
        self.assertIn("摸料参数无效", result.error)

    def test_parse_touch_material_invalid_segment(self) -> None:
        result = parse_touch_material_command("摸料 A3", {"摸料"})
        self.assertTrue(result.triggered)
        self.assertIn("摸料参数无效", result.error)


if __name__ == "__main__":
    unittest.main()
