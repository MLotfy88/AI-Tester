"""فحوص الـ rubric — المحور IF (اتباع التعليمات).

كل فحص = (text, ctx) -> (points 0..2, note).
IF1/IF2/IF3 **تلقائية بالكامل**: عدّ الجمل/النقاط/الكلمات وتحليل JSON.
"""
from __future__ import annotations

import json
import re

from .rubric_lib import (
    bullet_count,
    code_blocks,
    contains_any,
    count_any,
    english_count,
    fail,
    header_count,
    non_empty_lines,
    numbers_in,
    ok,
    partial,
    sentence_count,
    sentences,
    word_count,
    words,
)

# --------------------------------------------------------------------------- IF1
#: ٣ جمل بالظبط، من غير قوائم أو عناوين
IF1_FORBIDDEN = ("مقدمة", "خاتمة", "الخلاصة", "خلاصة", "أولاً", "أولًا", "ثانياً", "ثانيًا")


def _if1_exact_sentences(text: str) -> tuple[float, str]:
    """R1: ٣ جمل بالظبط."""
    n = sentence_count(text)
    if n == 3:
        return 2.0, "٣ جمل بالظبط ✓"
    if n in (2, 4):
        return 1.0, f"{n} جمل (المطلوب 3)"
    return 0.0, f"{n} جمل — بعيد عن 3"

def _if1_no_lists(text: str) -> tuple[float, str]:
    """R2: من غير قوائم أو عناوين."""
    b = bullet_count(text)
    h = header_count(text)
    if b == 0 and h == 0:
        return 2.0, "مفيش قوائم ولا عناوين ✓"
    if b + h <= 1:
        return 1.0, f"عنصر تنسيق واحد ({b} قوائم · {h} عناوين)"
    return 0.0, f"تنسيق مخالف ({b} قوائم · {h} عناوين)"


def _if1_correct_abc(text: str) -> tuple[float, str]:
    """R3: الشرح صحيح (A/B/C حسب القيمة)."""
    has_abc = bool(re.search(r"\bA\s*/\s*B\s*/\s*C\b", text, re.I)) or all(
        re.search(rf"\b{k}\b", text) for k in ("A", "B", "C")
    )
    has_value = contains_any(
        text,
        ("القيمة", "قيم", "الإيراد", "الايراد", "المبيعات", "turnover", "value", "الأهمية", "قيمة المخزون"),
    )
    has_80 = contains_any(text, ("80", "٨٠", "80%", "٨٠٪"))
    has_15 = contains_any(text, ("15", "١٥"))
    # الرد بالإنجليزي مش ماشي للسؤال العربي ⇒خصم
    en_ratio = english_count(text) / max(1, word_count(text))
    if en_ratio > 0.5:
        return 0.0, f"الشرح بالإنجليزي ({en_ratio:.0%}) مش مصري"
    if has_abc and has_value:
        return 2.0, "شرح A/B/C حسب القيمة ✓"
    if has_abc:
        return 1.0, "ذكر A/B/C بس مش التوزيع"
    return 0.0, "مفيش تعريف A/B/C"


def _if1_no_intro_outro(text: str) -> tuple[float, str]:
    """R4: من غير مقدمة أو خاتمة زيادة."""
    stripped = [ln for ln in non_empty_lines(text)]
    first = stripped[0] if stripped else ""
    last = stripped[-1] if stripped else ""
    n = count_any(text, IF1_FORBIDDEN)
    if n == 0:
        return 2.0, "مفيش مقدمة/خاتمة ✓"
    if n <= 2:
        return 1.0, f" فيه {n} عبارة مقدمة/خاتمة"
    return 0.0, f"{n} عبارات مقدمة/خاتمة"


def _if1_clear(text: str) -> tuple[float, str]:
    """R5: واضح."""
    w = word_count(text)
    sents = sentences(text)
    long_sent = max((word_count(s) for s in sents), default=0)
    if 30 <= w <= 120 and long_sent <= 40:
        return 2.0, f"واضح ({w} كلمة · أطول جملة {long_sent})"
    if w <= 160:
        return 1.0, f"طول {w} كلمة"
    return 0.0, f"مطوّل ({w} كلمة)"


# --------------------------------------------------------------------------- IF2
IF2_KEYS = ("item", "reorder_point", "reasoning")


