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


# --------------------------------------------------------------------------- بيئة التشغيل
RUNNER_LABELS = {
    "kaggle_gpu": "Kaggle GPU",
    "github_cpu": "GitHub Actions (CPU)",
    "local_gpu": "جهازك (GPU)",
    "local_cpu": "جهازك (CPU)",
    "custom": "بيئة تشغيل مخصّصة",
}


def runner_kind(run_meta: dict | None) -> str:
    """نوع بيئة التشغيل — مفتاح ثابت يتحوّل لوسم مقروء."""
    return str((run_meta or {}).get("runner_kind") or "local")


def infer_runner_meta(run_meta: dict | None, results: list[dict] | None = None) -> dict:
    """يستنتج بيئة التشغيل من النتائج لو الـ`run_meta` القديم مفيهوش `runner_kind`.

    السبب: تشغيلات قديمة اتعملت على GPU بس التقرير كان بيقول «CPU» لأن الوسم
    الثابت مكانش موجود. الاستنتاج من `device` / `gpu_name` / `ngl` بيمنع الوسم الغلط
    لما نعيد توليد تقرير قديم من الـ payload.
    """
    meta = dict(run_meta or {})
    if str(meta.get("runner_kind") or "").strip():
        return meta

    device = str(meta.get("device") or "").lower()
    gpu = str(meta.get("runner_gpu") or "").strip()
    gpu_runtime = False
    for result in results or []:
        rt = result.get("runtime") or {}
        if not gpu:
            gpu = str(rt.get("gpu_name") or "").strip()
        if gpu or str(rt.get("gpu_name") or "").strip():
            gpu_runtime = True
        try:
            if int(rt.get("ngl") or 0) > 0:
                gpu_runtime = True
        except (TypeError, ValueError):
            pass

    if gpu:
        meta["runner_gpu"] = gpu
    gpu_device = any(k in device for k in ("cuda", "vulkan", "metal", "rocm"))
    meta["runner_kind"] = "local_gpu" if (gpu_runtime or gpu_device or gpu) else "local_cpu"
    return meta


def runner_label(run_meta: dict | None) -> str:
    """وسم عربي واضح لبيئة التشغيل، مع اسم الكارت لو معروف.

    **القاعدة:** التقرير ممنوع يقول «GitHub runner (CPU)» أو «نظري» لما التشغيل
    كان على GPU. الوسم بيتحدد من `run_meta` اللي بيجي من الـ CLI.
    """
    meta = run_meta or {}
    explicit = str(meta.get("runner_label") or "").strip()
    if explicit:
        return explicit
    kind = runner_kind(meta)
    base = RUNNER_LABELS.get(kind, RUNNER_LABELS["custom"])
    gpu = str(meta.get("runner_gpu") or "").strip()
    if gpu and gpu.lower() not in base.lower():
        return f"{base} — {gpu}"
    return base


def measured_on_gpu(run_meta: dict | None) -> bool:
    """هل الأرقام المقيسة اتأخذت على GPU فعلي؟"""
    meta = run_meta or {}
    if str(meta.get("runner_gpu") or "").strip():
        return True
    return runner_kind(meta) in ("kaggle_gpu", "local_gpu")


def baseline_platform_warning(exam_cfg: dict | None, run_meta: dict | None) -> str:
    """تحذير لو خط الأساس المنشور اتقاس على جهاز مختلف عن بيئة التشغيل الحالية.

    المقارنة **بين الموديلات** تفضل سليمة (كلهم نفس البيئة)، لكن «الفرق عن خط
    الأساس» مش فرق جهاز واحد ⇒ لازم يظهر تحذير صريح في HTML وExcel وsummary.
    """
    baseline = baseline_config(exam_cfg)
    if not baseline:
        return ""
    measured_kind = str(baseline.get("measured_kind") or "").strip()
    if not measured_kind:
        return ""
    kind = runner_kind(run_meta)
    measured_gpu = str(baseline.get("measured_gpu") or "").strip().lower()
    current_gpu = str((run_meta or {}).get("runner_gpu") or "").strip().lower()
    same_kind = measured_kind == kind
    same_gpu = (
        not measured_gpu
        or not current_gpu
        or measured_gpu in current_gpu
        or current_gpu in measured_gpu
    )
    if same_kind and same_gpu:
        return ""
    measured_on = str(baseline.get("measured_on") or measured_gpu or measured_kind)
    return (
        f"المرجع الإضافي {baseline.get('total')}/100 اتقاس على **{measured_on}**، "
        f"والتشغيل الحالي على **{runner_label(run_meta)}**. "
        "المقارنة بين الموديلات سليمة (كلهم نفس البيئة)، لكن «الفرق عن المرجع الإضافي» "
        "مش فرق جهاز واحد — خُده كمؤشر مش كحكم."
    )


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
    "baseline_platform_warning",
    "display_name",
    "measured_on_gpu",
    "model_axis_pct",
    "runner_kind",
    "runner_label",
    "source_badge",
    "source_label",
    "target_axis_pct",
    "target_config",
    "target_gap",
    "target_radar_values",
    "target_ranking",
    "trust_flag_for",
]
