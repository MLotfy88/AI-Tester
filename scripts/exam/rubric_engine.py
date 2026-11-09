"""محرك الـ rubric الحتمي (v3) — 5 معايير × 2 درجات لكل سؤال.

كل معيار في الـ rubric بيتحوّل ل فحص نصي/رقمي حتمي ⇒ نفس الإجابة دايماً
بتدي نفس الدرجة (مفيش LLM-judge ⇒ مفيش حتمية مكسورة).

نقاط المعيار: 0 / 1 / 2 (جزئي مسموح) ⇒ 10 درجات كحد أقصى للسؤال.

التسلسل:
  1. `score_question()` بيقيّم الأسئلة الخمسة لمعرّف واحد.
  2. `aggregate()` بيجمع:
       · درجة السؤال = مجموع نقاط المعايير (0..10)
       · نسبة المحور = مجموع درجات أسئلته / (10 × عدد أسئلته) × 100
       · نقاط المحور = نسبة المحور × وزن المحور
       · المجموع = مجموع نقاط المحاور (0..100)
  3. البوابة: أي محور نزل عن `min_percent` ⇒ **فشل حرج**.
"""
from __future__ import annotations

import inspect
from typing import Any, Callable

from .rubric_lib import fail, ok

# نوع الفحص: (text, ctx) -> (points, note)
Check = Callable[[str, dict], tuple[float, str]]


def _invoke(check: Any, text: str, ctx: dict) -> tuple[float, str]:
    """ينادي الفحص بمعاملاتهSupported (1 أو 2)."""
    try:
        params = inspect.signature(check).parameters
    except (TypeError, ValueError):  # pragma: no cover
        params = {"text": None, "ctx": None}
    if len(params) >= 2:
        result = check(text, ctx)
    else:
        result = check(text)
    # بعض الفحوص بترجع dict جاهز
    if isinstance(result, dict):
        return float(result.get("points") or 0.0), str(result.get("note") or "")
    points, note = result
    return float(points), str(note)

from .checks_br_tl import CHECKS_BR_TL  # noqa: E402
from .checks_eg_st import CHECKS_EG_ST  # noqa: E402
from .checks_if_dc import CHECKS_IF_DC  # noqa: E402
from .checks_lg_hn import CHECKS_LG_HN  # noqa: E402

#: كل الفحوص: {question_id: [check1..check5]} — الترتيب = ترتيب الـ rubric.
ALL_CHECKS: dict[str, list[Check]] = {}
for _group in (CHECKS_EG_ST, CHECKS_LG_HN, CHECKS_IF_DC, CHECKS_BR_TL):
    ALL_CHECKS.update(_group)


def has_checks(qid: str) -> bool:
    return qid in ALL_CHECKS


def score_question(
    qid: str,
    text: str,
    ctx: dict | None = None,
    rubric: list[str] | None = None,
) -> list[dict]:
    """بيقيّم معايير السؤال الخمسة.

    بيرجّع list من 5 عناصر: `{points, note, label, passed}`.
    """
    ctx = ctx or {}
    checks = ALL_CHECKS.get(str(qid).upper())
    rubric = list(rubric or [])
    out: list[dict] = []

    # ── حارس الرد الفاضي ────────────────────────────────────────────────────
    # ⚠ من غيره كان الرد الفاضي بياخد **18.21/100** لأن معايير زي
    #   «مبيألفش تفاصيل» و«قصير» و«مفيش تشخيص» بتتحقق *فارغاً* على نص فاضي
    #   ⇒ الموديل اللي رجّع ولا كلمة بياخد نقاط مجاناً.
    #   الرد الفاضي (من غير استدعاء أدوات) = صفر على السؤال.
    if not (text or "").strip() and not (ctx.get("tool_calls") or []):
        for idx in range(5):
            label = rubric[idx] if idx < len(rubric) else ""
            out.append(
                {
                    **fail("رد فاضي — مفيش نقاط"),
                    "label": label,
                    "passed": False,
                    "partial": False,
                }
            )
        return out

    if not checks:
        for idx in range(5):
            label = rubric[idx] if idx < len(rubric) else ""
            out.append({**fail("مفيش فحص حتمي لهذا السؤال"), "label": label, "passed": False})
        return out

    for idx, check in enumerate(checks):
        label = rubric[idx] if idx < len(rubric) else ""
        try:
            points, note = _invoke(check, text or "", ctx)
        except Exception as exc:  # pragma: no cover — أمان
            points, note = 0.0, f"خطأ في الفحص: {type(exc).__name__}: {exc}"
        points = round(max(0.0, min(2.0, float(points))), 2)
        out.append(
            {
                "points": points,
                "note": note,
                "label": label,
                "passed": points >= 2.0,
                "partial": 0.0 < points < 2.0,
            }
        )
    return out