def _if2_valid_json(text: str) -> tuple[float, str]:
    """R1: JSON صالح فقط."""
    raw = (text or "").strip()
    if not raw:
        return 0.0, "رد فاضي"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        # نجرّب نشيل Markdown wrapper
        stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.M).strip()
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError:
            return 0.0, f"JSON مش صالح: {exc.msg}"
    if not isinstance(data, dict):
        return 0.0, "JSON صالح بس مش object"
    return 2.0, "JSON صالح ✓"


def _if2_exact_keys(text: str) -> tuple[float, str]:
    """R2: المفاتيح الثلاثة بالظبط."""
    raw = (text or "").strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.M).strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return 0.0, "مفيش JSON صالح نتحقق منه"
    if not isinstance(data, dict):
        return 0.0, "JSON مش object"
    keys = {str(k) for k in data.keys()}
    exact = keys == set(IF2_KEYS)
    if exact:
        return 2.0, "المفاتيح الثلاثة بالظبط ✓"
    missing = set(IF2_KEYS) - keys
    extra = keys - set(IF2_KEYS)
    if not missing:
        return 1.0, f"المفاتيح الأساسية موجودة بس فيه زيادة: {sorted(extra)}"
    return 0.0, f"ناقص: {sorted(missing)}"


def _if2_reorder_point(text: str) -> tuple[float, str]:
    """R3: reorder_point = 130."""
    raw = (text or "").strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.M).strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return 0.0, "مفيش JSON صالح"
    if not isinstance(data, dict):
        return 0.0, "JSON مش object"
    val = data.get("reorder_point")
    if isinstance(val, bool):
        return 0.0, "reorder_point مش رقم"
    if isinstance(val, (int, float)):
        if float(val) == 130:
            return 2.0, "reorder_point = 130 ✓"
        return 0.0, f"reorder_point = {val} (المطلوب 130)"
    if isinstance(val, str) and val.strip() in ("130", "١٣٠"):
        return 1.0, "reorder_point = '130' كنص"
    return 0.0, "reorder_point مش موجود/م.about نوع غلط"


def _if2_equation(text: str) -> tuple[float, str]:
    """R4: reasoning فيه المعادلة (20×5+30)."""
    raw = (text or "").strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.M).strip()
    reasoning = ""
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            reasoning = str(data.get("reasoning") or "")
    except json.JSONDecodeError:
        reasoning = raw
    nums = numbers_in(reasoning)
    has_20 = any(abs(n - 20) < 0.01 for n in nums)
    has_5 = any(abs(n - 5) < 0.01 for n in nums)
    has_30 = any(abs(n - 30) < 0.01 for n in nums)
    has_100 = any(abs(n - 100) < 0.01 for n in nums)
    has_130 = any(abs(n - 130) < 0.01 for n in nums)
    ops = contains_any(reasoning, ("*", "×", "x", "X", "+", "=", "plus", "times"))
    if (has_20 and has_5 and has_30) or (has_100 and has_30):
        return 2.0, "المعادلة (20×5+30) موجودة ✓"
    if has_20 and has_5:
        return 1.0, "المدخلات موجودة بس مش مكتملة"
    if has_130:
        return 1.0, "النتيجة موجودة بس مش المعادلة"
    return 0.0, "مفيش معادلة في reasoning"


def _if2_no_markdown(text: str) -> tuple[float, str]:
    """R5: من غير علامات markdown ولا نص زيادة."""
    raw = (text or "").strip()
    has_fence = "```" in raw
    try:
        json.loads(raw)
        extra = 0
    except json.JSONDecodeError:
        extra = 1
    if not has_fence and extra == 0:
        return 2.0, "JSON نضيف بلا markdown ✓"
    if not has_fence:
        return 1.0, "مفيش markdown بس فيه نص زيادة"
    return 0.0, "فيه markdown fences"


# --------------------------------------------------------------------------- IF3
def _if3_five_bullets(text: str) -> tuple[float, str]:
    """R1: ٥ نقاط بالظبط."""
    lines = non_empty_lines(text)
    bullets = [
        ln
        for ln in lines
        if re.match(r"^\s*(?:[-*•◄–—>]|\d{1,2}[\.\)]|[a-zA-Z][\.\)])\s+", ln)
    ]
    n = len(bullets)
    if n == 5:
        return 2.0, "٥ نقاط بالظبط ✓"
    if n in (4, 6):
        return 1.0, f"{n} نقاط (المطلوب 5)"
    return 0.0, f"{n} نقاط — بعيد عن 5"


