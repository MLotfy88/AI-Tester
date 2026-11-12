"""محمّل مواصفات الامتحان الجديد (v3) من `exam/exam_questions_v2.json`.

المنهجية الجديدة (بديل كاملة عن ورقة v2 القديمة):
  · 33 سؤال **مصحّح** (سابقاً 21) · 8 محاور بأوزان · 14 سؤال استكشاف بلا درجة.
  · كل سؤال = **5 معايير rubric × درجتين** ⇒ 10 درجات كحد أقصى للسؤال.
  · لكل محور **حد أدنى (%)** — النزول تحته = **ضعيف** (المستوى الأدنى).
  · مستويات الحكم الخمسة بتتحدَّد من **المجموع النهائي** فقط
    (كل 20% مستوى): ممتاز ≥80 · جيد جدًا ≥60 · جيد ≥40 · مقبول ≥20 · ضعيف <20.
    المرجع (Gemini) **عرض فقط** وما بيشاركش في التقييم.
  · كل سؤال بتمريرة **واحدة**: درجة واحدة + ملاحظة واحدة مطابقة ليها.

الملف ده **هو المصدر الوحيد للحقيقة**: `common.load_exam()` بيرجّع شكلًا
موحّد مبني من الـ JSON، فكل Scripts بتقرأ نفس المواصفات بالظبط.

مفيش أي أرقام مخترعة: أي مرجع لازم يكون مكتوب مصدره في `config/references.yaml`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .checks_profile import PROFILE_MAX, PROFILE_RUBRIC

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SPEC_PATH = ROOT / "exam" / "exam_questions_v2.json"
REFERENCES_PATH = ROOT / "config" / "references.yaml"

#: درجة المعيار الواحد في الـ rubric (5 معايير × 2 = 10 درجات للسؤال)
RUBRIC_POINTS = 2.0

#: مستويات الحكم الخمسة (قابلة للتعديل من config/references.yaml).
#: بتتحدَّد من **المجموع النهائي /100** فقط — مفيش أي مدخل من المرجع.
#: كل 20% = مستوى: ممتاز ≥80 · جيد جدًا ≥60 · جيد ≥40 · مقبول ≥20 · ضعيف <20.
DEFAULT_VERDICTS = [
    {"min": 80, "label": "ممتاز"},
    {"min": 60, "label": "جيد جدًا"},
    {"min": 40, "label": "جيد"},
    {"min": 20, "label": "مقبول"},
    {"min": 0, "label": "ضعيف"},
]

#: إعدادات التشغيل الموصى بها (ورقة «إعدادات التشغيل»)
#:
#: `max_tokens` — ميزانية التوليد لكل سؤال. كانت 4000 وبتقطع إجابات
#: الأسئلة اللي محتاجة تفكير طويل (finish_reason="length").
#: الافتراضي دلوقتي 12000 عشانactus أهم.
#:
#: `ctx_size` — لازم يكون أكبر من `max_tokens` + حجم الـprompt (~512 توكن)،
#: وإلا llama-server بيرفض الطلب (HTTP 400) والرد بيطلع فاضي.
#: 16384 هو أصغر حجم \"آمن\" يغطي 12000.
DEFAULT_SETTINGS = {
    "temperature": 0.6,
    "top_p": 0.95,
    "seed": 1234,
    "max_tokens": 12000,
    "ctx_size": 16384,
    "max_answer_chars": 6000,
    "repeats": 1,
    "repeat_for": [],
}


class SpecError(ValueError):
    """مواصفات الامتحان ناقصة أو غير متسقة."""


# --------------------------------------------------------------------------- تحميل
def load_spec(path: str | Path | None = None) -> dict:
    """يقرأ ملف المواصفات JSON خام."""
    p = Path(path) if path else DEFAULT_SPEC_PATH
    if not p.is_absolute():
        p = ROOT / p
    if not p.exists():
        raise SpecError(f"ملف مواصفات الامتحان مش موجود: {p}")
    with p.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise SpecError("ملف المواصفات لازم يكون JSON object.")
    return data


def _load_references() -> dict:
    """مراجع **العرض فقط** من `config/references.yaml` (اختياري)."""
    try:
        from common import load_yaml

        data = load_yaml(REFERENCES_PATH)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


# --------------------------------------------------------------------------- بناء
def build_exam(spec: dict | None = None, *, references: dict | None = None) -> dict:
    """يبني الـ exam config الموحّد من مواصفات v3."""
    spec = spec if spec is not None else load_spec()
    refs = references if references is not None else _load_references()

    categories_in = spec.get("categories") or []
    scored_in = spec.get("scored") or []
    profile_in = spec.get("profile_unscored") or []
    if not categories_in:
        raise SpecError("مفيش محاور في المواصفات (categories).")
    if not scored_in:
        raise SpecError("مفيش أسئلة مصحّحة في المواصفات (scored).")

    run_settings = dict(spec.get("run_settings") or {})
    settings = dict(DEFAULT_SETTINGS)
    for key in ("temperature", "top_p", "seed", "max_tokens", "ctx_size"):
        if run_settings.get(key) is not None:
            settings[key] = run_settings[key]
    if run_settings.get("repeat_for"):
        settings["repeat_for"] = list(run_settings["repeat_for"])
    settings["repeats"] = int(run_settings.get("repeats") or settings["repeats"])

    # ── المحاور ───────────────────────────────────────────────────────────────
    categories: dict[str, dict] = {}
    for cat in categories_in:
        key = str(cat.get("key") or "").strip().upper()
        if not key:
            raise SpecError("محور من غير key في المواصفات.")
        categories[key] = {
            "key": key,
            "name": str(cat.get("name") or key),
            "short": str(cat.get("short") or cat.get("name") or key),
            "weight": float(cat.get("weight") or 0),
            "min_percent": float(cat.get("min_percent") or 0),
            "questions": [],
        }

    # ── الأسئلة ──────────────────────────────────────────────────────────────
    questions: list[dict] = []
    for q in scored_in:
        qid = str(q.get("id") or "").strip().upper()
        cat = str(q.get("category") or "").strip().upper()
        if not qid:
            raise SpecError("سؤال من غير id في المواصفات.")
        if cat not in categories:
            raise SpecError(f"السؤال {qid} بيح��ي على محور مش معروف: {cat}")
        rubric = [str(x) for x in (q.get("rubric") or [])]
        if len(rubric) != 5:
            raise SpecError(
                f"السؤال {qid} rubric لازم يكون 5 معايير (المواصفات فيها {len(rubric)})."
            )
        categories[cat]["questions"].append(qid)
        questions.append(
            {
                "id": qid,
                "category": cat,
                "title": str(q.get("title") or qid),
                "prompt": str(q.get("prompt") or ""),
                "rubric": rubric,
                "method": str(q.get("method") or "حكم"),
                "note": str(q.get("note") or ""),
                "use_tools": bool(q.get("use_tools")),
                "quick": bool(q.get("quick")),
                "why": str(q.get("why") or ""),
                "max": RUBRIC_POINTS * len(rubric),
            }
        )

    total_weight = sum(c["weight"] for c in categories.values())
    if abs(total_weight - 100.0) > 0.01:
        raise SpecError(f"مجموع أوزان المحاور {total_weight} مش 100.")

    # ── أسئلة الاستكشاف (ميزة إضافية — مش بتدخل في المجموع الأساسي) ───────
    profile = [
        {
            "id": str(p.get("id") or ""),
            "domain": str(p.get("domain") or ""),
            "prompt": str(p.get("prompt") or ""),
            "expert_points": str(p.get("expert_points") or ""),
            "rag_fixes": str(p.get("rag_fixes") or ""),
            "rubric": list(PROFILE_RUBRIC),
            "max": PROFILE_MAX,
        }
        for p in profile_in
    ]

    verdicts = list(refs.get("verdicts") or DEFAULT_VERDICTS)

    exam: dict[str, Any] = {
        "version": "v3",
        "spec_version": spec.get("version"),
        "spec_path": _rel_to_root(DEFAULT_SPEC_PATH),
        "max_score": 100.0,
        "rubric_points": RUBRIC_POINTS,
        "system_prompt": str(spec.get("system_prompt_style") or ""),
        "settings": settings,
        "categories": categories,
        "questions": questions,
        "profile": profile,
        "profile_max": PROFILE_MAX,
        "tools": list(spec.get("tools") or []),
        "verdicts": verdicts,
        "references": dict(refs.get("references") or {}),
    }
    return exam


def _rel_to_root(path: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(ROOT)).replace("\\", "/")
    except Exception:
        return str(path)


# --------------------------------------------------------------------------- مساعدات
def question_map(exam: dict) -> dict[str, dict]:
    return {str(q["id"]): q for q in (exam.get("questions") or [])}


def category_of(exam: dict, qid: str) -> str:
    q = question_map(exam).get(str(qid).upper())
    return str(q.get("category")) if q else ""


def all_questions(exam: dict) -> list[dict]:
    """كل الأسئلة بالترتيب: الـ33 المصحّحة + أسئلة الاستكشاف (P1..P14).

    أسئلة الاستكشاف مبوتوبة category = "PROFILE" عشان المصحّح يفرق بينها
    (بتتقيم مستقلة ولا تدخل في المجموع الأساسي).
    """
    out: list[dict] = list(exam.get("questions") or [])
    for p in exam.get("profile") or []:
        out.append(
            {
                "id": str(p.get("id") or ""),
                "category": "PROFILE",
                "title": str(p.get("domain") or p.get("id") or ""),
                "prompt": str(p.get("prompt") or ""),
                "rubric": list(p.get("rubric") or PROFILE_RUBRIC),
                "method": "استكشافي",
                "note": "ميزة إضافية — لا تدخل في المجموع الأساسي",
                "use_tools": False,
                "quick": False,
                "profile": True,
                "domain": str(p.get("domain") or ""),
                "expert_points": str(p.get("expert_points") or ""),
                "max": PROFILE_MAX,
            }
        )
    return out


def repeats_for(exam: dict, category_key: str) -> int:
    """عدد مرات تكرار السؤال: 1 (مرة واحدة) أو `settings.repeats`."""
    settings = exam.get("settings") or {}
    targets = {str(x).upper() for x in (settings.get("repeat_for") or [])}
    if str(category_key).upper() in targets:
        return max(1, int(settings.get("repeats") or 1))
    return 1


def total_planned_requests(exam: dict, *, include_profile: bool = True) -> int:
    """عدد طلبات الـ LLM المتوقعة (بلا retries)."""
    scored = len(exam.get("questions") or [])
    extra = 0
    for q in exam.get("questions") or []:
        extra += repeats_for(exam, q["category"]) - 1
    profile = len(exam.get("profile") or []) if include_profile else 0
    return scored + extra + profile


#: أكبر عدد توكنات الـ prompt (system + question + tool defs) تقريباً.
#:/questions themselves are tiny (≤400 chars) ⇒ ~250 tokens is a safe ceiling.
PROMPT_TOKEN_RESERVE = 512


def max_tokens_fits_ctx(max_tokens: int, ctx: int) -> bool:
    """هل `max_tokens` هيدخل جوه `ctx` ولا الـserver هيرفض الطلب؟

    llama.cpp بيحسب الـKV cache على `ctx` توكن بالظبط: الـprompt بياخد
    جزء، والباقي空間 للتوليد. لو `max_tokens + prompt > ctx` ⇒
    الطلب بيرجع 400 وترد فاضي.
    """
    return int(max_tokens) + PROMPT_TOKEN_RESERVE <= int(ctx)


def min_ctx_for_max_tokens(max_tokens: int) -> int:
    """أصغر `ctx` يناسب `max_tokens` (مع هامش للـprompt)."""
    return int(max_tokens) + PROMPT_TOKEN_RESERVE


__all__ = [
    "DEFAULT_SETTINGS",
    "DEFAULT_SPEC_PATH",
    "DEFAULT_VERDICTS",
    "PROMPT_TOKEN_RESERVE",
    "REFERENCES_PATH",
    "RUBRIC_POINTS",
    "ROOT",
    "SpecError",
    "build_exam",
    "category_of",
    "load_spec",
    "max_tokens_fits_ctx",
    "min_ctx_for_max_tokens",
    "question_map",
    "repeats_for",
    "total_planned_requests",
]
