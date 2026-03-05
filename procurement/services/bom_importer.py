# procurement/services/bom_importer.py
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re
from typing import Any, Dict, List, Optional, Tuple

import openpyxl

from masters.models import Item, normalize_item_description


def _h(s: Any) -> str:
    """Normalize header cell text."""
    if s is None:
        return ""
    s = str(s).strip().lower()
    s = s.replace("\n", " ")
    s = re.sub(r"\s+", " ", s)
    return s


def _to_decimal(v: Any) -> Optional[Decimal]:
    if v is None:
        return None
    if isinstance(v, (int, float, Decimal)):
        try:
            return Decimal(str(v))
        except Exception:
            return None
    s = str(v).strip()
    if s == "":
        return None
    # remove commas
    s = s.replace(",", "")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


# Canonical fields and their possible header aliases (company differences)
ALIASES = {
    # REQUIRED (at least one of these must be found)
    "item_description": [
        "item description", "item", "description", "member", "profile", "section", "main section",
        "material", "item desc", "item-description"
    ],

    # OPTIONAL but supported
    "mark_no": [
        "mark no", "mark", "mark_no", "mark number", "fabrication mark no", "fab mark no",
        "member mark", "m/c mark", "mc mark"
    ],
    "item_no": ["item no", "item number", "item_no", "itm no", "sr no", "s.no", "sno"],
    "qty_all": ["qty all", "unit qty", "qty", "quantity", "nos", "no.", "no's", "total qty"],
    "length": ["length", "len", "cut length", "lg", "l (mm)", "length (mm)"],
    "width": ["width", "w", "wd", "b (mm)", "width (mm)"],
    "thk": ["thickness", "thk", "p thk", "plate thk", "t (mm)", "thickness (mm)"],
    "unit_wt": ["unit wt", "unit weight", "wt", "weight", "unit-wt", "unitweight"],
    "drawing_no": ["drawing no", "dwg no", "drg no", "drawing", "dwg", "drg"],
}


IGNORE_SHEET_NAME_CONTAINS = ["summary", "notes", "index", "cover"]


@dataclass
class ExtractedRow:
    sheet_name: str
    excel_row: int

    mark_no: str
    drawing_no: str
    item_no: str

    item_description_raw: str
    item_id: int

    qty_all: Decimal
    length_mm: Optional[Decimal]
    width_mm: Optional[Decimal]
    thk_mm: Optional[Decimal]
    line_weight_kg: Optional[Decimal]


def detect_header_row(ws, max_scan_rows: int = 40) -> Tuple[Optional[int], Optional[List[str]]]:
    """
    Find the best header row by looking for presence of required alias 'item_description'
    and at least one other known header.
    """
    for r in range(1, min(max_scan_rows, ws.max_row) + 1):
        row_vals = [ws.cell(row=r, column=c).value for c in range(1, ws.max_column + 1)]
        headers = [_h(v) for v in row_vals]

        # required: item_description alias present
        has_item_desc = any(hdr in ALIASES["item_description"] for hdr in headers)
        if not has_item_desc:
            continue

        # at least one more field hint
        other_hits = 0
        for key in ("mark_no", "qty_all", "item_no", "unit_wt", "length"):
            if any(hdr in ALIASES[key] for hdr in headers):
                other_hits += 1
        if other_hits >= 1:
            return r, headers

    return None, None


def build_col_map(headers: List[str]) -> Dict[str, int]:
    col_map: Dict[str, int] = {}
    for idx, htxt in enumerate(headers):
        for canonical, aliases in ALIASES.items():
            if canonical in col_map:
                continue
            if htxt in aliases:
                col_map[canonical] = idx
                break
    return col_map


def get_cell(row: List[Any], col_map: Dict[str, int], key: str) -> Any:
    idx = col_map.get(key)
    if idx is None:
        return None
    if idx >= len(row):
        return None
    return row[idx]


