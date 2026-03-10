from __future__ import annotations

import base64
import io
import json
import math
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


def _measure_text_width(font: ImageFont.FreeTypeFont | ImageFont.ImageFont, text: str) -> int:
    if not text:
        return 0
    if hasattr(font, "getlength"):
        return int(math.ceil(float(font.getlength(text))))
    bbox = font.getbbox(text)
    return int(bbox[2] - bbox[0])


def _wrap_text_to_width(
    text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont, max_width: int
) -> list[str]:
    if not text:
        return [""]

    wrapped_lines: list[str] = []
    for source_line in text.split("\n"):
        if not source_line:
            wrapped_lines.append("")
            continue

        current = ""
        for ch in source_line:
            candidate = current + ch
            if current and _measure_text_width(font, candidate) > max_width:
                wrapped_lines.append(current)
                current = ch
            else:
                current = candidate
        wrapped_lines.append(current or "")

    return wrapped_lines or [""]


def _pick_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    plugin_root = Path(__file__).resolve().parents[2]
    candidates = [
        plugin_root / "assets" / "fonts" / "NotoSansCJKsc-Regular.otf",
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simsun.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            return ImageFont.truetype(str(path), size)
        except Exception:
            continue
    return ImageFont.load_default()


def _nonempty_row_indices(values: list[list[Any]]) -> list[int]:
    row_indices: list[int] = []
    for row_index, row in enumerate(values, start=1):
        if any(_cell_to_text(item).strip() for item in row):
            row_indices.append(row_index)
    return row_indices


def _preferred_col_width(
    texts: list[str], font: ImageFont.FreeTypeFont | ImageFont.ImageFont, min_width: int, max_width: int
) -> int:
    width = min_width
    for text in texts:
        for line in text.split("\n"):
            width = max(width, _measure_text_width(font, line[:60]) + 18)
    return min(max_width, max(min_width, width))


def render_sheet_snapshot(
    sheet_title: str,
    values: list[list[Any]],
    header_rows: int = 3,
    tail_nonempty_rows: int = 20,
    chunk_size: int = 18,
) -> SheetSnapshotImage:
    del chunk_size

    nonempty_rows = _nonempty_row_indices(values)
    if not nonempty_rows:
        raise ValueError(f"{sheet_title} has no data to capture.")

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
        raise ValueError(f"{sheet_title} has no data to capture.")

    text_map: dict[tuple[int, int], str] = {}
    for row_index in selected_rows:
        row = values[row_index - 1] if row_index - 1 < len(values) else []
        for col_index in range(1, max_col + 1):
            value = row[col_index - 1] if col_index - 1 < len(row) else ""
            text_map[(row_index, col_index)] = _cell_to_text(value)

    title_font = _pick_font(22)
    header_font = _pick_font(14)
    body_font = _pick_font(13)
    meta_font = _pick_font(12)

    row_num_width = 72
    min_col_width = 72
    max_col_width = 180
    cell_padding_x = 8
    cell_padding_y = 6
    line_height = 17
    row_min_height = 28
    title_height = 74
    header_height = 44
    separator_height = 30
    margin = 24

    col_widths: dict[int, int] = {}
    for col_index in range(1, max_col + 1):
        texts = [_col_label(col_index)]
        texts.extend(text_map.get((row_index, col_index), "") for row_index in selected_rows)
        col_widths[col_index] = _preferred_col_width(texts, body_font, min_col_width, max_col_width)

    row_blocks: list[tuple[str, int | str]] = [("data", row_index) for row_index in range(1, header_rows + 1)]
    if last_rows:
        row_blocks.append(("separator", "... skipped to last non-empty rows ..."))
    for row_index in last_rows:
        if row_index > header_rows:
            row_blocks.append(("data", row_index))

    row_heights: list[int] = []
    for block_type, payload in row_blocks:
        if block_type == "separator":
            row_heights.append(separator_height)
            continue

        row_index = int(payload)
        max_lines = 1
        for col_index in range(1, max_col + 1):
            width = max(20, col_widths[col_index] - cell_padding_x * 2)
            lines = _wrap_text_to_width(text_map.get((row_index, col_index), ""), body_font, width)
            max_lines = max(max_lines, len(lines))
        row_heights.append(max(row_min_height, cell_padding_y * 2 + max_lines * line_height))

    table_width = row_num_width + sum(col_widths[col_index] for col_index in range(1, max_col + 1))
    table_height = header_height + sum(row_heights)
    image_width = margin * 2 + table_width
    image_height = margin * 2 + title_height + table_height

    image = Image.new("RGB", (image_width, image_height), "white")
    draw = ImageDraw.Draw(image)

    text_color = "#0f172a"
    muted = "#475569"
    grid = "#cbd5e1"
    header_bg = "#e2e8f0"
    row_header_bg = "#f1f5f9"
    top_header_bg = "#f8fafc"
    separator_bg = "#fff7ed"

    draw.text((margin, margin), f"Sheet Snapshot - {sheet_title}", fill=text_color, font=title_font)
    draw.text(
        (margin, margin + 30),
        f"Rows: first {header_rows} header rows + last {tail_nonempty_rows} non-empty rows",
        fill=muted,
        font=meta_font,
    )
    draw.text(
        (margin, margin + 48),
        f"Original rows: {', '.join(str(item) for item in selected_rows)}",
        fill=muted,
        font=meta_font,
    )

    table_x = margin
    table_y = margin + title_height

    x = table_x
    draw.rectangle([x, table_y, x + row_num_width, table_y + header_height], fill=row_header_bg, outline=grid, width=1)
    draw.text((x + 10, table_y + 12), "#", fill=text_color, font=header_font)
    x += row_num_width
    for col_index in range(1, max_col + 1):
        width = col_widths[col_index]
        draw.rectangle([x, table_y, x + width, table_y + header_height], fill=header_bg, outline=grid, width=1)
        draw.text((x + cell_padding_x, table_y + 12), _col_label(col_index), fill=text_color, font=header_font)
        x += width

    current_y = table_y + header_height
    row_height_iter = iter(row_heights)
    for block_type, payload in row_blocks:
        row_height = next(row_height_iter)
        if block_type == "separator":
            draw.rectangle(
                [table_x, current_y, table_x + table_width, current_y + row_height],
                fill=separator_bg,
                outline=grid,
                width=1,
            )
            draw.text((table_x + 12, current_y + 8), str(payload), fill=muted, font=meta_font)
            current_y += row_height
            continue

        row_index = int(payload)
        row_fill = top_header_bg if row_index <= header_rows else "white"
        x = table_x
        draw.rectangle([x, current_y, x + row_num_width, current_y + row_height], fill=row_header_bg, outline=grid, width=1)
        draw.text((x + 8, current_y + 7), str(row_index), fill=text_color, font=header_font)
        x += row_num_width
        for col_index in range(1, max_col + 1):
            width = col_widths[col_index]
            draw.rectangle([x, current_y, x + width, current_y + row_height], fill=row_fill, outline=grid, width=1)
            lines = _wrap_text_to_width(
                text_map.get((row_index, col_index), ""),
                body_font,
                max(20, width - cell_padding_x * 2),
            )
            text_y = current_y + cell_padding_y
            max_visible_lines = max(1, (row_height - cell_padding_y * 2) // line_height)
            for line in lines[:max_visible_lines]:
                draw.text((x + cell_padding_x, text_y), line, fill=text_color, font=body_font)
                text_y += line_height
            x += width
        current_y += row_height

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True, compress_level=6)
    data_url = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
    return SheetSnapshotImage(data_url=data_url, selected_rows=selected_rows, max_col=max_col)
