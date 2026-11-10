"""Excel merge helper for the standalone merge tool (folder ``merge/``).

This module is intentionally **self-contained**: it imports nothing from the
original tool's ``scripts/`` package, so the merge tool can never affect the
original tool.

Sheet layout produced by the original tool (per run):

  Summary      header + one row per model + Gemini reference row + spacer
               + ranking title + ranking header + one row per model
  Categories   header + 9 rows per model (8 axes + total)
  Gates        header + 8 rows per model
  Questions    header + 33 rows per model
  Profile      header + 14 rows per model
  Rubric       header + 165 rows per model (33 questions x 5 criteria)
  Fit          header + 1 row per model + one trailing note row
  Performance  header + 1 row per model (+ optional note row)
  SpeedDetail  2 key columns + 4 columns per model
               (seconds / tok-s / tokens / finish)
  Settings     header + 1 row per model (+ warning rows)
  Answers      header + 33 rows per model
  Meta         header + global rows + llama.cpp rows + per-model rows
"""
from __future__ import annotations

import pathlib
from copy import copy

#: Row labels that mark a trailing note (kept once, at the very end).
NOTE_PREFIXES = ("تنويه", "مفيش بيانات")

#: Meta labels that belong to a single model (not to the run).
META_MODEL_PREFIXES = (
    "quant ",
    "قالب SHA",
    "prompt SHA",
    "server log ",
    "زمن التشغيل",
)

#: Meta label holding the model count.
META_COUNT_LABEL = "عدد الموديلات"

#: Emoji used by the ranking table title.
RANK_MARK = "\U0001F3AF"


# ═════════════════════════════════════════════════════════ helpers
def _has_value(cell) -> bool:
    return cell.value is not None and str(cell.value).strip() != ""


def _row_is_blank(ws, row_idx: int) -> bool:
    return not any(
        _has_value(ws.cell(row=row_idx, column=c))
        for c in range(1, ws.max_column + 1)
    )


def _is_note_row(ws, row_idx: int) -> bool:
    """صف ملاحظة/تنبيه — بيتنقل مرة واحدة بس في آخر الشيت."""
    first = str(ws.cell(row=row_idx, column=1).value or "").strip()
    return any(first.startswith(prefix) for prefix in NOTE_PREFIXES)


def _snapshot(ws, row_idx: int, cols) -> list:
    """يلتقط قيم صف + تنسيقاته (نسخة مستقلة عن الـworkbook الأصلي)."""
    out = []
    for c in cols:
        cell = ws.cell(row=row_idx, column=c)
        styled = cell.has_style
        out.append(
            (
                cell.value,
                copy(cell.font) if styled else None,
                copy(cell.fill) if styled else None,
                copy(cell.border) if styled else None,
                copy(cell.alignment) if styled else None,
                cell.number_format if styled else "General",
            )
        )
    return out


def _restore(ws, row_idx: int, snap: list, overrides: dict | None = None) -> None:
    """يكتب صف ملتقَط في الشيت الهدف (مع إمكانية تعديل خلايا محددة)."""
    overrides = overrides or {}
    for i, item in enumerate(snap, start=1):
        value, font, fill, border, alignment, number_format = item
        cell = ws.cell(row=row_idx, column=i)
        cell.value = overrides[i] if i in overrides else value
        if font is not None:
            cell.font = font
            cell.fill = fill
            cell.border = border
            cell.alignment = alignment
            cell.number_format = number_format


def _last_number(ws, row_idx: int):
    """آخر قيمة رقمية في الصف (بستخدمها لمسافة القرب من المرجع)."""
    for c in range(ws.max_column, 0, -1):
        value = ws.cell(row=row_idx, column=c).value
        if isinstance(value, (int, float)):
            return float(value)
        if value is not None and str(value).strip() not in ("", "—", "-"):
            try:
                return float(str(value).strip())
            except ValueError:
                continue
    return None


def _finalize_sheet(ws, freeze: str = "A2", auto_filter: bool = True) -> None:
    ws.freeze_panes = freeze
    ws.sheet_view.rightToLeft = True
    ws.auto_filter.ref = ws.dimensions if auto_filter else None


# ═════════════════════════════════════════════════════════ data sheets
def _merge_data_sheet(ws_out, sources) -> int:
    """صفوف النماذج: بنضيف صفوف كل مصدر تحت بعض (الهيدر بيفضل من الأول)."""
    added = 0
    notes: list[list] = []

    # ملاحظات موجودة في الملف الأول — لازم تفضل في الآخر
    for r in range(ws_out.max_row, 1, -1):
        if _is_note_row(ws_out, r):
            notes.append(_snapshot(ws_out, r, range(1, ws_out.max_column + 1)))
            ws_out.delete_rows(r)

    for ws_in in sources:
        cols = range(1, ws_in.max_column + 1)
        for r in range(2, ws_in.max_row + 1):
            if _row_is_blank(ws_in, r):
                continue
            if _is_note_row(ws_in, r):
                if not notes:
                    notes.append(_snapshot(ws_in, r, cols))
                continue
            _restore(ws_out, ws_out.max_row + 1, _snapshot(ws_in, r, cols))
            added += 1

    for snap in notes:
        _restore(ws_out, ws_out.max_row + 1, snap)

    _finalize_sheet(ws_out)
    return added