def validate_and_extract_workbook(xlsx_path: str) -> Dict[str, Any]:
    """
    Returns:
      ok: bool
      summary: dict
      errors: list of dict (mismatch / parse issues)
      extracted: list of ExtractedRow (only if ok)
      detected: per sheet meta
    """
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)

    # Preload item norms → (id, description) for fast match + suggestions
    items = list(Item.objects.filter(is_active=True).only("id", "item_description", "item_description_norm"))
    item_by_norm = {it.item_description_norm: it for it in items}

    extracted: List[ExtractedRow] = []
    errors: List[Dict[str, Any]] = []
    detected: Dict[str, Any] = {}

    sheets_used = 0

    for sheet_name in wb.sheetnames:
        if any(x in sheet_name.lower() for x in IGNORE_SHEET_NAME_CONTAINS):
            continue

        ws = wb[sheet_name]
        header_row, headers = detect_header_row(ws)
        if not header_row or not headers:
            detected[sheet_name] = {"skipped": True, "reason": "header_not_detected"}
            continue

        col_map = build_col_map(headers)

        # required: item_description must be mapped
        if "item_description" not in col_map:
            detected[sheet_name] = {"skipped": True, "reason": "item_description_column_not_found", "header_row": header_row}
            continue

        sheets_used += 1
        detected[sheet_name] = {"skipped": False, "header_row": header_row, "col_map": col_map}

        last_mark = ""
        last_drawing = ""

        for r in range(header_row + 1, ws.max_row + 1):
            row_vals = [ws.cell(row=r, column=c).value for c in range(1, ws.max_column + 1)]

            # skip empty rows
            if all(v is None or str(v).strip() == "" for v in row_vals):
                continue

            item_desc = get_cell(row_vals, col_map, "item_description")
            if item_desc is None or str(item_desc).strip() == "":
                continue

            item_desc_raw = str(item_desc).strip()

            # optional fields
            mark_no = get_cell(row_vals, col_map, "mark_no")
            drawing_no = get_cell(row_vals, col_map, "drawing_no")
            item_no = get_cell(row_vals, col_map, "item_no")

            qty_all = get_cell(row_vals, col_map, "qty_all")
            length_mm = get_cell(row_vals, col_map, "length")
            width_mm = get_cell(row_vals, col_map, "width")
            thk_mm = get_cell(row_vals, col_map, "thk")
            unit_wt = get_cell(row_vals, col_map, "unit_wt")

            # carry forward mark/drawing if blank (common in Frigate)
            if mark_no is not None and str(mark_no).strip():
                last_mark = str(mark_no).strip()
            mark_no_final = last_mark

            if drawing_no is not None and str(drawing_no).strip():
                last_drawing = str(drawing_no).strip()
            drawing_no_final = last_drawing

            item_no_final = str(item_no).strip() if item_no is not None else ""

            # qty: if column missing or blank, default to 1 (safe for validation phase)
            qty_dec = _to_decimal(qty_all) or Decimal("1")

            # match item master strictly
            norm = normalize_item_description(item_desc_raw)
            it = item_by_norm.get(norm)
            if not it:
                # suggestions: simple contains based on first 5 chars
                hint = item_desc_raw.replace(" ", "")[:6]
                sugg = [x.item_description for x in items if hint.lower() in (x.item_description_norm or "")]
                errors.append({
                    "type": "ITEM_MISMATCH",
                    "sheet_name": sheet_name,
                    "excel_row": r,
                    "mark_no": mark_no_final,
                    "item_no": item_no_final,
                    "item_description_in_bom": item_desc_raw,
                    "normalized": norm,
                    "message": "Item Description not found in Item Master (must match item_description).",
                    "suggestions": sugg[:8],
                })
                continue

            extracted.append(ExtractedRow(
                sheet_name=sheet_name,
                excel_row=r,
                mark_no=mark_no_final,
                drawing_no=drawing_no_final,
                item_no=item_no_final,
                item_description_raw=item_desc_raw,
                item_id=it.id,
                qty_all=qty_dec,
                length_mm=_to_decimal(length_mm),
                width_mm=_to_decimal(width_mm),
                thk_mm=_to_decimal(thk_mm),
                line_weight_kg=_to_decimal(unit_wt),
            ))

    summary = {
        "sheets_total": len(wb.sheetnames),
        "sheets_used": sheets_used,
        "rows_extracted": len(extracted),
        "marks_found": len({(x.sheet_name, x.mark_no) for x in extracted if x.mark_no}),
        "errors": len(errors),
    }

    return {
        "ok": len(errors) == 0,
        "summary": summary,
        "errors": errors,
        "extracted": extracted if len(errors) == 0 else [],
        "detected": detected,
    }