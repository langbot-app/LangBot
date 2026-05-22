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

    @staticmethod
    def _sample_matrix_for_date(base_date: dt.date) -> list[list[object]]:
        prev_date = base_date - dt.timedelta(days=1)
        return [
            ["", "批次", "投料日期", "烧结压实", "粉碎压实", "成品压实", "扣电", "扣电", "扣电", "Li+含量", "碳含量", "粉末电阻", "麦克比表", "3.2V平台效率"],
            ["", "", "", "", "", "", "0.1C充", "0.1C放", "0.1C首效", "", "", "", "", ""],
            ["", "", "", "", "", "", ">=155", ">=150", ">=96", "", "", "", "", ""],
            [base_date.strftime("%Y-%m-%d"), "DA2603-001", base_date.strftime("%Y-%m-%d"), 2.31, 2.37, 2.40, 160.0, 156.0, 97.5, 0.03, 1.20, 80.0, 10.5, 82.0],
            [prev_date.strftime("%Y-%m-%d"), "DA2603-000", prev_date.strftime("%Y-%m-%d"), 2.30, 2.35, 2.39, 159.0, 155.0, 97.1, 0.035, 1.25, 82.0, 10.3, 81.5],
        ]

    def test_load_sheet_table_from_matrix(self) -> None:
        df = day_metrics.load_sheet_table_from_matrix(self._sample_matrix())
        self.assertIn("投料日期", df.columns)
        self.assertIn("批次", df.columns)
        self.assertTrue(len(df) >= 2)

    def test_build_standard_report_defaults_to_concise_summary(self) -> None:
        out = day_metrics.build_standard_report_from_matrices(
            sheet_matrices={"S18-A线": self._sample_matrix()},
            selected_sheets=["S18-A线"],
            date_arg="2026-03-03",
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
        self.assertTrue(text.startswith("2026.03.04 制程及成品日报"))
        self.assertIn("1、总体结论", text)
        self.assertIn("2、异常项", text)
        self.assertIn("3、关键指标", text)
        self.assertIn("4、数据质量", text)
        self.assertNotIn("原料bom", text)
        self.assertNotIn("制程趋势", text)
        self.assertNotIn("成品趋势", text)
        self.assertNotIn("工艺验证", text)

    def test_build_standard_report_detailed_keeps_original_detail_text(self) -> None:
        out = day_metrics.build_standard_report_from_matrices(
            sheet_matrices={"S18-A线": self._sample_matrix()},
            selected_sheets=["S18-A线"],
            date_arg="2026-03-03",
            date_mode="global",
            lookback_days=7,
            trend_days=3,
            stale_threshold_process=2,
            stale_threshold_product=3,
            stale_threshold_electrochem=5,
            report_show_placeholder_sections=False,
            spec_registry_json="",
            report_output_style="detailed",
        )
        text = out["text"]
        self.assertTrue(text.startswith("2026.03.04数据表更新"))
        self.assertIn("1、制程", text)
        self.assertIn("2、成品", text)
        self.assertNotIn("3、制程", text)
        self.assertNotIn("原料bom", text)
        self.assertNotIn("工艺验证", text)

    def test_build_standard_report_hybrid_appends_engineering_detail(self) -> None:
        out = day_metrics.build_standard_report_from_matrices(
            sheet_matrices={"S18-A线": self._sample_matrix()},
            selected_sheets=["S18-A线"],
            date_arg="2026-03-03",
            date_mode="global",
            lookback_days=7,
            trend_days=3,
            stale_threshold_process=2,
            stale_threshold_product=3,
            stale_threshold_electrochem=5,
            report_show_placeholder_sections=False,
            spec_registry_json="",
            report_output_style="hybrid",
        )
        text = out["text"]
        self.assertTrue(text.startswith("2026.03.04 制程及成品日报"))
        self.assertIn("【工程版】", text)
        self.assertIn("2026.03.04数据表更新", text)

    def test_build_standard_report_concise_supports_multiple_lines(self) -> None:
        out = day_metrics.build_standard_report_from_matrices(
            sheet_matrices={"S18-A线": self._sample_matrix(), "S20-C线": self._sample_matrix()},
            selected_sheets=["S18-A线", "S20-C线"],
            date_arg="2026-03-03",
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
        self.assertIn("S18-A线 烧结压实", text)
        self.assertIn("S20-C线 烧结压实", text)
        self.assertNotIn("成品趋势", text)

    def test_build_standard_report_concise_summarizes_abnormal_items(self) -> None:
        out = day_metrics.build_standard_report_from_matrices(
            sheet_matrices={"S18-A线": self._sample_matrix()},
            selected_sheets=["S18-A线"],
            date_arg="2026-03-03",
            date_mode="global",
            lookback_days=7,
            trend_days=3,
            stale_threshold_process=2,
            stale_threshold_product=3,
            stale_threshold_electrochem=5,
            report_show_placeholder_sections=False,
            spec_registry_json='{"rules":[{"model":"S18","metric":"成品压实","spec":">=2.50"}]}',
        )
        text = out["text"]
        self.assertIn("需关注", text)
        self.assertIn("成品压实", text)
        self.assertIn("投料批次", text)

    def test_fmt_status_can_hide_governance_attention(self) -> None:
        stat = {
            "状态": day_metrics.STAT_HAS_DATA,
            "有数据": True,
            "判异": {"异常": False},
            "spec_health": {
                "suspected": True,
                "abnormal_days": 6,
                "total_days": 14,
                "longest_consecutive_abnormal": 6,
            },
        }

        shown = day_metrics._fmt_status(stat, force=True, show_spec_attention=True)
        hidden = day_metrics._fmt_status(stat, force=True, show_spec_attention=False)

        self.assertIn("治理关注", shown)
        self.assertNotIn("治理关注", hidden)
        self.assertIn("正常", hidden)

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

    def test_fmt_range_should_show_data_not_ready_when_no_data(self) -> None:
        stat = {"状态": day_metrics.STAT_NO_DATA, "有数据": False}
        self.assertEqual(day_metrics._fmt_range(stat, 3), "数据未出")
        self.assertEqual(day_metrics._with_unit("数据未出", "ppm"), "数据未出")

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

    def test_build_report_supports_metric_aliases_by_product(self) -> None:
        matrix = self._sample_matrix()
        matrix[0][3] = "熟化压实"

        out = day_metrics.build_standard_report_from_matrices(
            sheet_matrices={"S18-A线": matrix},
            selected_sheets=["S18-A线"],
            date_arg="2026-03-03",
            date_mode="global",
            lookback_days=7,
            trend_days=3,
            stale_threshold_process=2,
            stale_threshold_product=3,
            stale_threshold_electrochem=5,
            report_show_placeholder_sections=False,
            spec_registry_json="",
            metric_aliases_json='{"products":{"S18":{"烧结压实":["熟化压实"]}}}',
        )

        process_metrics = out["line_reports"][0]["metrics"]["制程"]
        self.assertAlmostEqual(process_metrics["烧结压实"]["min"], 2.31, places=3)

    def test_build_report_supports_bitable_product_metric_fields(self) -> None:
        matrix = [
            [
                "",
                "批次",
                "投料日期",
                "成品压实",
                "残碱(Li+)",
                "碳含量",
                "粉阻(粉末电阻)",
                "比表(麦克比表)",
                "pH",
                "Li含量",
                "Fe含量",
                "P含量",
                "Na+K含量",
                "杂质含量",
                "铁溶出",
            ],
            ["", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
            ["", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
            [
                "2026-05-20",
                "S18-CP-DA2605-103-A2-1",
                "2026-05-20",
                2.384,
                316,
                1.22,
                34.5,
                10.8,
                9.26,
                4.45,
                34.64,
                19.63,
                0.012630,
                0.001423,
                13.921,
            ],
            [
                "2026-05-20",
                "S18-CP-DA2605-103-A2-2",
                "2026-05-20",
                2.380,
                304,
                1.20,
                35.1,
                10.6,
                9.32,
                4.43,
                34.60,
                19.60,
                0.012909,
                0.001452,
                14.572,
            ],
        ]

        out = day_metrics.build_standard_report_from_matrices(
            sheet_matrices={"S18-A线": matrix},
            selected_sheets=["S18-A线"],
            date_arg="2026-05-20",
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
        self.assertAlmostEqual(product_metrics["残碱(Li+)"]["min"], 304.0, places=3)
        self.assertAlmostEqual(product_metrics["残碱(Li+)"]["max"], 316.0, places=3)
        self.assertAlmostEqual(product_metrics["粉阻(粉末电阻)"]["max"], 35.1, places=3)
        self.assertAlmostEqual(product_metrics["比表(麦克比表)"]["max"], 10.8, places=3)
        self.assertAlmostEqual(product_metrics["pH"]["max"], 9.32, places=3)
        self.assertAlmostEqual(product_metrics["Li含量"]["min"], 4.43, places=3)
        self.assertAlmostEqual(product_metrics["Fe含量"]["max"], 34.64, places=3)
        self.assertAlmostEqual(product_metrics["P含量"]["min"], 19.60, places=3)
        self.assertAlmostEqual(product_metrics["Na+K含量"]["max"], 0.012909, places=6)
        self.assertAlmostEqual(product_metrics["杂质含量"]["max"], 0.001452, places=6)
        self.assertAlmostEqual(product_metrics["铁溶出"]["max"], 14.572, places=3)
        self.assertNotIn("3160000", out["text"])

    def test_build_report_uses_spec_limits_from_config(self) -> None:
        out = day_metrics.build_standard_report_from_matrices(
            sheet_matrices={"S18-A线": self._sample_matrix()},
            selected_sheets=["S18-A线"],
            date_arg="2026-03-03",
            date_mode="global",
            lookback_days=7,
            trend_days=3,
            stale_threshold_process=2,
            stale_threshold_product=3,
            stale_threshold_electrochem=5,
            report_show_placeholder_sections=False,
            spec_registry_json='{"rules":[{"model":"S18","metric":"成品压实","spec":">=2.50"}]}',
        )

        product_metrics = out["line_reports"][0]["metrics"]["成品"]
        self.assertTrue(product_metrics["成品压实"]["判异"]["异常"])

    def test_build_report_should_skip_sheet_if_feed_date_stale_for_six_days(self) -> None:
        today = dt.date.today()
        recent_matrix = self._sample_matrix_for_date(today)
        stale_matrix = self._sample_matrix_for_date(today - dt.timedelta(days=6))

        out = day_metrics.build_standard_report_from_matrices(
            sheet_matrices={"S18-A线": recent_matrix, "S006-B线": stale_matrix},
            selected_sheets=["S18-A线", "S006-B线"],
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

        self.assertEqual(out["used_sheets"], ["S18-A线"])
        self.assertEqual(len(out["line_reports"]), 1)
        self.assertEqual(out["line_reports"][0]["line_label"], "S18-A线")
        self.assertTrue(any("S006-B线" in str(item) and "未纳入日报" in str(item) for item in out["line_errors"]))

    def test_build_report_should_return_empty_text_when_all_sheets_stale(self) -> None:
        stale_date = dt.date.today() - dt.timedelta(days=6)
        stale_matrix = self._sample_matrix_for_date(stale_date)

        out = day_metrics.build_standard_report_from_matrices(
            sheet_matrices={"S18-A线": stale_matrix},
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

        self.assertEqual(out["used_sheets"], [])
        self.assertEqual(out["line_reports"], [])
        self.assertIn("当前无6天内更新的数据表", out["text"])
        self.assertTrue(any("S18-A线" in str(item) and "未纳入日报" in str(item) for item in out["line_errors"]))


if __name__ == "__main__":
    unittest.main()