def _if3_word_limit(text: str) -> tuple[float, str]:
    """R2: كل نقطة ٨ كلمات أو أقل."""
    lines = non_empty_lines(text)
    bullets = [
        ln
        for ln in lines
        if re.match(r"^\s*(?:[-*•◄–—>]|\d{1,2}[\.\)]|[a-zA-Z][\.\)])\s+", ln)
    ]
    if not bullets:
        return 0.0, "مفيش نقاط نتحقق منها"
    counts = []
    for ln in bullets:
        content = re.sub(r"^\s*(?:[-*•◄–—>]|\d{1,2}[\.\)]|[a-zA-Z][\.\)])\s+", "", ln)
        counts.append(len(words(content)))
    over = [c for c in counts if c > 8]
    if not over:
        return 2.0, f"كل النقاط ≤8 كلمات (أطولها {max(counts)}) ✓"
    if len(over) == 1 and max(counts) <= 11:
        return 1.0, f"نقطة واحدة تجاوزت ({max(counts)} كلمة)"
    return 0.0, f"{len(over)} نقاط تجاوزت الحد (أطولها {max(counts)})"


def _if3_no_intro_outro(text: str) -> tuple[float, str]:
    """R3: من غير مقدمة وخاتمة."""
    lines = non_empty_lines(text)
    bullets = [
        ln
        for ln in lines
        if re.match(r"^\s*(?:[-*•◄–—>]|\d{1,2}[\.\)]|[a-zA-Z][\.\)])\s+", ln)
    ]
    if not bullets:
        return 0.0, "مفيش نقاط"
    extra = [ln for ln in lines if ln not in bullets]
    if not extra:
        return 2.0, "نقاط فقط ✓"
    if len(extra) == 1 and len(extra[0]) < 40:
        return 1.0, "سطر مقدمة/خاتمة قصير"
    return 0.0, f"{len(extra)} سطور زيادة"


def _if3_realistic_varied(text: str) -> tuple[float, str]:
    """R4: الأسباب واقعية ومتنوعة."""
    lines = non_empty_lines(text)
    bullets = [
        ln
        for ln in lines
        if re.match(r"^\s*(?:[-*•◄–—>]|\d{1,2}[\.\)]|[a-zA-Z][\.\)])\s+", ln)
    ]
    if not bullets:
        return 0.0, "مفيش نقاط"
    groups = (
        ("مواصفات", "spec", "التوافق", "مطابقة", "标准和", "الstandard"),
        ("تخليص", "جمارك", "customs", "الرسوم", "المعالجة"),
        ("نقل", "شحن", "transport", "logistics", "الخدمات", "السCUL"),
        ("مورد", "supplier", "المورد", "الموردين", "توريد"),
        ("جودة", "فحص", "quality", "inspection", "التالف"),
        ("أوراق", "مستندات", "documents", "الفاتورة", "الجمارك", "التوثيق"),
        ("طقس", "weather", "الأحوال الجوية", "الطقس"),
        ("تأخير", "تاخير", "delay", "تأخر"),
        ("خطأ", "خطأ", "error", "غلط", "أخطاء"),
    )
    hits = sum(1 for g in groups if contains_any(" ".join(bullets), g))
    if hits >= 4:
        return 2.0, f"أسباب متنوعة وواقعية ({hits} نوع)"
    if hits >= 2:
        return 1.0, f"تنوع جزئي ({hits} نوع)"
    return 0.0, f"أسباب غير متنوعة ({hits} نوع)"


def _if3_no_repeat(text: str) -> tuple[float, str]:
    """R5: من غير تكرار."""
    lines = non_empty_lines(text)
    bullets = [
        re.sub(r"^\s*(?:[-*•◄–—>]|\d{1,2}[\.\)]|[a-zA-Z][\.\)])\s+", "", ln)
        for ln in lines
        if re.match(r"^\s*(?:[-*•◄–—>]|\d{1,2}[\.\)]|[a-zA-Z][\.\)])\s+", ln)
    ]
    if len(bullets) < 2:
        return 1.0, "مفيش نقاط كافية للحكم"
    norm = [re.sub(r"\s+", " ", b.lower()) for b in bullets]
    if len(set(norm)) == len(norm):
        return 2.0, "مفيش تكرار ✓"
    dupes = len(norm) - len(set(norm))
    return 0.0, f"{dupes} نقاط مكررة"


