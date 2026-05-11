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

    result = asyncio.run(listener._upsert_record_to_bitable(table_id, {"开度": 10.0}, match_fields))

    assert result.ok is True
    assert result.detail == "rec_new"
    assert result.record_id == "rec_new"
    assert result.operation == "create"
    assert listener._record_lookup_cache[cache_key] == "rec_new"
    assert listener._find_existing_record_id.await_count == 2
    assert listener._find_existing_record_id.await_args_list[1].kwargs["use_cache"] is False
    listener._update_record_to_bitable.assert_awaited_once_with(table_id, "rec_stale", {"开度": 10.0})
    listener._write_record_to_bitable.assert_awaited_once_with(table_id, {"开度": 10.0})


class _RecallEvent:
    def __init__(self, launcher_type: str = "person"):
        self.launcher_type = launcher_type


class _RecallEventContext:
    def __init__(self, launcher_type: str = "person"):
        self.event = _RecallEvent(launcher_type=launcher_type)


def test_recall_restore_previous_fields_from_history_when_latest() -> None:
    listener = _build_listener(
        {
            "enable_recall_revert": True,
            "enable_recall_restore_previous": True,
            "reply_on_recall": False,
            "private_notify_on_write": False,
        }
    )
    event_ctx = _RecallEventContext()

    history_entry = {
        "record_id": "hist_1",
        "fields": {
            "history_source_message_id": "msg_bad",
            "history_target_table_id": "tbl_main",
            "history_target_record_id": "rec_1",
            "history_operation": "update",
            "history_before_fields_json": '{"开度": 10.0, "源消息ID": "msg_good"}',
            "history_after_fields_json": '{"开度": 999.0, "源消息ID": "msg_bad"}',
            "history_route_key": "spray.A",
            "history_batch_id": "S006-DA2602-001",
            "history_line": "A",
            "history_logged_at_ts": "200",
            "history_status": "applied",
        },
    }
    older_entry = {
        "record_id": "hist_0",
        "fields": {
            "history_source_message_id": "msg_good",
            "history_target_table_id": "tbl_main",
            "history_target_record_id": "rec_1",
            "history_operation": "update",
            "history_before_fields_json": '{"开度": 8.0, "源消息ID": "msg_old"}',
            "history_after_fields_json": '{"开度": 10.0, "源消息ID": "msg_good"}',
            "history_route_key": "spray.A",
            "history_batch_id": "S006-DA2602-001",
            "history_line": "A",
            "history_logged_at_ts": "100",
            "history_status": "applied",
        },
    }

    listener._find_history_entries_by_source_message_id = AsyncMock(
        return_value=(
            "tbl_history",
            [listener._parse_history_entry(history_entry)],
        )
    )
    listener._find_history_entries_by_target_record = AsyncMock(
        return_value=[
            listener._parse_history_entry(history_entry),
            listener._parse_history_entry(older_entry),
        ]
    )
    listener._ensure_table_fields = AsyncMock(return_value=(True, "", {"开度": 1, "源消息ID": 1}))
    listener._normalize_write_fields = MagicMock(side_effect=lambda fields, _types: dict(fields))
    listener._update_record_to_bitable = AsyncMock(return_value=(True, "rec_1"))
    listener._update_history_entry_status = AsyncMock(return_value=(True, "hist_1"))
    listener._send_feedback = AsyncMock()

    asyncio.run(
        listener._handle_recalled_message(
            event_ctx,
            {"message_id": "msg_bad", "recall_time": "2026-03-12 10:00:00", "recall_type": "user"},
        )
    )

    listener._ensure_table_fields.assert_awaited_once_with(
        "tbl_main",
        {"开度": 10.0, "源消息ID": "msg_good"},
    )
    listener._update_record_to_bitable.assert_awaited_once_with(
        "tbl_main",
        "rec_1",
        {"开度": 10.0, "源消息ID": "msg_good"},
    )
    listener._update_history_entry_status.assert_awaited_once_with(
        "tbl_history",
        "hist_1",
        "recalled_restored",
        "restored previous fields",
    )
    listener._send_feedback.assert_not_awaited()


