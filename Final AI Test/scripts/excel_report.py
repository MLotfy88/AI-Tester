"""بناء تقرير Excel من نتائج التشغيل الموجودة في الذاكرة.

الشيتات: Summary / Questions / Axes / Gates / Fit / Performance / SpeedDetail / Answers / Meta
لا يقرأ أي JSON وسيط؛ بياخد قائمة النتائج كما خرجت من run_exam.py.
"""
from __future__ import annotations

import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from common import fmt_num, human_bytes, now_iso
from references import (
    source_badge,
    target_config,
    target_gap,
    target_ranking,
    trust_flag_for,
)

HEADER_FILL = PatternFill("solid", fgColor="111827")
HEADER_FONT = Font(color="FFFFFF", bold=True, size=11)
TITLE_FONT = Font(color="0F172A", bold=True, size=14)
ACCENT_FILL = PatternFill("solid", fgColor="E0F2FE")
BASE_FILL = PatternFill("solid", fgColor="FEF3C7")
OK_FILL = PatternFill("solid", fgColor="D1FAE5")
BAD_FILL = PatternFill("solid", fgColor="FEE2E2")
WARN_FILL = PatternFill("solid", fgColor="FEF9C3")
MUT_FILL = PatternFill("solid", fgColor="F1F5F9")
THIN = Side(style="thin", color="E2E8F0")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
RIGHT = Alignment(horizontal="right", vertical="top", wrap_text=True)
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)

VERDICT_FILL = {
    "جاهز ✅": OK_FILL,
    "ممتاز 🟢": OK_FILL,
    "مقبول 🟡": WARN_FILL,
    "ضعيف 🟠": WARN_FILL,
    "مرفوض 🔴": BAD_FILL,
    "غير موثوق ⛔": BAD_FILL,
    "خطير ⛔": BAD_FILL,  # الاسم القديم (ورقة §0.5 قبل التوضيح)
}


def _pct(score: float | int | None, maximum: float | int | None) -> float | None:
    try:
        if not maximum:
            return None
        return round(100.0 * float(score) / float(maximum), 1)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _gates_fired(exam: dict | None) -> list[str]:
    if not exam:
        return []
    return [g["code"] for g in exam.get("gates", []) if g.get("fired")]


def _gate_text(exam: dict | None) -> str:
    fired = _gates_fired(exam)
    return "، ".join(fired) if fired else "سليمة"


def _status(result: dict) -> str:
    return "تم" if result.get("status") == "ok" and result.get("exam") else "فشل"


def _baseline(exam_cfg: dict) -> dict:
    return exam_cfg.get("baseline") or {}


def _style_header(ws: Worksheet, row: int = 1) -> None:
    for cell in ws[row]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = CENTER
        cell.border = BORDER


def _style_body(ws: Worksheet, *, start: int = 2, widths: dict[int, int] | None = None) -> None:
    for row in ws.iter_rows(min_row=start, max_row=ws.max_row, max_col=ws.max_column):
        for cell in row:
            cell.alignment = RIGHT
            cell.border = BORDER
    if widths:
        for idx, width in widths.items():
            ws.column_dimensions[get_column_letter(idx)].width = width
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    ws.sheet_view.rightToLeft = True


