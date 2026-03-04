"""Unit tests for feishu_process_bitable_plugin core behaviors."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

from plugins.feishu_process_bitable_plugin.components.event_listeners.auto_process_to_bitable import (
    AutoProcessToBitableListener,
)


def _build_listener(config: dict | None = None) -> AutoProcessToBitableListener:
    listener = AutoProcessToBitableListener()
    plugin = MagicMock()
    plugin.get_config.return_value = config or {}
    listener.plugin = plugin
    return listener


def test_upsert_refreshes_stale_record_cache_then_creates() -> None:
    listener = _build_listener({"upsert_by_batch": True})

    table_id = "tbl_test"
    match_fields = {"批次号": "S006-DA2602-001"}
    cache_key = listener._build_record_lookup_cache_key(table_id, match_fields)
    listener._record_lookup_cache[cache_key] = "rec_stale"

    listener._find_existing_record_id = AsyncMock(side_effect=["rec_stale", ""])
    listener._update_record_to_bitable = AsyncMock(
        return_value=(False, "bitable update failed, msg=RecordIdNotFound")
    )
    listener._write_record_to_bitable = AsyncMock(return_value=(True, "rec_new"))

    ok, detail = asyncio.run(listener._upsert_record_to_bitable(table_id, {"开度": 10.0}, match_fields))

    assert ok is True
    assert detail == "rec_new"
    assert listener._record_lookup_cache[cache_key] == "rec_new"
    assert listener._find_existing_record_id.await_count == 2
    assert listener._find_existing_record_id.await_args_list[1].kwargs["use_cache"] is False
    listener._update_record_to_bitable.assert_awaited_once_with(table_id, "rec_stale", {"开度": 10.0})
    listener._write_record_to_bitable.assert_awaited_once_with(table_id, {"开度": 10.0})


def test_parse_spray_extracts_each_batch_block_without_cross_contamination() -> None:
    listener = _build_listener()
    text = """
A线喷雾批次号: S006-QQT-DA2602-130
开度: 10
进口温度: 100
出口温度: 80
雾化轮转速: 3000
水分: 1.0

B线喷雾批次号: S006-QQT-DB2602-131
开度: 20
进口温度: 110
出口温度: 90
雾化轮转速: 3200
水分: 1.2
""".strip()

    records = listener._parse_spray(text, "2026-03-04 08:00:00")

    assert len(records) == 2
    record_a = next(r for r in records if r.batch_id == "S006-DA2602-130")
    record_b = next(r for r in records if r.batch_id == "S006-DB2602-131")

    assert record_a.route_key == "spray.A"
    assert record_a.fields["开度"] == 10.0
    assert record_a.fields["进口温度"] == 100.0
    assert record_a.fields["出口温度"] == 80.0
    assert record_a.fields["雾化轮转速"] == 3000.0
    assert record_a.fields["水分"] == 1.0

    assert record_b.route_key == "spray.B"
    assert record_b.fields["开度"] == 20.0
    assert record_b.fields["进口温度"] == 110.0
    assert record_b.fields["出口温度"] == 90.0
    assert record_b.fields["雾化轮转速"] == 3200.0
    assert record_b.fields["水分"] == 1.2


def test_parse_feeding_extracts_each_batch_block_without_cross_contamination() -> None:
    listener = _build_listener()
    text = """
批次号: S006-TL-DA2602-001
磷酸铁需补: 10
碳酸锂需补: 1
D5总量: 2
BL总量: 3