# ═════════════════════════════════════════════════════════ SpeedDetail
def _merge_speed_sheet(ws_out, sources) -> int:
    """SpeedDetail: الأعمدة بتتمدد — 4 أعمدة لكل موديل بعد عمودين أساسيين."""
    added = 0
    base_rows = ws_out.max_row
    for ws_in in sources:
        start_col = ws_out.max_column + 1
        for c in range(3, ws_in.max_column + 1):
            target_col = start_col + (c - 3)
            for r in range(1, min(ws_in.max_row, base_rows) + 1):
                src = ws_in.cell(row=r, column=c)
                dst = ws_out.cell(row=r, column=target_col)
                dst.value = src.value
                if src.has_style:
                    dst.font = copy(src.font)
                    dst.fill = copy(src.fill)
                    dst.border = copy(src.border)
                    dst.alignment = copy(src.alignment)
                    dst.number_format = src.number_format
            letter = ws_in.cell(row=1, column=c).column_letter
            width = ws_in.column_dimensions[letter].width
            if width:
                ws_out.column_dimensions[
                    ws_out.cell(row=1, column=target_col).column_letter
                ].width = width
            added += 1
    ws_out.freeze_panes = "C2"
    ws_out.sheet_view.rightToLeft = True
    return added


# ═════════════════════════════════════════════════════════ Summary
def _summary_blocks(ws):
    """بيرجع (صف المرجع، صف عنوان الترتيب، صف هيدر الترتيب)."""
    gemini_row = rank_title = rank_header = None
    for r in range(1, ws.max_row + 1):
        a = str(ws.cell(row=r, column=1).value or "").strip()
        b = str(ws.cell(row=r, column=2).value or "")
        if gemini_row is None and a in ("—", "-", "") and "Gemini" in b:
            gemini_row = r
        if rank_title is None and a.startswith(RANK_MARK):
            rank_title = r
            rank_header = r + 1
    return gemini_row, rank_title, rank_header


def _merge_summary_sheet(wb_out, wbs, ref_total=None, model_count=None) -> int:
    """Summary: جدول الموديلات + صف المرجع + جدول ترتيب القرب — كلهم في شيت واحد."""
    old = wb_out["Summary"]
    index = wb_out.sheetnames.index("Summary")
    widths = {
        key: dim.width for key, dim in old.column_dimensions.items() if dim.width
    }

    header_snap = None
    model_snaps: list[list] = []
    gemini_snap = None
    title_snap = None
    rank_header_snap = None
    rank_rows: list[tuple] = []  # (distance, snapshot)

    for wb in wbs:
        if "Summary" not in wb.sheetnames:
            continue
        ws = wb["Summary"]
        cols = range(1, ws.max_column + 1)
        gemini_row, rank_title, rank_header = _summary_blocks(ws)
        if header_snap is None:
            header_snap = _snapshot(ws, 1, cols)
        model_end = gemini_row or rank_title or (ws.max_row + 1)
        for r in range(2, model_end):
            if _row_is_blank(ws, r):
                continue
            model_snaps.append(_snapshot(ws, r, cols))
        if gemini_row and gemini_snap is None:
            gemini_snap = _snapshot(ws, gemini_row, cols)
        if rank_title:
            if title_snap is None:
                title_snap = _snapshot(ws, rank_title, cols)
                rank_header_snap = _snapshot(ws, rank_header, cols)
            for r in range(rank_header + 1, ws.max_row + 1):
                if _row_is_blank(ws, r):
                    continue
                rank_rows.append((_last_number(ws, r), _snapshot(ws, r, cols)))

    wb_out.remove(old)
    ws = wb_out.create_sheet("Summary", index)

    if header_snap:
        _restore(ws, 1, header_snap)

    row = ws.max_row + 1
    for i, snap in enumerate(model_snaps, 1):
        _restore(ws, row, snap, overrides={1: i})
        row += 1

    if gemini_snap:
        overrides = {}
        if ref_total is not None:
            overrides[4] = ref_total
        _restore(ws, row, gemini_snap, overrides=overrides)
        row += 1

    row += 1  # سطر فاصل

    if title_snap:
        _restore(ws, row, title_snap)
        row += 1
        _restore(ws, row, rank_header_snap)
        row += 1
        rank_rows.sort(key=lambda item: (item[0] is None, item[0]))
        for i, (_, snap) in enumerate(rank_rows, 1):
            _restore(ws, row, snap, overrides={1: i})
            row += 1

    for key, width in widths.items():
        ws.column_dimensions[key].width = width
    _finalize_sheet(ws)
    return len(model_snaps)


