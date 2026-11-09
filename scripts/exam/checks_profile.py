"""تصحيح الأسئلة الاستكشافية (P1..P14) — **ميزة إضافية** لا تدخل في المجموع الأساسي.

الأفكار:
  · كل سؤال استكشافي بيتقيّم بـ 4 معايير (0..5 لكل واحد) ⇒ 0..20 للسؤال.
  · **التقييم الاستكشافي = متوسط درجات الـ14 سؤال** ⇒ من 20 (مش 280).
  · المعيار الأول (تغطية النقاط الأساسية) مبني على `expert_points` من
    المواصفات ⇒ تصحيح حتمي من غير LLM-judge.
  · **مش بيلمس** المجموع الأساسي ولا الحكم (المستوى) — زي «ماجستير» في
    إعلان وظيفة: ميزة موجودة بس مش شرط.

المعيار (5 نقاط) = التغطية · المباشرة · التنظيم · العمق/التفاصيل العملية.
"""
from __future__ import annotations

import re

from .rubric_lib import (
    bullet_count,
    code_blocks,
    contains_any,
    copied_ratio,
    header_count,
    numbers_in,
    repeated_clause_count,
    repetition_score,
    strip_tashkeel,
    word_count,
)

#: rubric الأسئلة الاستكشافية (نفس المعايير الأربعة لكل سؤال).
PROFILE_RUBRIC = [
    "يغطي النقاط الأساسية المتوقعة",
    "إجابة مباشرة من غير حشو",
    "منظّم وواضح",
    "فيه عمق وتفاصيل عملية",
]

#: نقاط كل معيار (من 5) — 4 معايير ⇒ 20 للسؤال.
CRITERION_MAX = 5.0

#: أقصى تقييم استكشافي (متوسط درجات الـ14 سؤال).
PROFILE_MAX = 20.0

#: علامات «رد ميتا» (رد بيرد على السؤال بدل ما يجاوب) — بتخصم من المباشرة.
_META_MARKERS = (
    "هل يمكنك",
    "هل لديك",
    "أبحث عن السؤال",
    "هذا هو السؤال",
    "السؤال الذي أرسلته",
)


def _norm(text: str) -> str:
    """تطبيع عربي/إنجليزي للمقارنة (تشكيل · همزات · ة/ه · ى/ي)."""
    t = strip_tashkeel(text or "").lower()
    t = re.sub(r"[أإآ]", "ا", t)
    t = t.replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و").replace("ئ", "ي")
    return re.sub(r"\s+", " ", t)


def expected_points(expected: str) -> list[str]:
    """نقاط الإجابة المتوقعة من حقل `expert_points` (مفصولة بـ «،» أو الفواصل)."""
    raw = re.sub(r"^\s*(مثل|مثال|أمثلة|امثلة)\s*:\s*", "", (expected or "").strip())
    parts = re.split(r"[,،;؛\n]+", raw)
    return [p.strip(" .·-—:") for p in parts if p.strip(" .·-—:")]


def _keywords(chunk: str) -> list[str]:
    """كلمات مميزة من نقطة واحدة (عربي 4+ حروف · إنجليزي 3+ حروف)."""
    toks = re.findall(r"[\u0600-\u06FF]{4,}|[A-Za-z][A-Za-z0-9\-]{2,}", chunk or "")
    return [t for t in toks if len(t) >= 4 or re.search(r"[A-Za-z]", t)]


def _present(keyword: str, norm_text: str) -> bool:
    """الكلمة موجودة في النص (مرنة مع/من غير «ال» التعريف)."""
    if keyword in norm_text:
        return True
    if keyword.startswith("ال") and len(keyword) > 4 and keyword[2:] in norm_text:
        return True
    return False


def _coverage(text: str, expected: str) -> tuple[float, str]:
    """C1: تغطية النقاط الأساسية المتوقعة (0..5)."""
    points = expected_points(expected)
    if not points:
        return 2.5, "مفيش نقاط متوقعة محددة — تقييم نصي"
    ntext = _norm(text)
    hit = 0
    missing: list[str] = []
    for chunk in points:
        keys = _keywords(chunk)
        if not keys:
            hit += 1
            continue
        found = sum(1 for k in keys if _present(_norm(k), ntext))
        if found / len(keys) >= 0.5:
            hit += 1
        else:
            missing.append(chunk[:28])
    ratio = hit / len(points)
    if ratio >= 0.8:
        pts = 5.0
    elif ratio >= 0.6:
        pts = 4.0
    elif ratio >= 0.4:
        pts = 3.0
    elif ratio > 0:
        pts = 2.0
    else:
        pts = 0.0
    note = f"غطي {hit}/{len(points)} نقطة متوقعة ({int(ratio * 100)}%)"
    if missing:
        note += f" · ناقص: {'، '.join(missing[:3])}"
    return pts, note


