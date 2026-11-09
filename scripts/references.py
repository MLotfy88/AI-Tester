"""مراجع العرض — الامتحان v3.

المرجع الوحيد هو **Gemini 2.5 Pro** وهو **عرض فقط (display-only)**:

  · **لا يدخل** في حساب درجة أي نموذج.
  · **لا يدخل** في الحكم (verdict) ولا في بوابات الحد الأدنى.
  · أرقامه **بنشماركات عامة منشورة** لنفس النموذج — مش مقاسة على أسئلة امتحاننا،
    فاتحوّلت لتقدير لكل محور على سعة 0..100. مصدر كل رقم مكتوب في
    `config/references.yaml`.
  · في v3 مفيش «خط أساس» ولا «شريط هدف» ولا وسم «غير موثوق» — اتشالوا كلهم.

**المسافة عن المرجع** = متوسط |فرق النسبة| على المحاور الثمانية (٠ = مطابق تماماً).
مفيش أي «مجموع مرجعي» لأن مجموع Gemini التقديري **مش درجة rubric** — أي مقارنة
بالمجموع كانت هتبقى مقارنة بين قياسين مختلفين.
"""
from __future__ import annotations

import re
from typing import Any

#: لون مرجع Gemini في كل الرسوم (بنتّفق مع CSS التقرير)
GEMINI_COLOR = "#c084fc"

SOURCE_LABELS = {
    "public_benchmarks": "بنشماركات عامة منشورة",
    "measured": "مقاس آلياً",
    "manual": "معايرة يدوية",
    "published": "منشور",
    "": "مصدر غير معلن",
}

#: اختصارات المحاور الثمانية — للجداول والرسوم (الاسم الكامل أطول من اللازم)
CATEGORY_SHORT = {
    "EG": "العامية",
    "ST": "أسلوب Gemini",
    "LG": "المنطق",
    "HN": "الصدق",
    "IF": "الالتزام",
    "DC": "التوثيق",
    "BR": "النقد",
    "TL": "الأدوات",
}


def category_short(exam_cfg: dict | None, key: str) -> str:
    """اسم مختصر للمحور — من `short` في المواصفات أو من الخريطة الافتراضية."""
    categories = ((exam_cfg or {}).get("categories") or {})
    cfg: dict = {}
    if isinstance(categories, dict):
        cfg = categories.get(str(key)) or {}
    else:
        # JSON الخام: categories=list
        for row in categories:
            if isinstance(row, dict) and str(row.get("key") or "") == str(key):
                cfg = row
                break
    short = str(cfg.get("short") or "").strip()
    name = str(cfg.get("name") or "").strip()
    if short and short != name:
        return short
    return CATEGORY_SHORT.get(str(key), name or str(key))


# --------------------------------------------------------------------------- مرجع Gemini
def gemini_reference(exam_cfg: dict | None) -> dict:
    """كتلة مرجع Gemini من `exam_cfg["references"]["gemini"]`."""
    refs = (exam_cfg or {}).get("references") or {}
    return dict(refs.get("gemini") or {})


def gemini_axes(exam_cfg: dict | None) -> dict[str, dict]:
    """تقدير Gemini لكل محور: `{KEY: {value, fit, basis, why}}`."""
    return dict(gemini_reference(exam_cfg).get("axes") or {})


def gemini_values(exam_cfg: dict | None) -> dict[str, float]:
    """أرقام Gemini الصالحة (0..100) لكل محور — المحاور اللي مفيش لها رقم بتتتجاهل."""
    out: dict[str, float] = {}
    for key, row in gemini_axes(exam_cfg).items():
        value = (row or {}).get("value")
        if isinstance(value, (int, float)):
            out[str(key)] = float(value)
    return out