# ═════════════════════════════════════════════════════════ Meta
def _meta_kind(ws, row_idx: int) -> str:
    first = str(ws.cell(row=row_idx, column=1).value or "").strip()
    if first.startswith("llama.cpp"):
        return "llama"
    if any(first.startswith(prefix) for prefix in META_MODEL_PREFIXES):
        return "model"
    return "global"


def _merge_meta_sheet(wb_out, wbs, model_count=None) -> int:
    """Meta: الصفوف العامة من أول تشغيل + صفوف كل موديل من كل التشغيلات."""
    old = wb_out["Meta"]
    index = wb_out.sheetnames.index("Meta")
    widths = {
        key: dim.width for key, dim in old.column_dimensions.items() if dim.width
    }

    header_snap = None
    globals_: list[list] = []
    llama_rows: list[tuple[str, list]] = []
    model_rows: list[list] = []
    seen_llama: set[str] = set()

    for wb_index, wb in enumerate(wbs):
        if "Meta" not in wb.sheetnames:
            continue
        ws = wb["Meta"]
        cols = range(1, ws.max_column + 1)
        if header_snap is None:
            header_snap = _snapshot(ws, 1, cols)
        for r in range(2, ws.max_row + 1):
            if _row_is_blank(ws, r):
                continue
            kind = _meta_kind(ws, r)
            if kind == "global":
                # الصفوف العامة (تواريخ التشغيل · الإعدادات · المرجع) بتتكرر
                # في كل ملف — بناخدها من أول تشغيل بس.
                if wb_index != 0:
                    continue
                label = str(ws.cell(row=r, column=1).value or "").strip()
                if label == META_COUNT_LABEL and model_count is not None:
                    snap = _snapshot(ws, r, cols)
                    snap[1] = (model_count, *snap[1][1:])
                    globals_.append(snap)
                else:
                    globals_.append(_snapshot(ws, r, cols))
            elif kind == "llama":
                version = str(ws.cell(row=r, column=2).value or "")
                if version in seen_llama:
                    continue
                seen_llama.add(version)
                llama_rows.append((version, _snapshot(ws, r, cols)))
            else:
                model_rows.append(_snapshot(ws, r, cols))

    wb_out.remove(old)
    ws = wb_out.create_sheet("Meta", index)

    if header_snap:
        _restore(ws, 1, header_snap)
    row = ws.max_row + 1
    for snap in globals_:
        _restore(ws, row, snap)
        row += 1
    for _, snap in llama_rows:
        _restore(ws, row, snap)
        row += 1
    for snap in model_rows:
        _restore(ws, row, snap)
        row += 1

    for key, width in widths.items():
        ws.column_dimensions[key].width = width
    _finalize_sheet(ws, auto_filter=False)
    return len(model_rows)


# ═════════════════════════════════════════════════════════ color scale
def _refresh_color_scale(ws, column: int) -> None:
    """يعيد تطبيق تدرج اللون على عمود النسبة بعد إضافة صفوف جديدة."""
    from openpyxl.formatting.rule import ColorScaleRule
    from openpyxl.utils import get_column_letter

    if ws.max_row < 2:
        return
    try:
        ws.conditional_formatting = type(ws.conditional_formatting)()
    except Exception:
        pass
    letter = get_column_letter(column)
    ws.conditional_formatting.add(
        f"{letter}2:{letter}{ws.max_row}",
        ColorScaleRule(
            start_type="num",
            start_value=0,
            start_color="F8696B",
            mid_type="num",
            mid_value=50,
            mid_color="FFEB84",
            end_type="num",
            end_value=100,
            end_color="63BE7B",
        ),
    )


# ═════════════════════════════════════════════════════════ public API
def merge_workbooks(
    paths: list[pathlib.Path],
    out_path: pathlib.Path,
    ref_total=None,
    model_count: int | None = None,
) -> pathlib.Path:
    """يدمج ملفات Excel (كل ملف = تشغيل مستقل) في ملف واحد."""
    from openpyxl import load_workbook

    wbs = [load_workbook(p) for p in paths]
    wb_out = wbs[0]
    others = wbs[1:]

    if "Summary" in wb_out.sheetnames:
        _merge_summary_sheet(wb_out, wbs, ref_total=ref_total, model_count=model_count)

    for name in list(wb_out.sheetnames):
        if name in ("Summary", "Meta", "SpeedDetail"):
            continue
        sources = [wb[name] for wb in others if name in wb.sheetnames]
        if not sources:
            continue
        ws_out = wb_out[name]
        _merge_data_sheet(ws_out, sources)
        if name == "Categories":
            _refresh_color_scale(ws_out, 8)

    if "Meta" in wb_out.sheetnames:
        _merge_meta_sheet(wb_out, wbs, model_count=model_count)

    if "SpeedDetail" in wb_out.sheetnames:
        sources = [wb["SpeedDetail"] for wb in others if "SpeedDetail" in wb.sheetnames]
        if sources:
            _merge_speed_sheet(wb_out["SpeedDetail"], sources)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb_out.save(out_path)
    return out_path
