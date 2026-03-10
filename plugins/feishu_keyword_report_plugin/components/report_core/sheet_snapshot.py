from __future__ import annotations

import base64
import io
import json
import math
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


@dataclass(frozen=True)
class SheetSnapshotImage:
    data_url: str
    selected_rows: list[int]
    max_col: int


def _cell_to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        return f"{value:g}"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value).replace("\r\n", "\n").replace("\r", "\n")


def _col_label(index: int) -> str:
    out = ""
    value = index
    while value > 0:
        value, rem = divmod(value - 1, 26)
        out = chr(65 + rem) + out
    return out


def _wrap_text(text: str, width_chars: int) -> list[str]:
    if not text:
        return [""]
    lines: list[str] = []
    for raw_line in text.split("\n"):
        wrapped = textwrap.wrap(raw_line, width=width_chars, break_long_words=True, break_on_hyphens=False)
        lines.extend(wrapped or [""])
    return lines or [""]


def _pick_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simsun.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _nonempty_row_indices(values: list[list[Any]]) -> list[int]:
    rows: list[int] = []
    for row_index, row in enumerate(values, start=1):
        if any(_cell_to_text(item).strip() for item in row):
            rows.append(row_index)
    return rows


def render_sheet_snapshot(
    sheet_title: str,
    values: list[list[Any]],
    header_rows: int = 3,
    tail_nonempty_rows: int = 20,
    chunk_size: int = 18,
) -> SheetSnapshotImage:
    nonempty_rows = _nonempty_row_indices(values)
    if not nonempty_rows:
        raise ValueError(f"{sheet_title} 没有可截图的数据。")

    last_rows = nonempty_rows[-max(0, int(tail_nonempty_rows)) :] if tail_nonempty_rows > 0 else []
    selected_rows: list[int] = []
    for row_index in list(range(1, max(0, int(header_rows)) + 1)) + last_rows:
        if row_index not in selected_rows:
            selected_rows.append(row_index)

    max_col = 0
    for row_index in selected_rows:
        row = values[row_index - 1] if row_index - 1 < len(values) else []
        last_nonempty = 0
        for col_index, item in enumerate(row, start=1):
            if _cell_to_text(item).strip():
                last_nonempty = col_index
        max_col = max(max_col, last_nonempty)
    if max_col <= 0:
        raise ValueError(f"{sheet_title} 没有可截图的数据。")

    text_map: dict[tuple[int, int], str] = {}
    for row_index in selected_rows:
        row = values[row_index - 1] if row_index - 1 < len(values) else []
        for col_index in range(1, max_col + 1):
            value = row[col_index - 1] if col_index - 1 < len(row) else ""
            text_map[(row_index, col_index)] = _cell_to_text(value)

    col_widths: dict[int, int] = {}
    for col_index in range(1, max_col + 1):
        max_len = len(_col_label(col_index))
        for row_index in selected_rows:
            max_len = max(max_len, len(text_map.get((row_index, col_index), "")))
        col_widths[col_index] = min(200, max(90, 18 + max_len * 7))

    chunks: list[tuple[int, int]] = []
    start_col = 1
    while start_col <= max_col:
        end_col = min(max_col, start_col + max(1, int(chunk_size)) - 1)
        chunks.append((start_col, end_col))
        start_col = end_col + 1

    title_font = _pick_font(24)
    body_font = _pick_font(15)
    small_font = _pick_font(13)

    margin = 24
    sheet_title_height = 72
    chunk_title_height = 28
    header_height = 46
    separator_height = 34
    row_num_width = 70
    row_base_height = 28
    panel_gap = 28

    row_blocks: list[tuple[str, int | str]] = [("data", row_index) for row_index in range(1, header_rows + 1)]
    if last_rows:
        row_blocks.append(("separator", "... skipped to last non-empty rows ..."))
    for row_index in last_rows:
        if row_index > header_rows:
            row_blocks.append(("data", row_index))

    panel_specs: list[tuple[int, int, int, int, list[int]]] = []
    for start_col, end_col in chunks:
        panel_width = row_num_width + sum(col_widths[col] for col in range(start_col, end_col + 1))
        panel_height = chunk_title_height + header_height
        row_heights: list[int] = []
        for block_type, payload in row_blocks:
            if block_type == "separator":
                row_heights.append(separator_height)
                panel_height += separator_height
                continue
            row_index = int(payload)
            max_lines = 1
            for col_index in range(start_col, end_col + 1):
                width_chars = max(6, int((col_widths[col_index] - 12) / 7))
                lines = _wrap_text(text_map.get((row_index, col_index), ""), width_chars)
                max_lines = max(max_lines, len(lines))
            row_height = max(row_base_height, 10 + max_lines * 18)
            row_heights.append(row_height)
            panel_height += row_height
        panel_specs.append((start_col, end_col, panel_width, panel_height, row_heights))

    image_width = max(margin * 2 + spec[2] for spec in panel_specs)
    image_height = sheet_title_height + margin * 2 + sum(spec[3] for spec in panel_specs) + panel_gap * (len(panel_specs) - 1)
    image = Image.new("RGB", (image_width, image_height), "white")
    draw = ImageDraw.Draw(image)

    text_color = "#0f172a"
    muted = "#475569"
    grid = "#cbd5e1"
    header_bg = "#e2e8f0"
    row_header_bg = "#f1f5f9"
    section_bg = "#f8fafc"
    separator_bg = "#fff7ed"

    draw.text((margin, margin), f"Feishu Sheets 内容截图 - {sheet_title}", fill=text_color, font=title_font)
    draw.text(
        (margin, margin + 32),
        f"范围: 前 {header_rows} 行表头 + 最后 {tail_nonempty_rows} 行非空数据",
        fill=muted,
        font=small_font,
    )
    draw.text(
        (margin, margin + 50),
        f"原始行号: {', '.join(str(item) for item in selected_rows)}",
        fill=muted,
        font=small_font,
    )

    current_y = margin + sheet_title_height
    for start_col, end_col, panel_width, panel_height, row_heights in panel_specs:
        panel_x = margin
        draw.text((panel_x, current_y), f"列 {_col_label(start_col)}-{_col_label(end_col)}", fill=text_color, font=body_font)
        y = current_y + chunk_title_height

        x = panel_x
        draw.rectangle([x, y, x + row_num_width, y + header_height], fill=row_header_bg, outline=grid, width=1)
        draw.text((x + 10, y + 12), "#", fill=text_color, font=body_font)
        x += row_num_width
        for col_index in range(start_col, end_col + 1):
            width = col_widths[col_index]
            draw.rectangle([x, y, x + width, y + header_height], fill=header_bg, outline=grid, width=1)
            draw.text((x + 8, y + 12), _col_label(col_index), fill=text_color, font=body_font)
            x += width
        y += header_height

        row_height_iter = iter(row_heights)
        for block_type, payload in row_blocks:
            row_height = next(row_height_iter)
            if block_type == "separator":
                draw.rectangle([panel_x, y, panel_x + panel_width, y + row_height], fill=separator_bg, outline=grid, width=1)
                draw.text((panel_x + 12, y + 8), str(payload), fill=muted, font=small_font)
                y += row_height
                continue

            row_index = int(payload)
            row_fill = section_bg if row_index <= header_rows else "white"
            x = panel_x
            draw.rectangle([x, y, x + row_num_width, y + row_height], fill=row_header_bg, outline=grid, width=1)
            draw.text((x + 8, y + 8), str(row_index), fill=text_color, font=body_font)
            x += row_num_width
            for col_index in range(start_col, end_col + 1):
                width = col_widths[col_index]
                draw.rectangle([x, y, x + width, y + row_height], fill=row_fill, outline=grid, width=1)
                width_chars = max(6, int((width - 12) / 7))
                lines = _wrap_text(text_map.get((row_index, col_index), ""), width_chars)
                text_y = y + 6
                max_visible_lines = max(1, (row_height - 10) // 18)
                for line in lines[:max_visible_lines]:
                    draw.text((x + 6, text_y), line, fill=text_color, font=small_font)
                    text_y += 18
                x += width
            y += row_height
        current_y += panel_height + panel_gap

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    png_bytes = buffer.getvalue()
    data_url = "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")
    return SheetSnapshotImage(data_url=data_url, selected_rows=selected_rows, max_col=max_col)
