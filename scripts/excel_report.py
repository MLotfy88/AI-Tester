"""بناء تقرير Excel من نتائج التشغيل الموجودة في الذاكرة (الامتحان v3).

الشيتات: Summary / Categories / Gates / Questions / Rubric / Fit / Performance /
SpeedDetail / Settings / Answers / Meta
لا يقرأ أي JSON وسيط؛ بياخد قائمة النتائج كما خرجت من run_exam.py.

⚠ مرجع Gemini 2.5 Pro **عرض فقط**: بيتعرض في شيت Summary وCategories وMeta
بوسم واضح «مرجع» + «عرض فقط»، وبيوضّح إن **مالوش أي تأثير** في الدرجة ولا الحكم.
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
    category_short,
    gemini_gap,
    gemini_ranking,
    gemini_reference,
    gemini_total,
    gemini_values,
    infer_runner_meta,
    measured_on_gpu,
    runner_kind,
    runner_label,
    source_badge,
)

HEADER_FILL = PatternFill("solid", fgColor="111827")
HEADER_FONT = Font(color="FFFFFF", bold=True, size=11)
TITLE_FONT = Font(color="0F172A", bold=True, size=14)
ACCENT_FILL = PatternFill("solid", fgColor="E0F2FE")
GEM_FILL = PatternFill("solid", fgColor="EDE9FE")
OK_FILL = PatternFill("solid", fgColor="D1FAE5")
BAD_FILL = PatternFill("solid", fgColor="FEE2E2")
WARN_FILL = PatternFill("solid", fgColor="FEF9C3")
MUT_FILL = PatternFill("solid", fgColor="F1F5F9")
THIN = Side(style="thin", color="E2E8F0")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
RIGHT = Alignment(horizontal="right", vertical="top", wrap_text=True)
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)


# --------------------------------------------------------------------------- مساعدات
def _pct(score: float | int | None, maximum: float | int | None) -> float | None:
    try:
        if not maximum:
            return None
        return round(100.0 * float(score) / float(maximum), 1)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _status(result: dict) -> str:
    return "تم" if result.get("status") == "ok" and result.get("exam") else "فشل"


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


def _cat_keys(exam_cfg: dict) -> list[str]:
    """مفاتيح المحاور — بتقبل `categories` كـ dict (المولّد) أو list (JSON الخام)."""
    categories = (exam_cfg or {}).get("categories") or {}
    if isinstance(categories, dict):
        return list(categories.keys())
    return [str((c or {}).get("key") or "") for c in categories if isinstance(c, dict)]


def _cat_cfg(exam_cfg: dict, key: str) -> dict:
    """إعدادات محور واحد — dict أو list."""
    categories = (exam_cfg or {}).get("categories") or {}
    if isinstance(categories, dict):
        return dict(categories.get(key) or {})
    for row in categories:
        if isinstance(row, dict) and str(row.get("key") or "") == str(key):
            return dict(row)
    return {}


# --------------------------------------------------------------------------- Summary
def _summary_sheet(ws: Worksheet, results: list[dict], exam_cfg: dict) -> None:
    cat_keys = _cat_keys(exam_cfg)
    ref = gemini_reference(exam_cfg)
    headers = [
        "#",
        "الموديل",
        "الحالة",
        "الدرجة /100",
        "الحكم",
        "محاور تحت الحد الأدنى",
    ]
    headers += [category_short(exam_cfg, k) for k in cat_keys]
    headers += [
        "حدود الدنيا Fired",
        "Fit",
        "حجم الملف",
        "زمن التشغيل (د)",
        "Peak RSS",
        "tok/s فعلي",
        "توليد tok/s (مقيس)",
        "أول استجابة ms (مقيس)",
        "المسافة عن مرجع Gemini (عرض فقط)",
        "ملاحظة",
    ]
    ws.append(headers)
    _style_header(ws)

    for i, result in enumerate(results, 1):
        exam = result.get("exam") or {}
        fit = result.get("fit") or {}
        runtime = result.get("runtime") or {}
        cats = exam.get("categories") or {}
        total = exam.get("total")
        requests = runtime.get("requests") or []
        tps_values = [r.get("tps") for r in requests if r.get("tps")]
        avg_tps = round(sum(tps_values) / len(tps_values), 2) if tps_values else None
        perf = runtime.get("perf") or {}
        failed = list(exam.get("failed_categories") or [])
        failed_names = "، ".join(
            str(_cat_cfg(exam_cfg, k).get("name") or k) for k in failed
        ) or "سليمة"
        gap = gemini_gap(exam, exam_cfg) if ref else {"distance": None}
        row: list[Any] = [
            i,
            result.get("model") or "",
            _status(result),
            total if total is not None else "—",
            exam.get("verdict") or (result.get("error") or "لم يُشغّل"),
            failed_names,
        ]
        for key in cat_keys:
            cat = cats.get(key) or {}
            pct = cat.get("percent")
            cell = f"{fmt_num(pct, 1)}%" if pct is not None else "—"
            if cat.get("failed_min"):
                cell += " ⛔"
            row.append(cell)
        row += [
            "، ".join(str(g.get("code")) for g in (exam.get("gates") or []) if g.get("fired")) or "سليمة",
            fit.get("fit_class") or "—",
            fit.get("file_gib") if fit else "—",
            round(runtime.get("seconds_total", 0) / 60.0, 1) if runtime else "—",
            runtime.get("peak_rss_mib") if runtime else "—",
            avg_tps if avg_tps is not None else "—",
            (perf.get("tg_tps") or {}).get("avg") or "—",
            (perf.get("ttft_ms") or {}).get("avg") or "—",
            gap.get("distance") if gap.get("distance") is not None else "—",
            (result.get("error") or result.get("model_full") or "")[:200],
        ]
        ws.append(row)

    main_rows = ws.max_row

    # ── صف مرجعي: Gemini 2.5 Pro (عرض فقط — مالوش أي تأثير)
    if ref:
        values = gemini_values(exam_cfg)
        row: list[Any] = [
            "—",
            f"🎯 {ref.get('name', 'مرجع Gemini')}",
            "مرجع (عرض فقط ⛔)",
            gemini_total(exam_cfg) if gemini_total(exam_cfg) is not None else "—",
            "— مالوش أي تأثير في الحكم —",
            "—",
        ]
        for key in cat_keys:
            value = values.get(key)
            row.append(f"{fmt_num(value, 1)}%" if value is not None else "—")
        row += ["—", "—", "—", "—", "—", "—", "—", "—", "—"]
        row.append(f"{source_badge(ref)} — بنشماركات عامة منشورة، مش مقاسة على أسئلة الامتحان")
        ws.append(row)

    # ── جدول ترتيب القرب من المرجع (تحت الجدول الرئيسي)
    ranked = gemini_ranking([r for r in results if r.get("exam")], exam_cfg)
    if ranked and ref:
        ws.append([])
        ws.append(["🎯 ترتيب القرب من مرجع Gemini (عرض فقط ⛔)", ref.get("name", ""), source_badge(ref)])
        _style_header(ws, row=ws.max_row)
        ws.append(["#", "الموديل", "المجموع", *cat_keys, "المسافة"])
        _style_header(ws, row=ws.max_row)
        for i, row_data in enumerate(ranked, 1):
            gap = row_data["gap"]
            exam = row_data["result"].get("exam") or {}
            ws.append(
                [
                    i,
                    row_data["result"].get("model") or "",
                    fmt_num(exam.get("total"), 2),
                    *[
                        fmt_num(gap["per_axis"].get(key), 1)
                        for key in cat_keys
                    ],
                    fmt_num(gap.get("distance"), 1),
                ]
            )

    _style_body(ws, widths={1: 6, 2: 38, 3: 10, 4: 13, 5: 26, 6: 30})
    _set_widths(ws, {7: 11, 8: 13, 9: 11, 10: 11, 11: 11, 12: 11, 13: 11, 14: 11, 15: 14, 16: 22, 17: 12, 18: 15, 19: 15, 20: 18, 21: 20, 22: 28, 23: 45})
    _add_color_scale(ws, 4, end_row=main_rows)
    for row in ws.iter_rows(min_row=2, max_row=main_rows):
        verdict_cell = row[4]
        text = str(verdict_cell.value or "")
        if "فشل حرج" in text:
            verdict_cell.fill = BAD_FILL
            verdict_cell.font = Font(bold=True, color="991B1B")
        elif "قريب جدًا" in text:
            verdict_cell.fill = OK_FILL
        elif "قريب مع فجوات" in text:
            verdict_cell.fill = WARN_FILL
        if row[2].value == "فشل":
            row[2].fill = BAD_FILL
    ws.row_dimensions[1].height = 34
    ws.auto_filter.ref = f"A1:{get_column_letter(ws.max_column)}{main_rows}"


# --------------------------------------------------------------------------- Categories
def _categories_sheet(ws: Worksheet, results: list[dict], exam_cfg: dict) -> None:
    headers = [
        "الموديل",
        "المحور",
        "الاسم",
        "الوزن",
        "الحد الأدنى %",
        "الدرجة الخام",
        "الحد الأقصى",
        "النسبة %",
        "النقاط",
        "الحالة",
        "الأسئلة",
    ]
    ws.append(headers)
    _style_header(ws)
    for result in results:
        exam = result.get("exam")
        if not exam:
            continue
        model = result.get("model") or ""
        for key in _cat_keys(exam_cfg):
            cat = (exam.get("categories") or {}).get(key)
            if not cat:
                continue
            ws.append(
                [
                    model,
                    key,
                    cat.get("name") or "",
                    cat.get("weight"),
                    cat.get("min_percent"),
                    cat.get("score"),
                    cat.get("max"),
                    cat.get("percent"),
                    cat.get("points"),
                    "⛔ تحت الحد" if cat.get("failed_min") else "✅ فوق الحد",
                    "، ".join(cat.get("questions") or []),
                ]
            )
        ws.append(
            [
                model,
                "المجموع",
                "الإجمالي",
                100,
                "—",
                "—",
                100,
                exam.get("total"),
                exam.get("total"),
                exam.get("verdict") or "",
                "",
            ]
        )
    _style_body(ws, widths={1: 38, 2: 9, 3: 34, 4: 9, 5: 12, 6: 11, 7: 11, 8: 10, 9: 9, 10: 16, 11: 30})
    _add_color_scale(ws, 8)
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        if row[1].value == "المجموع":
            for cell in row:
                cell.font = Font(bold=True)
                cell.fill = ACCENT_FILL
        elif "⛔" in str(row[9].value or ""):
            row[9].fill = BAD_FILL
            row[9].font = Font(bold=True, color="991B1B")


# --------------------------------------------------------------------------- Gates (حدود الدنيا)
def _gates_sheet(ws: Worksheet, results: list[dict]) -> None:
    headers = ["الموديل", "المحور", "الوصف", "العتبة", "Fired", "التفاصيل", "الأسئلة"]
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
                    "نعم ⛔" if gate.get("fired") else "لا",
                    gate.get("detail"),
                    "، ".join(gate.get("questions") or []),
                ]
            )
    _style_body(ws, widths={1: 36, 2: 12, 3: 44, 4: 22, 5: 10, 6: 48, 7: 30})
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        fired = "نعم" in str(row[4].value or "")
        row[4].fill = BAD_FILL if fired else OK_FILL
        row[4].font = Font(bold=True, color="991B1B" if fired else "065F46")


# --------------------------------------------------------------------------- Questions
def _questions_sheet(ws: Worksheet, results: list[dict], exam_cfg: dict) -> None:
    headers = [
        "الموديل",
        "السؤال",
        "المحور",
        "العنوان",
        "الدرجة",
        "الحد",
        "%",
        "عدد التمريرات",
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
                    row.get("category"),
                    row.get("title"),
                    row.get("score"),
                    row.get("max"),
                    _pct(row.get("score"), row.get("max")),
                    row.get("passes"),
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
        widths={1: 34, 2: 8, 3: 8, 4: 28, 5: 9, 6: 7, 7: 8, 8: 10, 9: 9, 10: 10, 11: 9, 12: 10, 13: 28, 14: 60, 15: 70},
    )
    _add_color_scale(ws, 7)
    ws.row_dimensions[1].height = 30


# --------------------------------------------------------------------------- Rubric (تفصيل المعايير)
def _rubric_sheet(ws: Worksheet, results: list[dict], exam_cfg: dict) -> None:
    """تفصيل معايير الـ rubric لكل سؤال — المعيار، النقاط، وسبب الخصم."""
    headers = ["الموديل", "السؤال", "المحور", "المعيار", "النقاط", "الحد", "ملاحظة المعيار"]
    ws.append(headers)
    _style_header(ws)
    for result in results:
        exam = result.get("exam")
        if not exam:
            continue
        model = result.get("model") or ""
        for qid, row in (exam.get("questions") or {}).items():
            for crit in row.get("criteria") or []:
                ws.append(
                    [
                        model,
                        qid,
                        row.get("category"),
                        crit.get("label") or crit.get("index"),
                        crit.get("points"),
                        crit.get("max"),
                        crit.get("note") or "",
                    ]
                )
    _style_body(ws, widths={1: 34, 2: 8, 3: 8, 4: 40, 5: 9, 6: 7, 7: 70})
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        try:
            pts = float(row[4].value or 0)
        except (TypeError, ValueError):
            continue
        if pts >= 2:
            row[4].fill = OK_FILL
        elif pts > 0:
            row[4].fill = WARN_FILL
        else:
            row[4].fill = BAD_FILL


# --------------------------------------------------------------------------- Fit
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


# --------------------------------------------------------------------------- Performance
def _performance_sheet(ws: Worksheet, results: list[dict]) -> None:
    """الأداء **المقيس فعلياً** على الكارت — رقم حقيقي لكل موديل."""
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
                    "، ".join(str(c.get("name") or "?") for c in competing)
                    if competing
                    else "لا"
                ),
            ]
        )
    if not any_row:
        ws.append(["مفيش بيانات أداء مقيسة في هذا التشغيل."])
    _style_body(ws, widths={1: 34, 2: 34, 3: 12, 4: 8, 5: 9})
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        if row and row[-1].value and str(row[-1].value) != "لا":
            for cell in row:
                cell.fill = BAD_FILL
    ws.freeze_panes = "A2"


# --------------------------------------------------------------------------- SpeedDetail
def _speed_detail_sheet(ws: Worksheet, results: list[dict], exam_cfg: dict) -> None:
    """زمن كل سؤال × كل موديل."""
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
        for base in range(3, ws.max_column + 1, 4):
            finish_cell = row[base + 2]
            if str(finish_cell.value) == "length":
                finish_cell.fill = BAD_FILL
    ws.freeze_panes = "C2"


# --------------------------------------------------------------------------- Settings
def _settings_sheet(ws: Worksheet, results: list[dict]) -> None:
    """الإعدادات الفعلية لكل موديل."""
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
            "seed (مطبّق)",
            "max_tokens",
            "ctx",
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
                st.get("chat_template") or runtime.get("template") or "—",
                st.get("template_source") or "—",
                st.get("kv_cache_type") or runtime.get("kv") or "—",
                st.get("flash_attn") or runtime.get("flash_attn") or "—",
                st.get("n_gpu_layers") if st.get("n_gpu_layers") is not None else runtime.get("ngl", "—"),
                st.get("threads") if st.get("threads") is not None else runtime.get("threads", "—"),
                st.get("device") or runtime.get("device") or "—",
                " ".join(st.get("extra_server_args") or runtime.get("extra_args") or []) or "—",
                runtime.get("temperature", "—"),
                runtime.get("top_p", "—"),
                runtime.get("seed", "—"),
                runtime.get("max_tokens", "—"),
                runtime.get("ctx", "—"),
                " · ".join(f"{k}={v}" for k, v in rec.items()) or "—",
                st.get("sampling_source") or "—",
                (st.get("notes") or "")[:300],
            ]
        )
        for warning in st.get("warnings") or []:
            ws.append(["", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", f"⚠ {warning}"])
    _style_body(ws, widths={1: 46, 4: 40, 11: 30, 17: 40, 19: 50})
    ws.auto_filter.ref = None


# --------------------------------------------------------------------------- Answers
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
        "استدعاءات الأدوات",
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
            tools = " · ".join(
                f"{c.get('name')}({c.get('arguments')})" for c in (row.get("tool_calls") or [])
            )
            ws.append(
                [
                    model,
                    qid,
                    row.get("category"),
                    row.get("score"),
                    row.get("max"),
                    row.get("prompt") or "",
                    row.get("answer") or "",
                    row.get("reasoning") or "",
                    tools,
                    row.get("finish") or "",
                    row.get("tokens") if row.get("tokens") is not None else "—",
                    row.get("seconds") if row.get("seconds") is not None else "—",
                    row.get("chars"),
                    "، ".join(row.get("health") or []),
                    "؛ ".join(row.get("notes") or []),
                    row.get("error") or "",
                ]
            )
    _style_body(
        ws,
        widths={1: 30, 2: 7, 3: 7, 4: 8, 5: 6, 6: 46, 7: 100, 8: 60, 9: 30, 10: 10, 11: 9, 12: 9, 13: 8, 14: 26, 15: 50, 16: 30},
    )
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        ws.row_dimensions[row[0].row].height = 120
        for cell in row:
            cell.alignment = Alignment(horizontal="right", vertical="top", wrap_text=True)


# --------------------------------------------------------------------------- Meta
def _meta_sheet(ws: Worksheet, results: list[dict], exam_cfg: dict, run_meta: dict) -> None:
    ws.append(["البند", "القيمة", "ملاحظة"])
    _style_header(ws)
    settings = exam_cfg.get("settings") or {}
    categories = exam_cfg.get("categories") or {}
    ref = gemini_reference(exam_cfg)
    values = gemini_values(exam_cfg)
    values_text = "، ".join(f"{k}: {v}" for k, v in values.items()) or "—"
    if runner_kind(run_meta) == "kaggle_gpu":
        speed_note = (
            f"السرعة المقيسة على {runner_label(run_meta)} — GPU حقيقي. "
            "الكارت أسرع من Quadro M4000M؛ أعمدة tg/pp تقديرية لجهازك المستهدف."
        )
    elif measured_on_gpu(run_meta):
        speed_note = (
            f"السرعة المقيسة على {runner_label(run_meta)} — GPU حقيقي. "
            "أعمدة tg/pp تقديرية بنفس بيئة التشغيل."
        )
    else:
        speed_note = (
            f"السرعة المقيسة على {runner_label(run_meta)} — CPU. "
            "أعمدة tg/pp تقديرية لجهازك المستهدف."
        )
    rows: list[tuple[Any, Any, str]] = [
        ("تاريخ التقرير", now_iso(), "UTC"),
        ("بداية التشغيل", run_meta.get("started_at", "—"), ""),
        ("نهاية التشغيل", run_meta.get("finished_at", "—"), ""),
        ("عدد الموديلات", len(results), "بما فيهم الفاشل"),
        ("إصدار الامتحان", exam_cfg.get("version", "—"), "v3 — 33 سؤال · 8 محاور"),
        ("ملف المواصفات", exam_cfg.get("spec_path", "—"), "المصدر الوحيد للحقيقة"),
        ("عدد الأسئلة المصحّحة", len(exam_cfg.get("questions") or []), "5 معايير × درجتين"),
        ("عدد الأسئلة الاستكشافية", len(exam_cfg.get("profile") or []), "بلا درجة"),
        ("عدد المحاور", len(categories), ""),
        ("درجة المعيار", exam_cfg.get("rubric_points", 2), "2 × 5 = 10 درجات/سؤال"),
        ("temperature", settings.get("temperature"), "ثابت"),
        ("top_p", settings.get("top_p"), "ثابت"),
        ("seed", settings.get("seed"), "ثابت"),
        ("ctx_size", settings.get("ctx_size"), "ثابت — أي قيمة تانية تلغي المقارنة"),
        ("max_tokens", settings.get("max_tokens"), "ثابت"),
        ("max_answer_chars", settings.get("max_answer_chars"), ""),
        ("تكرار الأسئلة", settings.get("repeats"), "المحاور: " + "، ".join(settings.get("repeat_for") or [])),
        ("system prompt", run_meta.get("system_prompt", "—"), "من ملف المواصفات (system_prompt_style)"),
        ("قالب المحادثة", run_meta.get("template", "—"), ""),
        ("طريقة التشغيل", run_meta.get("mode", "llama-server /v1/chat/completions"), ""),
        ("بيئة التشغيل", runner_label(run_meta), "مصدر وسم التقرير"),
        ("GPU الفعلي", run_meta.get("runner_gpu") or "—", "لو فاضي ⇒ مفيش GPU"),
        ("نظام التشغيل", run_meta.get("platform") or platform.platform(), ""),
        ("Python", platform.python_version(), ""),
        ("ملاحظة السرعة", speed_note, "المقيس هو الأساس — السقوف النظرية ثانوية"),
        ("ملاحظة المقارنة", "كل الموديلات بنفس المصحح والإعدادات", "مفيش LLM-judge — تصحيح حتمي"),
        ("مرجع Gemini — الاسم", ref.get("name", "—"), "⛔ عرض فقط"),
        ("مرجع Gemini — المصدر", source_badge(ref), ref.get("source_kind", "")),
        ("مرجع Gemini — الرابط", (ref.get("primary_source") or {}).get("url", "—"), ""),
        ("مرجع Gemini — قيم المحاور", values_text, "تقدير 0..100 لكل محور"),
        ("مرجع Gemini — التأثير على الحكم", "لا يوجد ⛔", "لا يدخل في الدرجة ولا الحكم ولا حدود الدنيا"),
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
        manifest = result.get("manifest") or {}
        if manifest:
            ws.append(
                [
                    f"quant — {result.get('model', '')}",
                    manifest.get("quant_chosen") or manifest.get("quant_pattern") or "—",
                    f"النمط المطلوب: {manifest.get('quant_pattern') or '—'}",
                ]
            )
        if not runtime:
            continue
        ws.append([f"قالب SHA — {result.get('model', '')}", runtime.get("template_sha256", "—"), ""])
        ws.append([f"prompt SHA — {result.get('model', '')}", runtime.get("system_prompt_sha256", "—"), ""])
        ws.append([f"server log — {result.get('model', '')}", runtime.get("server_log", "—"), ""])
        ws.append([f"زمن التشغيل — {result.get('model', '')}", runtime.get("seconds_total", "—"), "ثانية"])

    _style_body(ws, widths={1: 42, 2: 70, 3: 40})
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        if str(row[0].value or "").startswith("مرجع Gemini"):
            for cell in row:
                cell.fill = GEM_FILL
    ws.auto_filter.ref = None


# --------------------------------------------------------------------------- الواجهة
def build_workbook(results: list[dict], exam_cfg: dict, run_meta: dict | None = None) -> Workbook:
    wb = Workbook()
    wb.remove(wb.active)
    run_meta = infer_runner_meta(run_meta, results)

    ws = wb.create_sheet("Summary")
    _summary_sheet(ws, results, exam_cfg)
    ws = wb.create_sheet("Categories")
    _categories_sheet(ws, results, exam_cfg)
    ws = wb.create_sheet("Gates")
    _gates_sheet(ws, results)
    ws = wb.create_sheet("Questions")
    _questions_sheet(ws, results, exam_cfg)
    ws = wb.create_sheet("Rubric")
    _rubric_sheet(ws, results, exam_cfg)
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

    wb.properties.title = "تقرير امتحان المساعد المصري v3"
    wb.properties.subject = "مقارنة موديلات GGUF — تصحيح حتمي 33 سؤال · 8 محاور"
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