def gemini_total(exam_cfg: dict | None) -> float | None:
    """متوسط التقدير المرجعي (0..100) — **مش درجة rubric**، رقم استرشادي فقط."""
    values = list(gemini_values(exam_cfg).values())
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def gemini_radar_values(exam_cfg: dict | None, keys: list[str]) -> list[float]:
    """قيم Gemini على أبعاد الرسم السداسي (حسب ترتيب `keys`)."""
    values = gemini_values(exam_cfg)
    return [values.get(str(key), 0.0) for key in keys]


def gemini_gap(exam: dict | None, exam_cfg: dict | None) -> dict:
    """فرق الموديل عن مرجع Gemini **على مستوى المحاور فقط**.

    بيرجع:
      `per_axis`  : فرق النسبة على كل محور (موجب = أعلى من المرجع)
      `distance`  : متوسط |فرق| على المحاور المتاحة (٠ = مطابق تماماً · الأقل = الأقرب)
      `reference` : أرقام المرجع المستخدمة
    """
    exam = exam or {}
    reference = gemini_values(exam_cfg)
    categories = exam.get("categories") or {}
    per_axis: dict[str, float] = {}
    gaps: list[float] = []
    for key, ref in reference.items():
        row = categories.get(key) or {}
        pct = row.get("percent")
        if not isinstance(pct, (int, float)):
            continue
        diff = round(float(pct) - float(ref), 2)
        per_axis[key] = diff
        gaps.append(abs(diff))
    distance = round(sum(gaps) / len(gaps), 2) if gaps else None
    return {"per_axis": per_axis, "distance": distance, "reference": reference}


def gemini_ranking(results: list[dict], exam_cfg: dict | None) -> list[dict]:
    """ترتيب الموديلات المقاسة من **الأقرب للمرجع** للأبعد.

    كل عنصر: `{result, gap, distance}` — `distance` أصغر = أقرب.
    """
    rows: list[dict] = []
    for result in results or []:
        if not result.get("exam"):
            continue
        gap = gemini_gap(result.get("exam"), exam_cfg)
        if gap.get("distance") is None:
            continue
        rows.append({"result": result, "gap": gap, "distance": gap["distance"]})
    rows.sort(key=lambda row: row["distance"])
    return rows


# --------------------------------------------------------------------------- التسميات
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
    """وسم قصير (badge) لمصدر المرجع."""
    cfg = cfg or {}
    kind = str(cfg.get("source_kind") or "").strip().lower()
    return SOURCE_LABELS.get(kind, SOURCE_LABELS[""])


def display_name(model: Any) -> str:
    """اسم الموديل المختصر للعرض.

    لو الموديل **مسار محلي** ⇒ نعرض **اسم الملف** بدون `.gguf` (المسار الكامل
    بيبقى متاح في `model_full` كـtooltip). لو **repo id** زي `owner/model` ⇒ نخليه زي ما هو.
    """
    text = str(model or "").strip()
    if not text:
        return ""
    if "/" in text or "\\" in text:
        base = text.replace("\\", "/").rsplit("/", 1)[-1]
        base = re.sub(r"\.gguf$", "", base, flags=re.I)
        return base or text
    return text


def axis_pct(score: Any, maximum: Any) -> float | None:
    """نسبة من 0 إلى 100 (أو None لو البيانات ناقصة)."""
    try:
        if maximum is None or float(maximum) == 0:
            return None
        return max(0.0, min(100.0, 100.0 * float(score) / float(maximum)))
    except (TypeError, ValueError):
        return None


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


__all__ = [
    "CATEGORY_SHORT",
    "GEMINI_COLOR",
    "RUNNER_LABELS",
    "SOURCE_LABELS",
    "axis_pct",
    "category_short",
    "display_name",
    "gemini_axes",
    "gemini_gap",
    "gemini_radar_values",
    "gemini_ranking",
    "gemini_reference",
    "gemini_total",
    "gemini_values",
    "infer_runner_meta",
    "measured_on_gpu",
    "runner_kind",
    "runner_label",
    "source_badge",
    "source_label",
]