# --------------------------------------------------------------------------- IF4
def _if4_two_english(text: str) -> tuple[float, str]:
    """R1: جملتين إنجليزي."""
    en_part = ""
    for line in non_empty_lines(text):
        if re.match(r"^\s*EN\s*[:\-]", line, re.I):
            en_part = line.split(":", 1)[-1] if ":" in line else line.split("-", 1)[-1]
            break
    if not en_part:
        en_part = text
    n = sentence_count(en_part)
    if n == 2:
        return 2.0, "جملتين إنجليزي ✓"
    if n in (1, 3):
        return 1.0, f"{n} جمل إنجليزي (المطلوب 2)"
    return 0.0, f"{n} جمل إنجليزي — بعيد"


def _if4_two_arabic(text: str) -> tuple[float, str]:
    """R2: جملتين عامية."""
    ar_part = ""
    for line in non_empty_lines(text):
        if re.match(r"^\s*AR\s*[:\-]", line, re.I):
            ar_part = line.split(":", 1)[-1] if ":" in line else line.split("-", 1)[-1]
            break
    if not ar_part:
        return 0.0, "مفيش قسم AR"
    n = sentence_count(ar_part)
    # لازم يكون عربي فعلاً (مش إنجليزي)
    ar_chars = len(re.findall(r"[\u0600-\u06ff]", ar_part))
    lat_chars = len(re.findall(r"[A-Za-z]", ar_part))
    if ar_chars < lat_chars:
        return 0.0, "قسم AR مش عربي"
    if n == 2:
        return 2.0, "جملتين عامية ✓"
    if n in (1, 3):
        return 1.0, f"{n} جمل عامية (المطلوب 2)"
    return 0.0, f"{n} جمل عامية — بعيد"


def _if4_format(text: str) -> tuple[float, str]:
    """R3: التنسيق EN/AR."""
    has_en = bool(re.search(r"(?m)^\s*EN\s*[:\-]", text))
    has_ar = bool(re.search(r"(?m)^\s*AR\s*[:\-]", text))
    if has_en and has_ar:
        en_pos = re.search(r"(?m)^\s*EN\s*[:\-]", text).start()
        ar_pos = re.search(r"(?m)^\s*AR\s*[:\-]", text).start()
        return 2.0, "التنسيق EN ثم AR ✓" if en_pos < ar_pos else "الترتيب معكوس (AR قبل EN)"
    if has_en or has_ar:
        return 1.0, "قسم واحد بس"
    return 0.0, "مفيش تنسيق EN/AR"


def _if4_translation_match(text: str) -> tuple[float, str]:
    """R4: الترجمة مطابقة للمعنى."""
    en_part = ""
    ar_part = ""
    for line in non_empty_lines(text):
        if not en_part and re.match(r"^\s*EN\s*[:\-]", line, re.I):
            en_part = line.split(":", 1)[-1]
        elif not ar_part and re.match(r"^\s*AR\s*[:\-]", line, re.I):
            ar_part = line.split(":", 1)[-1]
    en_keys = ("ownership", "total", "cost", "acquisition", "operat", "maintenance", "lifetime", "cost of owning")
    ar_keys = ("ملكية", "إجمالي", "تكلفة", "اكتساب", "تشغيل", "صيانة", "مدة", "تكلفه", "التملك")
    en_hit = contains_any(en_part, en_keys)
    ar_hit = contains_any(ar_part, ar_keys)
    if en_hit and ar_hit:
        return 2.0, "الترجمة مطابقة للمعنى ✓"
    if en_hit or ar_hit:
        return 1.0, "ناحية واحدة بس فيها المعنى"
    return 0.0, "مفيش معنى متطابق"


def _if4_correct_definition(text: str) -> tuple[float, str]:
    """R5: التعريف صحيح."""
    has_tco = bool(re.search(r"\bTCO\b", text)) or contains_any(text, ("TCO", "إجمالي تكلفة الملكية", "تكلفة الملكية"))
    has_acquisition = contains_any(text, ("ownership", "acquisition", "الاكتساب", "اقتناء", "شراء", "التملك", "ملكية"))
    has_ops = contains_any(text, ("operat", "maintenance", "تشغيل", "صيانة", "استخدام"))
    if has_tco and (has_acquisition or has_ops):
        return 2.0, "تعريف TCO صحيح ✓"
    if has_tco:
        return 1.0, "ذكر TCO بس التعريف ناقص"
    return 0.0, "مفيش تعريف TCO"


