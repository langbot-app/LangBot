from __future__ import annotations

import datetime as dt
import unittest

from components.report_core import day_metrics


class DayMetricsWrapperTest(unittest.TestCase):
    @staticmethod
    def _sample_matrix() -> list[list[object]]:
        return [
            ["", "批次", "投料日期", "烧结压实", "粉碎压实", "成品压实", "扣电", "扣电", "扣电", "Li+含量", "碳含量", "粉末电阻", "麦克比表", "3.2V平台效率"],
            ["", "", "", "", "", "", "0.1C充", "0.1C放", "0.1C首效", "", "", "", "", ""],
            ["", "", "", "", "", "", ">=155", ">=150", ">=96", "", "", "", "", ""],
            ["2026-03-03", "DA2603-001", "2026-03-03", 2.31, 2.37, 2.40, 160.0, 156.0, 97.5, 0.03, 1.20, 80.0, 10.5, 82.0],
            ["2026-03-02", "DA2603-000", "2026-03-02", 2.30, 2.35, 2.39, 159.0, 155.0, 97.1, 0.035, 1.25, 82.0, 10.3, 81.5],
        ]

    def test_load_sheet_table_from_matrix(self) -> None:
        df = day_metrics.load_sheet_table_from_matrix(self._sample_matrix())
        self.assertIn("投料日期", df.columns)
        self.assertIn("批次", df.columns)
        self.assertTrue(len(df) >= 2)

    def test_build_standard_report_and_strip_placeholder(self) -> None:
        out = day_metrics.build_standard_report_from_matrices(
            sheet_matrices={"S18-A线": self._sample_matrix()},
            selected_sheets=["S18-A线"],
            date_arg=None,
            date_mode="global",
            lookback_days=7,
            trend_days=3,
            stale_threshold_process=2,
            stale_threshold_product=3,
            stale_threshold_electrochem=5,
            report_show_placeholder_sections=False,
            spec_registry_json="",
        )
        text = out["text"]
        self.assertIn("制程", text)
        self.assertNotIn("原料bom", text)
        self.assertNotIn("工艺验证", text)

    def test_sheet_excel_serial_date_should_not_be_1970(self) -> None:
        matrix = self._sample_matrix()
        matrix[3][0] = 45292
        matrix[3][2] = 45292
        matrix[4][0] = 45291
        matrix[4][2] = 45291
        df = day_metrics.load_sheet_table_from_matrix(matrix)
        first_date = df["投料日期"].iloc[0]
        self.assertIsInstance(first_date, dt.date)
        self.assertGreaterEqual(first_date.year, 2020)
        self.assertNotEqual(first_date.year, 1970)

    def test_sheet_unix_ms_date_should_parse_correctly(self) -> None:
        matrix = self._sample_matrix()
        matrix[3][0] = 1735689600000
        matrix[3][2] = 1735689600000
        df = day_metrics.load_sheet_table_from_matrix(matrix)
        self.assertEqual(df["投料日期"].iloc[0], dt.date(2025, 1, 1))

    def test_parse_num_should_ignore_formula_text(self) -> None:
        formula = "VLOOKUP($C:$C,'S18-A线成品数据源'!$C:$CW,23,FALSE)"
        self.assertIsNone(day_metrics._parse_num(formula))
        self.assertIsNone(day_metrics._parse_num(f"={formula}"))
        self.assertEqual(day_metrics._parse_num("2.384"), 2.384)

    def test_build_report_should_ignore_formula_text_cells(self) -> None:
        matrix = [
            ["", "批次", "投料日期", "烧结压实", "粉碎压实", "成品压实", "扣电", "扣电", "扣电", "Li+含量", "碳含量", "粉末电阻", "麦克比表", "3.2V平台效率"],
            ["", "", "", "", "", "", "0.1C充", "0.1C放", "0.1C首效", "", "", "", "", ""],
            ["", "", "", "", "", "", ">=155", ">=150", ">=96", "", "", "", "", ""],
            [
                "2026-03-05",
                "DA2603-022",
                "2026-03-05",
                2.33,
                2.35,
                "VLOOKUP($C:$C,'S18-A线成品数据源'!$C:$CW,23,FALSE)",
                161.74,
                156.99,
                97.07,
                "VLOOKUP($C:$C,'S18-A线成品数据源'!$C:$CW,10,FALSE)",
                "VLOOKUP($C:$C,'S18-A线成品数据源'!$C:$CW,21,FALSE)",
                "VLOOKUP($C:$C,'S18-A线成品数据源'!$C:$CW,25,FALSE)",
                "VLOOKUP($C:$C,'S18-A线成品数据源'!$C:$CW,7,FALSE)",
                87.72,
            ],
            ["2026-03-05", "DA2603-025", "2026-03-05", 2.34, 2.38, 2.384, 161.70, 156.85, 97.00, 0.0304, 1.361, 14.1, 10.3589, 85.7],
            ["2026-03-05", "DA2603-026", "2026-03-05", 2.33, 2.37, 2.380, 161.20, 156.17, 96.88, 0.0316, 1.359, 14.9, 10.3456, 86.3],
        ]

        out = day_metrics.build_standard_report_from_matrices(
            sheet_matrices={"S18-A线": matrix},
            selected_sheets=["S18-A线"],
            date_arg="2026-03-05",
            date_mode="global",
            lookback_days=7,
            trend_days=3,
            stale_threshold_process=2,
            stale_threshold_product=3,
            stale_threshold_electrochem=5,
            report_show_placeholder_sections=False,
            spec_registry_json="",
        )

        product_metrics = out["line_reports"][0]["metrics"]["成品"]
        self.assertAlmostEqual(product_metrics["成品压实"]["min"], 2.38, places=3)
        self.assertAlmostEqual(product_metrics["成品压实"]["max"], 2.384, places=3)
        self.assertAlmostEqual(product_metrics["残碱(Li+)"]["min"], 304.0, places=3)
        self.assertAlmostEqual(product_metrics["残碱(Li+)"]["max"], 316.0, places=3)
        self.assertAlmostEqual(product_metrics["碳含量"]["max"], 1.361, places=3)
        self.assertAlmostEqual(product_metrics["粉阻(粉末电阻)"]["max"], 14.9, places=3)
        self.assertAlmostEqual(product_metrics["比表(麦克比表)"]["max"], 10.3589, places=4)
        self.assertNotIn("18.000", out["text"])
        self.assertNotIn("180000", out["text"])


if __name__ == "__main__":
    unittest.main()