def question_score(criteria: list[dict]) -> float:
    """درجة السؤال = مجموع نقاط المعايير (0..10)."""
    return round(sum(float(c.get("points") or 0.0) for c in criteria), 2)


def aggregate(
    exam: dict,
    per_question: dict[str, list[dict]],
) -> dict:
    """يجمع درجات الأسئلة ⇒ درجات المحاور ⇒ المجموع + البوابات.

    `per_question`: {qid: criteria_list}
    """
    categories = exam.get("categories") or {}
    questions = {str(q["id"]): q for q in (exam.get("questions") or [])}

    cat_rows: dict[str, dict] = {}
    total = 0.0
    for key, cfg in categories.items():
        qids = list(cfg.get("questions") or [])
        earned = 0.0
        max_points = 0.0
        detail: dict[str, float] = {}
        for qid in qids:
            qcfg = questions.get(qid) or {}
            qmax = float(qcfg.get("max") or 10.0)
            score = question_score(per_question.get(qid) or [])
            earned += score
            max_points += qmax
            detail[qid] = score
        pct = round(100.0 * earned / max_points, 2) if max_points else 0.0
        weight = float(cfg.get("weight") or 0.0)
        points = round(weight * pct / 100.0, 2)
        total += points
        min_percent = float(cfg.get("min_percent") or 0.0)
        failed = bool(min_percent > 0 and pct < min_percent)
        cat_rows[key] = {
            "key": key,
            "name": cfg.get("name", key),
            "short": cfg.get("short", key),
            "weight": weight,
            "min_percent": min_percent,
            "score": earned,
            "max": max_points,
            "percent": pct,
            "points": points,
            "failed_min": failed,
            "questions": qids,
            "question_scores": detail,
        }

    total = round(total, 2)
    failed_cats = [k for k, row in cat_rows.items() if row["failed_min"]]
    return {
        "categories": cat_rows,
        "total": total,
        "max": 100.0,
        "failed_categories": failed_cats,
    }


def verdict_for(exam: dict, total: float, failed_categories: list[str]) -> tuple[str, str]:
    """الحكم النهائي: مجموع الدرجات + بوابة الحد الأدنى (فشل حرج).

    حدود الحكم (ورقة «الملخص»): 85 / 70 / 55.
    """
    if failed_categories:
        cats = "، ".join(
            f"{(exam.get('categories') or {}).get(k, {}).get('name', k)}" for k in failed_categories
        )
        return "فشل حرج ⛔", f"محور تحت الحد الأدنى: {cats}"

    thresholds = list(exam.get("verdicts") or [])
    for row in thresholds:
        try:
            if total >= float(row.get("min", 0)):
                return str(row.get("label") or ""), f"المجموع {total}/100"
        except (TypeError, ValueError):
            continue
    return "غير محدَّد", f"المجموع {total}/100"


__all__ = [
    "ALL_CHECKS",
    "aggregate",
    "has_checks",
    "ok",
    "question_score",
    "score_question",
    "verdict_for",
]