CHECKS_IF = {
    "IF1": [
        _if1_exact_sentences,
        _if1_no_lists,
        _if1_correct_abc,
        _if1_no_intro_outro,
        _if1_clear,
    ],
    "IF2": [
        _if2_valid_json,
        _if2_exact_keys,
        _if2_reorder_point,
        _if2_equation,
        _if2_no_markdown,
    ],
    "IF3": [
        _if3_five_bullets,
        _if3_word_limit,
        _if3_no_intro_outro,
        _if3_realistic_varied,
        _if3_no_repeat,
    ],
    "IF4": [
        _if4_two_english,
        _if4_two_arabic,
        _if4_format,
        _if4_translation_match,
        _if4_correct_definition,
    ],
}


# --------------------------------------------------------------------------- DC
#: أسماء المسؤولين المذكورين في نقاش DC1
DC1_OWNERS = {
    "سارة": ("الشهادات", "شهادات", "الجودة"),
    "أحمد": ("العينات", "عينات", "العينة"),
    "المحاسبين": ("الكمية", "كمية", "السنوية", "سنوية"),
}


def _dc_sections(text: str) -> tuple[str, str]:
    """بيقسّم الرد لـ (قرارات، نقاط مفتوحة) حسب العناوين."""
    low = text.lower()
    dec_idx = -1
    open_idx = -1
    for kw in ("القرارات", "قرارات", "قرارات:"):
        i = low.find(kw)
        if i >= 0:
            dec_idx = i
            break
    for kw in ("نقاط مفتوحة", "مفتوحة", "open", "غير محسومة", "أسئلة متبقية"):
        i = low.find(kw)
        if i >= 0:
            open_idx = i
            break
    if dec_idx >= 0 and open_idx >= 0:
        if dec_idx < open_idx:
            return text[dec_idx:open_idx], text[open_idx:]
        return text[dec_idx:], text[:open_idx]
    if dec_idx >= 0:
        return text[dec_idx:], ""
    if open_idx >= 0:
        return "", text[open_idx:]
    return "", text


def _dc1_separates(text: str) -> tuple[float, str]:
    """R1: بيفصل القرارات عن النقاط المفتوحة."""
    dec, openp = _dc_sections(text)
    has_dec = bool(dec.strip()) and contains_any(text, ("القرارات", "قرارات", "قرار", "تم الاتفاق", "قررنا", "اتقرر"))
    has_open = bool(openp.strip()) or contains_any(text, ("مفتوحة", "مش محسومة", "لسه", "متبقية", "ناقص", "محتاجين"))
    if has_dec and has_open:
        return 2.0, "فصل القرارات عن النقاط المفتوحة ✓"
    if has_dec or has_open:
        return 1.0, "جزء واحد بس"
    return 0.0, "مفيش فصل واضح"


def _dc1_owners(text: str) -> tuple[float, str]:
    """R2: المهام بمسؤول (سارة/أحمد/المحاسبين)."""
    hits = 0
    for owner, kws in DC1_OWNERS.items():
        if contains_any(text, (owner,)) and contains_any(text, kws):
            hits += 1
    if hits >= 3:
        return 2.0, "المسؤوليات واضحة (3/3) ✓"
    if hits == 2:
        return 1.0, "مسؤوليتان بس"
    if hits == 1:
        return 1.0, "مسؤولية واحدة"
    return 0.0, "مفيش إسناد مسؤوليات"


def _dc1_priority_deadline(text: str) -> tuple[float, str]:
    """R3: بيحدد أولوية ومعيار انتهاء."""
    has_priority = contains_any(
        text, ("أولوية", "الأولوية", "عاجل", "حرج", "مهم", "أول", "أولى", "priority", "ترتيب")
    )
    has_deadline = contains_any(
        text,
        (
            "معيار انتهاء",
            "معيار",
            "تاريخ",
            "موعد",
            "خلال",
            "قبل",
            "deadline",
            "ينتهي",
            "انتهاء",
            "حتى",
            "days",
            "يوم",
            "أيام",
            "أسبوع",
        ),
    )
    has_criteria = contains_any(
        text,
        (
            "شرط",
            "شرط acceptance",
            "معيار",
            "يتم التحقق",
            "بعد التحقق",
            "عند استلام",
            "التأكد من",
            "يكون مكتمل",
            "مكتمل",
            "تم الموافقة",
            "موافقة",
        ),
    )
    n = sum([bool(has_priority), bool(has_deadline), bool(has_criteria)])
    if n >= 2:
        return 2.0, f"أولوية + معيار انتهاء ({n}/3) ✓"
    if n == 1:
        return 1.0, "عنصر واحد بس"
    return 0.0, "مفيش أولوية ولا معيار انتهاء"


