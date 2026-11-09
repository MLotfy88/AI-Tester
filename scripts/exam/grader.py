"""المصحّح الحتمي للامتحان v3 — 33 سؤال · 5 معايير × 2 · 8 محاور.

الفرق الجذري عن v2:
  · مفيش G1..G8 — بدلها **حد أدنى لكل محور** (min_percent).
  · مفيش سياستين (paper/baseline) — التصحيح واحد حتمي.
  · مفيش LLM-judge — كل معيار rubric متترجم ل فحص نصي/رقمي/تشغيل كود.
  · أسئلة LG/IF/TL بتتكرر وبنتاخد متوسطها.
  · **مرجع Gemini 2.5 Pro داخل الناتج كعرض فقط** — مالوش أي تأثير في الدرجة
    ولا في الحكم ولا في بوابات الحد الأدنى.

مخرجات `grade_exam()`:
  {
    "total": 0..100, "max": 100,
    "categories": {EG: {...}, ...},          # 8 محاور
    "questions":  {EG1: {...}, ...},         # صف لكل سؤال (بعد متوسط التكرار)
    "verdict": str, "verdict_note": str,
    "failed_categories": [key, ...],
    "gates": [{code, title, threshold, fired, detail, questions}],  # حدود الدنيا
    "references": {...},                     # مرجع Gemini (عرض فقط)
  }
"""
from __future__ import annotations

import re
from typing import Any

from .lib import lang_info
from .checks_profile import PROFILE_MAX, score_profile_question
from .rubric_engine import aggregate, question_score, score_question, verdict_for

#: لاحقة تمرير التكرار: "LG1__2" ⇒ التمريرة الثانية
_PASS_RE = re.compile(r"^(?P<qid>[A-Za-z]+\d+?)(?:__(?P<pass>\d+))?$")


def _norm_id(key: str) -> str:
    """يحوّل "lg1" / "LG1__2" / "LG1" ⇒ ("LG1", None أو رقم التمريرة)."""
    m = _PASS_RE.match(str(key).strip())
    if not m:
        return str(key).strip().upper(), None
    qid = m.group("qid").upper()
    p = m.group("pass")
    return qid, (int(p) if p else None)


def normalize_answers(raw: Any) -> dict[str, list[dict]]:
    """يطبّع الإجابات ⇒ {qid: [pass1, pass2, ...]}.

    بيقبل:
      · {id: str}
      · {id: dict}
      · {id__1: ..., id__2: ...}
      · {"answers": {...}}
      · [{"id": ..., "answer": ...}, ...]
    """
    if isinstance(raw, dict) and isinstance(raw.get("answers"), (dict, list)):
        raw = raw["answers"]

    rows: list[dict] = []
    if isinstance(raw, dict):
        for key, value in raw.items():
            qid, _ = _norm_id(key)
            if isinstance(value, str):
                rows.append({"id": qid, "answer": value, "key": key})
            elif isinstance(value, dict):
                rows.append({**value, "id": qid, "key": key})
            elif isinstance(value, list):
                for i, item in enumerate(value, 1):
                    if isinstance(item, str):
                        rows.append({"id": qid, "answer": item, "key": f"{key}__{i}"})
                    elif isinstance(item, dict):
                        rows.append({**item, "id": qid, "key": f"{key}__{i}"})
    elif isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            qid, _ = _norm_id(item.get("id") or item.get("qid") or "")
            if not qid:
                continue
            row = dict(item)
            if row.get("answer") is None:
                row["answer"] = row.get("text")
            if row.get("answer") is None and isinstance(row.get("message"), dict):
                row["answer"] = row["message"].get("content")
            rows.append(row)

    out: dict[str, list[dict]] = {}
    for row in rows:
        qid = str(row.get("id") or "").upper()
        if not qid:
            continue
        out.setdefault(qid, []).append(row)
    return out


# --------------------------------------------------------------------------- صحة الرد
def _health_flags(text: str, info: dict, finish: str | None, reasoning: str) -> list[str]:
    """علامات جودة الرد (معلوماتية — مش بتخصم نقاط)."""
    flags: list[str] = []
    if not text.strip():
        flags.append("رد فاضي")
    if finish == "length":
        flags.append("مبتور (length) — الإجابة ناقصة")
    if re.search(r"<think>|</think>", text, re.I):
        flags.append("thinking ظاهر في الرد")
    if info.get("other_hits"):
        flags.append("لهجة غير مصرية")
    if info.get("broken_hits"):
        flags.append("عربي مكسور")
    if info.get("foreign_hits"):
        flags.append("حروف من لغات غريبة")
    if re.search(r"<\|(?:im_start|im_end|eot_id|endoftext)\|>", text):
        flags.append("رموز قالب خام")
    if text and info.get("ar_ratio", 0) < 0.15 and info.get("lat_chars", 0) > 40:
        flags.append("انحراف لغة")
    return flags


