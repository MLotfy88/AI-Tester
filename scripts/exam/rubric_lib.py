"""أدوات تحليل النص العربي للـ rubric التلقائي (v3).

كل الفحوص هنا **حتمية** (نصية/رقمية/تشغيل كود) — مفيش LLM-judge.
الهدف: نترجم كل معيار من الـ rubric (5 معايير × 2 درجات لكل سؤال) ل فحص
حتمي يرجّع (نقاط من 0..2، سبب/ملاحظة).

المبادئ:
  · نص judge طبيعي ⇒ نقاط جزئية (0 / 1 / 2) مش صح/غلط.
  · نص judge = «مفيش» ⇒ الـ rubric نفسه بيلاقي معيار قابل للفحص ⇒
    بندي: المعايير الفحصية (تلقائي) ليها أولوية على التقديرية.
  · مفيش رقم مخترع: كل نقطة ليها سبب مكتوب.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

from .lib import (
    AR,
    EG_EXTRA,
    FOREIGN_SCRIPT,
    LAT,
    MSA,
    strip_tashkeel,
)

# --------------------------------------------------------------------------- أرقام
_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def norm_digits(text: str) -> str:
    """يوحّد الأرقام العربية-الهندية + يشيل فواصل الآلاف + الفاصلة العشرية."""
    t = (text or "").translate(_AR_DIGITS)
    t = t.replace("\u066b", ".")  # الفاصلة العشرية العربية ٫
    return re.sub(r"(?<=\d)[,\u066c\u060c](?=\d)", "", t)


def numbers_in(text: str) -> list[float]:
    """كل الأرقام في النص (بما فيها العشرية)."""
    out: list[float] = []
    for raw in re.findall(r"\d+(?:\.\d+)?", norm_digits(text)):
        try:
            out.append(float(raw))
        except ValueError:
            continue
    return out


def has_number_near(text: str, target: float, tol: float) -> bool:
    """هل فيه رقم قريب من `target` ضمن `tol`؟"""
    return any(abs(value - target) <= tol for value in numbers_in(text))


def has_int(text: str, value: int) -> bool:
    """هل الرقم الصحيح موجود كرقم مستقل؟"""
    n = norm_digits(text)
    return bool(re.search(r"(?<!\d)%d(?!\d)" % value, n))


# --------------------------------------------------------------------------- بنية الرد
BULLET_RE = re.compile(r"^\s*(?:[-*•◄–—>]|\d{1,2}[\.\)]|[a-zA-Z][\.\)])\s+", re.M)
HEADER_RE = re.compile(r"^\s*(?:#{1,6}\s+|\*\*[^*]{2,60}\*\*\s*:?\s*$)", re.M)
TABLE_RE = re.compile(r"^\s*\|.*\|\s*$", re.M)
LIST_MARKER_RE = re.compile(r"(?:^|\n)\s*(?:[-*•]|\d{1,2}[\.\)])\s+")
QUESTION_RE = re.compile(r"[?؟]")

#: فاصل الجمل (منهم harmonics: . ! ؟ ? …)
_SENT_SPLIT = re.compile(r"[.!؟?]+|\n{2,}")


def words(text: str) -> list[str]:
    return re.findall(r"\S+", text or "")


def word_count(text: str) -> int:
    return len(words(text))


def lines(text: str) -> list[str]:
    return [ln.strip() for ln in (text or "").splitlines()]


def non_empty_lines(text: str) -> list[str]:
    return [ln for ln in lines(text) if ln]


def bullet_count(text: str) -> int:
    return len(BULLET_RE.findall(text or ""))


def header_count(text: str) -> int:
    return len(HEADER_RE.findall(text or ""))


def has_table(text: str) -> bool:
    if TABLE_RE.search(text or "") and re.search(r"^\s*\|[\s\-:|]+\|\s*$", text or "", re.M):
        return True
    return False


def table_rows(text: str) -> int:
    if not has_table(text):
        return 0
    return len([ln for ln in TABLE_RE.findall(text or "") if ln.strip("| \t")]) - 1


def code_blocks(text: str) -> list[str]:
    return [m.group(2) for m in re.finditer(r"```([A-Za-z0-9_+-]*)\n(.*?)```", text or "", re.S)]


def has_code(text: str) -> bool:
    return bool(code_blocks(text))


def sentences(text: str) -> list[str]:
    raw = re.split(_SENT_SPLIT, text or "")
    return [s.strip() for s in raw if s and s.strip()]


def sentence_count(text: str) -> int:
    return len(sentences(text))


def question_count(text: str) -> int:
    return len(QUESTION_RE.findall(text or ""))


def english_tokens(text: str) -> list[str]:
    """كل الكلمات اللاتينية الطويلة (3+ حرف) — عشان نعرف «إنجليزي كتير»."""
    return re.findall(r"\b[A-Za-z][A-Za-z'-]{2,}\b", text or "")


def english_count(text: str) -> int:
    return len(english_tokens(text))


def position_of(text: str, needle: str) -> int:
    """أول موضع للكلمة (ـ -1 لو مش موجودة)."""
    return (text or "").find(needle)


def repetition_ratio(text: str, n: int = 5) -> float:
    """نسبة تكرار الـ n-grams (0..1) — كشف الردود المبلّغة/المكررة."""
    toks = words(strip_tashkeel(text))
    if len(toks) < n + 1:
        return 0.0
    grams = [" ".join(toks[i : i + n]) for i in range(len(toks) - n + 1)]
    if not grams:
        return 0.0
    unique = len(set(grams))
    return round(1.0 - unique / len(grams), 3)


def duplicate_lines(text: str) -> int:
    seen: set[str] = set()
    dupes = 0
    for ln in non_empty_lines(text):
        key = re.sub(r"\s+", " ", ln.lower())
        if key in seen:
            dupes += 1
        seen.add(key)
    return dupes


# --------------------------------------------------------------------------- اللغة
def ar_ratio(text: str) -> float:
    t = text or ""
    ar = len(AR.findall(t))
    lat = len(LAT.findall(t))
    return round(ar / max(1, ar + lat), 3)


def dialect_hits(text: str) -> int:
    return len(EG_EXTRA.findall(strip_tashkeel(text or "")))


def dialect_per_1k(text: str) -> float:
    n = max(1, word_count(text))
    return round(1000 * dialect_hits(text) / n, 1)


def msa_per_1k(text: str) -> float:
    n = max(1, word_count(text))
    m = len(MSA.findall(strip_tashkeel(text or "")))
    return round(1000 * m / n, 1)


def foreign_hits(text: str) -> int:
    return len(FOREIGN_SCRIPT.findall(text or ""))


# --------------------------------------------------------------------------- كلمات مفتاحية
def contains_any(text: str, needles: Iterable[str]) -> bool:
    low = strip_tashkeel((text or "").lower())
    return any(n.lower() in low for n in needles)


def count_any(text: str, needles: Iterable[str]) -> int:
    """عدد المرات (مش المرات المتمايزة) لكلمات من القائمة."""
    low = strip_tashkeel((text or "").lower())
    return sum(low.count(n.lower()) for n in needles)


def contains_groups(text: str, groups: Iterable[Iterable[str]]) -> int:
    """كام مجموعة من المجموعات اتحقت (كل مجموعة = أي كلمة منMotsها)."""
    low = strip_tashkeel((text or "").lower())
    hits = 0
    for group in groups:
        if any(n.lower() in low for n in group):
            hits += 1
    return hits


def near_context(text: str, needle: str, window: int = 80) -> str:
    """السياق حوالين كلمة (للحكم على «هل الرقم ده مؤكد؟»)."""
    low = (text or "").lower()
    idx = low.find(needle.lower())
    if idx < 0:
        return ""
    start = max(0, idx - window)
    return (text or "")[start : idx + len(needle) + window]


# --------------------------------------------------------------------------- علامات الصدق/الرفض
HEDGE_WORDS = (
    "مش عارف",
    "مش متأكد",
    "مش متاكد",
    "معروفش",
    "ما عرفش",
    "ما أعرفش",
    "مش واضح",
    "غامض",
    "مش متاح",
    "مش متاحة",
    "ما ينفعش اقول",
    "محتاج اتأكد",
    "لازم اتأكد",
    "دور على",
    "ابحث عن",
    "راجع",
    "اتحقق",
    "تأكد من",
    "المصدر الرسمي",
    "مش هقدر اقول",
    "ممكن يكون",
    "على حسب",
)

REFUSAL_WORDS = (
    "مش هقدر",
    "مش هينفع",
    "ما ينفعش",
    "ما أقدرش",
    "مش قادر",
    "ممنوع",
    "مخطئ",
    "غلط",
    "خطأ",
    "مفيش داعي",
    "رفض",
    "معارض",
)


def hedge_count(text: str) -> int:
    return count_any(text, HEDGE_WORDS)


def refusal_count(text: str) -> int:
    return count_any(text, REFUSAL_WORDS)


# --------------------------------------------------------------------------- نتيجة فحص
def ok(points: float, note: str = "") -> dict[str, Any]:
    return {"points": round(max(0.0, min(2.0, float(points))), 2), "note": note}


def fail(note: str = "") -> dict[str, Any]:
    return {"points": 0.0, "note": note}


def partial(points: float, note: str = "") -> dict[str, Any]:
    return ok(points, note)


__all__ = [
    "HEDGE_WORDS",
    "REFUSAL_WORDS",
    "ar_ratio",
    "bullet_count",
    "code_blocks",
    "contains_any",
    "contains_groups",
    "count_any",
    "dialect_hits",
    "dialect_per_1k",
    "duplicate_lines",
    "english_count",
    "english_tokens",
    "fail",
    "foreign_hits",
    "has_code",
    "has_int",
    "has_number_near",
    "has_table",
    "header_count",
    "hedge_count",
    "lines",
    "msa_per_1k",
    "near_context",
    "non_empty_lines",
    "norm_digits",
    "numbers_in",
    "ok",
    "partial",
    "position_of",
    "question_count",
    "refusal_count",
    "repetition_ratio",
    "sentence_count",
    "sentences",
    "table_rows",
    "word_count",
    "words",
]