def _dc1_no_fabrication(text: str) -> tuple[float, str]:
    """R4: مبيألفش قرارات مذكورتش."""
    # القرارات المذكورة فعلًا: طلب عينات، مراجعة شهادات، استخراج الكمية
    legit = (
        "عينات",
        "شهادات",
        "الكمية",
        "ميزانية",
        "موردين",
        "الخيوط",
        "3 موردين",
        "ثلاثة",
    )
    # علامات قرار مُختلق
    fake = (
        "قررنا التعاقد",
        "تمت الموافقة على",
        "اعتمدنا",
        "وافق الفريق على",
        "تم اختيار",
        "تم التعاقد",
        "اعتمد المورد",
        "تم حسم",
        "قرّرنا استبعاد",
    )
    n_fake = count_any(text, fake)
    if n_fake == 0:
        return 2.0, "مفيش قرارات مُختلقة ✓"
    if contains_any(text, legit) and n_fake <= 1:
        return 1.0, "فيه صياغة قريبة من قرار مُختلق"
    return 0.0, f"{n_fake} قرارات مُختلقة"


def _dc1_clean_format(text: str) -> tuple[float, str]:
    """R5: تنسيق نظيف وقابل للنسخ."""
    has_markers = contains_any(
        text,
        ("القرارات", "النقاط المفتوحة", "المهام", "المسؤول", "الأولوية", "معيار"),
    )
    n_struct = len(
        re.findall(r"(?m)^\s*(?:[-*•]|\d{1,2}[\.\)]|#{1,6}\s|\*\*[^*]+\*\*)", text)
    )
    if has_markers and n_struct >= 4:
        return 2.0, f"تنسيق منظم ({n_struct} عناصر) ✓"
    if has_markers or n_struct >= 2:
        return 1.0, "تنسيق جزئي"
    return 0.0, "تنسيق غير منظم"


# --------------------------------------------------------------------------- DC2
DC2_ELEMENTS = (
    ("هدف", "الهدف", "هدف", "objective", "goal"),
    ("مدخلات", "المدخلات", "مدخلات", "input", "المصدر"),
    ("خطوات", "الخطوات", "خطوات", "steps", "الإجراءات"),
    ("شرط الانتهاء", "شرط الانتهاء", "شرط", "معيار", "إنجاز", "acceptance"),
)


def _dc2_max_six(text: str) -> tuple[float, str]:
    """R1: ٦ مهام أو أقل."""
    tasks = _dc2_tasks(text)
    n = len(tasks)
    if 0 < n <= 6:
        return 2.0, f"{n} مهام ✓"
    if n == 0:
        return 0.0, "مفيش مهام مفصولة"
    return 0.0, f"{n} مهام — أكثر من 6"


def _dc2_tasks(text: str) -> list[str]:
    """بيقسّم الرد لمهام (تقسيم على فواصل/عناوين)."""
    lines = text.splitlines()
    tasks: list[str] = []
    cur: list[str] = []
    for ln in lines:
        if re.match(r"^\s*(?:#{1,6}\s|\d{1,2}[\.\)]|[-*•]\s*\*?\*?(?:مهمة|المهمة|Task|تاسك))", ln):
            if cur:
                tasks.append("\n".join(cur))
            cur = [ln]
        elif cur:
            cur.append(ln)
        elif ln.strip():
            cur = [ln]
    if cur:
        tasks.append("\n".join(cur))
    return [t for t in tasks if t.strip()]