批次号: S006-TL-DB2602-002
磷酸铁需补: 20
碳酸锂需补: 4
D5总量: 5
BL总量: 6
""".strip()

    records = listener._parse_feeding(text, "2026-03-04 08:00:00")

    assert len(records) == 2
    record_a = next(r for r in records if r.batch_id == "S006-TL-DA2602-001")
    record_b = next(r for r in records if r.batch_id == "S006-TL-DB2602-002")

    assert record_a.route_key == "feeding.A"
    assert record_a.fields["磷酸铁需补(kg)"] == 10.0
    assert record_a.fields["碳酸锂需补(kg)"] == 1.0
    assert record_a.fields["D5总量(kg)"] == 2.0
    assert record_a.fields["BL总量(kg)"] == 3.0

    assert record_b.route_key == "feeding.B"
    assert record_b.fields["磷酸铁需补(kg)"] == 20.0
    assert record_b.fields["碳酸锂需补(kg)"] == 4.0
    assert record_b.fields["D5总量(kg)"] == 5.0
    assert record_b.fields["BL总量(kg)"] == 6.0


def test_particle_text_priority_keeps_text_line_and_uses_ocr_d_values() -> None:
    listener = _build_listener({"merge_particle_size_to_stage_tables": True})
    plain_text = "S006-FS-DB2602-112-B2-55H"
    ocr_text = "S006-FS-DB2602-112-B1 D10:1.1 D50:2.2 D90:3.3 D99:4.4"

    records = listener._parse_records_with_text_priority(
        plain_text,
        ocr_text,
        "2026-03-04 08:00:00",
    )

    assert len(records) == 1
    record = records[0]
    assert record.scenario == "particle_size"
    assert record.route_key == "crushing.B"
    assert record.batch_id == "S006-FS-DB2602-112"
    assert record.fields["粉碎2线D10"] == 1.1
    assert record.fields["粉碎2线D50"] == 2.2
    assert record.fields["粉碎2线D90"] == 3.3
    assert record.fields["粉碎2线D99"] == 4.4
    assert "粉碎1线D10" not in record.fields


def test_particle_uses_ocr_fallback_when_plain_has_no_related_info() -> None:
    listener = _build_listener({"merge_particle_size_to_stage_tables": True})
    plain_text = "看图"
    ocr_text = "S006-FS-DB2602-113-B1 D10:5.1 D50:6.2 D90:7.3 D99:8.4"

    records = listener._parse_records_with_text_priority(
        plain_text,
        ocr_text,
        "2026-03-04 08:00:00",
    )

    assert len(records) == 1
    record = records[0]
    assert record.scenario == "particle_size"
    assert record.route_key == "crushing.B"
    assert record.batch_id == "S006-FS-DB2602-113"
    assert record.fields["粉碎1线D10"] == 5.1
    assert record.fields["粉碎1线D50"] == 6.2
    assert record.fields["粉碎1线D90"] == 7.3
    assert record.fields["粉碎1线D99"] == 8.4


def test_particle_text_d_values_not_overridden_by_ocr() -> None:
    listener = _build_listener({"merge_particle_size_to_stage_tables": True})
    plain_text = "S006-FS-DB2602-114-B2 D10:9.9 D50:8.8 D90:7.7 D99:6.6"
    ocr_text = "S006-FS-DB2602-114-B2 D10:1.1 D50:2.2 D90:3.3 D99:4.4"

    records = listener._parse_records_with_text_priority(
        plain_text,
        ocr_text,
        "2026-03-04 08:00:00",
    )

    assert len(records) == 1
    record = records[0]
    assert record.scenario == "particle_size"
    assert record.route_key == "crushing.B"
    assert record.batch_id == "S006-FS-DB2602-114"
    assert record.fields["D10"] == 9.9
    assert record.fields["D50"] == 8.8
    assert record.fields["D90"] == 7.7
    assert record.fields["D99"] == 6.6
    assert record.fields["粉碎2线D10"] == 9.9
    assert record.fields["粉碎2线D50"] == 8.8
    assert record.fields["粉碎2线D90"] == 7.7
    assert record.fields["粉碎2线D99"] == 6.6


def test_xm_text_anchor_uses_ocr_d_values_on_prefixed_fields() -> None:
    listener = _build_listener({"merge_particle_size_to_stage_tables": True})
    plain_text = "S006-XM-DB2602-130-B-160min"
    ocr_text = "S006-XM-DB2602-130-B-160min D10:1.1 D50:2.2 D90:3.3 D99:4.4"

    records = listener._parse_records_with_text_priority(
        plain_text,
        ocr_text,
        "2026-03-04 08:00:00",
    )
    records = listener._merge_records_for_write(records)

    assert len(records) == 1
    record = records[0]
    assert record.scenario == "particle_size"
    assert record.route_key == "wet_process.B"
    assert record.batch_id == "S006-DB2602-130"
    assert record.fields["细磨1线D10"] == 1.1
    assert record.fields["细磨1线D50"] == 2.2
    assert record.fields["细磨1线D90"] == 3.3
    assert record.fields["细磨1线D99"] == 4.4
    assert "D10" not in record.fields
    assert "D50" not in record.fields
    assert "D90" not in record.fields
    assert "D99" not in record.fields


def test_xm_text_d_values_not_overridden_by_ocr() -> None:
    listener = _build_listener({"merge_particle_size_to_stage_tables": True})
    plain_text = "S006-XM-DB2602-130-B-160min D10:9.9 D50:8.8 D90:7.7 D99:6.6"
    ocr_text = "S006-XM-DB2602-130-B-160min D10:1.1 D50:2.2 D90:3.3 D99:4.4"

    records = listener._parse_records_with_text_priority(
        plain_text,
        ocr_text,
        "2026-03-04 08:00:00",
    )
    records = listener._merge_records_for_write(records)

    assert len(records) == 1
    record = records[0]
    assert record.scenario == "particle_size"
    assert record.route_key == "wet_process.B"
    assert record.batch_id == "S006-DB2602-130"
    assert record.fields["细磨1线D10"] == 9.9
    assert record.fields["细磨1线D50"] == 8.8
    assert record.fields["细磨1线D90"] == 7.7
    assert record.fields["细磨1线D99"] == 6.6
    assert "D10" not in record.fields
    assert "D50" not in record.fields
    assert "D90" not in record.fields
    assert "D99" not in record.fields


def test_xm_without_sample_suffix_parses_minutes_as_time_not_sample() -> None:
    listener = _build_listener({"merge_particle_size_to_stage_tables": True})
    records = listener._parse_particle_size(
        "S006-XM-DB2602-130-160min D10:1.1 D50:2.2 D90:3.3 D99:4.4",
        "2026-03-04 08:00:00",
    )

    assert len(records) == 1
    record = records[0]
    assert record.scenario == "particle_size"
    assert record.route_key == "wet_process.B"
    assert record.batch_id == "S006-DB2602-130"
    assert record.fields["细磨研磨时间(min)"] == 160
    assert record.fields["细磨D10"] == 1.1
    assert record.fields["细磨D50"] == 2.2
    assert record.fields["细磨D90"] == 3.3
    assert record.fields["细磨D99"] == 4.4
    assert "细磨样品段" not in record.fields


def test_xm_solids_without_sample_suffix_parses_minutes_as_time_not_sample() -> None:
    listener = _build_listener({"merge_particle_size_to_stage_tables": True})
    records = listener._parse_xm_solids(
        "S006-XM-DB2602-130-160min：40.89%DC",
        "2026-03-04 08:00:00",
    )

    assert len(records) == 1
    record = records[0]
    assert record.scenario == "particle_size"
    assert record.route_key == "wet_process.B"
    assert record.batch_id == "S006-DB2602-130"
    assert record.fields["细磨研磨时间(min)"] == 160
    assert record.fields["细磨固含量(%)"] == 40.89
    assert "细磨样品段" not in record.fields
