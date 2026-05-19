from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from components.batch import compact_number, parse_float


@dataclass(frozen=True)
class RuleHit:
    level: str
    title: str
    evidence: str
    suggestion: str


def _first_number(fields: dict[str, Any], names: list[str]) -> float | None:
    for name in names:
        value = parse_float(fields.get(name))
        if value is not None:
            return value
    return None


def _has_any(fields: dict[str, Any], names: list[str]) -> bool:
    return any(str(fields.get(name, "")).strip() for name in names)


def diagnose_process(wide: dict[str, Any], abnormal: str = "") -> list[RuleHit]:
    hits: list[RuleHit] = []
    abnormal_text = abnormal or "批次复盘"
    stages = wide.get("stages", {}) if isinstance(wide.get("stages"), dict) else {}

    feeding = stages.get("feeding", {}) if isinstance(stages.get("feeding"), dict) else {}
    wet = stages.get("wet_process", {}) if isinstance(stages.get("wet_process"), dict) else {}
    spray = stages.get("spray", {}) if isinstance(stages.get("spray"), dict) else {}
    sintering = stages.get("sintering", {}) if isinstance(stages.get("sintering"), dict) else {}
    crushing = stages.get("crushing", {}) if isinstance(stages.get("crushing"), dict) else {}
    kiln = stages.get("kiln", {}) if isinstance(stages.get("kiln"), dict) else {}
    product = wide.get("product", {}) if isinstance(wide.get("product"), dict) else {}

    if not feeding:
        hits.append(RuleHit("中", "投料数据缺失", "未读取到投料补料和 D5/BL 总量。", "先补查投料记录，避免直接判断后段异常。"))
    if not wet:
        hits.append(RuleHit("中", "湿法数据缺失", "未读取到粗磨、细磨、合批粒度或固含量。", "补查湿法粒度和固含量，确认是否前置影响喷雾/烧结。"))
    if not spray:
        hits.append(RuleHit("中", "喷雾数据缺失", "未读取到喷雾温度、开度、转速或水分。", "补查喷雾状态，特别是水分和进出口温度。"))
    if not sintering:
        hits.append(RuleHit("高", "烧结压实数据缺失", "未读取到烧结段位压实均值。", "若异常与压实相关，应优先补齐烧结压实。"))

    sinter_values: list[float] = []
    for key, value in sintering.items():
        if "均值" in str(key) or "压实" in str(key):
            num = parse_float(value)
            if num is not None:
                sinter_values.append(num)
    if sinter_values:
        avg = sum(sinter_values) / len(sinter_values)
        spread = max(sinter_values) - min(sinter_values)
        if "压实" in abnormal_text and avg < 2.35:
            hits.append(
                RuleHit(
                    "高",
                    "烧结压实偏低",
                    f"烧结压实均值约 {compact_number(avg)}。",
                    "优先核查窑温、进出窑节拍、装钵稳定性和喷雾水分，必要时加严粉碎后压实复测。",
                )
            )
        if spread >= 0.03:
            hits.append(
                RuleHit(
                    "中",
                    "烧结段位差异偏大",
                    f"同批次段位压实极差约 {compact_number(spread)}。",
                    "按窑炉段和窑位追溯趋势，确认是否存在局部温场、装钵或气氛波动。",
                )
            )

    spray_moisture = _first_number(spray, ["水分", "喷雾水分"])
    if spray and spray_moisture is None:
        hits.append(RuleHit("中", "喷雾水分未记录", "喷雾表有记录但水分为空。", "补齐水分或确认是否未出结果，避免原因链断点。"))

    wet_d50 = _first_number(wet, ["细磨1线D50", "细磨2线D50", "细磨D50", "合批D50", "D50"])
    if wet_d50 is not None and (wet_d50 < 0.45 or wet_d50 > 0.65):
        hits.append(
            RuleHit(
                "中",
                "湿法 D50 偏离常见窗口",
                f"读取到湿法 D50={compact_number(wet_d50)}。",
                "核查砂磨时间、流量、固含量、锆球/棒销状态，并与同型号近期批次对比。",
            )
        )

    crushing_compaction = _first_number(crushing, ["粉碎1线压实值", "粉碎2线压实值", "压实", "粉碎压实"])
    if "压实" in abnormal_text and crushing and crushing_compaction is None:
        hits.append(RuleHit("中", "粉碎压实未出", "粉碎表存在记录但压实字段为空。", "补查粉碎压实，区分烧结偏低与粉碎后变化。"))

    if kiln and not _has_any(kiln, ["出窑开始时间", "出窑结束时间", "1号出窑开始时间", "2号出窑开始时间", "3号出窑开始时间"]):
        hits.append(RuleHit("低", "窑炉出窑时间不完整", "窑炉批次表未读取到明确出窑时间。", "补齐进出窑时间，便于分析节拍和停留时间。"))

    product_values = [parse_float(v) for v in product.values()]
    if product and not any(v is not None for v in product_values):
        hits.append(RuleHit("低", "成品数据未数值化", "读取到成品记录，但有效数值字段不足。", "检查公式、单位和表头解析，确认是否为引用公式未计算。"))

    return hits


def build_fallback_report(wide: dict[str, Any], hits: list[RuleHit], title: str) -> str:
    identity = wide.get("identity", {}) if isinstance(wide.get("identity"), dict) else {}
    batch = identity.get("core") or identity.get("raw") or "未知批次"
    lines = [f"{title}：{batch}", "", "【规则诊断】"]
    if hits:
        for idx, hit in enumerate(hits, start=1):
            lines.append(f"{idx}. [{hit.level}] {hit.title}")
            lines.append(f"   证据：{hit.evidence}")
            lines.append(f"   建议：{hit.suggestion}")
    else:
        lines.append("未命中明确异常规则，建议结合成品趋势和现场记录继续复核。")

    missing = wide.get("missing_data", [])
    if isinstance(missing, list) and missing:
        lines.extend(["", "【待补充数据】"])
        lines.extend(f"- {item}" for item in missing)
    lines.extend(["", "说明：以上为规则引擎兜底结果，未作自动放行、报废或配方变更判断。"])
    return "\n".join(lines).strip()

