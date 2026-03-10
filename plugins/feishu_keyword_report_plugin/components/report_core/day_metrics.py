#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import re
import sys
from dataclasses import dataclass
from typing import Any, Iterable, Optional

import numpy as np
import pandas as pd

LINE_A_SHEET = "S18-A线"
LINE_B_SHEET = "S006-B线"
LINE_A_LABEL = "S18-A线"
LINE_B_LABEL = "S006-B线"
STALE_SHEET_SKIP_DAYS = 6

STAT_HAS_DATA = "有数据"
STAT_NO_DATA = "无数据"
STAT_UNCONFIGURED = "未配置"
STAT_NO_DATA_TEXT = "数据未出"
STAT_STALE = "滞后"
STAT_UNCONFIGURED_TEXT = "本线未配置指标"

DEFAULT_SPEC_REGISTRY_PATH = os.path.join("config", "spec_registry.yaml")


@dataclass(frozen=True)
class ProductSpecProfile:
    model: str
    enable_spec: bool


@dataclass(frozen=True)
class StaleThresholdConfig:
    process_days: int = 2
    product_days: int = 3
    electrochem_days: int = 5


@dataclass(frozen=True)
class SpecHealthConfig:
    enabled: bool = True
    window_days: int = 14
    abnormal_ratio_threshold: float = 0.4
    min_consecutive_days: int = 5


PRODUCT_SPEC_PROFILES: dict[str, ProductSpecProfile] = {
    "S18": ProductSpecProfile(model="S18", enable_spec=True),
    "S006": ProductSpecProfile(model="S006", enable_spec=True),
}
DEFAULT_PROFILE = ProductSpecProfile(model="UNKNOWN", enable_spec=False)
LINE_A_SPEC_ENABLED = True
LINE_B_SPEC_ENABLED = True


def _ensure_utf8_stdout() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _norm_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and np.isnan(value):
        return ""
    text = str(value).strip()
    if text == "nan":
        return ""
    return text


def _is_spec_token(text: str) -> bool:
    s = _sanitize_col(text)
    if not s:
        return False
    if any(mark in s for mark in ("≤", "≥", "<=", ">=", "~", "±", "%", "ppm", "PPM")):
        return True
    if re.search(r"\d+(?:\.\d+)?\s*[-~]\s*\d+(?:\.\d+)?", s):
        return True
    return False


def _ffill_right(values: Iterable[Any], block_spec_token: bool = False) -> list[str]:
    out: list[str] = []
    last = ""
    for v in values:
        s = _norm_cell(v)
        if s:
            last = s
            out.append(last)
            continue
        if block_spec_token and _is_spec_token(last):
            out.append("")
            continue
        out.append(last)
    return out


