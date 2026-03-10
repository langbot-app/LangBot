from __future__ import annotations

import unittest

from components.data_sources import FeishuBitableSource, FeishuSheetsSource


class SheetsSourceTest(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_line_matrices(self) -> None:
        async def fake_api(method, endpoint, headers, payload=None, params=None):
            if endpoint.endswith("/sheets/query"):
                return {"sheets": [{"title": "S18-A线", "sheet_id": "sheetA"}]}
            if "/values/" in endpoint:
                self.assertIn("sheetA%21A1%3AZZ2000", endpoint)
                self.assertIn("valueRenderOption=UnformattedValue", endpoint)
                return {
                    "valueRange": {
                        "values": [
                            ["", "批次", "投料日期"],
                            ["2026-03-03", "DA2603-001", "2026-03-03"],
                        ]
                    }
                }
            raise AssertionError(f"Unexpected endpoint: {endpoint}")

        source = FeishuSheetsSource(fake_api)
        matrices, available, missing = await source.fetch_line_matrices(
            spreadsheet_token="sp_token",
            headers={"Authorization": "Bearer test"},
            target_sheet_names=["S18-A线", "S006-B线"],
            cell_range="A1:ZZ2000",
        )
        self.assertEqual(available, ["S18-A线"])
        self.assertEqual(missing, ["S006-B线"])
        self.assertIn("S18-A线", matrices)

    async def test_get_sheet_values_supports_custom_render_option(self) -> None:
        async def fake_api(method, endpoint, headers, payload=None, params=None):
            self.assertIn("valueRenderOption=FormattedValue", endpoint)
            return {"valueRange": {"values": [["表头"], ["值"]]}}

        source = FeishuSheetsSource(fake_api)
        values = await source.get_sheet_values(
            spreadsheet_token="sp_token",
            sheet_id="sheetA",
            cell_range="A1:A2",
            headers={"Authorization": "Bearer test"},
            value_render_option="FormattedValue",
        )
        self.assertEqual(values, [["表头"], ["值"]])

    async def test_query_recipe_by_batch_alias_match(self) -> None:
        async def fake_api(method, endpoint, headers, payload=None, params=None):
            if endpoint.endswith("/sheets/query"):
                return {
                    "sheets": [
                        {"title": "S18-A线", "sheet_id": "sheetA"},
                        {"title": "S18-B线", "sheet_id": "sheetB"},
                    ]
                }
            if "sheetA%21A1%3AZZ2000" in endpoint:
                return {
                    "valueRange": {
                        "values": [
                            ["批次号", "铁磷比", "锂量", "酸量", "钛量", "糖量", "PEG添加", "窑温"],
                            ["DA2603-004", "97.2", "250", "3.0", "39", "82", "79", "777.0"],
                            ["DA2603-005", "97.4", "253.125", "3.2", "40", "83", "80", "778.5"],
                        ]
                    }
                }
            if "sheetB%21A1%3AZZ2000" in endpoint:
                return {"valueRange": {"values": [["批次号"], ["DB2603-001"]]}}
            raise AssertionError(f"Unexpected endpoint: {endpoint}")

        source = FeishuSheetsSource(fake_api)
        data = await source.query_recipe_by_batch(
            spreadsheet_token="sp_token",
            headers={"Authorization": "Bearer test"},
            target_sheet_names=["S18-A线", "S18-B线"],
            cell_range="A1:ZZ2000",
            batch_core="DA2603-005",
            prefer_line="A",
            field_aliases={
                "批次号": ["批次号"],
                "铁磷比": ["铁磷比"],
                "锂量": ["锂量"],
                "酸量": ["酸量"],
                "钛量": ["钛量"],
                "糖量": ["糖量"],
                "peg量": ["peg量", "PEG添加"],
                "窑炉温度": ["窑炉温度", "窑温"],
            },
            placeholder="--",
        )
        self.assertEqual(data["铁磷比"], "97.4")
        self.assertEqual(data["peg量"], "80")
        self.assertEqual(data["窑炉温度"], "778.5")

    async def test_query_recipe_by_batch_with_multirow_header(self) -> None:
        async def fake_api(method, endpoint, headers, payload=None, params=None):
            if endpoint.endswith("/sheets/query"):
                return {
                    "sheets": [
                        {"title": "S18-A线", "sheet_id": "sheetA"},
                        {"title": "S006-B线", "sheet_id": "sheetB"},
                    ]
                }
            if "sheetA%21A1%3AZZ2000" in endpoint:
                return {
                    "valueRange": {
                        "values": [
                            ["是否为验证批次", "投料日期", "批次", "原料D5", "", "", "", "", "", "", "原料BL", "", "", "", "", "", "LiH2PO4", "", "", "TiO2", "BF", "ZT", "CI", "批次铁的重量", "窑炉线别", "窑炉温度"],
                            ["", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "百分含量", "Li2CO3", "H3PO4", "H3PO4", "H3PO4", "H3PO4", "H3PO4", "H3PO4", "H3PO4", "H3PO4"],
                            ["", "", "", "", "", "Fe/p(5滴)", "", "", "", "", "", "", "锂量kg/t", "", "", "", "%", "kg/t", "kg/t", "kg/t", "kg/t", "kg/t", "kg/t", "t", "B1/B2", "℃"],
                            ["是", "2026-01-01", "DA2601-005", "", "", "97.4", "", "", "", "", "", "", "253.125", "", "", "", "0.012", "2.7", "8.405", "3.2", "", "40", "83", "16", "A2", "778.5"],
                        ]
                    }
                }
            if "sheetB%21A1%3AZZ2000" in endpoint:
                return {
                    "valueRange": {
                        "values": [
                            ["投料日期", "批次", "原料D5", "", "", "", "", "", "", "", "", "", "原料BL", "", "", "", "", "H3BO3", "TiO2", "BF", "CD", "CI", "批次铁的重量", "窑炉线别", "窑炉温度"],
                            ["", "", "", "", "Fe/p(5滴)", "", "", "", "", "", "", "", "", "锂量kg/t", "", "", "", "kg/t", "kg/t", "kg/t", "kg/t", "kg/t", "t", "B1/B2", "℃"],
                            ["2026-02-03", "DB2602-013", "", "", "96.1", "", "", "", "", "", "", "", "", "251.3", "", "", "", "1.088", "2.915", "87.38", "2.66", "19.067", "12", "B1", "813"],
                        ]
                    }
                }
            raise AssertionError(f"Unexpected endpoint: {endpoint}")

        source = FeishuSheetsSource(fake_api)

        data_a = await source.query_recipe_by_batch(
            spreadsheet_token="sp_token",
            headers={"Authorization": "Bearer test"},
            target_sheet_names=["S18-A线", "S006-B线"],
            cell_range="A1:ZZ2000",
            batch_core="DA2601-005",
            prefer_line="A",
            prefer_model="S18",
            field_aliases={
                "批次号": ["批次号", "批次"],
                "铁磷比": ["铁磷比", "Fe/p"],
                "锂量": ["锂量", "锂量kg/t"],
                "酸量": ["酸量", "百分含量", "H3PO4", "H3BO3"],
                "钛量": ["钛量", "TiO2"],
                "糖量": ["糖量", "ZT", "BF"],
                "peg量": ["peg量", "CI", "CD"],
                "窑炉温度": ["窑炉温度", "窑温", "℃"],
            },
            placeholder="--",
        )
        self.assertEqual(data_a["铁磷比"], "97.4")
        self.assertEqual(data_a["锂量"], "253.125")
        self.assertEqual(data_a["酸量"], "1.2%")
        self.assertEqual(data_a["钛量"], "3.2")
        self.assertEqual(data_a["糖量"], "40")
        self.assertEqual(data_a["peg量"], "83")
        self.assertEqual(data_a["窑炉温度"], "778.5")

        data_b = await source.query_recipe_by_batch(
            spreadsheet_token="sp_token",
            headers={"Authorization": "Bearer test"},
            target_sheet_names=["S18-A线", "S006-B线"],
            cell_range="A1:ZZ2000",
            batch_core="DB2602-013",
            prefer_line="B",
            prefer_model="S006",
            field_aliases={
                "批次号": ["批次号", "批次"],
                "铁磷比": ["铁磷比", "Fe/p"],
                "锂量": ["锂量", "锂量kg/t"],
                "酸量": ["酸量", "百分含量", "H3PO4", "H3BO3"],
                "钛量": ["钛量", "TiO2"],
                "糖量": ["糖量", "ZT", "BF"],
                "peg量": ["peg量", "CI", "CD"],
                "窑炉温度": ["窑炉温度", "窑温", "℃"],
            },
            placeholder="--",
        )
        self.assertEqual(data_b["铁磷比"], "96.1")
        self.assertEqual(data_b["锂量"], "251.3")
        self.assertEqual(data_b["酸量"], "1.088")
        self.assertEqual(data_b["钛量"], "2.915")
        self.assertEqual(data_b["糖量"], "87.38")
        self.assertEqual(data_b["peg量"], "19.067")
        self.assertEqual(data_b["窑炉温度"], "813")

    async def test_query_recipe_by_batch_missing_fields(self) -> None:
        async def fake_api(method, endpoint, headers, payload=None, params=None):
            if endpoint.endswith("/sheets/query"):
                return {"sheets": [{"title": "S18-A线", "sheet_id": "sheetA"}]}
            if "sheetA%21A1%3AZZ2000" in endpoint:
                return {
                    "valueRange": {
                        "values": [
                            ["批次号", "铁磷比"],
                            ["DA2603-005", "97.4"],
                        ]
                    }
                }
            raise AssertionError(f"Unexpected endpoint: {endpoint}")

        source = FeishuSheetsSource(fake_api)
        data = await source.query_recipe_by_batch(
            spreadsheet_token="sp_token",
            headers={"Authorization": "Bearer test"},
            target_sheet_names=["S18-A线"],
            cell_range="A1:ZZ2000",
            batch_core="DA2603-005",
            prefer_line="A",
            field_aliases={"批次号": ["批次号"], "铁磷比": ["铁磷比"]},
            placeholder="--",
        )
        self.assertEqual(data["铁磷比"], "97.4")
        self.assertEqual(data["锂量"], "--")
        self.assertEqual(data["窑炉温度"], "--")


class BitableSourceTest(unittest.IsolatedAsyncioTestCase):
    async def test_query_latest_brief(self) -> None:
        async def fake_api(method, endpoint, headers, payload=None, params=None):
            if endpoint.endswith("/tables"):
                return {
                    "items": [
                        {"name": "A线烧结汇总", "table_id": "tblA"},
                        {"name": "B线烧结汇总", "table_id": "tblB"},
                    ],
                    "has_more": False,
                }
            if endpoint.endswith("/tables/tblA/records"):
                return {
                    "items": [
                        {
                            "fields": {
                                "路由": "line.a.sintering",
                                "批次号": "S18-SC-DA2603-005",
                                "消息时间": "2026-03-03T10:55:14+08:00",
                                "A1-均值": 2.364,
                            }
                        }
                    ],
                    "has_more": False,
                }
            if endpoint.endswith("/tables/tblB/records"):
                return {
                    "items": [
                        {
                            "fields": {
                                "路由": "line.b.sintering",
                                "批次号": "S006-SC-DB2602-130",
                                "消息时间": "2026-03-03T10:48:22+08:00",
                                "B1-均值": 2.491,
                            }
                        }
                    ],
                    "has_more": False,
                }
            raise AssertionError(f"Unexpected endpoint: {endpoint}")

        source = FeishuBitableSource(fake_api)
        text = await source.query_latest_brief(
            app_token="app_token",
            headers={"Authorization": "Bearer test"},
            table_ids_raw="",
            table_names_raw="A线烧结汇总,B线烧结汇总",
            route_field="路由",
            batch_field="批次号",
            message_time_field="消息时间",
            scan_limit=1000,
            detail_max_fields=4,
            no_data_text="无数据",
            title_text="当前出窑批次及烧结压实：",
        )
        self.assertIn("A线：S18-SC-DA2603-005", text)
        self.assertIn("B线：S006-SC-DB2602-130", text)

    async def test_query_latest_kiln_batch_by_segment_segment_mode(self) -> None:
        async def fake_api(method, endpoint, headers, payload=None, params=None):
            if endpoint.endswith("/tables"):
                return {"items": [{"name": "窑炉批次进窑出窑表", "table_id": "tblKiln"}], "has_more": False}
            if endpoint.endswith("/tables/tblKiln/records"):
                return {
                    "items": [
                        {
                            "fields": {
                                "批次号": "DA2603-021",
                                "窑炉段": "A2",
                                "1号出窑开始时间": "2026-03-07 06:23:00",
                                "2号出窑开始时间": "2026-03-07 06:24:00",
                                "3号出窑开始时间": "2026-03-07 06:25:00",
                            }
                        },
                        {
                            "fields": {
                                "批次号": "DA2603-023",
                                "窑炉段": "A2",
                                "1号出窑开始时间": "2026-03-07 06:30:00",
                                "2号出窑开始时间": "2026-03-07 06:31:00",
                                "3号出窑开始时间": "2026-03-07 06:32:00",
                            }
                        },
                    ],
                    "has_more": False,
                }
            raise AssertionError(f"Unexpected endpoint: {endpoint}")

        source = FeishuBitableSource(fake_api)
        item = await source.query_latest_kiln_batch_by_segment(
            app_token="app_token",
            headers={"Authorization": "Bearer test"},
            segment="A2",
            table_ids_raw="",
            table_names_raw="窑炉批次进窑出窑表",
            batch_field="批次号",
            scan_limit=1000,
        )
        assert item is not None
        self.assertEqual(item["batch_core"], "DA2603-023")
        self.assertEqual(item["slots"], ["1", "2", "3"])

    async def test_query_latest_kiln_batch_by_segment_slot_mode(self) -> None:
        async def fake_api(method, endpoint, headers, payload=None, params=None):
            if endpoint.endswith("/tables"):
                return {"items": [{"name": "窑炉批次进窑出窑表", "table_id": "tblKiln"}], "has_more": False}
            if endpoint.endswith("/tables/tblKiln/records"):
                return {
                    "items": [
                        {"fields": {"批次号": "DB2603-013", "窑炉段": "B1", "窑位": "1", "出窑开始时间": "2026-03-07 19:50:00"}},
                        {"fields": {"批次号": "DB2603-013", "窑炉段": "B1", "窑位": "2", "出窑开始时间": "2026-03-07 19:51:00"}},
                        {"fields": {"批次号": "DB2603-014", "窑炉段": "B1", "窑位": "1", "出窑开始时间": "2026-03-07 19:56:00"}},
                        {"fields": {"批次号": "DB2603-014", "窑炉段": "B1", "窑位": "2", "出窑开始时间": "2026-03-07 19:57:00"}},
                        {"fields": {"批次号": "DB2603-014", "窑炉段": "B1", "窑位": "3", "出窑开始时间": "2026-03-07 19:58:00"}},
                    ],
                    "has_more": False,
                }
            raise AssertionError(f"Unexpected endpoint: {endpoint}")

        source = FeishuBitableSource(fake_api)
        item = await source.query_latest_kiln_batch_by_segment(
            app_token="app_token",
            headers={"Authorization": "Bearer test"},
            segment="B1",
            table_ids_raw="",
            table_names_raw="窑炉批次进窑出窑表",
            batch_field="批次号",
            scan_limit=1000,
        )
        assert item is not None
        self.assertEqual(item["batch_core"], "DB2603-014")
        self.assertEqual(item["slots"], ["1", "2", "3"])

    async def test_query_sintering_detail_by_batch_segment(self) -> None:
        async def fake_api(method, endpoint, headers, payload=None, params=None):
            if endpoint.endswith("/tables"):
                return {"items": [{"name": "A线烧结汇总", "table_id": "tblA"}], "has_more": False}
            if endpoint.endswith("/tables/tblA/records"):
                return {
                    "items": [
                        {
                            "fields": {
                                "路由": "line.a.sintering",
                                "批次号": "S18-SC-DA2603-005",
                                "消息时间": "2026-03-07T08:10:00+08:00",
                                "A2-1": 2.300,
                            }
                        },
                        {
                            "fields": {
                                "路由": "line.a.sintering",
                                "批次号": "S18-SC-DA2603-005",
                                "消息时间": "2026-03-07T08:20:00+08:00",
                                "S18-SC-DA2603-005-A2-1-60min": 2.345,
                                "S18-SC-DA2603-005-A2-2-60min": 2.337,
                                "S18-SC-DA2603-005-A2-3-60min": 2.311,
                            }
                        },
                    ],
                    "has_more": False,
                }
            raise AssertionError(f"Unexpected endpoint: {endpoint}")

        source = FeishuBitableSource(fake_api)
        out = await source.query_sintering_detail_by_batch_segment(
            app_token="app_token",
            headers={"Authorization": "Bearer test"},
            batch_core="DA2603-005",
            segment="A2",
            table_ids_raw="",
            table_names_raw="A线烧结汇总",
            route_field="路由",
            batch_field="批次号",
            message_time_field="消息时间",
            scan_limit=1000,
        )
        self.assertEqual(len(out["details"]), 3)
        self.assertTrue(out["details"][0].startswith("S18-SC-DA2603-005-A2-1-60min"))
        self.assertAlmostEqual(float(out["avg"]), 2.331, places=3)


if __name__ == "__main__":
    unittest.main()
