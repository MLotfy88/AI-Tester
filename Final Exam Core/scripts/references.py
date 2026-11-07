"""مراجع المقارنة — **خط الأساس** (مقاس) + **شريط الهدف** (Gemini 2.5 Pro).

الفكرة:
  · `baseline` = الموديل المرجعي **المقاس آلياً** بنفس المصحّح ⇒ مرجع المقارنة
    الصالح (نفس السياسة + نفس الجهاز). مصدره معلن صراحةً.
  · `target`   = **شريط الهدف** — Gemini 2.5 Pro. أرقامه **معايرة يدوية** (§0.6)
    ⇒ بتظهر كـ«هدف» مش كـ«مقاس» في كل رسوم المقارنة، عشان نعرف مين الأقرب.

**قاعدة ثابتة:** كل مرجع في التقرير لازم يكون مكتوب مصدره. الموديلات المقاسة
بتظهر بأسمائها الحقيقية ومصدرها «مقاس في هذا التشغيل»، والمراجع اليدوية
بتظهر مع وسم واضح («معايرة يدوية» / «منشور §0.6»).

الوظائف دي **مش معتمدة** على أي ملف تاني — بتستقبل `exam_cfg` ونتائج التشغيل.
"""
from __future__ import annotations

import re
from typing import Any

# ألوان ثابتة للمراجع في كل الرسوم (بنتّفق مع CSS التقرير)
BASELINE_COLOR = "#fbbf24"   # خط الأساس — كهرماني
TARGET_COLOR = "#c084fc"     # شريط الهدف (Gemini) — بنفسجي

SOURCE_LABELS = {
    "measured": "مقاس آلياً",
    "manual": "معايرة يدوية",
    "published": "منشور في ورقة الامتحان",
    "": "مصدر غير معلن",
}

# وسم «غير موثوق ⛔» — نفس القيم في `exam/grader.py` (لازم تتظبط مع بعض)
TRUST_AXIS = "2"
TRUST_MIN = 18.0
TRUST_FLAG = "غير موثوق ⛔"


# --------------------------------------------------------------------------- الإعدادات
def baseline_config(exam_cfg: dict | None) -> dict:
    """خط الأساس (المقاس آلياً) من `config/exam.yaml`."""
    return dict((exam_cfg or {}).get("baseline") or {})


def target_config(exam_cfg: dict | None) -> dict:
    """شريط الهدف — Gemini 2.5 Pro (معايرة يدوية)."""
    return dict((exam_cfg or {}).get("target") or {})


def source_label(cfg: dict | None) -> str:
    """وسم مصدر واضح للمرجع — بيتعرض جنب اسمه في كل مكان."""
    cfg = cfg or {}
    kind = str(cfg.get("source_kind") or "").strip().lower()
    label = SOURCE_LABELS.get(kind, SOURCE_LABELS[""])
    model = str(cfg.get("source_model") or cfg.get("name") or "").strip()
    if model:
        return f"{label} · {model}"
    return label


def source_badge(cfg: dict | None) -> str:
    """وسم قصير (كbadge) لمصدر المرجع."""
    cfg = cfg or {}
    kind = str(cfg.get("source_kind") or "").strip().lower()
    if kind == "measured":
        return "مقاس آلياً"
    if kind == "manual":
        return "معايرة يدوية"
    if kind == "published":
        return "منشور §0.6"
    return "مصدر غير معلن"


def display_name(model: Any) -> str:
    """اسم الموديل المختصر للعرض.

    لو الموديل **مسار محلي** ⇒ نعرض **اسم الملف** بدون `.gguf` (المسار الكامل
    بيبقى متاح في `model_full` كـtooltip). لو **repo id** زي `owner/model` ⇒ نخليه زي ما هو.

    السبب: المسار الكامل (90+ حرف) بيخنق جداول التقرير ويصعّب المقارنة البصرية.
    """
    text = str(model or "").strip()
    if not text:
        return ""
    if "/" in text or "\\" in text:
        base = text.replace("\\", "/").rsplit("/", 1)[-1]
        base = re.sub(r"\.gguf$", "", base, flags=re.I)
        return base or text
    return text


def trust_flag_for(cfg: dict | None, axes_cfg: dict | None = None) -> str:
    """وسم «غير موثوق ⛔» لمرجع (خط الأساس/الهدف) — من الـconfig أو محسوب من ②.

    نفس منطق `exam/grader.py`: المحور ② < 18 ⇒ وسم على **المحور ② نفسه**
    (مش حكم كلي).
    """
    cfg = cfg or {}
    flag = str(cfg.get("trust_flag") or "").strip()
    if flag:
        return flag
    axes = cfg.get("axes") or {}
    score = axes.get(TRUST_AXIS)
    if score is None:
        return ""
    maxv = ((axes_cfg or {}).get(TRUST_AXIS) or {}).get("max")
    try:
        if float(score) < TRUST_MIN:
            return TRUST_FLAG
    except (TypeError, ValueError):
        pass
    return ""