def test_recall_skips_restore_when_newer_write_exists() -> None:
    listener = _build_listener(
        {
            "enable_recall_revert": True,
            "enable_recall_restore_previous": True,
            "reply_on_error": True,
            "private_notify_on_error": False,
        }
    )
    event_ctx = _RecallEventContext()

    recalled_entry = {
        "record_id": "hist_1",
        "fields": {
            "history_source_message_id": "msg_bad",
            "history_target_table_id": "tbl_main",
            "history_target_record_id": "rec_1",
            "history_operation": "update",
            "history_before_fields_json": '{"开度": 10.0, "源消息ID": "msg_good"}',
            "history_after_fields_json": '{"开度": 999.0, "源消息ID": "msg_bad"}',
            "history_route_key": "spray.A",
            "history_batch_id": "S006-DA2602-001",
            "history_line": "A",
            "history_logged_at_ts": "200",
            "history_status": "applied",
        },
    }
    newer_entry = {
        "record_id": "hist_2",
        "fields": {
            "history_source_message_id": "msg_new",
            "history_target_table_id": "tbl_main",
            "history_target_record_id": "rec_1",
            "history_operation": "update",
            "history_before_fields_json": '{"开度": 999.0, "源消息ID": "msg_bad"}',
            "history_after_fields_json": '{"开度": 12.0, "源消息ID": "msg_new"}',
            "history_route_key": "spray.A",
            "history_batch_id": "S006-DA2602-001",
            "history_line": "A",
            "history_logged_at_ts": "300",
            "history_status": "applied",
        },
    }

    listener._find_history_entries_by_source_message_id = AsyncMock(
        return_value=("tbl_history", [listener._parse_history_entry(recalled_entry)])
    )
    listener._find_history_entries_by_target_record = AsyncMock(
        return_value=[
            listener._parse_history_entry(newer_entry),
            listener._parse_history_entry(recalled_entry),
        ]
    )
    listener._update_history_entry_status = AsyncMock(return_value=(True, "hist_1"))
    listener._send_feedback = AsyncMock()

    asyncio.run(
        listener._handle_recalled_message(
            event_ctx,
            {"message_id": "msg_bad", "recall_time": "2026-03-12 10:00:00", "recall_type": "user"},
        )
    )

    listener._update_history_entry_status.assert_awaited_once_with(
        "tbl_history",
        "hist_1",
        "recalled_skipped_not_latest",
        "skipped restore because newer write exists",
    )
    listener._send_feedback.assert_awaited_once()
    feedback_text = listener._send_feedback.await_args.args[1]
    assert "newer write exists" in feedback_text


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


def test_parse_kiln_batch_io_supports_preferred_and_extended_segments() -> None:
    listener = _build_listener()
    text = (
        "DA2603-021\u6279\u6b21\u7ed3\u675f\u51fa\u7a91\n"
        "A2-1--06\uff1a23\n"
        "F1-2---06:24"
    )

    records = listener._parse_kiln_batch_io(text, "2026-03-06 08:00:00")

    assert len(records) == 2

    record_a2 = next(r for r in records if r.line == "A2")
    assert record_a2.scenario == "kiln_batch_io"
    assert record_a2.route_key == "kiln_batch_io"
    assert record_a2.batch_id == "DA2603-021"
    assert record_a2.fields["\u7a91\u7089\u6bb5"] == "A2"
    assert "\u7a91\u4f4d" not in record_a2.fields
    assert record_a2.fields["1\u53f7\u51fa\u7a91\u7ed3\u675f\u65f6\u95f4"] == "2026-03-06 06:23:00"

    record_f1 = next(r for r in records if r.line == "F1")
    assert record_f1.fields["\u7a91\u7089\u6bb5"] == "F1"
    assert "\u7a91\u4f4d" not in record_f1.fields
    assert record_f1.fields["2\u53f7\u51fa\u7a91\u7ed3\u675f\u65f6\u95f4"] == "2026-03-06 06:24:00"


