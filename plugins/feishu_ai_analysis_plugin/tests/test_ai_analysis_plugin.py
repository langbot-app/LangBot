from __future__ import annotations

import unittest

from components.analysis_service import AnalysisService
from components.batch import normalize_batch
from components.command_parser import parse_analysis_command
from components.data_sources import FeishuBaseSource, FeishuSheetSource
from components.diagnosis import diagnose_process


class CommandParserTest(unittest.TestCase):
    def test_parse_abnormal_command(self) -> None:
        result = parse_analysis_command("异常分析 S18-DA2603-005 压实偏低")
        self.assertTrue(result.triggered)
        assert result.value is not None
        self.assertEqual(result.value.kind, "abnormal")
        self.assertEqual(result.value.batch, "S18-DA2603-005")
        self.assertEqual(result.value.abnormal, "压实偏低")

    def test_parse_product_command_with_date(self) -> None:
        result = parse_analysis_command("成品分析 2026-05-19 S18-A线")
        self.assertTrue(result.triggered)
        assert result.value is not None
        self.assertEqual(result.value.kind, "product")
        self.assertEqual(result.value.date_arg, "2026-05-19")
        self.assertEqual(result.value.target, "S18-A线")

    def test_parse_batch_requires_batch(self) -> None:
        result = parse_analysis_command("批次分析")
        self.assertTrue(result.triggered)
        self.assertIn("批次号", result.error)


class BatchTest(unittest.TestCase):
    def test_normalize_batch_variants(self) -> None:
        self.assertEqual(normalize_batch("S18-SC-DA2603-005").core, "DA2603-005")
        self.assertEqual(normalize_batch("S18-FS-DA2603-005-A1").stage, "FS")
        self.assertEqual(normalize_batch("DB2603-008").line, "B")
        self.assertEqual(normalize_batch("S18-DA2603-007-A1").segment, "A1")


class DiagnosisTest(unittest.TestCase):
    def test_diagnose_low_compaction_and_missing_data(self) -> None:
        wide = {
            "identity": {"core": "DA2603-005"},
            "stages": {
                "sintering": {"A1-均值": "2.320", "A2-均值": "2.380"},
                "spray": {"进口温度": "242.7"},
                "crushing": {"批次号": "S18-FS-DA2603-005"},
            },
            "missing_data": [],
        }
        hits = diagnose_process(wide, "压实偏低")
        titles = [hit.title for hit in hits]
        self.assertIn("烧结压实偏低", titles)
        self.assertIn("烧结段位差异偏大", titles)
        self.assertIn("喷雾水分未记录", titles)
        self.assertIn("粉碎压实未出", titles)


class SheetSourceTest(unittest.TestCase):
    def test_matrix_to_rows_multirow_header(self) -> None:
        values = [
            ["", "", "原料D5", ""],
            ["投料日期", "批次", "Fe/p", "锂量kg/t"],
            ["2026.03.01", "DA2603-005", "97.4", "253.1"],
        ]
        rows = FeishuSheetSource.matrix_to_rows(values)
        self.assertEqual(len(rows), 1)
        self.assertTrue(any("批次" in key for key in rows[0]))
        self.assertIn("97.4", [str(v) for v in rows[0].values()])


class AnalysisServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_build_batch_wide_table(self) -> None:
        async def fake_api(method, endpoint, headers, payload=None, params=None):
            if endpoint.endswith("/tables"):
                return {
                    "items": [
                        {"name": "A线投料汇总", "table_id": "tblFeed"},
                        {"name": "A线烧结汇总", "table_id": "tblSinter"},
                    ],
                    "has_more": False,
                }
            if endpoint.endswith("/tables/tblFeed/records/search"):
                return {
                    "items": [
                        {
                            "fields": {
                                "批次号": "S18-DA2603-005-A1",
                                "消息时间": "2026-03-01 10:00:00",
                                "磷酸铁需补(kg)": "1.2",
                            }
                        }
                    ],
                    "has_more": False,
                }
            if endpoint.endswith("/tables/tblSinter/records/search"):
                return {
                    "items": [
                        {
                            "fields": {
                                "批次号": "S18-SC-DA2603-005",
                                "消息时间": "2026-03-01 12:00:00",
                                "A1-均值": "2.321",
                            }
                        }
                    ],
                    "has_more": False,
                }
            if endpoint.endswith("/sheets/query"):
                return {"sheets": [{"title": "S18-A线成品数据源", "sheet_id": "sheetA"}]}
            if "/values/" in endpoint:
                return {
                    "valueRange": {
                        "values": [
                            ["检测时间", "批次", "压实"],
                            ["2026.03.02", "DA2603-005", "2.37"],
                        ]
                    }
                }
            raise AssertionError(f"Unexpected endpoint: {endpoint}")

        base = FeishuBaseSource(fake_api)
        sheet = FeishuSheetSource(fake_api)
        service = AnalysisService(base_source=base, sheet_source=sheet)
        wide = await service.build_batch_wide_table(
            app_token="app",
            spreadsheet_token="sheet",
            headers={},
            batch_text="S18-DA2603-005",
            process_tables_raw={"feeding": ["A线投料汇总"], "sintering": ["A线烧结汇总"]},
            product_sheet_patterns=["成品数据源"],
            product_range="A1:ZZ2000",
            batch_field="批次号",
            message_time_field="消息时间",
            scan_limit=100,
            max_stage_fields=10,
        )
        self.assertEqual(wide["identity"]["core"], "DA2603-005")
        self.assertIn("feeding", wide["stages"])
        self.assertIn("sintering", wide["stages"])
        self.assertEqual(wide["product"]["sheet"], "S18-A线成品数据源")

    async def test_analyze_batch_fallback_without_llm(self) -> None:
        service = AnalysisService(base_source=FeishuBaseSource(lambda *a, **k: None), sheet_source=FeishuSheetSource(lambda *a, **k: None))
        text = await service.analyze_batch(
            {
                "identity": {"core": "DA2603-005"},
                "stages": {"sintering": {"A1-均值": "2.320"}},
                "missing_data": ["spray 未查询到记录"],
            },
            abnormal="压实偏低",
            mode="abnormal",
        )
        self.assertIn("异常分析", text)
        self.assertIn("规则诊断", text)
        self.assertIn("spray 未查询到记录", text)


if __name__ == "__main__":
    unittest.main()