# --------------------------------------------------------------------------- الحسابات
def axis_pct(score: Any, maximum: Any) -> float | None:
    """نسبة المحور من 0 إلى 100 (أو None لو البيانات ناقصة)."""
    try:
        if maximum is None or float(maximum) == 0:
            return None
        return max(0.0, min(100.0, 100.0 * float(score) / float(maximum)))
    except (TypeError, ValueError):
        return None


def target_axis_pct(target: dict | None, axes_cfg: dict | None, key: str) -> float | None:
    """نسبة محور الهدف (0..100)."""
    target = target or {}
    axes = target.get("axes") or {}
    maxv = ((axes_cfg or {}).get(key) or {}).get("max")
    return axis_pct(axes.get(key), maxv)


def model_axis_pct(exam: dict | None, axes_cfg: dict | None, key: str) -> float | None:
    """نسبة محور الموديل المقاس (0..100)."""
    exam = exam or {}
    axis = (exam.get("axes") or {}).get(key) or {}
    maxv = axis.get("max") or ((axes_cfg or {}).get(key) or {}).get("max")
    return axis_pct(axis.get("score"), maxv)


def target_radar_values(target: dict | None, axes_cfg: dict | None) -> list[float]:
    """قيم شريط الهدف على أبعاد الرسم السداسي (كلها 0..100).

    الأبعاد: ① ② ③ ④ · المجموع · نسبة العامية.
    """
    target = target or {}
    axes_cfg = axes_cfg or {}
    values: list[float] = []
    for key in ("1", "2", "3", "4"):
        values.append(target_axis_pct(target, axes_cfg, key) or 0.0)
    values.append(float(target.get("total") or 0.0))
    try:
        ar = float(target.get("ar_ratio") or 0.0) * 100.0
    except (TypeError, ValueError):
        ar = 0.0
    values.append(max(0.0, min(100.0, ar)))
    return values


def target_gap(exam: dict | None, target: dict | None, axes_cfg: dict | None) -> dict:
    """فجوة الموديل عن شريط الهدف (Gemini).

    بيرجع:
      `axis_pct`  : فرق النسبة على كل محور (0..100) — موجب = أعلى من الهدف
      `total`     : فرق المجموع بالنقاط
      `distance`  : متوسط فرق النسبة على المحاور الأربعة (٠ = مطابق تماماً)
                    **الأقل = الأقرب للهدف**
    """
    exam = exam or {}
    target = target or {}
    axes_cfg = axes_cfg or {}
    per_axis: dict[str, float] = {}
    gaps: list[float] = []
    for key in ("1", "2", "3", "4"):
        mpct = model_axis_pct(exam, axes_cfg, key)
        tpct = target_axis_pct(target, axes_cfg, key)
        if mpct is None or tpct is None:
            continue
        diff = round(mpct - tpct, 2)
        per_axis[key] = diff
        gaps.append(abs(diff))
    try:
        total_diff = round(float(exam.get("total") or 0.0) - float(target.get("total") or 0.0), 2)
    except (TypeError, ValueError):
        total_diff = 0.0
    distance = round(sum(gaps) / len(gaps), 2) if gaps else None
    return {
        "axis_pct": per_axis,
        "total": total_diff,
        "distance": distance,
    }


def target_ranking(results: list[dict], exam_cfg: dict | None) -> list[dict]:
    """ترتيب الموديلات المقاسة من **الأقرب للهدف** للأبعد.

    كل عنصر: `{result, gap, distance}` — `distance` أصغر = أقرب.
    """
    target = target_config(exam_cfg)
    axes_cfg = (exam_cfg or {}).get("axes") or {}
    rows: list[dict] = []
    for result in results or []:
        if not result.get("exam"):
            continue
        gap = target_gap(result.get("exam"), target, axes_cfg)
        if gap["distance"] is None:
            continue
        rows.append({"result": result, "gap": gap, "distance": gap["distance"]})
    rows.sort(key=lambda row: row["distance"])
    return rows


__all__ = [
    "BASELINE_COLOR",
    "TARGET_COLOR",
    "SOURCE_LABELS",
    "TRUST_AXIS",
    "TRUST_FLAG",
    "TRUST_MIN",
    "axis_pct",
    "baseline_config",
    "display_name",
    "model_axis_pct",
    "source_badge",
    "source_label",
    "target_axis_pct",
    "target_config",
    "target_gap",
    "target_radar_values",
    "target_ranking",
    "trust_flag_for",
]