def _directness(text: str, prompt: str) -> tuple[float, str]:
    """C2: إجابة مباشرة من غير لف ولا حشو (0..5)."""
    rep = repetition_score(text)
    clause = repeated_clause_count(text)
    copied = copied_ratio(text, prompt) if prompt else 0.0
    meta = contains_any(text, _META_MARKERS)
    if meta:
        return 0.0, "رد ميتا (بيرد على السؤال بدل ما يجاوب)"
    if rep < 0.25 and clause < 2 and copied < 0.3:
        return 5.0, "مباشرة من غير لف ولا حشو"
    if rep < 0.45 and clause < 3 and copied < 0.5:
        return 3.0, f"حشو/إعادة بسيط (نسبة تكرار {rep})"
    if rep < 0.65 and clause < 5:
        return 2.0, f"لف ودوران واضح (نسبة تكرار {rep})"
    return 0.0, f"حشو/تكرار واضح (نسبة تكرار {rep} · {clause} جملة مكررة)"


def _structure(text: str) -> tuple[float, str]:
    """C3: منظّم وواضح (0..5)."""
    w = word_count(text)
    structured = (
        bullet_count(text) >= 2 or header_count(text) >= 1 or bool(code_blocks(text))
    )
    if structured and 40 <= w <= 400:
        return 5.0, f"منظّم وواضح ({w} كلمة)"
    if structured:
        return 4.0, f"منظّم ({w} كلمة)"
    if 30 <= w <= 500:
        return 3.0, f"واضح بلا عناوين ({w} كلمة)"
    if 15 <= w < 700:
        return 2.0, f"قصير أو مختصر جداً ({w} كلمة)"
    return 0.0, f"طول غير مناسب ({w} كلمة)"


def _depth(text: str, expected: str) -> tuple[float, str]:
    """C4: فيه عمق وتفاصيل عملية (0..5)."""
    signals: list[str] = []
    if numbers_in(text):
        signals.append("أرقام")
    if contains_any(
        text,
        (
            "مثال",
            "مثلا",
            "بفرض",
            "أولاً",
            "ثم",
            "خطوة",
            "خطوات",
            "طريقة",
            "احسب",
            "قيس",
            "حدد",
            "قاعدة",
            "معيار",
            "توصية",
            "ينبغي",
        ),
    ):
        signals.append("خطوات/أمثلة")
    expected_keys = {k for chunk in expected_points(expected) for k in _keywords(chunk)}
    ntext = _norm(text)
    if any(_present(_norm(k), ntext) for k in expected_keys):
        signals.append("مصطلحات المجال")
    if bullet_count(text) >= 2 or header_count(text) >= 1:
        signals.append("تقسيم")
    n = len(signals)
    if n >= 3:
        pts = 5.0
    elif n == 2:
        pts = 3.0
    elif n == 1:
        pts = 2.0
    else:
        pts = 0.0
    return pts, ("عملي ومفصّل · " + "، ".join(signals)) if signals else "مفيش تفاصيل عملية"


def score_profile_question(
    text: str,
    expected: str = "",
    prompt: str = "",
) -> dict:
    """يصحّح سؤالاً استكشافياً ⇒ 4 معايير (0..5) ودرجة 0..20."""
    body = (text or "").strip()
    if not body:
        criteria = [
            {"index": i + 1, "label": label, "points": 0.0, "max": CRITERION_MAX, "note": "رد فاضي"}
            for i, label in enumerate(PROFILE_RUBRIC)
        ]
        return {"criteria": criteria, "score": 0.0, "max": PROFILE_MAX, "percent": 0.0}

    results = (
        _coverage(body, expected),
        _directness(body, prompt),
        _structure(body),
        _depth(body, expected),
    )
    criteria = [
        {
            "index": i + 1,
            "label": label,
            "points": round(float(pts), 2),
            "max": CRITERION_MAX,
            "note": note,
        }
        for i, (label, (pts, note)) in enumerate(zip(PROFILE_RUBRIC, results))
    ]
    score = round(sum(c["points"] for c in criteria), 2)
    return {
        "criteria": criteria,
        "score": score,
        "max": PROFILE_MAX,
        "percent": round(100.0 * score / PROFILE_MAX, 2),
    }


__all__ = [
    "CRITERION_MAX",
    "PROFILE_MAX",
    "PROFILE_RUBRIC",
    "expected_points",
    "score_profile_question",
]