def test_parse_kiln_batch_io_maps_all_time_fields_and_merges_same_slot() -> None:
    listener = _build_listener()
    text = (
        "DA2603-021\u6279\u6b21\u5f00\u59cb\u8fdb\u7a91\n"
        "A2-1--01:30\n"
        "DA2603-021\u6279\u6b21\u7ed3\u675f\u8fdb\u7a91\n"
        "A2-1--01:32\n"
        "DA2603-021\u6279\u6b21\u5f00\u59cb\u51fa\u7a91\n"
        "A2-1--06:20\n"
        "DA2603-021\u6279\u6b21\u7ed3\u675f\u51fa\u7a91\n"
        "A2-1--06:25"
    )

    records = listener._parse_kiln_batch_io(text, "2026-03-06 08:00:00")
    assert len(records) == 4

    merged = listener._merge_records_for_write(records)
    assert len(merged) == 1

    record = merged[0]
    assert record.line == "A2"
    assert record.batch_id == "DA2603-021"
    assert record.route_key == "kiln_batch_io"
    assert record.fields["1\u53f7\u8fdb\u7a91\u5f00\u59cb\u65f6\u95f4"] == "2026-03-06 01:30:00"
    assert record.fields["1\u53f7\u8fdb\u7a91\u7ed3\u675f\u65f6\u95f4"] == "2026-03-06 01:32:00"
    assert record.fields["1\u53f7\u51fa\u7a91\u5f00\u59cb\u65f6\u95f4"] == "2026-03-06 06:20:00"
    assert record.fields["1\u53f7\u51fa\u7a91\u7ed3\u675f\u65f6\u95f4"] == "2026-03-06 06:25:00"


def test_parse_kiln_batch_io_supports_inline_batch_events() -> None:
    listener = _build_listener()
    text = (
        "DC2605-001\u8fdb\u7a91\u7ed3\u675f\u65f6\u95f47:54\n"
        "DC2605-002\u8fdb\u7a91\u5f00\u59cb\u65f6\u95f47:55\n"
        "DC-2605-002\u8fdb\u7a91\u7ed3\u675f\u65f6\u95f410:04\n"
        "DC2605-008\u7ed3\u675f\u65f6\u95f44:40\n"
        "DC2605-009\u8fdb\u7a91\u65f6\u95f44:41\n"
        "DC-2605-003\u5f00\u59cb\u51fa\u7a91\u65f6\u95f401:15\n"
        "DC-2605-003\u7ed3\u675f\u51fa\u7a91\u65f6\u95f406:20\n"
        "DC-2605-004\u5f00\u59cb\u51fa\u7a91\u65f6\u95f406:20"
    )

    records = listener._parse_kiln_batch_io(text, "2026-05-11 08:00:00")
    assert len(records) == 8
    assert {record.line for record in records} == {"C"}
    assert {record.route_key for record in records} == {"kiln_batch_io.phase2"}

    merged = listener._merge_records_for_write(records)
    assert len(merged) == 6

    record_002 = next(r for r in merged if r.batch_id == "DC2605-002")
    assert record_002.fields["\u8fdb\u7a91\u5f00\u59cb\u65f6\u95f4"] == "2026-05-11 07:55:00"
    assert record_002.fields["\u8fdb\u7a91\u7ed3\u675f\u65f6\u95f4"] == "2026-05-11 10:04:00"

    record_008 = next(r for r in merged if r.batch_id == "DC2605-008")
    assert record_008.fields["\u8fdb\u7a91\u7ed3\u675f\u65f6\u95f4"] == "2026-05-11 04:40:00"

    record_009 = next(r for r in merged if r.batch_id == "DC2605-009")
    assert record_009.fields["\u8fdb\u7a91\u5f00\u59cb\u65f6\u95f4"] == "2026-05-11 04:41:00"

    record_003 = next(r for r in merged if r.batch_id == "DC2605-003")
    assert record_003.fields["\u51fa\u7a91\u5f00\u59cb\u65f6\u95f4"] == "2026-05-11 01:15:00"
    assert record_003.fields["\u51fa\u7a91\u7ed3\u675f\u65f6\u95f4"] == "2026-05-11 06:20:00"