def _add_color_scale(ws: Worksheet, column: int, start_row: int = 2, end_row: int | None = None) -> None:
    last = end_row if end_row is not None else ws.max_row
    if last < start_row:
        return
    rng = f"{get_column_letter(column)}{start_row}:{get_column_letter(column)}{last}"
    ws.conditional_formatting.add(
        rng,
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


def _set_widths(ws: Worksheet, widths: dict[int, int]) -> None:
    for idx, width in widths.items():
        ws.column_dimensions[get_column_letter(idx)].width = width


# --------------------------------------------------------------------------- الشيتات
def _summary_sheet(ws: Worksheet, results: list[dict], exam_cfg: dict) -> None:
    headers = [
        "#",
        "الموديل",
        "الحالة",
        "الدرجة /100",
        "درجة المقارنة (baseline)",
        "الحكم",
        "غير موثوق (②)",
        "المحور ①",
        "المحور ②",
        "المحور ③",
        "المحور ④",
        "البوابات Fired",
        "Fit",
        "ngl (الجهاز)",
        "حجم الملف",
        "زمن التشغيل (د)",
        "Peak RSS",
        "tok/s فعلي",
        "توليد tok/s (مقيس)",
        "أول استجابة ms (مقيس)",
        "الفرق عن الأساس",
        "الفرق عن الهدف (Gemini)",
        "المسافة عن الهدف",
        "ملاحظة",
    ]
    ws.append(headers)
    _style_header(ws)
    base_total = float(_baseline(exam_cfg).get("total") or 0)
    axes_cfg = exam_cfg.get("axes") or {}
    target = target_config(exam_cfg)

    for i, result in enumerate(results, 1):
        exam = result.get("exam") or {}
        fit = result.get("fit") or {}
        runtime = result.get("runtime") or {}
        axes = exam.get("axes") or {}
        total = exam.get("total")
        requests = runtime.get("requests") or []
        tps_values = [r.get("tps") for r in requests if r.get("tps")]
        avg_tps = round(sum(tps_values) / len(tps_values), 2) if tps_values else None
        perf = runtime.get("perf") or {}
        diff = round(float(total) - base_total, 2) if total is not None and base_total else None
        # وسم «غير موثوق» — على المحور ② فقط (مش حكم كلي)
        trust_flag = str(exam.get("trust_flag") or "") or str(
            (axes.get("2") or {}).get("trust_flag") or ""
        )
        gap = target_gap(exam, target, axes_cfg) if target else {"total": None, "distance": None}
        ws.append(
            [
                i,
                result.get("model") or "",
                _status(result),
                total if total is not None else "—",
                (exam.get("baseline") or {}).get("total", "—") if exam else "—",
                exam.get("verdict") or (result.get("error") or "لم يُشغّل"),
                trust_flag or "—",
                _axis_text(axes, "1"),
                _axis_text(axes, "2"),
                _axis_text(axes, "3"),
                _axis_text(axes, "4"),
                _gate_text(exam) if exam else "—",
                fit.get("fit_class") or "—",
                fit.get("ngl") if fit else "—",
                fit.get("file_gib") if fit else "—",
                round(runtime.get("seconds_total", 0) / 60.0, 1) if runtime else "—",
                runtime.get("peak_rss_mib") if runtime else "—",
                avg_tps if avg_tps is not None else "—",
                (perf.get("tg_tps") or {}).get("avg") or "—",
                (perf.get("ttft_ms") or {}).get("avg") or "—",
                diff if diff is not None else "—",
                gap.get("total") if gap.get("total") is not None else "—",
                gap.get("distance") if gap.get("distance") is not None else "—",
                (result.get("error") or result.get("model_full") or "")[:200],
            ]
        )

    # صف مرجعي لخط الأساس (مش موديل اتشغّل)
    base = _baseline(exam_cfg)
    if base:
        base_axes = base.get("axes") or {}
        ws.append(
            [
                "—",
                base.get("name", "خط الأساس"),
                "مرجع",
                base.get("total"),
                base.get("total"),
                base.get("verdict", ""),
                trust_flag_for(base, axes_cfg) or "—",
                base_axes.get("1", "—"),
                base_axes.get("2", "—"),
                base_axes.get("3", "—"),
                base_axes.get("4", "—"),
                "، ".join(base.get("gates") or []) or "سليمة",
                "—",
                "—",
                "—",
                "—",
                "—",
                "—",
                "—",
                0,
                "—",
                "—",
                f"مرجع — {base.get('note') or 'EXAM-PAPER-v1.md §0.6'}",
            ]
        )

    # صف مرجعي لشريط الهدف (Gemini 2.5 Pro) — معايرة يدوية، مش مقيس آلياً
    if target:
        t_axes = target.get("axes") or {}
        ws.append(
            [
                "—",
                f"🎯 {target.get('name', 'شريط الهدف')}",
                "هدف",
                target.get("total"),
                target.get("total"),
                target.get("verdict", ""),
                "—",
                t_axes.get("1", "—"),
                t_axes.get("2", "—"),
                t_axes.get("3", "—"),
                t_axes.get("4", "—"),
                "، ".join(target.get("gates") or []) or "سليمة",
                "—",
                "—",
                "—",
                "—",
                "—",
                "—",
                "—",
                "—",
                "—",
                0,
                0,
                f"{source_badge(target)} — {target.get('note') or ''}",
            ]
        )

    # ── ترتيب الموديلات حسب القرب من الهدف (أقل مسافة = أقرب)
    #    ملاحظة: بيتكتب **تحت** الجدول الرئيسي ⇒ بنحدد نطاق الفلتر/color-scale
    #    للجدول الرئيسي بس عشان الجدول الفرعي ما يفسدش الفلاتر.
    main_rows = ws.max_row
    ranked = target_ranking([r for r in results if r.get("exam")], exam_cfg)
    if ranked:
        ws.append([])
        ws.append(["🎯 ترتيب القرب من شريط الهدف", target.get("name", ""), source_badge(target)])
        _style_header(ws, row=ws.max_row)
        ws.append(["#", "الموديل", "المجموع", "Δ ① %", "Δ ② %", "Δ ③ %", "Δ ④ %", "Δ المجموع", "المسافة"])
        _style_header(ws, row=ws.max_row)
        for i, row in enumerate(ranked, 1):
            gap = row["gap"]
            ws.append(
                [
                    i,
                    row["result"].get("model") or "",
                    fmt_num((row["result"].get("exam") or {}).get("total"), 2),
                    fmt_num(gap["axis_pct"].get("1"), 1),
                    fmt_num(gap["axis_pct"].get("2"), 1),
                    fmt_num(gap["axis_pct"].get("3"), 1),
                    fmt_num(gap["axis_pct"].get("4"), 1),
                    fmt_num(gap.get("total"), 1),
                    fmt_num(gap.get("distance"), 1),
                ]
            )

    _style_body(ws, widths={1: 6, 2: 38, 3: 10, 4: 13, 5: 20, 10: 11, 11: 22, 14: 12, 19: 45})
    _set_widths(ws, {6: 16, 7: 15, 8: 11, 9: 11, 10: 11, 11: 11, 15: 17, 16: 13, 17: 13, 18: 18, 22: 20, 23: 14})
    _add_color_scale(ws, 4, end_row=main_rows)
    for row in ws.iter_rows(min_row=2, max_row=main_rows):
        verdict_cell = row[5]
        fill = VERDICT_FILL.get(str(verdict_cell.value))
        if fill:
            verdict_cell.fill = fill
        if row[2].value == "فشل":
            row[2].fill = BAD_FILL
        elif row[2].value == "مرجع":
            for cell in row:
                cell.fill = BASE_FILL
        elif row[2].value == "هدف":
            for cell in row:
                cell.fill = PatternFill("solid", fgColor="EDE9FE")
    ws.row_dimensions[1].height = 34
    # الفلتر يغطي الجدول الرئيسي بس (مش جدول الترتيب اللي تحته)
    ws.auto_filter.ref = f"A1:{get_column_letter(ws.max_column)}{main_rows}"


def _axis_text(axes: dict, key: str) -> str:
    axis = axes.get(str(key)) or {}
    if not axis:
        return "—"
    value = f"{fmt_num(axis.get('score'), 2)}/{fmt_num(axis.get('max'), 0)}"
    if axis.get("zeroed_by_gate"):
        value += " ⛔"
    return value


def _questions_sheet(ws: Worksheet, results: list[dict]) -> None:
    headers = [
        "الموديل",
        "السؤال",
        "المحور",
        "العنوان",
        "الدرجة",
        "الحد",
        "%",
        "الأساس",
        "عقوبة الطول",
        "حروف",
        "توكنز",
        "ثواني",
        "finish",
        "مؤشرات",
        "ملاحظات",
        "الإجابة (مقتطف)",
    ]
    ws.append(headers)
    _style_header(ws)
    for result in results:
        exam = result.get("exam")
        if not exam:
            continue
        model = result.get("model") or ""
        for qid, row in (exam.get("questions") or {}).items():
            notes = "؛ ".join(row.get("notes") or [])
            health = "، ".join(row.get("health") or [])
            answer = (row.get("answer") or "").replace("\r", " ").replace("\n", " ")
            ws.append(
                [
                    model,
                    qid,
                    row.get("axis"),
                    row.get("title"),
                    row.get("score"),
                    row.get("max"),
                    _pct(row.get("score"), row.get("max")),
                    row.get("base_score"),
                    row.get("length_penalty") or 0,
                    row.get("chars"),
                    row.get("tokens") if row.get("tokens") is not None else "—",
                    row.get("seconds") if row.get("seconds") is not None else "—",
                    row.get("finish") or "",
                    health,
                    notes[:900],
                    answer[:220],
                ]
            )
    _style_body(
        ws,
        widths={1: 34, 2: 7, 3: 7, 4: 26, 5: 9, 6: 7, 7: 8, 8: 9, 9: 12, 10: 8, 11: 10, 12: 9, 13: 10, 14: 28, 15: 60, 16: 70},
    )
    _add_color_scale(ws, 7)
    ws.row_dimensions[1].height = 30


def _axes_sheet(ws: Worksheet, results: list[dict], exam_cfg: dict | None = None) -> None:
    headers = [
        "الموديل",
        "المحور",
        "الاسم",
        "الدرجة",
        "الحد",
        "%",
        "قبل العقوبات",
        "عقوبات",
        "صُفّر ببوابة",
        "الأسئلة",
    ]
    ws.append(headers)
    _style_header(ws)
    for result in results:
        exam = result.get("exam")
        if not exam:
            continue
        model = result.get("model") or ""
        for key in ("1", "2", "3", "4"):
            axis = (exam.get("axes") or {}).get(key)
            if not axis:
                continue
            ws.append(
                [
                    model,
                    key,
                    axis.get("name") or "",
                    axis.get("score"),
                    axis.get("max"),
                    _pct(axis.get("score"), axis.get("max")),
                    axis.get("base_score"),
                    axis.get("penalty"),
                    "نعم" if axis.get("zeroed_by_gate") else "لا",
                    "، ".join(axis.get("questions") or []),
                ]
            )
        ws.append(
            [
                model,
                "المجموع",
                "الإجمالي",
                exam.get("total"),
                exam.get("max", 100),
                _pct(exam.get("total"), exam.get("max", 100)),
                exam.get("total_before_gates"),
                "",
                "",
                "",
            ]
        )
    # ── صفوف مرجعية: شريط الهدف (Gemini) + خط الأساس
    exam_cfg = exam_cfg or {}
    axes_cfg = exam_cfg.get("axes") or {}
    target = target_config(exam_cfg)
    if target:
        for key in ("1", "2", "3", "4"):
            cfg = axes_cfg.get(key) or {}
            maxv = cfg.get("max")
            score = (target.get("axes") or {}).get(key)
            if score is None:
                continue
            ws.append(
                [
                    f"🎯 {target.get('name')}",
                    key,
                    cfg.get("name") or "",
                    score,
                    maxv,
                    _pct(score, maxv),
                    score,
                    "",
                    "",
                    "، ".join(cfg.get("questions") or []),
                ]
            )
        ws.append(
            [
                f"🎯 {target.get('name')}",
                "المجموع",
                "الإجمالي",
                target.get("total"),
                100,
                _pct(target.get("total"), 100),
                target.get("total"),
                "",
                "",
                "",
            ]
        )
    base = _baseline(exam_cfg)
    if base:
        for key in ("1", "2", "3", "4"):
            cfg = axes_cfg.get(key) or {}
            score = (base.get("axes") or {}).get(key)
            if score is None:
                continue
            ws.append(
                [
                    base.get("name"),
                    key,
                    cfg.get("name") or "",
                    score,
                    cfg.get("max"),
                    _pct(score, cfg.get("max")),
                    score,
                    "",
                    "",
                    "، ".join(cfg.get("questions") or []),
                ]
            )
    _style_body(ws, widths={1: 38, 2: 9, 3: 34, 4: 10, 5: 8, 6: 8, 7: 14, 8: 10, 9: 14, 10: 30})
    _add_color_scale(ws, 6)
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        if row[1].value == "المجموع":
            for cell in row:
                cell.font = Font(bold=True)
                cell.fill = ACCENT_FILL
        elif str(row[0].value or "").startswith("🎯"):
            for cell in row:
                cell.fill = PatternFill("solid", fgColor="EDE9FE")
        elif row[0].value == (base or {}).get("name"):
            for cell in row:
                cell.fill = BASE_FILL


def _gates_sheet(ws: Worksheet, results: list[dict]) -> None:
    headers = ["الموديل", "البوابة", "الوصف", "الحد", "Fired", "التفاصيل", "الأسئلة", "العقوبة"]
    ws.append(headers)
    _style_header(ws)
    for result in results:
        exam = result.get("exam")
        if not exam:
            continue
        model = result.get("model") or ""
        for gate in exam.get("gates") or []:
            ws.append(
                [
                    model,
                    gate.get("code"),
                    gate.get("title"),
                    gate.get("threshold"),
                    "نعم" if gate.get("fired") else "لا",
                    gate.get("detail"),
                    "، ".join(gate.get("questions") or []),
                    gate.get("penalty") or 0,
                ]
            )
    _style_body(ws, widths={1: 36, 2: 9, 3: 44, 4: 30, 5: 8, 6: 48, 7: 22, 8: 10})
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        fired = row[4].value == "نعم"
        row[4].fill = BAD_FILL if fired else OK_FILL
        row[4].font = Font(bold=True, color="991B1B" if fired else "065F46")


def _fit_sheet(ws: Worksheet, results: list[dict]) -> None:
    headers = [
        "الموديل",
        "الملف",
        "الحجم (GiB)",
        "المعمارية",
        "Layers",
        "Heads",
        "KV Heads",
        "Head dim",
        "KV نوع",
        "KV (GiB)",
        "الاحتياج الكامل (GiB)",
        "ميزانية VRAM",
        "ngl (الجهاز)",
        "نسبة GPU",
        "Fit class",
        "سقف tg (نظري)",
        "سقف pp (نظري)",
        "Params (B)",
        "رام الجهاز",
        "ngl على الـ runner",
        "أمر التشغيل المقترح",
        "خطأ",
    ]
    ws.append(headers)
    _style_header(ws)
    for result in results:
        fit = result.get("fit") or {}
        runtime = result.get("runtime") or {}
        meta = fit.get("meta") or {}
        kv_heads = meta.get("head_count_kv")
        if isinstance(kv_heads, (list, tuple)):
            kv_heads = "، ".join(str(x) for x in kv_heads)
        ws.append(
            [
                result.get("model") or "",
                Path(str(fit.get("file") or "")).name if fit.get("file") else "—",
                fit.get("file_gib", "—"),
                meta.get("arch") or "—",
                meta.get("block_count") or fit.get("n_layers") or "—",
                meta.get("head_count") or "—",
                kv_heads or "—",
                fit.get("head_dim") or "—",
                fit.get("kv") or "—",
                fit.get("kv_total_gib", "—"),
                fit.get("need_full_gib", "—"),
                fit.get("budget_gib", "—"),
                fit.get("ngl", "—"),
                fit.get("gpu_share", "—"),
                fit.get("fit_class") or "—",
                fit.get("tg_tps", "—"),
                fit.get("pp_tps", "—"),
                fit.get("params_b_assumed", "—"),
                fit.get("ram_gib", "—"),
                runtime.get("ngl", "—"),
                fit.get("run_command") or "—",
                fit.get("error") or "",
            ]
        )
    _style_body(ws, widths={1: 34, 2: 30, 22: 70, 21: 52, 9: 9, 10: 10})
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        cls = row[14].value
        if cls == "Full GPU":
            row[14].fill = OK_FILL
        elif cls in ("Partial", "Mostly CPU"):
            row[14].fill = WARN_FILL
        elif cls in ("No fit", "Unknown"):
            row[14].fill = BAD_FILL
    # تنويه: أعمدة «سقف tg/pp» **نظرية** — المقيس في شيت Performance
    ws.append(
        [
            "تنويه",
            "أعمدة «سقف tg» و«سقف pp» **تقديرات رياضية** من مواصفات الجهاز المستهدف "
            "(config/device_profile.yaml) — للمقارنة والتخطيط فقط.",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "الأرقام **المقيسة فعلياً** على الكارت موجودة في شيت Performance.",
        ]
    )
    note_row = ws.max_row
    for cell in ws[note_row]:
        cell.fill = WARN_FILL
        cell.alignment = Alignment(horizontal="right", vertical="center", wrap_text=True)


def _answers_sheet(ws: Worksheet, results: list[dict]) -> None:
    headers = [
        "الموديل",
        "السؤال",
        "المحور",
        "الدرجة",
        "الحد",
        "السؤال النصي",
        "الإجابة",
        "التفكير (reasoning)",
        "thinking مرئي (G5)",
        "قناة reasoning",
        "finish",
        "توكنز",
        "ثواني",
        "حروف",
        "المؤشرات",
        "ملاحظات المصحح",
        "خطأ التشغيل",
    ]
    ws.append(headers)
    _style_header(ws)
    for result in results:
        exam = result.get("exam")
        if not exam:
            continue
        model = result.get("model") or ""
        for qid, row in (exam.get("questions") or {}).items():
            ws.append(
                [
                    model,
                    qid,
                    row.get("axis"),
                    row.get("score"),
                    row.get("max"),
                    row.get("prompt") or "",
                    row.get("answer") or "",
                    row.get("reasoning") or "",
                    "نعم (G5)" if row.get("think_visible") else "لا",
                    f"{row.get('reasoning_chars') or 0} حرف — "
                    + ("محتوى" if row.get("reasoning_present") else "فارغة"),
                    row.get("finish") or "",
                    row.get("tokens") if row.get("tokens") is not None else "—",
                    row.get("seconds") if row.get("seconds") is not None else "—",
                    row.get("chars"),
                    "، ".join(row.get("health") or []),
                    "؛ ".join(row.get("notes") or []),
                    row.get("error") or "",
                ]
            )
    _style_body(ws, widths={1: 30, 2: 7, 3: 7, 4: 8, 5: 6, 6: 46, 7: 100, 8: 60, 9: 14, 10: 18, 11: 10, 12: 9, 13: 9, 14: 8, 15: 26, 16: 50, 17: 30})
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        ws.row_dimensions[row[0].row].height = 120
        for cell in row:
            cell.alignment = Alignment(horizontal="right", vertical="top", wrap_text=True)
        if row[8].value == "نعم (G5)":
            row[8].fill = BAD_FILL
        if row[9].value and "محتوى" in str(row[9].value):
            row[9].fill = WARN_FILL


def _meta_sheet(ws: Worksheet, results: list[dict], exam_cfg: dict, run_meta: dict) -> None:
    ws.append(["البند", "القيمة", "ملاحظة"])
    _style_header(ws)
    settings = exam_cfg.get("settings") or {}
    baseline = _baseline(exam_cfg)
    baseline_axes = baseline.get("axes") or {}
    baseline_axes_text = "، ".join(f"{k}: {v}" for k, v in baseline_axes.items()) or "—"
    target = target_config(exam_cfg)
    target_axes = target.get("axes") or {}
    target_axes_text = "، ".join(f"{k}: {v}" for k, v in target_axes.items()) or "—"
    rows: list[tuple[Any, Any, str]] = [
        ("تاريخ التقرير", now_iso(), "UTC"),
        ("بداية التشغيل", run_meta.get("started_at", "—"), ""),
        ("نهاية التشغيل", run_meta.get("finished_at", "—"), ""),
        ("عدد الموديلات", len(results), "بما فيهم الفاشل"),
        ("إصدار ورقة الامتحان", exam_cfg.get("version", "—"), "EXAM-PAPER-v1.md"),
        ("عدد الأسئلة", len(exam_cfg.get("questions") or []), ""),
        ("الدرجة الكاملة", exam_cfg.get("max_score", 100), ""),
        ("temperature", settings.get("temperature"), "ثابت"),
        ("top_p", settings.get("top_p"), "ثابت"),
        ("seed", settings.get("seed"), "ثابت"),
        ("ctx_size", settings.get("ctx_size"), "ثابت — أي قيمة تانية تلغي المقارنة"),
        ("max_tokens", settings.get("max_tokens"), "ثابت"),
        ("max_answer_chars", settings.get("max_answer_chars"), "أطول من كده ⇒ عقوبة"),
        ("length_penalty", settings.get("length_penalty"), ""),
        ("baseline name", baseline.get("name", "—"), "خط الأساس للمقارنة"),
        ("baseline source", baseline.get("source_kind", "—"), baseline.get("note", "")),
        ("baseline total", baseline.get("total", "—"), "الموديل الأساس بالمصحح الحتمي"),
        ("baseline axes", baseline_axes_text, ""),
        ("baseline gates", "، ".join(baseline.get("gates") or []), ""),
        ("target name", target.get("name", "—"), "شريط الهدف (Gemini 2.5 Pro)"),
        ("target source", target.get("source_kind", "—"), target.get("note", "")),
        ("target total", target.get("total", "—"), "معايرة يدوية — مش مقيس آلياً"),
        ("target axes", target_axes_text, ""),
        ("قالب المحادثة", exam_cfg.get("runtime", {}).get("template", ""), ""),
        ("system prompt", exam_cfg.get("runtime", {}).get("system_prompt", ""), ""),
        ("طريقة التشغيل", run_meta.get("mode", "llama-server /v1/chat/completions"), ""),
        ("منصة الـ runner", platform.platform(), ""),
        ("Python", platform.python_version(), ""),
        ("ملاحظة السرعة", "حسابات tg/pp نظرية لجهازك المستهدف", "GitHub runner CPU فقط — مفيش GPU"),
        ("ملاحظة المقارنة", "كل الموديلات بنفس المصحح والإعدادات", "مفيش LLM-judge"),
        ("وسم غير موثوق", "على المحور ② فقط (أقل من 18/28)", "مش حكم كلي — الحكم على مجموع الدرجات"),
    ]
    for row in rows:
        ws.append(list(row))

    seen: set[str] = set()
    for result in results:
        runtime = result.get("runtime") or {}
        version = runtime.get("llama_version") or "—"
        if version in seen:
            continue
        seen.add(version)
        ws.append(["llama.cpp", version, "من --version"])
    for result in results:
        runtime = result.get("runtime") or {}
        if not runtime:
            continue
        ws.append([f"قالب SHA — {result.get('model', '')}", runtime.get("template_sha256", "—"), ""])
        ws.append([f"prompt SHA — {result.get('model', '')}", runtime.get("system_prompt_sha256", "—"), ""])
        ws.append([f"server log — {result.get('model', '')}", runtime.get("server_log", "—"), ""])
        ws.append([f"زمن التشغيل — {result.get('model', '')}", runtime.get("seconds_total", "—"), "ثانية"])

    _style_body(ws, widths={1: 42, 2: 70, 3: 40})
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        if str(row[0].value or "").startswith("baseline"):
            for cell in row:
                cell.fill = BASE_FILL
        elif str(row[0].value or "").startswith("target"):
            for cell in row:
                cell.fill = PatternFill("solid", fgColor="EDE9FE")
    ws.auto_filter.ref = None


def _settings_sheet(ws: Worksheet, results: list[dict]) -> None:
    """الإعدادات الفعلية لكل موديل + توصيات المطوّر (مهم للمقارنة بين الأوزان)."""
    ws.append(
        [
            "الموديل",
            "المصدر",
            "مطابقة",
            "القالب",
            "مصدر القالب",
            "KV cache",
            "flash-attn",
            "ngl",
            "threads",
            "device",
            "flags إضافية",
            "temp (مطبّق)",
            "top_p (مطبّق)",
            "top_k (موصى)",
            "min_p (موصى)",
            "توصيات التوليد",
            "مصدر التوصيات",
            "ملاحظات",
        ]
    )
    _style_header(ws)
    for result in results:
        st = result.get("settings") or {}
        runtime = result.get("runtime") or {}
        rec = st.get("recommended_sampling") or {}
        ws.append(
            [
                result.get("model") or "",
                st.get("source") or "—",
                st.get("matched_key") or "—",
                st.get("chat_template") or runtime.get("template_sha256") or "—",
                st.get("template_source") or "—",
                st.get("kv_cache_type") or runtime.get("kv") or "—",
                st.get("flash_attn") or runtime.get("flash_attn") or "—",
                st.get("n_gpu_layers") if st.get("n_gpu_layers") is not None else runtime.get("ngl", "—"),
                st.get("threads") if st.get("threads") is not None else runtime.get("threads", "—"),
                st.get("device") or runtime.get("device") or "—",
                " ".join(st.get("extra_server_args") or runtime.get("extra_args") or []) or "—",
                runtime.get("temperature", "—"),
                runtime.get("top_p", "—"),
                rec.get("top_k", "—"),
                rec.get("min_p", "—"),
                " · ".join(f"{k}={v}" for k, v in rec.items()) or "—",
                st.get("sampling_source") or "—",
                (st.get("notes") or "")[:300],
            ]
        )
        for warning in st.get("warnings") or []:
            ws.append(["", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", f"⚠ {warning}"])
    _style_body(ws, widths={1: 46, 4: 40, 11: 30, 16: 40, 18: 50})
    ws.auto_filter.ref = None


# --------------------------------------------------------------------------- الواجهة
def _performance_sheet(ws: Worksheet, results: list[dict]) -> None:
    """الأداء **المقيس فعلياً** على الكارت — رقم حقيقي لكل موديل.

    الأرقام مصدرها `timings` من llama.cpp (سرعة توليد/معالجة حقيقية) وأوقات
    الطلبات الفعلية. مفيش تقدير رياضي في هذا الشيت.
    """
    ws.append(
        [
            "الموديل",
            "المصدر",
            "device",
            "ngl",
            "threads",
            "توليد tok/s (متوسط)",
            "توليد tok/s (أدنى)",
            "توليد tok/s (أعلى)",
            "توليد tok/s (وسيط)",
            "توليد tok/s (p95 أدنى)",
            "معالجة prompt tok/s (متوسط)",
            "أول استجابة ms (متوسط)",
            "أول استجابة ms (p95)",
            "زمن الطلب s (متوسط)",
            "زمن الطلب s (أعلى)",
            "زمن معالجة prompt ms (متوسط)",
            "زمن توليد ms (متوسط)",
            "تجهيز الموديل s",
            "إجمالي الامتحان s",
            "ذاكرة RAM مقيسة MiB",
            "ذاكرة VRAM مقيسة MiB",
            "اسم الكارت",
            "توكنز مولّدة",
            "سقف tg نظري",
            "المقيس ÷ النظري %",
            "عدد الطلبات",
            "⚠ منافسة على الكارت",
        ]
    )
    _style_header(ws)
    any_row = False
    for result in results:
        runtime = result.get("runtime") or {}
        perf = runtime.get("perf") or {}
        if not perf:
            continue
        any_row = True
        fit = result.get("fit") or {}
        tg = perf.get("tg_tps") or {}
        pp = perf.get("pp_tps") or {}
        req = perf.get("request_seconds") or {}
        ttft = perf.get("ttft_ms") or {}
        prompt_ms = perf.get("prompt_ms") or {}
        predicted_ms = perf.get("predicted_ms") or {}
        ceil_tg = fit.get("tg_tps")
        ratio = None
        if tg.get("avg") and ceil_tg:
            ratio = round(float(tg["avg"]) / float(ceil_tg) * 100, 1)
        competing = (runtime.get("gpu_contention") or {}).get("competing_processes") or []
        ws.append(
            [
                result.get("model") or "",
                perf.get("source") or "—",
                runtime.get("device") or "—",
                runtime.get("ngl") if runtime.get("ngl") is not None else "—",
                runtime.get("threads") or "—",
                tg.get("avg", "—"),
                tg.get("min", "—"),
                tg.get("max", "—"),
                tg.get("median", "—"),
                tg.get("p95", "—"),
                pp.get("avg", "—"),
                ttft.get("avg", "—"),
                ttft.get("p95", "—"),
                req.get("avg", "—"),
                req.get("max", "—"),
                prompt_ms.get("avg", "—"),
                predicted_ms.get("avg", "—"),
                perf.get("startup_seconds", "—"),
                perf.get("seconds_total", "—"),
                runtime.get("peak_rss_mib") if runtime.get("peak_rss_mib") else "—",
                runtime.get("peak_vram_mib") if runtime.get("peak_vram_mib") else "—",
                runtime.get("gpu_name") or "—",
                perf.get("total_generated_tokens", "—"),
                ceil_tg if ceil_tg else "—",
                ratio if ratio is not None else "—",
                perf.get("requests_count", "—"),
                (
                    "، ".join(
                        str(c.get("name") or "?") for c in competing
                    )
                    if competing
                    else "لا"
                ),
            ]
        )
    if not any_row:
        ws.append(["مفيش بيانات أداء مقيسة في هذا التشغيل."])
    _style_body(ws, widths={1: 34, 2: 34, 3: 12, 4: 8, 5: 9})
    # لو فيه صف فيه منافسة ⇒ لوّنه أحمر (السرعة المقيسة مش مضبوطة)
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        if row and row[-1].value and str(row[-1].value) != "لا":
            for cell in row:
                cell.fill = BAD_FILL
    ws.freeze_panes = "A2"


def _speed_detail_sheet(ws: Worksheet, results: list[dict], exam_cfg: dict) -> None:
    """زمن كل سؤال × كل موديل — counterpart لجدول السرعة في HTML.

    كل الأرقام **مقيسة فعلياً** (أوقات الطلبات الفعلية + `timings` من llama.cpp).
    """
    models = [r for r in results if r.get("status") == "ok" and r.get("exam")]
    questions = exam_cfg.get("questions") or []
    headers = ["السؤال", "عنوان السؤال"]
    for result in models:
        short = str(result.get("model") or "").replace("\\", "/").rsplit("/", 1)[-1]
        headers += [
            f"{short} — ثوانٍ",
            f"{short} — tok/s",
            f"{short} — توكنز",
            f"{short} — finish",
        ]
    ws.append(headers)
    _style_header(ws)
    for q in questions:
        qid = str(q.get("id"))
        row_values: list = [qid, q.get("title") or ""]
        for result in models:
            qrow = ((result.get("exam") or {}).get("questions") or {}).get(qid) or {}
            seconds = qrow.get("seconds")
            tokens = qrow.get("tokens")
            tps = None
            try:
                if seconds and tokens:
                    tps = round(float(tokens) / float(seconds), 2)
            except (TypeError, ValueError, ZeroDivisionError):
                tps = None
            row_values += [
                round(float(seconds), 2) if seconds is not None else "—",
                tps if tps is not None else "—",
                tokens if tokens is not None else "—",
                qrow.get("finish") or "—",
            ]
        ws.append(row_values)
    _style_body(ws, widths={1: 9, 2: 40})
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        for idx in range(3, ws.max_column + 1):
            cell = row[idx - 1]
            cell.alignment = CENTER
        # كل 4 أعمدة: ثوانٍ / tok/s / توكنز / finish
        for base in range(3, ws.max_column + 1, 4):
            finish_cell = row[base + 2]
            if str(finish_cell.value) == "length":
                finish_cell.fill = BAD_FILL
    ws.freeze_panes = "C2"


def build_workbook(results: list[dict], exam_cfg: dict, run_meta: dict | None = None) -> Workbook:
    wb = Workbook()
    wb.remove(wb.active)
    run_meta = run_meta or {}

    ws = wb.create_sheet("Summary")
    _summary_sheet(ws, results, exam_cfg)
    ws = wb.create_sheet("Questions")
    _questions_sheet(ws, results)
    ws = wb.create_sheet("Axes")
    _axes_sheet(ws, results, exam_cfg)
    ws = wb.create_sheet("Gates")
    _gates_sheet(ws, results)
    ws = wb.create_sheet("Fit")
    _fit_sheet(ws, results)
    ws = wb.create_sheet("Performance")
    _performance_sheet(ws, results)
    ws = wb.create_sheet("SpeedDetail")
    _speed_detail_sheet(ws, results, exam_cfg)
    ws = wb.create_sheet("Settings")
    _settings_sheet(ws, results)
    ws = wb.create_sheet("Answers")
    _answers_sheet(ws, results)
    ws = wb.create_sheet("Meta")
    _meta_sheet(ws, results, exam_cfg, run_meta)

    wb.properties.title = "تقرير امتحان المساعد المصري"
    wb.properties.subject = "مقارنة موديلات GGUF — تصحيح حتمي"
    wb.properties.creator = "AI Online Tester"
    wb.properties.created = datetime.now(timezone.utc)
    return wb


def write_workbook(
    results: list[dict],
    path: str | Path,
    exam_cfg: dict,
    run_meta: dict | None = None,
) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    wb = build_workbook(results, exam_cfg, run_meta)
    wb.save(p)
    return p


__all__ = ["build_workbook", "write_workbook"]