def _dc2_all_elements(text: str) -> tuple[float, str]:
    """R2: كل مهمة فيها العناصر الأربعة."""
    tasks = _dc2_tasks(text)
    if not tasks:
        return 0.0, "مفيش مهام مفصولة"
    complete = 0
    for t in tasks:
        present = sum(1 for group in DC2_ELEMENTS if contains_any(t, group))
        if present >= 4:
            complete += 1
    ratio = complete / len(tasks)
    if ratio >= 0.75:
        return 2.0, f"{complete}/{len(tasks)} مهام كاملة العناصر ✓"
    if ratio >= 0.4:
        return 1.0, f"{complete}/{len(tasks)} مهام كاملة"
    return 0.0, f"{complete}/{len(tasks)} مهام كاملة — ضعيف"


def _dc2_order_independent(text: str) -> tuple[float, str]:
    """R3: مهام مستقلة وبترتيب منطقي."""
    tasks = _dc2_tasks(text)
    if len(tasks) < 2:
        return 0.0, "مفيش ترتيب للحكم"
    numbered = len(re.findall(r"(?m)^\s*\d{1,2}[\.\)]\s*\S", text))
    has_sequence_words = contains_any(
        text,
        ("ثم", "بعدين", "أولاً", "أولًا", "أخيراً", "أخيرًا", "لاحقاً", "لاحقًا", "بعد"),
    )
    has_depends = contains_any(text, ("يعتمد", "منتج من", "بناءً على", "بعد ما", "يستخدم نتيجة", "المخرجات"))
    if numbered >= len(tasks) or has_sequence_words:
        return 2.0, f"ترتيب منطقي واضح ({numbered} ترقيم) ✓"
    if has_depends:
        return 1.0, "ذكر الاعتماد بين المهام"
    return 0.0, "مفيش ترتيب واضح"


def _dc2_measurable(text: str) -> tuple[float, str]:
    """R4: شروط انتهاء قابلة للقياس."""
    measurable = contains_any(
        text,
        (
            "خلال",
            "بنسبة",
            "%",
            "٪",
            "في خلال",
            "لا يقل",
            "لا تقل",
            "على الأقل",
            "أقل من",
            "أكثر من",
            "مكتمل",
            "تم استلام",
            "تم التحقق",
            "موافقة",
            "تم اعتماد",
            "مطابق",
            "مطابقة",
            "صفر",
            "100%",
            "١٠٠٪",
            "لا أخطاء",
            "بدون أخطاء",
            "كل الأصناف",
            "لكل صنف",
            "يعمل بنجاح",
            "كل الأصناف",
            "مكتمل",
            "موثّق",
            "معتمد",
            "مستلم",
            "موثقة",
        ),
    )
    vague = contains_any(text, ("في أقرب وقت", "لاحقًا", "قريبًا", "whenever", "أبدًا", "بشكل مناسب"))
    if measurable and not vague:
        return 2.0, "شروط انتهاء قابلة للقياس ✓"
    if measurable:
        return 1.0, "في معيار بس فيه عبارات مبهمة"
    return 0.0, "شروط انتهاء مبهمة"


def _dc2_small_model(text: str) -> tuple[float, str]:
    """R5: مناسبة لنموذج صغير (مهمة واحدة واضحة)."""
    tasks = _dc2_tasks(text)
    if not tasks:
        return 0.0, "مفيش مهام"
    long_tasks = [t for t in tasks if len(t.split()) > 120]
    has_multi_goal = count_any(text, ("و كمان", "وكمان", "بالإضافة إلى", "plus"))
    if not long_tasks and not has_multi_goal:
        return 2.0, "كل مهمة صغيرة وواضحة ✓"
    if len(long_tasks) <= 1:
        return 1.0, "مهمة واحدة كبيرة"
    return 0.0, f"{len(long_tasks)} مهام كبيرة لنموذج صغير"


# --------------------------------------------------------------------------- DC3
def _dc3_numbered_steps(text: str) -> tuple[float, str]:
    """R1: خطوات مرقمة ومنطقية."""
    n = len(re.findall(r"(?m)^\s*(?:\d{1,2}[\.\)]|[-*•]\s*\*\*?\d|الخطوة\s*\d)", text))
    if n >= 5:
        return 2.0, f"{n} خطوات مرقمة ✓"
    if n >= 3:
        return 1.0, f"{n} خطوات"
    return 0.0, f"{n} خطوات مرقمة — قليلة"