def test_parse_kiln_batch_io_routes_c_d_e_lines_to_phase2_table() -> None:
    listener = _build_listener()
    text = (
        "DC2605-001\u8fdb\u7a91\u5f00\u59cb\u65f6\u95f47:55\n"
        "DD2605-001\u8fdb\u7a91\u7ed3\u675f\u65f6\u95f47:54\n"
        "DE-2605-002\u5f00\u59cb\u51fa\u7a91\u65f6\u95f406:20"
    )

    records = listener._parse_kiln_batch_io(text, "2026-05-11 08:00:00")

    assert len(records) == 3
    assert {record.line for record in records} == {"C", "D", "E"}
    assert {record.route_key for record in records} == {"kiln_batch_io.phase2"}
    assert listener._resolve_table_name("kiln_batch_io.phase2") == "\u4e8c\u671f\u7a91\u7089\u6279\u6b21\u8fdb\u7a91\u51fa\u7a91\u8868"


def test_parse_kiln_batch_io_keeps_a_b_lines_on_primary_table() -> None:
    listener = _build_listener()
    text = (
        "DA2605-001\u8fdb\u7a91\u5f00\u59cb\u65f6\u95f47:55\n"
        "DB2605-001\u8fdb\u7a91\u7ed3\u675f\u65f6\u95f47:54"
    )

    records = listener._parse_kiln_batch_io(text, "2026-05-11 08:00:00")

    assert len(records) == 2
    assert {record.line for record in records} == {"A", "B"}
    assert {record.route_key for record in records} == {"kiln_batch_io"}


def test_parse_kiln_batch_io_slot_mode_keeps_one_row_per_position() -> None:
    listener = _build_listener({"kiln_batch_io_row_mode": "slot"})
    text = "DA2603-021\u6279\u6b21\u7ed3\u675f\u51fa\u7a91\nA2-1--06:23"

    records = listener._parse_kiln_batch_io(text, "2026-03-06 08:00:00")

    assert len(records) == 1
    record = records[0]
    assert record.line == "A2-1"
    assert record.fields["\u7a91\u7089\u6bb5"] == "A2"
    assert record.fields["\u7a91\u4f4d"] == "1"
    assert record.fields["\u51fa\u7a91\u7ed3\u675f\u65f6\u95f4"] == "2026-03-06 06:23:00"


def test_parse_kiln_batch_io_rolls_back_to_previous_day_after_midnight() -> None:
    listener = _build_listener()
    text = "DA2603-021\u6279\u6b21\u7ed3\u675f\u51fa\u7a91\nA2-1--23:55"

    records = listener._parse_kiln_batch_io(text, "2026-03-06 00:10:00")

    assert len(records) == 1
    record = records[0]
    assert record.fields["1\u53f7\u51fa\u7a91\u7ed3\u675f\u65f6\u95f4"] == "2026-03-05 23:55:00"


def test_parse_kiln_batch_io_rolls_forward_to_next_day_before_midnight() -> None:
    listener = _build_listener()
    text = "DA2603-021\u6279\u6b21\u5f00\u59cb\u8fdb\u7a91\nA2-1--00:10"

    records = listener._parse_kiln_batch_io(text, "2026-03-06 23:55:00")

    assert len(records) == 1
    record = records[0]
    assert record.fields["1\u53f7\u8fdb\u7a91\u5f00\u59cb\u65f6\u95f4"] == "2026-03-07 00:10:00"


def test_parse_kiln_batch_io_can_be_disabled_by_process_switch() -> None:
    listener = _build_listener({"process_switch_json": {"kiln_batch_io": False}})
    text = "DA2603-021\u6279\u6b21\u7ed3\u675f\u51fa\u7a91\nA2-1--06:23"

    records = listener._parse_kiln_batch_io(text, "2026-03-06 08:00:00")

    assert records == []


def test_parse_pure_water_supports_ab_line_header_with_single_batch() -> None:
    listener = _build_listener()
    text = "车间A/B线纯水PH：6.47\nS18-TL-DA2603-032"

    records = listener._parse_pure_water(text, "2026-03-07 08:00:00")

    assert len(records) == 1
    record = records[0]
    assert record.scenario == "pure_water"
    assert record.line == "A"
    assert record.batch_id == "S18-TL-DA2603-032"
    assert record.route_key == "pure_water.A"
    assert record.fields["PH值"] == 6.47
    assert record.fields["消息时间"] == "2026-03-07 08:00:00"