def _ctx_for(payload: dict) -> dict:
    """يبني سياق الفحص (trace الأدوات + سياق السؤال)."""
    calls = payload.get("tool_calls") or []
    if isinstance(calls, dict):
        calls = [calls]
    normalized = []
    for c in calls:
        if not isinstance(c, dict):
            continue
        name = c.get("name") or c.get("function") or c.get("tool") or ""
        args = c.get("arguments") or c.get("args") or c.get("parameters") or {}
        normalized.append({"name": str(name), "arguments": args})
    results = payload.get("tool_results") or {}
    if not isinstance(results, dict):
        results = {}
    return {
        "tool_calls": normalized,
        "tool_results": results,
        "text_before_first_call": str(payload.get("text_before_first_call") or ""),
        "prompt": str(payload.get("prompt") or ""),
        "question_id": str(payload.get("id") or ""),
    }


def _avg(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


# --------------------------------------------------------------------------- المصحّح
def grade_exam(
    answers_raw: Any,
    exam: dict,
    *,
    model_meta: dict | None = None,
) -> dict:
    """يصحّح إجابات نموذج واحد على امتحان v3."""
    answers = normalize_answers(answers_raw)
    questions_cfg = {str(q["id"]): q for q in (exam.get("questions") or [])}
    settings = exam.get("settings") or {}

    rows: dict[str, dict] = {}
    per_question_criteria: dict[str, list[dict]] = {}

    for qid, qcfg in questions_cfg.items():
        rubric = list(qcfg.get("rubric") or [])
        qmax = float(qcfg.get("max") or (2.0 * len(rubric)))
        passes = answers.get(qid) or []
        # تمريرة واحدة فاضية لو مفيش رد خالص
        if not passes:
            passes = [{"answer": "", "finish": "missing"}]

        pass_details: list[dict] = []
        per_pass_criteria: list[list[dict]] = []

        for idx, payload in enumerate(passes, 1):
            text = str(payload.get("answer") or "")
            reasoning = str(payload.get("reasoning") or "")
            finish = payload.get("finish") or payload.get("finish_reason")
            usage = payload.get("usage") or {}
            tokens = usage.get("completion_tokens") if isinstance(usage, dict) else None
            if tokens is None:
                tokens = payload.get("completion_tokens")
            info = lang_info(text)
            ctx = _ctx_for({**payload, "id": qid, "prompt": qcfg.get("prompt", "")})

            criteria = score_question(qid, text, ctx, rubric)
            per_pass_criteria.append(criteria)

            pass_details.append(
                {
                    "pass": idx,
                    "answer": text,
                    "reasoning": reasoning,
                    "finish": finish,
                    "seconds": payload.get("seconds"),
                    "tokens": tokens,
                    "error": payload.get("error") or "",
                    "tool_calls": ctx["tool_calls"],
                    "tool_results": ctx["tool_results"],
                    "criteria": criteria,
                    "score": question_score(criteria),
                    "max": qmax,
                    "health": _health_flags(text, info, finish, reasoning),
                    "stats": {
                        k: info.get(k)
                        for k in (
                            "ar_chars",
                            "lat_chars",
                            "ar_ratio",
                            "words",
                            "eg_hits",
                            "eg_per_1k",
                            "msa_per_1k",
                            "other_hits",
                            "broken_hits",
                            "foreign_hits",
                        )
                    },
                }
            )

        # ── معايير السؤال: من **التمريرة الأولى** بس (تمريرة واحدة = درجة واحدة)
        #   السبب: متوسط التمريرات كان بيخلّي الدرجة ما تطابقش الملاحظة المعروضة
        #   (نقطة من تمريرة + ملاحظة من تمريرة تانية) ⇒ قرار «المشكلة دي
        #   عرضية بس» بقى ملغي: دلوقتي درجة واحدة وملاحظة واحدة من نفس الرد.
        first_criteria = per_pass_criteria[0] if per_pass_criteria else []
        merged: list[dict] = []
        for i, crit in enumerate(first_criteria):
            points = float(crit.get("points") or 0.0)
            note = str(crit.get("note") or "")
            merged.append(
                {
                    "index": i + 1,
                    "label": rubric[i] if i < len(rubric) else "",
                    "points": points,
                    "max": 2.0,
                    "passed": points >= 2.0,
                    "partial": 0.0 < points < 2.0,
                    "notes": [note] if note else [],
                    "note": note,
                }
            )
        per_question_criteria[qid] = merged

        score = question_score(merged)
        health: list[str] = []
        for p in pass_details:
            for h in p["health"]:
                if h not in health:
                    health.append(h)

        # ── حقول مريحة من التمريرة الأولى (التقارير بتقرأها مباشرة)
        first = pass_details[0] if pass_details else {}
        total_chars = sum(len(str(p.get("answer") or "")) for p in pass_details)
        total_tokens = sum(
            int(p.get("tokens") or 0) for p in pass_details if p.get("tokens") is not None
        )
        total_seconds = round(
            sum(float(p.get("seconds") or 0.0) for p in pass_details), 2
        )
        tool_calls: list[dict] = []
        for p in pass_details:
            for call in p.get("tool_calls") or []:
                tool_calls.append(call)

        rows[qid] = {
            "id": qid,
            "title": qcfg.get("title", ""),
            "prompt": qcfg.get("prompt", ""),
            "why": qcfg.get("why", ""),
            "category": qcfg.get("category", ""),
            "category_name": (
                (exam.get("categories") or {}).get(str(qcfg.get("category") or ""), {}).get("name", "")
            ),
            "rubric": rubric,
            "criteria": merged,
            "score": score,
            "max": qmax,
            "percent": round(100.0 * score / qmax, 2) if qmax else 0.0,
            "passes": len(pass_details),
            "pass_details": pass_details,
            "answer": first.get("answer", ""),
            "reasoning": first.get("reasoning", ""),
            "chars": total_chars,
            "tokens": total_tokens or None,
            "seconds": total_seconds or None,
            "finish": first.get("finish") or "",
            "error": first.get("error") or "",
            "tool_calls": tool_calls,
            "think_visible": bool(re.search(r"<think>|</think>", first.get("answer") or "", re.I)),
            "notes": [c["note"] for c in merged if c.get("note")],
            "health": health,
            "empty": not any(str(p.get("answer") or "").strip() for p in pass_details),
        }

    # ── الأسئلة الاستكشافية: ميزة إضافية (0..20) — مش بتأثر على المجموع ولا الحكم
    profile_rows: dict[str, dict] = {}
    profile_scores: list[float] = []
    for p in exam.get("profile") or []:
        pid = str(p.get("id") or "").strip().upper()
        if not pid:
            continue
        passes = answers.get(pid) or []
        payload = passes[0] if passes else {}
        text = str(payload.get("answer") or "")
        res = score_profile_question(
            text,
            str(p.get("expert_points") or ""),
            str(p.get("prompt") or ""),
        )
        profile_scores.append(float(res["score"]))
        profile_rows[pid] = {
            "id": pid,
            "domain": str(p.get("domain") or ""),
            "prompt": str(p.get("prompt") or ""),
            "expected": str(p.get("expert_points") or ""),
            "rubric": list(p.get("rubric") or []),
            "answer": text,
            "criteria": res["criteria"],
            "score": res["score"],
            "max": PROFILE_MAX,
            "percent": res["percent"],
            "answered": bool(text.strip()),
        }

    # التقييم الاستكشافي = متوسط درجات **الأسئلة المجاوبة** (0..20)
    # (السؤال اللي ما اتبعتش مش بيحسب صفر — هو مش جزء من التقييم أصلاً)
    answered_scores = [
        float(row["score"]) for row in profile_rows.values() if row.get("answered")
    ]
    profile_total = (
        round(sum(answered_scores) / len(answered_scores), 2) if answered_scores else 0.0
    )
    profile_info = {
        "questions": profile_rows,
        "total": profile_total,
        "max": PROFILE_MAX,
        "percent": round(100.0 * profile_total / PROFILE_MAX, 2) if PROFILE_MAX else 0.0,
        "count": len(profile_rows),
        "answered": len(answered_scores),
        "note": "ميزة إضافية — لا تؤثر على المجموع الأساسي ولا على الحكم",
    }

    # ── التجميع على مستوى المحاور (وزن + حد أدنى)
    agg = aggregate(exam, per_question_criteria)
    categories = agg["categories"]
    total = agg["total"]
    failed = list(agg["failed_categories"])
    verdict, verdict_note = verdict_for(exam, total, failed)

    # ── بوابات الحد الأدنى (بديل G1..G8)
    gates = []
    for key, row in categories.items():
        gates.append(
            {
                "code": f"MIN_{key}",
                "title": f"الحد الأدنى لمحور {row.get('name', key)}",
                "threshold": f"≥ {row.get('min_percent', 0):g}%",
                "fired": bool(row.get("failed_min")),
                "detail": (
                    f"{row.get('percent', 0):g}% (الحد الأدنى {row.get('min_percent', 0):g}%)"
                ),
                "questions": list(row.get("questions") or []),
            }
        )

    return {
        "model": (model_meta or {}).get("repo", ""),
        "model_meta": model_meta or {},
        "version": exam.get("version", "v3"),
        "total": total,
        "max": 100.0,
        "categories": categories,
        "questions": rows,
        "profile": profile_info,
        "verdict": verdict,
        "verdict_note": verdict_note,
        "failed_categories": failed,
        "gates": gates,
        "gate_hits": [g["code"] for g in gates if g["fired"]],
        "references": exam.get("references") or {},
        "settings": {
            "temperature": settings.get("temperature"),
            "top_p": settings.get("top_p"),
            "seed": settings.get("seed"),
            "ctx_size": settings.get("ctx_size"),
            "max_tokens": settings.get("max_tokens"),
            "repeats": settings.get("repeats"),
            "repeat_for": settings.get("repeat_for"),
        },
        "answers_seen": sorted(answers.keys()),
        "missing_questions": sorted(set(questions_cfg) - set(answers)),
    }


__all__ = ["grade_exam", "normalize_answers"]