def _dedupe(names: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    out: list[str] = []
    for name in names:
        count = seen.get(name, 0) + 1
        seen[name] = count
        out.append(name if count == 1 else f"{name}__{count}")
    return out


def _sanitize_col(name: str) -> str:
    text = re.sub(r"\s+", "", str(name)).strip()
    return (
        text.replace("＋", "+")
        .replace("﹢", "+")
        .replace("。", ".")
        .replace("．", ".")
        .replace("｡", ".")
        .replace("，", ",")
        .replace("（", "(")
        .replace("）", ")")
        .replace("～", "~")
        .replace("—", "-")
        .replace("−", "-")
        .replace("－", "-")
    )


def detect_model_from_sheet(sheet_name: str) -> str:
    text = _sanitize_col(sheet_name).upper()
    if "S18" in text:
        return "S18"
    if "S006" in text:
        return "S006"
    return "UNKNOWN"


def get_profile_for_sheet(sheet_name: str) -> ProductSpecProfile:
    return PRODUCT_SPEC_PROFILES.get(detect_model_from_sheet(sheet_name), DEFAULT_PROFILE)


def list_workbook_sheets(path: str) -> list[str]:
    with pd.ExcelFile(path, engine="calamine") as book:
        return [str(n).strip() for n in book.sheet_names if str(n).strip()]


def _has_effective_data_body(df: pd.DataFrame) -> bool:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return False
    body = df.drop(columns=["投料日期", "批次", "是否为验证批次"], errors="ignore")
    if body.empty:
        return False
    normalized = body.apply(lambda col: col.map(_norm_cell))
    normalized = normalized.apply(lambda col: col.where(col.str.strip().ne(""), np.nan))
    normalized = normalized.apply(lambda col: col.where(col.str.lower().ne("nan"), np.nan))
    return not normalized.dropna(how="all").empty


def list_line_sheets_with_skipped(path: str) -> tuple[list[str], dict[str, str]]:
    sheets = list_workbook_sheets(path)
    line_like = [s for s in sheets if "线" in s]
    candidates = line_like if line_like else sheets
    preferred = [s for s in candidates if detect_model_from_sheet(s) != "UNKNOWN"]
    candidates = preferred if preferred else candidates

    usable: list[str] = []
    skipped: dict[str, str] = {}
    for sheet_name in candidates:
        try:
            df = load_sheet_table(path, sheet_name)
        except Exception as e:
            skipped[sheet_name] = f"无法解析：{e}"
            continue
        if not _has_effective_data_body(df):
            skipped[sheet_name] = "无数据体"
            continue
        usable.append(sheet_name)
    return usable, skipped


def list_line_sheets(path: str) -> list[str]:
    usable, _ = list_line_sheets_with_skipped(path)
    return usable


_BATCH_RE = re.compile(r"^(?:D?[AB]\d{4}-\d{3}|[A-Za-z]+\d{3,8}-\d{2,4})$")


def _col_contains(col: str, token: str) -> bool:
    def _normalize_for_match(text: str) -> str:
        s = _sanitize_col(text).lower().replace("μ", "u").replace("µ", "u")
        return re.sub(r"[_\(\)\[\]\{\}]", "", s)

    norm_col = _normalize_for_match(col)
    norm_token = _normalize_for_match(token)
    return (token in str(col)) or (norm_token in norm_col)


def _find_row_contains(df: pd.DataFrame, keyword: str, max_rows: int = 80) -> Optional[int]:
    for i in range(min(len(df), max_rows)):
        row = df.iloc[i].astype(str)
        if row.str.contains(keyword, na=False, regex=False).any():
            return i
    return None


def _is_date_like(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (dt.date, dt.datetime, pd.Timestamp)):
        return True
    if isinstance(value, float) and np.isnan(value):
        return False
    s = _norm_cell(value)
    if not s:
        return False
    # 纯短数字更可能是工艺参数，不当作日期
    if re.fullmatch(r"\d{1,4}", s):
        return False
    # Excel 序列日期常见区间（约 1954~2091）
    if re.fullmatch(r"\d+(?:\.\d+)?", s):
        try:
            num = float(s)
            return 20000 <= num <= 70000
        except Exception:
            return False
    parsed = pd.to_datetime(s, errors="coerce")
    return not pd.isna(parsed)


def _find_data_start(df: pd.DataFrame, header_start: int = 0, max_rows: int = 240) -> Optional[int]:
    scan_start = max(0, int(header_start))
    scan_end = min(len(df), max_rows)

    # 1) 优先按批次格式命中（兼容 DA2601-001 / S006001-001 等）
    for i in range(scan_start, scan_end):
        row = df.iloc[i].astype(str)
        if row.str.match(_BATCH_RE, na=False).any():
            return i

    # 2) 回退：首列是日期，次列是非空批次文本
    for i in range(scan_start, scan_end):
        if df.shape[1] < 2:
            break
        row = df.iloc[i]
        c0 = row.iloc[0]
        c1 = _norm_cell(row.iloc[1])
        if not c1:
            continue
        # 排除明显表头关键词
        if any(k in c1 for k in ("批次", "线别", "窑炉温度", "D10", "D50", "D90", "均值", "时间")):
            continue
        if _is_date_like(c0):
            return i
    return None


def _make_columns_from_multirow_header(header_df: pd.DataFrame) -> list[str]:
    row_count = len(header_df)
    filled_rows: list[list[str]] = []
    for i in range(row_count):
        row_values = header_df.iloc[i].tolist()
        # 前两行可右向填充；最后一行保留原位，避免规格口径串列到右侧指标
        if i < max(0, row_count - 1):
            filled_rows.append(_ffill_right(row_values, block_spec_token=True))
        else:
            filled_rows.append([_norm_cell(v) for v in row_values])

    cols: list[str] = []
    for j in range(header_df.shape[1]):
        parts: list[str] = []
        for i in range(len(filled_rows)):
            s = _norm_cell(filled_rows[i][j])
            if s and (not parts or s != parts[-1]):
                parts.append(s)
        cols.append(_sanitize_col("_".join(parts)) if parts else f"COL{j}")
    return _dedupe(cols)


def _read_excel_raw(path: str, sheet_name: str) -> pd.DataFrame:
    # 使用 calamine 读 Excel：不依赖样式，兼容性更强（对 WPS/复杂样式表更稳）
    return pd.read_excel(path, sheet_name=sheet_name, header=None, engine="calamine")


def load_sheet_table(path: str, sheet_name: str) -> pd.DataFrame:
    raw = _read_excel_raw(path, sheet_name=sheet_name)

    header_start = _find_row_contains(raw, "批次") or 0
    data_start = _find_data_start(raw, header_start=header_start)
    if data_start is None or data_start <= header_start:
        raise ValueError(f"无法定位数据起始行：{path} / {sheet_name}")

    header_df = raw.iloc[header_start:data_start, :]
    cols = _make_columns_from_multirow_header(header_df)

    df = raw.iloc[data_start:, :].copy()
    df.columns = cols
    df = df.dropna(how="all")

    if "投料日期" in df.columns:
        # 兼容“日期单元格合并/只在首行填写”的情况：先转 datetime 再向下填充，再转 date
        s = pd.to_datetime(df["投料日期"], errors="coerce")
        s = s.ffill()
        df["投料日期"] = s.dt.date
    if "批次" in df.columns:
        s = df["批次"].astype(str).str.strip().replace({"": np.nan, "nan": np.nan})
        df["批次"] = s.ffill()
    if "是否为验证批次" in df.columns:
        s = df["是否为验证批次"].astype(str).str.strip().replace({"": np.nan, "nan": np.nan})
        df["是否为验证批次"] = s.ffill()
    return df


def _parse_num(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, float) and np.isnan(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    upper_text = text.upper()
    if upper_text.startswith("="):
        return None
    if re.match(r"^[A-Z]{2,}[A-Z0-9_]*\(", upper_text):
        return None
    parts = text.split("/")
    nums: list[float] = []
    for part in parts:
        cleaned = (
            part.replace("≤", "")
            .replace("≥", "")
            .replace("＋", "+")
            .replace("。", ".")
            .replace("．", ".")
            .replace("%", "")
            .strip()
        )
        cleaned = re.sub(r"(?<=\d),(?=\d)", ".", cleaned)
        m = re.search(r"[-+]?\d+(?:\.\d+)?", cleaned)
        if m:
            nums.append(float(m.group(0)))
    if not nums:
        return None
    return float(sum(nums) / len(nums))


def _to_num_series(s: pd.Series) -> pd.Series:
    return s.apply(_parse_num)


def _flatten_numeric_values(df: pd.DataFrame, cols: list[str]) -> pd.Series:
    if not cols:
        return pd.Series(dtype=float)
    series_list = [_to_num_series(df[c]) for c in cols if c in df.columns]
    if not series_list:
        return pd.Series(dtype=float)
    values = pd.concat(series_list, axis=0).dropna()
    return values


@dataclass(frozen=True)
class RangeStat:
    min: float
    max: float
    mean: float
    n: int


def _range_stat(values: pd.Series) -> Optional[RangeStat]:
    values = values.dropna()
    if values.empty:
        return None
    return RangeStat(
        min=float(values.min()),
        max=float(values.max()),
        mean=float(values.mean()),
        n=int(values.shape[0]),
    )


@dataclass(frozen=True)
class Spec:
    lower: Optional[float]
    upper: Optional[float]
    text: str


@dataclass(frozen=True)
class SpecRule:
    metric: str
    spec: Spec
    model: Optional[str] = None
    line: Optional[str] = None


_NUM = r"[-+]?\d+(?:[.,]\d+)?"


def _to_float(text: str) -> float:
    return float(text.replace(",", "."))


def parse_spec_from_colname(col: str) -> Optional[Spec]:
    # 从列名里解析常见内控口径：≥x、≤x、a~b、a-b、x±y
    # 注意：这里只用于“是否超内控”的粗判定；真正口径建议从“内控/规格表”统一维护。
    text = _sanitize_col(col).replace("～", "~").replace("—", "-").replace("−", "-")
    text = re.sub(r"(?<=\d),(?=\d)", ".", text)

    m = re.search(rf"(?:≥|>=)\s*({_NUM})", text)
    if m:
        return Spec(lower=_to_float(m.group(1)), upper=None, text=f"≥{m.group(1)}")
    m = re.search(rf"(?:≤|<=)\s*({_NUM})", text)
    if m:
        return Spec(lower=None, upper=_to_float(m.group(1)), text=f"≤{m.group(1)}")
    m = re.search(rf"({_NUM})\s*[~-]\s*({_NUM})", text)
    if m:
        a = _to_float(m.group(1))
        b = _to_float(m.group(2))
        lo, hi = (a, b) if a <= b else (b, a)
        return Spec(lower=lo, upper=hi, text=f"{lo}-{hi}")
    m = re.search(rf"({_NUM})\s*±\s*({_NUM})", text)
    if m:
        x = _to_float(m.group(1))
        y = _to_float(m.group(2))
        return Spec(lower=x - y, upper=x + y, text=f"{x}±{y}")
    return None


def _normalize_match_key(text: str) -> str:
    normalized = _sanitize_col(text).lower()
    return re.sub(r"[\s_\-\(\)\[\]\{\}]+", "", normalized)


def _parse_spec_literal(spec_text: str) -> Optional[Spec]:
    text = _sanitize_col(spec_text)
    if not text:
        return None
    return parse_spec_from_colname(f"口径_{text}")


def load_spec_registry(path: Optional[str]) -> list[SpecRule]:
    if not path:
        return []
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read().strip()
    except Exception:
        return []
    if not raw:
        return []

    data: Any = None
    try:
        data = json.loads(raw)
    except Exception:
        try:
            import yaml  # type: ignore

            data = yaml.safe_load(raw)
        except Exception:
            data = None

    if data is None:
        return []
    rules_data = data.get("rules") if isinstance(data, dict) else data
    if not isinstance(rules_data, list):
        return []

    out: list[SpecRule] = []
    for item in rules_data:
        if not isinstance(item, dict):
            continue
        metric = _norm_cell(item.get("metric"))
        if not metric:
            continue
        spec_obj: Optional[Spec] = None
        raw_spec = item.get("spec")
        if isinstance(raw_spec, dict):
            lower = _parse_num(raw_spec.get("lower"))
            upper = _parse_num(raw_spec.get("upper"))
            if lower is None and upper is None:
                continue
            text = _norm_cell(raw_spec.get("text")) or (
                f"{lower}-{upper}"
                if lower is not None and upper is not None
                else (f"≥{lower}" if lower is not None else f"≤{upper}")
            )
            spec_obj = Spec(lower=lower, upper=upper, text=text)
        else:
            spec_obj = _parse_spec_literal(_norm_cell(raw_spec))
        if spec_obj is None:
            continue
        model = _norm_cell(item.get("model")).upper() or None
        line = _norm_cell(item.get("line")) or None
        out.append(SpecRule(metric=metric, spec=spec_obj, model=model, line=line))
    return out


def _resolve_spec_from_registry(
    rules: list[SpecRule], line_label: str, model: str, metric_key: str, cols: list[str]
) -> Optional[Spec]:
    if not rules:
        return None
    line_norm = _normalize_match_key(line_label)
    model_norm = _normalize_match_key(model.upper())
    metric_norm = _normalize_match_key(metric_key)
    col_norms = [_normalize_match_key(c) for c in cols]

    def _metric_match(rule_metric: str) -> tuple[bool, int]:
        rule_norm = _normalize_match_key(rule_metric)
        if not rule_norm:
            return False, 0
        if metric_norm and rule_norm == metric_norm:
            return True, 20
        if metric_norm and (rule_norm in metric_norm or metric_norm in rule_norm):
            return True, 15
        if any(rule_norm in c or c in rule_norm for c in col_norms if c):
            return True, 10
        return False, 0

    best: Optional[tuple[int, Spec]] = None
    for rule in rules:
        matched, metric_score = _metric_match(rule.metric)
        if not matched:
            continue

        score = metric_score
        if rule.line:
            if _normalize_match_key(rule.line) != line_norm:
                continue
            score += 100
        if rule.model:
            if _normalize_match_key(rule.model) != model_norm:
                continue
            score += 30

        if best is None or score > best[0]:
            best = (score, rule.spec)
    return best[1] if best is not None else None


def _spec_is_reasonable_for_metric(col: str, spec: Spec) -> bool:
    # 0.1C 相关指标常见量纲为百量级，若口径上限仍小于10通常是误拼接（例如继承了 Li+ ≤0.055）
    if any(_col_contains(col, k) for k in ("0.1C充", "0.1C放", "0.1C首效")):
        bounds = [x for x in (spec.lower, spec.upper) if x is not None]
        if not bounds:
            return False
        if max(abs(x) for x in bounds) < 10:
            return False
    return True


def _normalized_spec_for_metric(col: str, scale: float = 1.0) -> Optional[Spec]:
    spec = parse_spec_from_colname(col)
    if spec is None:
        return None
    if not _spec_is_reasonable_for_metric(col, spec):
        return None
    scale_value = float(scale if scale is not None else 1.0)
    if scale_value != 1.0:
        spec = Spec(
            lower=None if spec.lower is None else spec.lower * scale_value,
            upper=None if spec.upper is None else spec.upper * scale_value,
            text=spec.text,
        )
    return spec


def _scale_spec(spec: Optional[Spec], scale: float = 1.0) -> Optional[Spec]:
    if spec is None:
        return None
    scale_value = float(scale if scale is not None else 1.0)
    if scale_value == 1.0:
        return spec
    return Spec(
        lower=None if spec.lower is None else spec.lower * scale_value,
        upper=None if spec.upper is None else spec.upper * scale_value,
        text=spec.text,
    )


def _state_has_data(state: str) -> bool:
    return state in (STAT_HAS_DATA, STAT_STALE)


def _spec_health_is_suspect(stat: dict[str, Any]) -> bool:
    info = stat.get("spec_health")
    return isinstance(info, dict) and bool(info.get("suspected"))


def _spec_health_text(stat: dict[str, Any]) -> str:
    info = stat.get("spec_health")
    if not isinstance(info, dict) or not info.get("suspected"):
        return ""
    abnormal_days = int(info.get("abnormal_days", 0))
    total_days = int(info.get("total_days", 0))
    longest = int(info.get("longest_consecutive_abnormal", 0))
    if total_days <= 0:
        return "治理关注：口径疑似不匹配"
    return f"治理关注：口径疑似不匹配（{abnormal_days}/{total_days}天异常，最长连续{longest}天）"


def _metric_group_for_stale(section: str, metric_key: str) -> str:
    if section == "制程":
        return "process"
    if metric_key in ("0.1C充电", "0.1C放电", "首效", "平台效率"):
        return "electrochem"
    return "product"


def _stale_threshold_for_metric(section: str, metric_key: str, cfg: StaleThresholdConfig) -> int:
    group = _metric_group_for_stale(section, metric_key)
    if group == "process":
        return int(cfg.process_days)
    if group == "electrochem":
        return int(cfg.electrochem_days)
    return int(cfg.product_days)


def _compute_spec_health_for_metric(
    df: pd.DataFrame,
    cols: list[str],
    report_date: dt.date,
    scale: float,
    enable_spec: bool,
    spec: Optional[Spec],
    window_days: int,
    abnormal_ratio_threshold: float,
    min_consecutive_days: int,
) -> Optional[dict[str, Any]]:
    if not enable_spec or spec is None or not cols or "投料日期" not in df.columns:
        return None
    if window_days <= 0:
        return None

    points: list[tuple[dt.date, bool]] = []
    scan_limit = max(60, window_days * 8)
    for delta in range(0, scan_limit + 1):
        d = report_date - dt.timedelta(days=delta)
        day = df[df["投料日期"] == d]
        st = _stat_for_cols(day, cols, scale=scale, enable_spec=enable_spec, explicit_spec=spec)
        if not st.get("有数据"):
            continue
        judge = st.get("判异")
        abnormal = bool(isinstance(judge, dict) and judge.get("异常"))
        points.append((d, abnormal))
        if len(points) >= window_days:
            break

    if not points:
        return None

    points = list(reversed(points))
    total_days = len(points)
    abnormal_days = sum(1 for _, abnormal in points if abnormal)
    ratio = abnormal_days / total_days if total_days else 0.0
    longest = 0
    current = 0
    for _, abnormal in points:
        if abnormal:
            current += 1
            if current > longest:
                longest = current
        else:
            current = 0

    suspected = ratio >= float(abnormal_ratio_threshold) and longest >= int(min_consecutive_days)
    return {
        "total_days": int(total_days),
        "abnormal_days": int(abnormal_days),
        "abnormal_ratio": float(ratio),
        "longest_consecutive_abnormal": int(longest),
        "suspected": bool(suspected),
        "window_days": int(window_days),
    }


def _stat_state(stat: dict[str, Any]) -> str:
    if not isinstance(stat, dict):
        return STAT_NO_DATA
    state = stat.get("状态")
    if state in (STAT_HAS_DATA, STAT_STALE, STAT_NO_DATA, STAT_UNCONFIGURED):
        return str(state)
    if stat.get("有数据"):
        return STAT_HAS_DATA
    return STAT_NO_DATA


def _resolve_metric_spec(
    *,
    cols: list[str],
    scale: float,
    enable_spec: bool,
    metric_key: str,
    line_label: str,
    model: str,
    spec_registry: Optional[list[SpecRule]],
) -> Optional[Spec]:
    if not enable_spec:
        return None
    registry_spec = _resolve_spec_from_registry(
        rules=spec_registry or [],
        line_label=line_label,
        model=model,
        metric_key=metric_key,
        cols=cols,
    )
    if registry_spec is not None:
        return _scale_spec(registry_spec, scale=scale)
    for c in cols:
        spec = _normalized_spec_for_metric(c, scale=scale)
        if spec is not None:
            return spec
    return None


def judge_out_of_spec(values: pd.Series, spec: Optional[Spec]) -> Optional[dict[str, Any]]:
    if spec is None:
        return None
    values = values.dropna()
    if values.empty:
        return None
    out_low = spec.lower is not None and (values < spec.lower).any()
    out_high = spec.upper is not None and (values > spec.upper).any()
    if not (out_low or out_high):
        return {"异常": False, "口径": spec.text}
    return {
        "异常": True,
        "口径": spec.text,
        "低于下限": bool(out_low),
        "高于上限": bool(out_high),
    }


def _has_any_metric_data(df: pd.DataFrame, date_: dt.date) -> bool:
    if "投料日期" not in df.columns:
        return False
    day = df[df["投料日期"] == date_]
    if day.empty:
        return False

    patterns = [
        "成品压实",
        "粉末电阻",
        "碳含量",
        "麦克比表",
        "Li+含量",
        "0.1C充",
        "0.1C放",
        "0.1C首效",
        "3.2V容量占比",
        "烧结压实",
        "粉碎压实",
    ]
    for pat in patterns:
        cols = [c for c in df.columns if _col_contains(c, pat)]
        values = _flatten_numeric_values(day, cols)
        if not values.empty:
            return True
    return False


def pick_date_from_dfs(dfs: Iterable[pd.DataFrame], date_arg: Optional[str]) -> dt.date:
    if date_arg:
        return pd.to_datetime(date_arg).date()

    dates: set[dt.date] = set()
    valid_dfs: list[pd.DataFrame] = [df for df in dfs if isinstance(df, pd.DataFrame)]
    for df in valid_dfs:
        if "投料日期" in df.columns:
            dates |= set([d for d in df["投料日期"].dropna().tolist() if isinstance(d, dt.date)])
    if not dates:
        raise ValueError("无法从Excel中推断最新日期，请使用 --date 指定。")

    # 优先选择“最新且有关键指标数据”的日期（避免最新投料日期只有制程前段录入，成品/扣电还未出数）
    for d in sorted(dates, reverse=True):
        if any(_has_any_metric_data(df, d) for df in valid_dfs):
            return d

    # 兜底：取最大日期
    return max(dates)


def pick_date(df_a: pd.DataFrame, df_b: pd.DataFrame, date_arg: Optional[str]) -> dt.date:
    return pick_date_from_dfs([df_a, df_b], date_arg)


def _latest_feed_date(df: pd.DataFrame) -> Optional[dt.date]:
    if "投料日期" not in df.columns:
        return None
    dates = [d for d in df["投料日期"].dropna().tolist() if isinstance(d, dt.date)]
    return max(dates) if dates else None


def _resolve_stale_sheet_anchor_date(date_arg: Optional[str]) -> dt.date:
    if date_arg:
        return pd.to_datetime(date_arg).date()
    return dt.date.today()


def _stat_for_cols(
    day: pd.DataFrame,
    cols: list[str],
    scale: float = 1.0,
    enable_spec: bool = True,
    metric_key: str = "",
    line_label: str = "",
    model: str = "UNKNOWN",
    spec_registry: Optional[list[SpecRule]] = None,
    explicit_spec: Optional[Spec] = None,
) -> dict[str, Any]:
    values = _flatten_numeric_values(day, cols)
    if scale != 1.0:
        values = values * scale
    st = _range_stat(values)
    if st is None:
        return {"有数据": False, "状态": STAT_NO_DATA, "quality_flags": []}
    spec = explicit_spec or _resolve_metric_spec(
        cols=cols,
        scale=scale,
        enable_spec=enable_spec,
        metric_key=metric_key,
        line_label=line_label,
        model=model,
        spec_registry=spec_registry,
    )
    batch_judge = _batch_out_of_spec_summary(day, cols, scale=scale, enable_spec=enable_spec, explicit_spec=spec)
    judge = judge_out_of_spec(values, spec)
    if isinstance(batch_judge, dict):
        abnormal_batches = int(batch_judge.get("异常批次", 0))
        judge = {"异常": abnormal_batches > 0, "口径": "按列规格(按批次汇总)"}
    return {
        "有数据": True,
        "状态": STAT_HAS_DATA,
        "min": st.min,
        "max": st.max,
        "mean": st.mean,
        "n": st.n,
        "判异": judge,
        "批次判异": batch_judge,
        "quality_flags": [],
    }


_BATCH_PARSE_RE = re.compile(r"^(?P<prefix>[A-Za-z0-9-]+?)(?P<yymm>\d{4})-(?P<seq>\d{3})$")


def _batch_sort_key(batch: str) -> tuple[Any, ...]:
    b = (batch or "").strip()
    m = _BATCH_PARSE_RE.match(b)
    if not m:
        return (b, 0, 0)
    return (m.group("prefix"), int(m.group("yymm")), int(m.group("seq")))


def _split_consecutive(nums: list[int]) -> list[tuple[int, int]]:
    if not nums:
        return []
    out: list[tuple[int, int]] = []
    start = nums[0]
    prev = nums[0]
    for n in nums[1:]:
        if n == prev + 1:
            prev = n
            continue
        out.append((start, prev))
        start = n
        prev = n
    out.append((start, prev))
    return out


def _format_seq_span(start: int, end: int) -> str:
    if start == end:
        return f"{start:03d}"
    if end == start + 1:
        return f"{start:03d}-{end:03d}"
    return f"{start:03d}~{end:03d}"


def _summarize_batches(batches: list[str]) -> str:
    batches = [b.strip() for b in batches if isinstance(b, str) and b.strip() and b.strip().lower() != "nan"]
    if not batches:
        return ""
    batches = sorted(list(dict.fromkeys(batches)), key=_batch_sort_key)
    if len(batches) == 1:
        return batches[0]

    parsed: list[tuple[str, int, int]] = []
    for b in batches:
        m = _BATCH_PARSE_RE.match(b)
        if not m:
            # 存在无法解析的批次号时，退回到逐个列举，避免误判成连续区间
            return "、".join(batches)
        parsed.append((m.group("prefix"), int(m.group("yymm")), int(m.group("seq"))))

    # 同一前缀+年月内：
    # - 连续：DA2602-103-104 / S006-DB2602-074~079
    # - 不连续：DA2602-103、105
    result_parts: list[str] = []
    keys: list[tuple[str, int]] = []
    grouped: dict[tuple[str, int], list[int]] = {}
    for prefix, yymm, seq in parsed:
        key = (prefix, yymm)
        if key not in grouped:
            grouped[key] = []
            keys.append(key)
        grouped[key].append(seq)

    for prefix, yymm in keys:
        seqs = sorted(set(grouped[(prefix, yymm)]))
        spans = _split_consecutive(seqs)
        if not spans:
            continue

        first_start, first_end = spans[0]
        head = f"{prefix}{yymm:04d}-{_format_seq_span(first_start, first_end)}"
        if len(spans) == 1:
            result_parts.append(head)
            continue

        tail = [_format_seq_span(s, e) for s, e in spans[1:]]
        result_parts.append("、".join([head] + tail))

    return "、".join(result_parts)


def _batch_summary_for_day(day: pd.DataFrame, cols: list[str]) -> str:
    if day.empty or "批次" not in day.columns:
        return ""
    metric_cols = [c for c in cols if c in day.columns]
    if not metric_cols:
        return ""

    has_value = pd.Series(False, index=day.index)
    for c in metric_cols:
        s = _to_num_series(day[c])
        has_value = has_value | s.notna()

    if not has_value.any():
        return ""

    batches = day.loc[has_value, "批次"].dropna().astype(str).tolist()
    return _summarize_batches(batches)


def _batch_out_of_spec_summary(
    day: pd.DataFrame,
    cols: list[str],
    scale: float = 1.0,
    enable_spec: bool = True,
    explicit_spec: Optional[Spec] = None,
) -> Optional[dict[str, int]]:
    if day.empty or "批次" not in day.columns or not enable_spec:
        return None
    metric_cols = [c for c in cols if c in day.columns]
    if not metric_cols:
        return None

    batch_series = day["批次"].astype(str).str.strip()
    valid_batch_mask = (batch_series != "") & (batch_series.str.lower() != "nan")

    has_value = pd.Series(False, index=day.index)
    for c in metric_cols:
        has_value = has_value | _to_num_series(day[c]).notna()
    total_batches = set(batch_series[has_value & valid_batch_mask].tolist())

    abnormal_batches: set[str] = set()
    low_batches: set[str] = set()
    high_batches: set[str] = set()
    spec_cols = 0 if explicit_spec is None else 1

    for c in metric_cols:
        spec = explicit_spec if explicit_spec is not None else _normalized_spec_for_metric(c, scale=scale)
        if spec is None:
            continue
        if explicit_spec is None:
            spec_cols += 1

        values = _to_num_series(day[c])
        if scale != 1.0:
            values = values * scale
        valid_value_mask = values.notna() & valid_batch_mask
        if not valid_value_mask.any():
            continue

        values = values[valid_value_mask]
        value_batches = batch_series[valid_value_mask]

        if spec.lower is not None:
            low_mask = values < spec.lower
            if low_mask.any():
                hit = set(value_batches[low_mask].tolist())
                low_batches |= hit
                abnormal_batches |= hit
        if spec.upper is not None:
            high_mask = values > spec.upper
            if high_mask.any():
                hit = set(value_batches[high_mask].tolist())
                high_batches |= hit
                abnormal_batches |= hit

    if spec_cols <= 0:
        return None

    return {
        "总批次": int(len(total_batches)),
        "异常批次": int(len(abnormal_batches)),
        "低于下限批次": int(len(low_batches)),
        "高于上限批次": int(len(high_batches)),
        "口径列数": int(spec_cols),
    }


def _latest_stat_within_days(
    df: pd.DataFrame,
    cols: list[str],
    report_date: dt.date,
    lookback_days: int,
    scale: float = 1.0,
    enable_spec: bool = True,
    configured: bool = True,
    metric_key: str = "",
    section: str = "",
    line_label: str = "",
    model: str = "UNKNOWN",
    line_max_date: Optional[dt.date] = None,
    stale_threshold_days: int = 0,
    spec_registry: Optional[list[SpecRule]] = None,
    spec_health: Optional[SpecHealthConfig] = None,
) -> dict[str, Any]:
    if not configured:
        return {"有数据": False, "状态": STAT_UNCONFIGURED, "quality_flags": []}
    if "投料日期" not in df.columns:
        return {"有数据": False, "状态": STAT_NO_DATA, "quality_flags": []}

    metric_spec = _resolve_metric_spec(
        cols=cols,
        scale=scale,
        enable_spec=enable_spec,
        metric_key=metric_key,
        line_label=line_label,
        model=model,
        spec_registry=spec_registry,
    )
    spec_health_info = None
    if spec_health and spec_health.enabled:
        spec_health_info = _compute_spec_health_for_metric(
            df=df,
            cols=cols,
            report_date=report_date,
            scale=scale,
            enable_spec=enable_spec,
            spec=metric_spec,
            window_days=max(1, int(spec_health.window_days)),
            abnormal_ratio_threshold=float(spec_health.abnormal_ratio_threshold),
            min_consecutive_days=max(1, int(spec_health.min_consecutive_days)),
        )

    for delta in range(0, max(0, lookback_days) + 1):
        d = report_date - dt.timedelta(days=delta)
        day = df[df["投料日期"] == d]
        st = _stat_for_cols(
            day,
            cols,
            scale=scale,
            enable_spec=enable_spec,
            metric_key=metric_key,
            line_label=line_label,
            model=model,
            spec_registry=spec_registry,
            explicit_spec=metric_spec,
        )
        if st.get("有数据"):
            lag_base = line_max_date if isinstance(line_max_date, dt.date) else report_date
            lag_days = max(0, (lag_base - d).days)
            st["状态"] = STAT_STALE if lag_days > max(0, int(stale_threshold_days)) else STAT_HAS_DATA
            st["来源日期"] = d
            st["是否当日"] = (delta == 0)
            st["来源批次摘要"] = _batch_summary_for_day(day, cols)
            st["lag_days"] = int(lag_days)
            st["quality_flags"] = list(st.get("quality_flags", []))
            if isinstance(spec_health_info, dict):
                st["spec_health"] = spec_health_info
                if bool(spec_health_info.get("suspected")):
                    st["quality_flags"].append("口径疑似不匹配")
            return st
    return {"有数据": False, "状态": STAT_NO_DATA, "quality_flags": []}


_LI_PASS_MAX = 500
_TREND_ANOMALY_RATIO = 1.3
_LI_TREND_ANOMALY_ABS = 80
_TREND_MAX_LOOKBACK_DAYS = 60
_TREND_SIGNIFICANT_REL = 0.005
_TREND_SIGNIFICANT_REL_LI = 0.02
_TREND_SIGNIFICANT_ABS_LI = 10.0


def _trend_for_cols(
    df: pd.DataFrame,
    cols: list[str],
    report_date: dt.date,
    trend_points: int,
    max_lookback_days: int,
    scale: float = 1.0,
    anomaly_ratio: float = _TREND_ANOMALY_RATIO,
    anomaly_abs: Optional[float] = None,
    enable_spec: bool = True,
    configured: bool = True,
    metric_key: str = "",
    line_label: str = "",
    model: str = "UNKNOWN",
    spec_registry: Optional[list[SpecRule]] = None,
) -> dict[str, Any]:
    if not configured:
        return {"有数据": False, "状态": STAT_UNCONFIGURED, "窗口": trend_points, "点数": 0}
    if "投料日期" not in df.columns or not cols or trend_points <= 0:
        return {"有数据": False, "状态": STAT_NO_DATA, "窗口": trend_points, "点数": 0}

    points: list[tuple[dt.date, dict[str, Any]]] = []
    for delta in range(0, max_lookback_days + 1):
        d = report_date - dt.timedelta(days=delta)
        day = df[df["投料日期"] == d]
        st = _stat_for_cols(
            day,
            cols,
            scale=scale,
            enable_spec=enable_spec,
            metric_key=metric_key,
            line_label=line_label,
            model=model,
            spec_registry=spec_registry,
        )
        if st.get("有数据"):
            points.append((d, st))
            if len(points) >= trend_points:
                break

    if not points:
        return {"有数据": False, "状态": STAT_NO_DATA, "窗口": trend_points, "点数": 0}

    points = list(reversed(points))
    means = [p[1]["mean"] for p in points]
    overall_mean = float(sum(means) / len(means)) if means else float("nan")
    anomalies: list[dict[str, Any]] = []
    if overall_mean and not np.isnan(overall_mean):
        lower = overall_mean / anomaly_ratio if anomaly_ratio > 0 else overall_mean
        upper = overall_mean * anomaly_ratio
        for d, st in points:
            mean = float(st["mean"])
            if mean < lower or mean > upper or (anomaly_abs is not None and abs(mean - overall_mean) >= anomaly_abs):
                anomalies.append({"日期": d, "mean": mean})

    direction = "—"
    if means[-1] > means[0] + 1e-9:
        direction = "↑"
    elif means[-1] < means[0] - 1e-9:
        direction = "↓"

    return {
        "有数据": True,
        "状态": STAT_HAS_DATA,
        "窗口": trend_points,
        "点数": len(points),
        "日期": [p[0] for p in points],
        "均值": means,
        "方向": direction,
        "异常": anomalies,
    }


def extract_metrics(
    df: pd.DataFrame,
    report_date: dt.date,
    lookback_days: int,
    trend_days: int = 7,
    enable_spec: bool = True,
    line_label: str = "",
    model: str = "UNKNOWN",
    stale_thresholds: Optional[StaleThresholdConfig] = None,
    spec_registry: Optional[list[SpecRule]] = None,
    spec_health: Optional[SpecHealthConfig] = None,
) -> dict[str, Any]:
    if "投料日期" in df.columns:
        day = df[df["投料日期"] == report_date].copy()
        line_dates = [d for d in df["投料日期"].dropna().tolist() if isinstance(d, dt.date)]
        line_max_date = max(line_dates) if line_dates else report_date
    else:
        day = df.head(0).copy()
        line_max_date = report_date

    stale_cfg = stale_thresholds or StaleThresholdConfig()
    health_cfg = spec_health or SpecHealthConfig()
    registry_rules = spec_registry or []

    # 注意：很多表会出现“均值未填，但B1-1/B1-2/B1-3已填”的情况，因此这里不只取“均值”
    sinter_cols = [c for c in df.columns if "烧结压实" in c]
    crush_cols = [c for c in df.columns if "粉碎压实" in c]

    prod_density_cols = [c for c in df.columns if "成品压实" in c]
    powder_res_cols = [c for c in df.columns if _col_contains(c, "粉末电阻")]
    li_cols = [c for c in df.columns if _col_contains(c, "Li+含量")]
    carbon_cols = [c for c in df.columns if c.startswith("碳含量")]
    if not carbon_cols:
        carbon_cols = [c for c in df.columns if _col_contains(c, "碳含量") and not _col_contains(c, "粉碎碳含量")]
    bet_cols = [c for c in df.columns if "麦克比表" in c]

    charge_cols = [c for c in df.columns if _col_contains(c, "0.1C充")]
    discharge_cols = [c for c in df.columns if _col_contains(c, "0.1C放")]
    eff_cols = [c for c in df.columns if _col_contains(c, "0.1C首效")]

    plat_cols = [c for c in df.columns if _col_contains(c, "3.2V容量占比")]
    if not plat_cols:
        plat_cols = [c for c in df.columns if _col_contains(c, "3.2V平台效率")]
    if not plat_cols:
        plat_cols = [c for c in df.columns if _col_contains(c, "2.95V容量占比")]

    trend_lookback_days = max(lookback_days, trend_days * 5, 30)
    trend_lookback_days = min(trend_lookback_days, _TREND_MAX_LOOKBACK_DAYS)

    def _latest(section: str, metric_key: str, cols: list[str], scale: float = 1.0, configured: bool = True) -> dict[str, Any]:
        return _latest_stat_within_days(
            df=df,
            cols=cols,
            report_date=report_date,
            lookback_days=lookback_days,
            scale=scale,
            enable_spec=enable_spec,
            configured=configured,
            metric_key=metric_key,
            section=section,
            line_label=line_label,
            model=model,
            line_max_date=line_max_date,
            stale_threshold_days=_stale_threshold_for_metric(section, metric_key, stale_cfg),
            spec_registry=registry_rules,
            spec_health=health_cfg,
        )

    def _trend(
        section: str,
        metric_key: str,
        cols: list[str],
        scale: float = 1.0,
        anomaly_abs: Optional[float] = None,
        configured: bool = True,
    ) -> dict[str, Any]:
        return _trend_for_cols(
            df,
            cols,
            report_date,
            trend_days,
            trend_lookback_days,
            scale=scale,
            anomaly_abs=anomaly_abs,
            enable_spec=enable_spec,
            configured=configured,
            metric_key=metric_key,
            line_label=line_label,
            model=model,
            spec_registry=registry_rules,
        )

    li_configured = bool(li_cols)
    sinter_configured = bool(sinter_cols)
    crush_configured = bool(crush_cols)
    prod_density_configured = bool(prod_density_cols)
    powder_res_configured = bool(powder_res_cols)
    carbon_configured = bool(carbon_cols)
    bet_configured = bool(bet_cols)
    charge_configured = bool(charge_cols)
    discharge_configured = bool(discharge_cols)
    eff_configured = bool(eff_cols)
    plat_configured = bool(plat_cols)

    li_trend = _trend("成品", "残碱(Li+)", li_cols, scale=10000, anomaly_abs=_LI_TREND_ANOMALY_ABS, configured=li_configured)
    sinter_trend = _trend("制程", "烧结压实", sinter_cols, configured=sinter_configured)
    crush_trend = _trend("制程", "粉碎压实", crush_cols, configured=crush_configured)
    prod_density_trend = _trend("成品", "成品压实", prod_density_cols, configured=prod_density_configured)
    powder_res_trend = _trend("成品", "粉阻(粉末电阻)", powder_res_cols, configured=powder_res_configured)
    carbon_trend = _trend("成品", "碳含量", carbon_cols, configured=carbon_configured)
    bet_trend = _trend("成品", "比表(麦克比表)", bet_cols, configured=bet_configured)
    charge_trend = _trend("成品", "0.1C充电", charge_cols, configured=charge_configured)
    discharge_trend = _trend("成品", "0.1C放电", discharge_cols, configured=discharge_configured)
    eff_trend = _trend("成品", "首效", eff_cols, configured=eff_configured)
    plat_trend = _trend("成品", "平台效率", plat_cols, configured=plat_configured)

    return {
        "制程": {
            "烧结压实": _latest("制程", "烧结压实", sinter_cols, configured=sinter_configured),
            "粉碎压实": _latest("制程", "粉碎压实", crush_cols, configured=crush_configured),
            "烧结压实趋势": sinter_trend,
            "粉碎压实趋势": crush_trend,
        },
        "成品": {
            "成品压实": _latest("成品", "成品压实", prod_density_cols, configured=prod_density_configured),
            "0.1C充电": _latest("成品", "0.1C充电", charge_cols, configured=charge_configured),
            "0.1C放电": _latest("成品", "0.1C放电", discharge_cols, configured=discharge_configured),
            "首效": _latest("成品", "首效", eff_cols, configured=eff_configured),
            "平台效率": _latest("成品", "平台效率", plat_cols, configured=plat_configured),
            "残碱(Li+)": _latest("成品", "残碱(Li+)", li_cols, scale=10000, configured=li_configured),
            "碳含量": _latest("成品", "碳含量", carbon_cols, configured=carbon_configured),
            "粉阻(粉末电阻)": _latest("成品", "粉阻(粉末电阻)", powder_res_cols, configured=powder_res_configured),
            "比表(麦克比表)": _latest("成品", "比表(麦克比表)", bet_cols, configured=bet_configured),
            "残碱(Li+)趋势": li_trend,
            "成品压实趋势": prod_density_trend,
            "0.1C充电趋势": charge_trend,
            "0.1C放电趋势": discharge_trend,
            "首效趋势": eff_trend,
            "平台效率趋势": plat_trend,
            "碳含量趋势": carbon_trend,
            "粉阻(粉末电阻)趋势": powder_res_trend,
            "比表(麦克比表)趋势": bet_trend,
        },
        "当日行数": int(day.shape[0]),
    }


def resolve_report_dates(
    line_dfs: dict[str, pd.DataFrame], date_arg: Optional[str], date_mode: str = "per-line"
) -> dict[str, dt.date]:
    if not line_dfs:
        return {}
    if date_arg:
        fixed_date = pd.to_datetime(date_arg).date()
        return {label: fixed_date for label in line_dfs}
    mode = (date_mode or "per-line").strip().lower()
    if mode == "global":
        global_date = pick_date_from_dfs(line_dfs.values(), None)
        return {label: global_date for label in line_dfs}
    return {label: pick_date_from_dfs([df], None) for label, df in line_dfs.items()}


def validate_sheet_data(df: pd.DataFrame, auto_fix: bool = False) -> dict[str, Any]:
    out_df = df.copy()
    issues: list[dict[str, Any]] = []
    fixed_count = 0

    rules = [
        {"type": "首效超范围", "token": "0.1C首效", "lower": 0.0, "upper": 100.0, "auto_fix": True},
        {"type": "成品压实超范围", "token": "成品压实", "lower": 1.5, "upper": 4.0, "auto_fix": False},
        {"type": "比表超范围", "token": "麦克比表", "lower": 0.0, "upper": 30.0, "auto_fix": False},
        {"type": "Li+超范围", "token": "Li+含量", "lower": 0.0, "upper": 1.0, "auto_fix": False},
        {"type": "粉阻超范围", "token": "粉末电阻", "lower": 0.0, "upper": 200.0, "auto_fix": False},
        {"type": "碳含量超范围", "token": "碳含量", "lower": 0.0, "upper": 10.0, "auto_fix": False},
    ]

    for rule in rules:
        cols = [c for c in out_df.columns if _col_contains(c, str(rule["token"]))]
        if not cols:
            continue
        lower = float(rule["lower"])
        upper = float(rule["upper"])
        for col in cols:
            values = _to_num_series(out_df[col])
            bad_mask = values.notna() & ((values < lower) | (values > upper))
            if not bad_mask.any():
                continue

            for idx in out_df.index[bad_mask]:
                parsed = float(values.loc[idx])
                raw_value = out_df.at[idx, col]
                source_date = out_df.at[idx, "投料日期"] if "投料日期" in out_df.columns else None
                source_batch = out_df.at[idx, "批次"] if "批次" in out_df.columns else None

                suggested_value: Optional[float] = None
                fixed = False
                if bool(rule["auto_fix"]) and auto_fix and float(parsed).is_integer() and 100 < parsed <= 10000:
                    suggested_value = parsed / 100.0
                    out_df.at[idx, col] = suggested_value
                    fixed = True
                    fixed_count += 1

                issues.append(
                    {
                        "类型": str(rule["type"]),
                        "列名": col,
                        "索引": int(idx),
                        "原始值": raw_value,
                        "解析值": parsed,
                        "建议值": suggested_value,
                        "投料日期": source_date if isinstance(source_date, dt.date) else None,
                        "批次": _norm_cell(source_batch),
                        "已自动修正": fixed,
                        "quality_flags": [str(rule["type"])],
                    }
                )

    return {"df": out_df, "issues": issues, "fixed_count": fixed_count}


def _quality_issue_to_text(issue: dict[str, Any], line_label: Optional[str] = None) -> str:
    date_part = issue.get("投料日期")
    date_text = date_part.strftime("%Y.%m.%d") if isinstance(date_part, dt.date) else "未知日期"
    batch_text = issue.get("批次") or "批次未知"
    col_text = str(issue.get("列名") or "未知列")
    value_text = str(issue.get("原始值"))
    line_prefix = f"{line_label} " if line_label else ""
    fix_hint = ""
    if issue.get("已自动修正") and issue.get("建议值") is not None:
        fix_hint = f"（已按{issue['建议值']:.2f}修正）"
    elif issue.get("建议值") is not None:
        fix_hint = f"（建议{issue['建议值']:.2f}）"
    return f"{line_prefix}{date_text} {batch_text} {col_text}={value_text}{fix_hint}"


def _merge_stats(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    if not a.get("有数据") and not b.get("有数据"):
        if _stat_state(a) == STAT_UNCONFIGURED and _stat_state(b) == STAT_UNCONFIGURED:
            return {"有数据": False, "状态": STAT_UNCONFIGURED}
        return {"有数据": False, "状态": STAT_NO_DATA}

    mins: list[float] = []
    maxs: list[float] = []
    means: list[float] = []
    ns: list[int] = []
    for st in (a, b):
        if st.get("有数据"):
            mins.append(float(st["min"]))
            maxs.append(float(st["max"]))
            means.append(float(st["mean"]))
            ns.append(int(st["n"]))

    total_n = sum(ns) if ns else 0
    mean = sum(m * n for m, n in zip(means, ns)) / total_n if total_n else float("nan")
    return {
        "有数据": True,
        "状态": STAT_HAS_DATA,
        "min": float(min(mins)),
        "max": float(max(maxs)),
        "mean": float(mean),
        "n": int(total_n),
    }


def _fmt_range(stat: dict[str, Any], decimals: int = 3) -> str:
    state = _stat_state(stat)
    if state == STAT_UNCONFIGURED:
        return STAT_UNCONFIGURED_TEXT
    if not _state_has_data(state):
        return STAT_NO_DATA_TEXT
    mn = float(stat["min"])
    mx = float(stat["max"])
    if mn == mx:
        return f"{mn:.{decimals}f}"
    return f"{mn:.{decimals}f}-{mx:.{decimals}f}"


def _fmt_status(stat: dict[str, Any], force: bool = False, show_spec_attention: bool = True) -> str:
    state = _stat_state(stat)
    if not _state_has_data(state):
        return ""
    parts: list[str] = []

    if show_spec_attention and _spec_health_is_suspect(stat):
        parts.append(_spec_health_text(stat))
    else:
        judge = stat.get("判异") if isinstance(stat, dict) else None
        if not isinstance(judge, dict):
            if force and stat.get("有数据"):
                parts.append("未设定口径")
        else:
            abnormal = judge.get("异常")
            batch_judge = stat.get("批次判异") if isinstance(stat, dict) else None
            if abnormal is True and isinstance(batch_judge, dict):
                total = int(batch_judge.get("总批次", 0))
                abnormal_cnt = int(batch_judge.get("异常批次", 0))
                if total > 0 and abnormal_cnt > 0:
                    low_cnt = int(batch_judge.get("低于下限批次", 0))
                    high_cnt = int(batch_judge.get("高于上限批次", 0))
                    direction_parts: list[str] = []
                    if low_cnt > 0:
                        direction_parts.append("低于下限")
                    if high_cnt > 0:
                        direction_parts.append("高于上限")
                    direction = f"，{'/'.join(direction_parts)}" if direction_parts else ""
                    parts.append(f"异常，{abnormal_cnt}/{total}批次超规{direction}")
                else:
                    parts.append("异常")
            elif abnormal is True:
                parts.append("异常")
            elif abnormal is False:
                parts.append("正常")

    if not parts:
        return ""
    return f"（{'；'.join([p for p in parts if p])}）"


def _fmt_source_date(stat: dict[str, Any]) -> str:
    if not _state_has_data(_stat_state(stat)):
        return ""
    d = stat.get("来源日期")
    if not isinstance(d, dt.date):
        return ""
    date_str = d.strftime("%Y.%m.%d")
    batch_summary = stat.get("来源批次摘要")
    if isinstance(batch_summary, str) and batch_summary:
        return f"（投料时间{date_str}，投料批次{batch_summary}）"
    return f"（投料时间{date_str}，投料批次未知）"


def _with_unit(value: str, unit: str) -> str:
    return value if value in (STAT_NO_DATA_TEXT, STAT_UNCONFIGURED_TEXT) else f"{value}{unit}"


def _fmt_report_date(report_date: dt.date) -> str:
    return (report_date + dt.timedelta(days=1)).strftime("%Y.%m.%d")


def _fmt_metric(
    stat: dict[str, Any],
    decimals: int,
    force_status: bool = False,
    show_spec_attention: bool = True,
) -> str:
    return (
        _fmt_range(stat, decimals)
        + _fmt_status(stat, force=force_status, show_spec_attention=show_spec_attention)
        + _fmt_source_date(stat)
    )


def _fmt_li_status(stat: dict[str, Any]) -> str:
    if not _state_has_data(_stat_state(stat)):
        return ""
    return "（合格）" if float(stat["max"]) < _LI_PASS_MAX else "（超标）"


def _trend_sparkline(values: list[float]) -> str:
    if not values:
        return ""
    levels = "▁▂▃▄▅▆▇█"
    vmin = min(values)
    vmax = max(values)
    if vmin == vmax:
        return levels[0] * len(values)
    span = vmax - vmin
    chars: list[str] = []
    for v in values:
        idx = int(round((v - vmin) / span * (len(levels) - 1)))
        idx = max(0, min(len(levels) - 1, idx))
        chars.append(levels[idx])
    return "".join(chars)


def _fmt_trend_dates(trend: dict[str, Any]) -> str:
    dates = trend.get("日期") or []
    if not dates:
        return ""
    sorted_dates = sorted([d for d in dates if isinstance(d, dt.date)])
    if not sorted_dates:
        return ""
    is_continuous = all(
        (sorted_dates[i] - sorted_dates[i - 1]).days == 1 for i in range(1, len(sorted_dates))
    )
    if is_continuous:
        if len(sorted_dates) == 1:
            return sorted_dates[0].strftime("%m.%d")
        return f"{sorted_dates[0].strftime('%m.%d')}-{sorted_dates[-1].strftime('%m.%d')}"
    return "/".join(d.strftime("%m.%d") for d in sorted_dates)


def _trend_significant(trend: dict[str, Any], rel_threshold: float, abs_threshold: Optional[float]) -> bool:
    if not trend.get("有数据"):
        return False
    means = trend.get("均值") or []
    if len(means) < 2:
        return False
    mn = min(means)
    mx = max(means)
    amplitude = mx - mn
    if abs_threshold is not None and amplitude >= abs_threshold:
        return True
    mean = sum(means) / len(means) if means else 0.0
    if mean and amplitude / mean >= rel_threshold:
        return True
    return False


def _fmt_trend_brief(trend: dict[str, Any], decimals: int, unit: str = "") -> str:
    state = _stat_state(trend)
    if state == STAT_UNCONFIGURED:
        return STAT_UNCONFIGURED_TEXT
    if not _state_has_data(state):
        return "无数据"
    means = trend.get("均值") or []
    if not means:
        return "无数据"
    fmt = lambda v: f"{v:.{decimals}f}"
    mn = min(means)
    mx = max(means)
    direction = trend.get("方向", "—")
    if direction == "↑":
        word = "微升"
    elif direction == "↓":
        word = "微降"
    else:
        word = "稳定"
    range_str = f"{fmt(mn)}~{fmt(mx)}"
    if unit:
        range_str = f"{range_str}{unit}"
    dates = _fmt_trend_dates(trend)
    suffix = f" [{dates}]" if dates else ""
    return f"{word}（{range_str}）{suffix}"


def _fmt_trend_layered(
    trend: dict[str, Any], decimals: int, unit: str, rel_threshold: float, abs_threshold: Optional[float]
) -> str:
    if _trend_significant(trend, rel_threshold, abs_threshold):
        return _fmt_trend(trend, decimals, unit)
    return _fmt_trend_brief(trend, decimals, unit)


def _fmt_trend(trend: dict[str, Any], decimals: int, unit: str = "") -> str:
    state = _stat_state(trend)
    if state == STAT_UNCONFIGURED:
        return STAT_UNCONFIGURED_TEXT
    if not _state_has_data(state):
        return "无数据"
    means = trend.get("均值") or []
    if not means:
        return "无数据"
    fmt = lambda v: f"{v:.{decimals}f}"
    seq = ",".join(fmt(v) for v in means)
    spark = _trend_sparkline(means)
    base = f"{seq} / {spark}（{trend.get('方向', '—')}）"
    if unit:
        base = f"{base}{unit}"
    dates = _fmt_trend_dates(trend)
    if dates:
        base = f"{base}（日期{dates}）"
    anomalies = trend.get("异常") or []
    if not anomalies:
        return base
    first = anomalies[0]
    date_str = first["日期"].strftime("%Y.%m.%d") if isinstance(first.get("日期"), dt.date) else "未知日期"
    hint = f"异常：{date_str} {fmt(first['mean'])}"
    if unit:
        hint = f"{hint}{unit}"
    if len(anomalies) > 1:
        hint += f" 等{len(anomalies)}天"
    return f"{base}，{hint}"


def build_wecom_text(report_date: dt.date, a: dict[str, Any], b: dict[str, Any]) -> str:
    date_str = _fmt_report_date(report_date)

    a_sinter_stat = a["制程"]["烧结压实"]
    b_sinter_stat = b["制程"]["烧结压实"]
    a_sinter = _fmt_metric(a_sinter_stat, 3, force_status=True)
    b_sinter = _fmt_metric(b_sinter_stat, 3, force_status=False)
    ab_sinter = _fmt_range(_merge_stats(a_sinter_stat, b_sinter_stat), 3)

    a_crush_stat = a["制程"]["粉碎压实"]
    b_crush_stat = b["制程"]["粉碎压实"]
    a_crush = _fmt_metric(a_crush_stat, 3, force_status=True)
    b_crush = _fmt_metric(b_crush_stat, 3, force_status=False)
    ab_crush = _fmt_range(_merge_stats(a_crush_stat, b_crush_stat), 3)
    a_sinter_trend = _fmt_trend_layered(a["制程"]["烧结压实趋势"], 3, "", _TREND_SIGNIFICANT_REL, None)
    b_sinter_trend = _fmt_trend_layered(b["制程"]["烧结压实趋势"], 3, "", _TREND_SIGNIFICANT_REL, None)
    a_crush_trend = _fmt_trend_layered(a["制程"]["粉碎压实趋势"], 3, "", _TREND_SIGNIFICANT_REL, None)
    b_crush_trend = _fmt_trend_layered(b["制程"]["粉碎压实趋势"], 3, "", _TREND_SIGNIFICANT_REL, None)

    a_prod_density_stat = a["成品"]["成品压实"]
    b_prod_density_stat = b["成品"]["成品压实"]
    ab_prod_density = _fmt_range(_merge_stats(a_prod_density_stat, b_prod_density_stat), 3)

    a_charge = _fmt_metric(a["成品"]["0.1C充电"], 1, force_status=True)
    a_discharge = _fmt_metric(a["成品"]["0.1C放电"], 1, force_status=True)
    a_eff = _fmt_metric(a["成品"]["首效"], 2, force_status=True)
    a_plat = _fmt_metric(a["成品"]["平台效率"], 1, force_status=True)

    b_charge = _fmt_metric(b["成品"]["0.1C充电"], 1, force_status=False)
    b_discharge = _fmt_metric(b["成品"]["0.1C放电"], 1, force_status=False)
    b_eff = _fmt_metric(b["成品"]["首效"], 2, force_status=False)
    b_plat = _fmt_metric(b["成品"]["平台效率"], 1, force_status=False)

    ab_alkali_stat = _merge_stats(a["成品"]["残碱(Li+)"], b["成品"]["残碱(Li+)"])
    ab_alkali = _fmt_range(ab_alkali_stat, 0)
    if LINE_B_SPEC_ENABLED:
        ab_alkali_status = _fmt_li_status(ab_alkali_stat)
    else:
        ab_alkali_status = "（规格口径待更新）" if ab_alkali_stat.get("有数据") else ""
    a_carbon = _fmt_metric(a["成品"]["碳含量"], 2, force_status=True)
    b_carbon = _fmt_metric(b["成品"]["碳含量"], 2, force_status=False)
    a_powder_r = _fmt_metric(a["成品"]["粉阻(粉末电阻)"], 1, force_status=True)
    b_powder_r = _fmt_metric(b["成品"]["粉阻(粉末电阻)"], 1, force_status=False)
    a_bet = _fmt_metric(a["成品"]["比表(麦克比表)"], 1, force_status=True)
    b_bet = _fmt_metric(b["成品"]["比表(麦克比表)"], 1, force_status=False)
    a_prod_trend = _fmt_trend_layered(a["成品"]["成品压实趋势"], 3, "", _TREND_SIGNIFICANT_REL, None)
    b_prod_trend = _fmt_trend_layered(b["成品"]["成品压实趋势"], 3, "", _TREND_SIGNIFICANT_REL, None)
    a_charge_trend = _fmt_trend_layered(a["成品"]["0.1C充电趋势"], 1, "", _TREND_SIGNIFICANT_REL, None)
    b_charge_trend = _fmt_trend_layered(b["成品"]["0.1C充电趋势"], 1, "", _TREND_SIGNIFICANT_REL, None)
    a_discharge_trend = _fmt_trend_layered(a["成品"]["0.1C放电趋势"], 1, "", _TREND_SIGNIFICANT_REL, None)
    b_discharge_trend = _fmt_trend_layered(b["成品"]["0.1C放电趋势"], 1, "", _TREND_SIGNIFICANT_REL, None)
    a_eff_trend = _fmt_trend_layered(a["成品"]["首效趋势"], 2, "", _TREND_SIGNIFICANT_REL, None)
    b_eff_trend = _fmt_trend_layered(b["成品"]["首效趋势"], 2, "", _TREND_SIGNIFICANT_REL, None)
    a_plat_trend = _fmt_trend_layered(a["成品"]["平台效率趋势"], 1, "", _TREND_SIGNIFICANT_REL, None)
    b_plat_trend = _fmt_trend_layered(b["成品"]["平台效率趋势"], 1, "", _TREND_SIGNIFICANT_REL, None)
    a_li_trend = _fmt_trend_layered(
        a["成品"]["残碱(Li+)趋势"], 0, "ppm", _TREND_SIGNIFICANT_REL_LI, _TREND_SIGNIFICANT_ABS_LI
    )
    b_li_trend = _fmt_trend_layered(
        b["成品"]["残碱(Li+)趋势"], 0, "ppm", _TREND_SIGNIFICANT_REL_LI, _TREND_SIGNIFICANT_ABS_LI
    )
    a_carbon_trend = _fmt_trend_layered(a["成品"]["碳含量趋势"], 2, "", _TREND_SIGNIFICANT_REL, None)
    b_carbon_trend = _fmt_trend_layered(b["成品"]["碳含量趋势"], 2, "", _TREND_SIGNIFICANT_REL, None)
    a_powder_trend = _fmt_trend_layered(a["成品"]["粉阻(粉末电阻)趋势"], 1, "", _TREND_SIGNIFICANT_REL, None)
    b_powder_trend = _fmt_trend_layered(b["成品"]["粉阻(粉末电阻)趋势"], 1, "", _TREND_SIGNIFICANT_REL, None)
    a_bet_trend = _fmt_trend_layered(a["成品"]["比表(麦克比表)趋势"], 1, "", _TREND_SIGNIFICANT_REL, None)
    b_bet_trend = _fmt_trend_layered(b["成品"]["比表(麦克比表)趋势"], 1, "", _TREND_SIGNIFICANT_REL, None)

    # 输出结构按你给的 1~6 段落口径；未提供的数据先保留占位，便于你后续把“第二张表”接进来。
    lines: list[str] = []
    lines.append(f"{date_str}数据表更新：")
    if not LINE_B_SPEC_ENABLED:
        lines.append(f"注：{LINE_B_LABEL}已更换产品，规格口径待更新，当前仅展示数据区间，不做超规判定。")
    lines.append("1、原料bom：本次Excel未包含（待接入第二张表/Sheet）")
    lines.append("2、配方：本次Excel未包含（待接入第二张表/Sheet）")
    lines.append(
        f"3、制程：烧结压实({LINE_A_LABEL}+{LINE_B_LABEL}) {ab_sinter}；{LINE_A_LABEL} {a_sinter}；{LINE_B_LABEL} {b_sinter}。"
        f"粉碎压实({LINE_A_LABEL}+{LINE_B_LABEL}) {ab_crush}；{LINE_A_LABEL} {a_crush}；{LINE_B_LABEL} {b_crush}。"
    )
    trend_points = max(a["制程"]["烧结压实趋势"].get("点数", 0), b["制程"]["烧结压实趋势"].get("点数", 0))
    trend_window = max(a["制程"]["烧结压实趋势"].get("窗口", 0), b["制程"]["烧结压实趋势"].get("窗口", 0))
    if trend_points:
        label = f"近{trend_points}日数据均值"
        if trend_window and trend_points < trend_window:
            label = f"{label}（不足{trend_window}日数据）"
        lines.append(f"  制程趋势（{label}）：")
        lines.append(f"    烧结压实 {LINE_A_LABEL} {a_sinter_trend}；{LINE_B_LABEL} {b_sinter_trend}。")
        lines.append(f"    粉碎压实 {LINE_A_LABEL} {a_crush_trend}；{LINE_B_LABEL} {b_crush_trend}。")
    lines.append("4、成品：")
    lines.append(f"  ①{LINE_A_LABEL}+{LINE_B_LABEL}成品压实：{ab_prod_density}。")
    lines.append(f"  ②0.1C充电：{LINE_A_LABEL} {a_charge}；{LINE_B_LABEL} {b_charge}。")
    lines.append(f"0.1C放电：{LINE_A_LABEL} {a_discharge}；{LINE_B_LABEL} {b_discharge}。")
    lines.append(f"首效：{LINE_A_LABEL} {a_eff}；{LINE_B_LABEL} {b_eff}。")
    lines.append(f"平台效率：{LINE_A_LABEL} {a_plat}；{LINE_B_LABEL} {b_plat}。")
    lines.append(f"  ③残碱(Li+)：{LINE_A_LABEL}+{LINE_B_LABEL} {_with_unit(ab_alkali, 'ppm')}{ab_alkali_status}。")
    lines.append(f"  ④碳含量：{LINE_A_LABEL} {a_carbon}；{LINE_B_LABEL} {b_carbon}。")
    lines.append(f"  ⑤粉阻(粉末电阻)：{LINE_A_LABEL} {a_powder_r}；{LINE_B_LABEL} {b_powder_r}。")
    lines.append(f"  ⑥比表(麦克比表)：{LINE_A_LABEL} {a_bet}；{LINE_B_LABEL} {b_bet}。")
    trend_points = max(a["成品"]["残碱(Li+)趋势"].get("点数", 0), b["成品"]["残碱(Li+)趋势"].get("点数", 0))
    trend_window = max(a["成品"]["残碱(Li+)趋势"].get("窗口", 0), b["成品"]["残碱(Li+)趋势"].get("窗口", 0))
    if trend_points:
        label = f"近{trend_points}日数据均值"
        if trend_window and trend_points < trend_window:
            label = f"{label}（不足{trend_window}日数据）"
        lines.append(f"  成品趋势（{label}）：")
        lines.append(f"    成品压实 {LINE_A_LABEL} {a_prod_trend}；{LINE_B_LABEL} {b_prod_trend}。")
        lines.append(f"    0.1C充电 {LINE_A_LABEL} {a_charge_trend}；{LINE_B_LABEL} {b_charge_trend}。")
        lines.append(f"    0.1C放电 {LINE_A_LABEL} {a_discharge_trend}；{LINE_B_LABEL} {b_discharge_trend}。")
        lines.append(f"    首效 {LINE_A_LABEL} {a_eff_trend}；{LINE_B_LABEL} {b_eff_trend}。")
        lines.append(f"    平台效率 {LINE_A_LABEL} {a_plat_trend}；{LINE_B_LABEL} {b_plat_trend}。")
        lines.append(f"    残碱(Li+) {LINE_A_LABEL} {a_li_trend}；{LINE_B_LABEL} {b_li_trend}。")
        lines.append(f"    碳含量 {LINE_A_LABEL} {a_carbon_trend}；{LINE_B_LABEL} {b_carbon_trend}。")
        lines.append(f"    粉阻(粉末电阻) {LINE_A_LABEL} {a_powder_trend}；{LINE_B_LABEL} {b_powder_trend}。")
        lines.append(f"    比表(麦克比表) {LINE_A_LABEL} {a_bet_trend}；{LINE_B_LABEL} {b_bet_trend}。")
    lines.append("5、下一步计划：本次Excel未包含（可从模板/手工输入/第二张表接入）")
    lines.append("6、工艺验证：本次Excel未包含（待接入第二张表/Sheet）")
    return "\n".join(lines)


def build_wecom_text_single(
    report_date: dt.date,
    metrics: dict[str, Any],
    line_label: str,
    model: str,
    enable_spec: bool = True,
    quality_issues: Optional[list[dict[str, Any]]] = None,
    show_spec_attention: bool = True,
) -> str:
    date_str = _fmt_report_date(report_date)

    process = metrics["制程"]
    product = metrics["成品"]

    sinter = _fmt_metric(process["烧结压实"], 3, force_status=True, show_spec_attention=show_spec_attention)
    crush = _fmt_metric(process["粉碎压实"], 3, force_status=True, show_spec_attention=show_spec_attention)

    prod_density = _fmt_metric(product["成品压实"], 3, force_status=True, show_spec_attention=show_spec_attention)
    charge = _fmt_metric(product["0.1C充电"], 1, force_status=True, show_spec_attention=show_spec_attention)
    discharge = _fmt_metric(product["0.1C放电"], 1, force_status=True, show_spec_attention=show_spec_attention)
    eff = _fmt_metric(product["首效"], 2, force_status=True, show_spec_attention=show_spec_attention)
    plat = _fmt_metric(product["平台效率"], 1, force_status=True, show_spec_attention=show_spec_attention)

    li_stat = product["残碱(Li+)"]
    li = (
        _with_unit(_fmt_range(li_stat, 0), "ppm")
        + _fmt_status(li_stat, force=True, show_spec_attention=show_spec_attention)
        + _fmt_source_date(li_stat)
    )
    carbon = _fmt_metric(product["碳含量"], 2, force_status=True, show_spec_attention=show_spec_attention)
    powder_r = _fmt_metric(
        product["粉阻(粉末电阻)"], 1, force_status=True, show_spec_attention=show_spec_attention
    )
    bet = _fmt_metric(product["比表(麦克比表)"], 1, force_status=True, show_spec_attention=show_spec_attention)

    sinter_trend = _fmt_trend_layered(process["烧结压实趋势"], 3, "", _TREND_SIGNIFICANT_REL, None)
    crush_trend = _fmt_trend_layered(process["粉碎压实趋势"], 3, "", _TREND_SIGNIFICANT_REL, None)
    prod_trend = _fmt_trend_layered(product["成品压实趋势"], 3, "", _TREND_SIGNIFICANT_REL, None)
    charge_trend = _fmt_trend_layered(product["0.1C充电趋势"], 1, "", _TREND_SIGNIFICANT_REL, None)
    discharge_trend = _fmt_trend_layered(product["0.1C放电趋势"], 1, "", _TREND_SIGNIFICANT_REL, None)
    eff_trend = _fmt_trend_layered(product["首效趋势"], 2, "", _TREND_SIGNIFICANT_REL, None)
    plat_trend = _fmt_trend_layered(product["平台效率趋势"], 1, "", _TREND_SIGNIFICANT_REL, None)
    li_trend = _fmt_trend_layered(product["残碱(Li+)趋势"], 0, "ppm", _TREND_SIGNIFICANT_REL_LI, _TREND_SIGNIFICANT_ABS_LI)
    carbon_trend = _fmt_trend_layered(product["碳含量趋势"], 2, "", _TREND_SIGNIFICANT_REL, None)
    powder_trend = _fmt_trend_layered(product["粉阻(粉末电阻)趋势"], 1, "", _TREND_SIGNIFICANT_REL, None)
    bet_trend = _fmt_trend_layered(product["比表(麦克比表)趋势"], 1, "", _TREND_SIGNIFICANT_REL, None)

    lines: list[str] = []
    lines.append(f"{date_str}数据表更新（{line_label} / {model}）：")
    if not enable_spec:
        lines.append("注：当前线别未匹配到产品规格口径，仅展示数据区间，不做超规判定。")
    lines.append("1、原料bom：本次Excel未包含（待接入第二张表/Sheet）")
    lines.append("2、配方：本次Excel未包含（待接入第二张表/Sheet）")
    lines.append(f"3、制程：烧结压实 {sinter}；粉碎压实 {crush}。")

    process_trend_points = max(process["烧结压实趋势"].get("点数", 0), process["粉碎压实趋势"].get("点数", 0))
    process_trend_window = max(process["烧结压实趋势"].get("窗口", 0), process["粉碎压实趋势"].get("窗口", 0))
    if process_trend_points:
        label = f"近{process_trend_points}日数据均值"
        if process_trend_window and process_trend_points < process_trend_window:
            label = f"{label}（不足{process_trend_window}日数据）"
        lines.append(f"  制程趋势（{label}）：")
        lines.append(f"    烧结压实 {sinter_trend}。")
        lines.append(f"    粉碎压实 {crush_trend}。")

    lines.append("4、成品：")
    lines.append(f"  ①成品压实：{prod_density}。")
    lines.append(f"  ②0.1C充电：{charge}。")
    lines.append(f"0.1C放电：{discharge}。")
    lines.append(f"首效：{eff}。")
    lines.append(f"平台效率：{plat}。")
    lines.append(f"  ③残碱(Li+)：{li}。")
    lines.append(f"  ④碳含量：{carbon}。")
    lines.append(f"  ⑤粉阻(粉末电阻)：{powder_r}。")
    lines.append(f"  ⑥比表(麦克比表)：{bet}。")

    product_trend_points = max(
        product["成品压实趋势"].get("点数", 0),
        product["0.1C充电趋势"].get("点数", 0),
        product["0.1C放电趋势"].get("点数", 0),
        product["首效趋势"].get("点数", 0),
        product["平台效率趋势"].get("点数", 0),
        product["残碱(Li+)趋势"].get("点数", 0),
        product["碳含量趋势"].get("点数", 0),
        product["粉阻(粉末电阻)趋势"].get("点数", 0),
        product["比表(麦克比表)趋势"].get("点数", 0),
    )
    product_trend_window = max(
        product["成品压实趋势"].get("窗口", 0),
        product["0.1C充电趋势"].get("窗口", 0),
        product["0.1C放电趋势"].get("窗口", 0),
        product["首效趋势"].get("窗口", 0),
        product["平台效率趋势"].get("窗口", 0),
        product["残碱(Li+)趋势"].get("窗口", 0),
        product["碳含量趋势"].get("窗口", 0),
        product["粉阻(粉末电阻)趋势"].get("窗口", 0),
        product["比表(麦克比表)趋势"].get("窗口", 0),
    )
    if product_trend_points:
        label = f"近{product_trend_points}日数据均值"
        if product_trend_window and product_trend_points < product_trend_window:
            label = f"{label}（不足{product_trend_window}日数据）"
        lines.append(f"  成品趋势（{label}）：")
        lines.append(f"    成品压实 {prod_trend}。")
        lines.append(f"    0.1C充电 {charge_trend}。")
        lines.append(f"    0.1C放电 {discharge_trend}。")
        lines.append(f"    首效 {eff_trend}。")
        lines.append(f"    平台效率 {plat_trend}。")
        lines.append(f"    残碱(Li+) {li_trend}。")
        lines.append(f"    碳含量 {carbon_trend}。")
        lines.append(f"    粉阻(粉末电阻) {powder_trend}。")
        lines.append(f"    比表(麦克比表) {bet_trend}。")

    if quality_issues:
        lines.append(f"  数据质量告警：{len(quality_issues)}项。")
        for issue in quality_issues[:5]:
            lines.append(f"    - {_quality_issue_to_text(issue)}")
        if len(quality_issues) > 5:
            lines.append(f"    - 其余{len(quality_issues) - 5}项省略。")

    lines.append("5、下一步计划：本次Excel未包含（可从模板/手工输入/第二张表接入）")
    lines.append("6、工艺验证：本次Excel未包含（待接入第二张表/Sheet）")
    return "\n".join(lines)


def build_wecom_text_multi(line_reports: list[dict[str, Any]], show_spec_attention: bool = True) -> str:
    if not line_reports:
        return ""

    valid_reports = [
        r
        for r in line_reports
        if isinstance(r, dict) and isinstance(r.get("metrics"), dict) and isinstance(r.get("line_label"), str)
    ]
    if not valid_reports:
        return ""

    line_labels = [str(r["line_label"]) for r in valid_reports]
    line_metrics = {str(r["line_label"]): r["metrics"] for r in valid_reports}
    line_enable_spec = {str(r["line_label"]): bool(r.get("enable_spec", True)) for r in valid_reports}

    report_dates = [r.get("report_date") for r in valid_reports if isinstance(r.get("report_date"), dt.date)]
    date_set = sorted({d for d in report_dates if isinstance(d, dt.date)})
    if len(date_set) == 1:
        date_str = _fmt_report_date(date_set[0])
    else:
        date_str = (
            "/".join(_fmt_report_date(d) for d in date_set)
            if date_set
            else _fmt_report_date(dt.date.today())
        )

    def _metric_parts(section: str, key: str, decimals: int) -> str:
        parts: list[str] = []
        for label in line_labels:
            st = line_metrics[label][section][key]
            parts.append(
                f"{label} "
                + _fmt_metric(
                    st,
                    decimals,
                    force_status=line_enable_spec[label],
                    show_spec_attention=show_spec_attention,
                )
            )
        return "；".join(parts)

    def _trend_parts(section: str, key: str, decimals: int, unit: str, rel: float, abs_v: Optional[float]) -> str:
        parts: list[str] = []
        for label in line_labels:
            trend = line_metrics[label][section][key]
            parts.append(f"{label} {_fmt_trend_layered(trend, decimals, unit, rel, abs_v)}")
        return "；".join(parts)

    def _max_points(section: str, key: str) -> int:
        return max((int(line_metrics[label][section][key].get("点数", 0)) for label in line_labels), default=0)

    def _max_window(section: str, key: str) -> int:
        return max((int(line_metrics[label][section][key].get("窗口", 0)) for label in line_labels), default=0)

    lines: list[str] = []
    lines.append(f"{date_str}数据表更新（{ '、'.join(line_labels) }）：")
    no_spec_lines = [label for label in line_labels if not line_enable_spec[label]]
    if no_spec_lines:
        lines.append(f"注：{ '、'.join(no_spec_lines) }规格口径待更新，当前仅展示数据区间，不做超规判定。")
    lines.append("1、原料bom：本次Excel未包含（待接入第二张表/Sheet）")
    lines.append("2、配方：本次Excel未包含（待接入第二张表/Sheet）")
    lines.append(
        "3、制程："
        + f"烧结压实 {_metric_parts('制程', '烧结压实', 3)}。"
        + f"粉碎压实 {_metric_parts('制程', '粉碎压实', 3)}。"
    )

    process_points = max(
        _max_points("制程", "烧结压实趋势"),
        _max_points("制程", "粉碎压实趋势"),
    )
    process_window = max(
        _max_window("制程", "烧结压实趋势"),
        _max_window("制程", "粉碎压实趋势"),
    )
    if process_points:
        label = f"近{process_points}日数据均值"
        if process_window and process_points < process_window:
            label = f"{label}（不足{process_window}日数据）"
        lines.append(f"  制程趋势（{label}）：")
        lines.append(
            "    烧结压实 "
            + _trend_parts("制程", "烧结压实趋势", 3, "", _TREND_SIGNIFICANT_REL, None)
            + "。"
        )
        lines.append(
            "    粉碎压实 "
            + _trend_parts("制程", "粉碎压实趋势", 3, "", _TREND_SIGNIFICANT_REL, None)
            + "。"
        )

    lines.append("4、成品：")
    lines.append(f"  ①成品压实：{_metric_parts('成品', '成品压实', 3)}。")
    lines.append(f"  ②0.1C充电：{_metric_parts('成品', '0.1C充电', 1)}。")
    lines.append(f"0.1C放电：{_metric_parts('成品', '0.1C放电', 1)}。")
    lines.append(f"首效：{_metric_parts('成品', '首效', 2)}。")
    lines.append(f"平台效率：{_metric_parts('成品', '平台效率', 1)}。")
    lines.append(f"  ③残碱(Li+)：{_metric_parts('成品', '残碱(Li+)', 0)}。")
    lines.append(f"  ④碳含量：{_metric_parts('成品', '碳含量', 2)}。")
    lines.append(f"  ⑤粉阻(粉末电阻)：{_metric_parts('成品', '粉阻(粉末电阻)', 1)}。")
    lines.append(f"  ⑥比表(麦克比表)：{_metric_parts('成品', '比表(麦克比表)', 1)}。")

    product_points = max(
        _max_points("成品", "成品压实趋势"),
        _max_points("成品", "0.1C充电趋势"),
        _max_points("成品", "0.1C放电趋势"),
        _max_points("成品", "首效趋势"),
        _max_points("成品", "平台效率趋势"),
        _max_points("成品", "残碱(Li+)趋势"),
        _max_points("成品", "碳含量趋势"),
        _max_points("成品", "粉阻(粉末电阻)趋势"),
        _max_points("成品", "比表(麦克比表)趋势"),
    )
    product_window = max(
        _max_window("成品", "成品压实趋势"),
        _max_window("成品", "0.1C充电趋势"),
        _max_window("成品", "0.1C放电趋势"),
        _max_window("成品", "首效趋势"),
        _max_window("成品", "平台效率趋势"),
        _max_window("成品", "残碱(Li+)趋势"),
        _max_window("成品", "碳含量趋势"),
        _max_window("成品", "粉阻(粉末电阻)趋势"),
        _max_window("成品", "比表(麦克比表)趋势"),
    )
    if product_points:
        label = f"近{product_points}日数据均值"
        if product_window and product_points < product_window:
            label = f"{label}（不足{product_window}日数据）"
        lines.append(f"  成品趋势（{label}）：")
        lines.append("    成品压实 " + _trend_parts("成品", "成品压实趋势", 3, "", _TREND_SIGNIFICANT_REL, None) + "。")
        lines.append("    0.1C充电 " + _trend_parts("成品", "0.1C充电趋势", 1, "", _TREND_SIGNIFICANT_REL, None) + "。")
        lines.append("    0.1C放电 " + _trend_parts("成品", "0.1C放电趋势", 1, "", _TREND_SIGNIFICANT_REL, None) + "。")
        lines.append("    首效 " + _trend_parts("成品", "首效趋势", 2, "", _TREND_SIGNIFICANT_REL, None) + "。")
        lines.append("    平台效率 " + _trend_parts("成品", "平台效率趋势", 1, "", _TREND_SIGNIFICANT_REL, None) + "。")
        lines.append(
            "    残碱(Li+) "
            + _trend_parts("成品", "残碱(Li+)趋势", 0, "ppm", _TREND_SIGNIFICANT_REL_LI, _TREND_SIGNIFICANT_ABS_LI)
            + "。"
        )
        lines.append("    碳含量 " + _trend_parts("成品", "碳含量趋势", 2, "", _TREND_SIGNIFICANT_REL, None) + "。")
        lines.append(
            "    粉阻(粉末电阻) "
            + _trend_parts("成品", "粉阻(粉末电阻)趋势", 1, "", _TREND_SIGNIFICANT_REL, None)
            + "。"
        )
        lines.append(
            "    比表(麦克比表) "
            + _trend_parts("成品", "比表(麦克比表)趋势", 1, "", _TREND_SIGNIFICANT_REL, None)
            + "。"
        )

    lines.append("5、下一步计划：本次Excel未包含（可从模板/手工输入/第二张表接入）")
    lines.append("6、工艺验证：本次Excel未包含（待接入第二张表/Sheet）")
    return "\n".join(lines)


_LEADER_ABNORMAL_KEYS: list[tuple[str, str]] = [
    ("制程", "烧结压实"),
    ("制程", "粉碎压实"),
    ("成品", "成品压实"),
    ("成品", "0.1C充电"),
    ("成品", "0.1C放电"),
    ("成品", "首效"),
    ("成品", "平台效率"),
    ("成品", "残碱(Li+)"),
    ("成品", "碳含量"),
    ("成品", "粉阻(粉末电阻)"),
    ("成品", "比表(麦克比表)"),
]

_LEADER_KEY_METRICS: list[tuple[str, str, int, str]] = [
    ("制程", "烧结压实", 3, ""),
    ("制程", "粉碎压实", 3, ""),
    ("成品", "成品压实", 3, ""),
    ("成品", "0.1C放电", 1, ""),
    ("成品", "首效", 2, ""),
    ("成品", "残碱(Li+)", 0, "ppm"),
]


def _stat_is_abnormal(stat: Any) -> bool:
    if not isinstance(stat, dict):
        return False
    if _spec_health_is_suspect(stat):
        return False
    judge = stat.get("判异")
    return isinstance(judge, dict) and bool(judge.get("异常") is True)


def _stat_source_batch_text(stat: Any) -> str:
    if not isinstance(stat, dict):
        return "投料批次未知"
    source_date = stat.get("来源日期")
    batch_summary = stat.get("来源批次摘要")
    if isinstance(source_date, dt.date):
        date_str = source_date.strftime("%Y.%m.%d")
        if isinstance(batch_summary, str) and batch_summary:
            return f"{date_str}投料批次{batch_summary}"
        return f"{date_str}投料批次未知"
    if isinstance(batch_summary, str) and batch_summary:
        return f"投料批次{batch_summary}"
    return "投料批次未知"


def _leader_key_metric_line(line_label: str, metrics: dict[str, Any]) -> str:
    parts: list[str] = []
    for section, key, decimals, unit in _LEADER_KEY_METRICS:
        st = metrics.get(section, {}).get(key)
        if not isinstance(st, dict):
            continue
        value = _fmt_range(st, decimals)
        if unit:
            value = _with_unit(value, unit)
        parts.append(f"{key}{value}")
    if not parts:
        return f"{line_label} 无有效数据"
    return f"{line_label} " + "，".join(parts)


def build_wecom_text_leader(line_reports: list[dict[str, Any]], show_spec_attention: bool = True) -> str:
    valid_reports = [
        r
        for r in line_reports
        if isinstance(r, dict) and isinstance(r.get("metrics"), dict) and isinstance(r.get("line_label"), str)
    ]
    if not valid_reports:
        return ""

    report_dates = [r.get("report_date") for r in valid_reports if isinstance(r.get("report_date"), dt.date)]
    date_set = sorted({d for d in report_dates if isinstance(d, dt.date)})
    if len(date_set) == 1:
        date_str = date_set[0].strftime("%Y.%m.%d")
    else:
        date_str = "/".join(d.strftime("%Y.%m.%d") for d in date_set) if date_set else dt.date.today().strftime("%Y.%m.%d")

    abnormal_items: list[str] = []
    spec_attention_items: list[str] = []
    key_metric_lines: list[str] = []
    quality_items: list[str] = []
    for r in valid_reports:
        line_label = str(r["line_label"])
        metrics = r["metrics"]
        key_metric_lines.append(_leader_key_metric_line(line_label, metrics))
        for section, key in _LEADER_ABNORMAL_KEYS:
            st = metrics.get(section, {}).get(key)
            if show_spec_attention and _spec_health_is_suspect(st):
                spec_attention_items.append(f"{line_label} {key}")
            elif _stat_is_abnormal(st):
                abnormal_items.append(f"{line_label} {key}（{_stat_source_batch_text(st)}）")
        for issue in r.get("quality_issues", []) if isinstance(r.get("quality_issues"), list) else []:
            if isinstance(issue, dict):
                quality_items.append(_quality_issue_to_text(issue, line_label=line_label))

    abnormal_items = list(dict.fromkeys(abnormal_items))
    spec_attention_items = list(dict.fromkeys(spec_attention_items))
    quality_items = list(dict.fromkeys(quality_items))
    if abnormal_items:
        conclusion = f"关注（{len(abnormal_items)}项异常）"
        abnormal_text = "；".join(abnormal_items)
        if show_spec_attention and spec_attention_items:
            abnormal_text += f"；治理关注（{len(spec_attention_items)}项口径疑似）：" + "；".join(spec_attention_items[:3])
            if len(spec_attention_items) > 3:
                abnormal_text += f"；其余{len(spec_attention_items) - 3}项省略"
    elif show_spec_attention and spec_attention_items:
        conclusion = f"治理关注（{len(spec_attention_items)}项口径疑似）"
        abnormal_text = "；".join(spec_attention_items[:3])
        if len(spec_attention_items) > 3:
            abnormal_text += f"；其余{len(spec_attention_items) - 3}项省略"
    else:
        conclusion = "正常"
        abnormal_text = "无"

    if quality_items:
        quality_text = f"共{len(quality_items)}项；" + "；".join(quality_items[:3])
        if len(quality_items) > 3:
            quality_text += f"；其余{len(quality_items) - 3}项省略"
    else:
        quality_text = "无"

    key_metric_text = "；".join([x for x in key_metric_lines if x]) if key_metric_lines else "无"
    lines = [
        f"1、今日结论（{date_str}）：{conclusion}",
        f"2、异常项清单：{abnormal_text}",
        f"3、关键指标区间：{key_metric_text}",
        f"4、数据质量告警：{quality_text}",
    ]
    return "\n".join(lines)


def main() -> int:
    _ensure_utf8_stdout()

    parser = argparse.ArgumentParser(description="从Excel生成企业微信日报文本（制程/成品）。")
    parser.add_argument("--excel", default=None, help="Excel路径；默认匹配当前目录下 *.xlsx")
    parser.add_argument("--sheet", default=None, help="指定要生成日报的工作表名（可逗号分隔多张，如 S18-B线,S006-B线）")
    parser.add_argument("--model", default=None, choices=["S18", "S006"], help="按产品型号筛选工作表")
    parser.add_argument("--list-sheets", action="store_true", help="仅列出工作簿中的候选线别并退出")
    parser.add_argument("--date", default=None, help="日期：YYYY-MM-DD；默认取表内最新投料日期")
    parser.add_argument(
        "--date-mode",
        default="per-line",
        choices=["per-line", "global"],
        help="日期策略：per-line按线独立日期（默认），global全线统一日期",
    )
    parser.add_argument("--lookback-days", type=int, default=7, help="指标取数向前回溯天数（避免当日某列为空显示“未录入”）")
    parser.add_argument("--trend-days", type=int, default=7, help="趋势窗口（近N次有数）；设为0可关闭")
    parser.add_argument("--disable-trend", action="store_true", help="关闭趋势窗口分析")
    parser.add_argument("--show-skipped-sheets", action="store_true", help="输出被跳过的工作表及原因")
    parser.add_argument("--stale-threshold-process", type=int, default=2, help="制程指标滞后阈值（天）")
    parser.add_argument("--stale-threshold-product", type=int, default=3, help="成品物性指标滞后阈值（天）")
    parser.add_argument("--stale-threshold-electrochem", type=int, default=5, help="电化学指标滞后阈值（天）")
    parser.add_argument(
        "--spec-registry",
        default=DEFAULT_SPEC_REGISTRY_PATH,
        help=f"规格配置文件路径（默认 {DEFAULT_SPEC_REGISTRY_PATH}；配置优先于列名解析）",
    )
    parser.add_argument("--spec-health-window", type=int, default=14, help="口径健康判定窗口（近N个有数日期）")
    parser.add_argument("--spec-health-threshold", type=float, default=0.4, help="口径健康判定异常占比阈值")
    parser.add_argument("--auto-fix-quality", action="store_true", help="自动修正明显首效录入异常（如 9781 -> 97.81）")
    parser.add_argument("--out", default=None, help="输出到文件（UTF-8）；不填则打印到控制台")
    args = parser.parse_args()

    path = args.excel
    if not path:
        matches = sorted(glob.glob("*.xlsx"))
        if not matches:
            print("未找到Excel：请使用 --excel 指定路径", file=sys.stderr)
            return 2
        path = matches[0]

    all_sheets = list_workbook_sheets(path)
    line_sheets, skipped_sheets = list_line_sheets_with_skipped(path)

    if args.list_sheets:
        if not line_sheets:
            print("未识别到可用线别工作表。")
            if args.show_skipped_sheets and skipped_sheets:
                print("被跳过工作表：")
                for name, reason in skipped_sheets.items():
                    print(f"- {name}: {reason}")
            return 0
        print("候选线别工作表：")
        for s in line_sheets:
            model = detect_model_from_sheet(s)
            print(f"- {s} (model={model})")
        if args.show_skipped_sheets and skipped_sheets:
            print("被跳过工作表：")
            for name, reason in skipped_sheets.items():
                print(f"- {name}: {reason}")
        return 0

    if not line_sheets:
        detail = "；".join([f"{k}:{v}" for k, v in skipped_sheets.items()]) if skipped_sheets else "无可用线别"
        raise ValueError(f"未识别到可用线别工作表：{path}（{detail}）")

    selected_sheets: list[str] = []
    if args.sheet:
        selected_sheets = [s.strip() for s in str(args.sheet).split(",") if s.strip()]
        if not selected_sheets:
            raise ValueError("--sheet 不能为空")
        missing = [s for s in selected_sheets if s not in all_sheets]
        if missing:
            raise ValueError(f"工作表不存在：{', '.join(missing)}；可选：{', '.join(all_sheets)}")
        if args.model:
            mismatch = [
                s
                for s in selected_sheets
                if detect_model_from_sheet(s) not in (args.model, "UNKNOWN")
            ]
            if mismatch:
                detail = ", ".join([f"{s}({detect_model_from_sheet(s)})" for s in mismatch])
                raise ValueError(f"以下工作表与 --model {args.model} 不一致：{detail}")
    else:
        selected_sheets = list(line_sheets)
        if args.model:
            selected_sheets = [s for s in selected_sheets if detect_model_from_sheet(s) == args.model]
            if not selected_sheets:
                available = ", ".join([f"{s}({detect_model_from_sheet(s)})" for s in line_sheets]) or "无"
                raise ValueError(f"未找到型号为 {args.model} 的候选线别；现有：{available}")

    trend_days = 0 if args.disable_trend else max(0, int(args.trend_days))
    stale_cfg = StaleThresholdConfig(
        process_days=max(0, int(args.stale_threshold_process)),
        product_days=max(0, int(args.stale_threshold_product)),
        electrochem_days=max(0, int(args.stale_threshold_electrochem)),
    )
    spec_health_cfg = SpecHealthConfig(
        enabled=True,
        window_days=max(1, int(args.spec_health_window)),
        abnormal_ratio_threshold=max(0.0, min(1.0, float(args.spec_health_threshold))),
        min_consecutive_days=5,
    )
    spec_registry_rules = load_spec_registry(args.spec_registry)
    if args.spec_registry and not spec_registry_rules and not os.path.exists(args.spec_registry):
        print(f"规格配置文件不存在：{args.spec_registry}（将回退列名解析）", file=sys.stderr)

    line_dfs: dict[str, pd.DataFrame] = {}
    line_errors: list[str] = []
    for sheet_name in selected_sheets:
        try:
            line_dfs[sheet_name] = load_sheet_table(path, sheet_name)
        except Exception as e:
            line_errors.append(f"{sheet_name}: {e}")

    if not line_dfs:
        raise ValueError("所选线别全部读取失败：" + "；".join(line_errors))

    report_dates = resolve_report_dates(line_dfs, args.date, args.date_mode)

    line_reports: list[dict[str, Any]] = []
    for sheet_name, df in line_dfs.items():
        detected_model = detect_model_from_sheet(sheet_name)
        model = detected_model if detected_model != "UNKNOWN" else (args.model or detected_model)
        profile = PRODUCT_SPEC_PROFILES.get(model, get_profile_for_sheet(sheet_name))

        quality = validate_sheet_data(df, auto_fix=args.auto_fix_quality)
        df_for_metrics = quality["df"]
        report_date = report_dates[sheet_name]
        metrics = extract_metrics(
            df_for_metrics,
            report_date,
            args.lookback_days,
            trend_days,
            enable_spec=profile.enable_spec,
            line_label=sheet_name,
            model=model,
            stale_thresholds=stale_cfg,
            spec_registry=spec_registry_rules,
            spec_health=spec_health_cfg,
        )
        line_reports.append(
            {
                "line_label": sheet_name,
                "report_date": report_date,
                "model": model,
                "enable_spec": profile.enable_spec,
                "metrics": metrics,
                "quality_issues": quality["issues"],
                "quality_fixed_count": int(quality["fixed_count"]),
            }
        )

    if len(line_reports) == 1:
        r = line_reports[0]
        detail_text = build_wecom_text_single(
            report_date=r["report_date"],
            metrics=r["metrics"],
            line_label=r["line_label"],
            model=r.get("model", "UNKNOWN"),
            enable_spec=bool(r.get("enable_spec", True)),
            quality_issues=r.get("quality_issues"),
        )
    else:
        detail_text = build_wecom_text_multi(line_reports)

    leader_text = build_wecom_text_leader(line_reports)
    text = leader_text if not detail_text else (leader_text + "\n\n【工程版】\n" + detail_text)

    if line_errors:
        print("部分线别读取失败：" + "；".join(line_errors), file=sys.stderr)
    if args.show_skipped_sheets and skipped_sheets:
        print("被跳过工作表：", file=sys.stderr)
        for name, reason in skipped_sheets.items():
            print(f"- {name}: {reason}", file=sys.stderr)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
            f.write("\n")
    else:
        print(text)
    return 0

_DEFAULT_SPEC_REGISTRY_PAYLOAD: dict[str, Any] = {
    "rules": [
        {"model": "S18", "metric": "成品压实", "spec": ">=2.37"},
        {"model": "S18", "metric": "首效", "spec": ">=96"},
        {"model": "S18", "metric": "平台效率", "spec": "79~87"},
        {"model": "S18", "metric": "比表(麦克比表)", "spec": "9.75~11.25"},
        {"model": "S006", "metric": "成品压实", "spec": ">=2.53"},
        {"model": "S006", "metric": "首效", "spec": ">=96.3"},
        {"model": "S006", "metric": "比表(麦克比表)", "spec": "11.25~13.45"},
    ]
}

_PLACEHOLDER_PREFIXES = (
    "1、原料bom：",
    "2、配方：",
    "5、下一步计划：",
    "6、工艺验证：",
)


def _normalize_sheet_date_value(value: Any) -> Optional[dt.date]:
    if value is None:
        return None
    if isinstance(value, float) and np.isnan(value):
        return None
    if isinstance(value, (dt.date, dt.datetime, pd.Timestamp)):
        ts = pd.to_datetime(value, errors="coerce")
        if pd.isna(ts):
            return None
        return ts.date()

    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None

    numeric_value: Optional[float] = None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        numeric_value = float(value)
    else:
        try:
            numeric_value = float(text)
        except Exception:
            numeric_value = None

    if numeric_value is not None:
        # Excel 序列日期（天数）
        if 20000 <= numeric_value <= 70000:
            ts = pd.to_datetime(numeric_value, unit="D", origin="1899-12-30", errors="coerce")
            if not pd.isna(ts):
                return ts.date()
        # Unix 毫秒时间戳
        if 1e12 <= numeric_value < 1e15:
            ts = pd.to_datetime(numeric_value, unit="ms", errors="coerce")
            if not pd.isna(ts):
                return ts.date()
        # Unix 秒时间戳
        if 1e9 <= numeric_value < 1e11:
            ts = pd.to_datetime(numeric_value, unit="s", errors="coerce")
            if not pd.isna(ts):
                return ts.date()

    ts = pd.to_datetime(text, errors="coerce")
    if pd.isna(ts):
        return None
    return ts.date()


def load_sheet_table_from_matrix(values: list[list[Any]]) -> pd.DataFrame:
    raw = pd.DataFrame(values if isinstance(values, list) else [])
    if raw.empty:
        raise ValueError("在线表格数据为空")

    header_start = _find_row_contains(raw, "批次") or 0
    data_start = _find_data_start(raw, header_start=header_start)
    if data_start is None or data_start <= header_start:
        raise ValueError("无法定位数据起始行")

    header_df = raw.iloc[header_start:data_start, :]
    cols = _make_columns_from_multirow_header(header_df)
    df = raw.iloc[data_start:, :].copy()
    df.columns = cols
    df = df.dropna(how="all")

    if "投料日期" in df.columns:
        s = df["投料日期"].map(_normalize_sheet_date_value)
        s = s.ffill()
        df["投料日期"] = s
    if "批次" in df.columns:
        s = df["批次"].astype(str).str.strip().replace({"": np.nan, "nan": np.nan})
        df["批次"] = s.ffill()
    if "是否为验证批次" in df.columns:
        s = df["是否为验证批次"].astype(str).str.strip().replace({"": np.nan, "nan": np.nan})
        df["是否为验证批次"] = s.ffill()
    return df


def load_spec_registry_from_json_text(spec_registry_json: str) -> list[SpecRule]:
    payload: Any
    raw = (spec_registry_json or "").strip()
    if raw:
        try:
            payload = json.loads(raw)
        except Exception as exc:
            raise ValueError(f"spec_registry_json 不是合法 JSON：{exc}") from exc
    else:
        payload = _DEFAULT_SPEC_REGISTRY_PAYLOAD

    items: list[Any]
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        maybe = payload.get("rules", [])
        items = maybe if isinstance(maybe, list) else []
    else:
        items = []

    rules: list[SpecRule] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        metric = _sanitize_col(item.get("metric", ""))
        spec_text = _sanitize_col(item.get("spec", ""))
        if not metric or not spec_text:
            continue

        model_raw = _sanitize_col(item.get("model", ""))
        model = model_raw.upper() if model_raw else None
        spec = _parse_spec_literal(spec_text)
        if spec is None:
            continue
        rules.append(SpecRule(metric=metric, model=model, spec=spec))
    return rules


def strip_placeholder_sections(text: str) -> str:
    if not text:
        return ""
    lines = []
    for line in text.splitlines():
        if any(line.strip().startswith(prefix) for prefix in _PLACEHOLDER_PREFIXES):
            continue
        lines.append(line)

    renumbered: list[str] = []
    section_index = 1
    for line in lines:
        if re.match(r"^\d+、", line):
            line = re.sub(r"^\d+、", f"{section_index}、", line, count=1)
            section_index += 1
        renumbered.append(line)
    return "\n".join(renumbered).strip()


def build_standard_report_from_matrices(
    sheet_matrices: dict[str, list[list[Any]]],
    selected_sheets: Optional[list[str]],
    date_arg: Optional[str],
    date_mode: str,
    lookback_days: int,
    trend_days: int,
    stale_threshold_process: int,
    stale_threshold_product: int,
    stale_threshold_electrochem: int,
    report_show_placeholder_sections: bool,
    show_spec_attention: bool = True,
    spec_registry_json: str = "",
    auto_fix_quality: bool = False,
) -> dict[str, Any]:
    target_sheets = list(selected_sheets or sheet_matrices.keys())
    if not target_sheets:
        raise ValueError("未提供可查询工作表")

    line_dfs: dict[str, pd.DataFrame] = {}
    line_errors: list[str] = []
    for sheet_name in target_sheets:
        values = sheet_matrices.get(sheet_name)
        if values is None:
            line_errors.append(f"{sheet_name}: 工作表不存在")
            continue
        try:
            df = load_sheet_table_from_matrix(values)
            if not _has_effective_data_body(df):
                raise ValueError("无数据体")
            line_dfs[sheet_name] = df
        except Exception as exc:
            line_errors.append(f"{sheet_name}: {exc}")

    if not line_dfs:
        detail = "；".join(line_errors) if line_errors else "无可用数据"
        raise ValueError(f"没有可生成日报的线别：{detail}")

    anchor_date = _resolve_stale_sheet_anchor_date(date_arg)
    filtered_line_dfs: dict[str, pd.DataFrame] = {}
    for sheet_name, df in line_dfs.items():
        latest_date = _latest_feed_date(df)
        if not isinstance(latest_date, dt.date):
            filtered_line_dfs[sheet_name] = df
            continue

        lag_days = (anchor_date - latest_date).days
        if lag_days >= STALE_SHEET_SKIP_DAYS:
            line_errors.append(
                f"{sheet_name}: 最新投料日期{latest_date.strftime('%Y.%m.%d')}，距基准日{anchor_date.strftime('%Y.%m.%d')}已{lag_days}天，未纳入日报"
            )
            continue

        filtered_line_dfs[sheet_name] = df

    line_dfs = filtered_line_dfs
    if not line_dfs:
        return {
            "text": "当前无6天内更新的数据表，暂无可汇报数据。",
            "line_reports": [],
            "line_errors": line_errors,
            "used_sheets": [],
        }

    stale_cfg = StaleThresholdConfig(
        process_days=max(0, int(stale_threshold_process)),
        product_days=max(0, int(stale_threshold_product)),
        electrochem_days=max(0, int(stale_threshold_electrochem)),
    )
    spec_health_cfg = SpecHealthConfig()
    spec_registry_rules = load_spec_registry_from_json_text(spec_registry_json)
    report_dates = resolve_report_dates(line_dfs, date_arg, date_mode)

    line_reports: list[dict[str, Any]] = []
    for sheet_name, df in line_dfs.items():
        detected_model = detect_model_from_sheet(sheet_name)
        model = detected_model if detected_model != "UNKNOWN" else detected_model
        profile = PRODUCT_SPEC_PROFILES.get(model, get_profile_for_sheet(sheet_name))
        quality = validate_sheet_data(df, auto_fix=auto_fix_quality)
        df_for_metrics = quality["df"]
        report_date = report_dates[sheet_name]
        metrics = extract_metrics(
            df_for_metrics,
            report_date,
            max(0, int(lookback_days)),
            max(0, int(trend_days)),
            enable_spec=profile.enable_spec,
            line_label=sheet_name,
            model=model,
            stale_thresholds=stale_cfg,
            spec_registry=spec_registry_rules,
            spec_health=spec_health_cfg,
        )
        line_reports.append(
            {
                "line_label": sheet_name,
                "report_date": report_date,
                "model": model,
                "enable_spec": profile.enable_spec,
                "metrics": metrics,
                "quality_issues": quality["issues"],
                "quality_fixed_count": int(quality["fixed_count"]),
            }
        )

    line_reports.sort(key=lambda x: str(x.get("line_label", "")))
    if len(line_reports) == 1:
        report = line_reports[0]
        text = build_wecom_text_single(
            report_date=report["report_date"],
            metrics=report["metrics"],
            line_label=report["line_label"],
            model=str(report.get("model", "UNKNOWN")),
            enable_spec=bool(report.get("enable_spec", True)),
            quality_issues=report.get("quality_issues"),
            show_spec_attention=show_spec_attention,
        )
    else:
        text = build_wecom_text_multi(line_reports, show_spec_attention=show_spec_attention)

    if not report_show_placeholder_sections:
        text = strip_placeholder_sections(text)

    return {
        "text": text.strip(),
        "line_reports": line_reports,
        "line_errors": line_errors,
        "used_sheets": list(line_dfs.keys()),
    }


if __name__ == "__main__":
    raise SystemExit(main())