def _dc3_responsibilities(text: str) -> tuple[float, str]:
    """R2: مسؤوليات واضحة."""
    has_roles = contains_any(
        text,
        (
            "المسؤول",
            "المسؤولية",
            "responsible",
            "المستلم",
            "المخزن",
            "الاستلام",
            "المورد",
            "المشتري",
            "المستشار",
            "الطبيب",
            "الممرض",
            "المعاين",
            "الفاحص",
            "أمين المخزن",
            "ضابط",
        ),
    )
    n_roles = count_any(
        text,
        (
            "المسؤول",
            "المستلم",
            "المخزن",
            "المورد",
            "المشتري",
            "المعاين",
            "الفاحص",
            "الممرض",
            "الطبيب",
            "أمين المخزن",
        ),
    )
    if has_roles and n_roles >= 2:
        return 2.0, f"مسؤوليات واضحة ({n_roles} دور) ✓"
    if has_roles:
        return 1.0, "ذكر دور واحد بس"
    return 0.0, "مفيش مسؤوليات"


def _dc3_checkpoints(text: str) -> tuple[float, str]:
    """R3: نقاط فحص (الصلاحية، التلف، مطابقة أمر الشراء)."""
    expiry = contains_any(text, ("الصلاحية", "صلاحية", "expiry", "expiration", "تاريخ الانتهاء", "انتهاء الصلاحية"))
    damage = contains_any(text, ("التلف", "تلف", "damage", "مDamage", "سليم", "سلامة", "الكسر", "العبوة"))
    po_match = contains_any(
        text,
        ("أمر الشراء", "أمر شراء", "PO", "purchase order", "المطابقة", "مطابقة", "مطابق", "الفاتورة"),
    )
    n = sum([bool(expiry), bool(damage), bool(po_match)])
    if n >= 3:
        return 2.0, "نقاط الفحص الثلاثة ✓"
    if n == 2:
        return 1.0, "نقطتي فحص بس"
    if n == 1:
        return 1.0, "نقطة فحص واحدة"
    return 0.0, "مفيش نقاط فحص"


def _dc3_expiry_rule(text: str) -> tuple[float, str]:
    """R4: قاعدة للصلاحية القصيرة (رفض أو قبول مشروط)."""
    reject = contains_any(text, ("رفض", "يرفض", "لا يتم الاستلام", "ترفض", "عدم الاستلام", "منع الاستلام", "reject"))
    conditional = contains_any(
        text,
        (
            "قبول مشروط",
            "مشروط",
            "بشرط",
            "مع الاستخدام",
            "استخدام أول",
            "FEFO",
            "الأقرب انتهاء",
            "تسليم مع",
            "موافقة",
            "إرجاع",
            "رفض أو قبول",
            "لا يقبل",
            "لا يتم",
        ),
    )
    has_short = contains_any(text, ("متبقية", "قليلة", "قصر", "قصيرة", "أقل من", "قرب الانتهاء", "شهر", "أشهر"))
    if (reject or conditional) and has_short:
        return 2.0, "قاعدة صلاحية قصيرة واضحة ✓"
    if reject or conditional:
        return 1.0, "قاعدة موجودة بس مش مربوطة بقصر الصلاحية"
    return 0.0, "مفيش قاعدة للصلاحية القصيرة"


def _dc3_one_page(text: str) -> tuple[float, str]:
    """R5: قابل للاستخدام فعلًا وبطول صفحة."""
    w = word_count(text)
    if 60 <= w <= 520:
        return 2.0, f"طول صفحة ({w} كلمة) ✓"
    if w < 60:
        return 1.0, f"قصير جداً ({w} كلمة)"
    if w <= 750:
        return 1.0, f"أطول من صفحة ({w} كلمة)"
    return 0.0, f"طويل جداً ({w} كلمة)"


CHECKS_DC = {
    "DC1": [
        _dc1_separates,
        _dc1_owners,
        _dc1_priority_deadline,
        _dc1_no_fabrication,
        _dc1_clean_format,
    ],
    "DC2": [
        _dc2_max_six,
        _dc2_all_elements,
        _dc2_order_independent,
        _dc2_measurable,
        _dc2_small_model,
    ],
    "DC3": [
        _dc3_numbered_steps,
        _dc3_responsibilities,
        _dc3_checkpoints,
        _dc3_expiry_rule,
        _dc3_one_page,
    ],
}

#: كل فحوص IF + DC
CHECKS_IF_DC: dict[str, list] = {**CHECKS_IF, **CHECKS_DC}
