"""تقرير HTML «مِحْيَر» — ملف واحد مستقل (RTL) لمقارنة موديلات GGUF.

التصميم الجديد بالكامل (ثيم بارد + خط Cairo + مرجع Gemini + رادار بتحكّم مستقل
+ ملف أسئلة بفلترة وترتيب وطيّ/فرد) بدل التصميم القديم.

- **ملف واحد بدون اعتماد خارجي**: CSS + JS + البيانات متضمّنة جوه الـ HTML.
  خط Cairo بيتحمّل من Google لو فيه إنترنت، والتقرير بيرجع لخط النظام لو مفيش.
- **كل الأرقام مقيسة**: مبنية من نتائج التشغيل في الذاكرة — مفيش أرقام تقديرية.
- **مرجع Gemini 2.5 Pro عرض فقط ⛔**: مالوش أي تأثير في الدرجة ولا في الحكم.
  درجته المحسوبة = مجموع(نسبة المحور × وزنه) — نفس طريقة المجموع الأساسي.
- **الحكم من المجموع النهائي فقط** (كل 20%): ممتاز ≥80 · جيد جدًا ≥60 · جيد ≥40 ·
  مقبول ≥20 · ضعيف <20. ومحور تحت الحد الأدنى = معلومة ⛔ بس (مش بيفرض مستوى).
- **الأسئلة الاستكشافية (P1..P14)**: تقييم مستقل من 20، بره المجموع والحكم.

ملاحظة: الملف ده **مولّد** — مصدر التصميم هو `design-preview/assets/`، و
`design-preview/sync_to_tool.py` بيحدّث `scripts/html_report.py` من Design.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from common import dump_json_for_html, now_iso
from references import category_short, infer_runner_meta, runner_label

#: ألوان الموديلات في الرسوم (نفس ترتيب `design-preview/assets/js/01-core.js`).
COLORS = ["#5AA9FF", "#35D6C0", "#A78BFA", "#FF8FA3", "#6EE7B7", "#F5C45E"]

# ═════════════════════════════════════════════════════════ CSS / JS / HTML
# الثوابت دي (CSS/JS/TEMPLATE) بتتستبدل وقت التوليد — design-preview/sync_to_tool.py.
# أمّا `__CSS__`/`__JS__`/`__DATA__` جوه الـ TEMPLATE فدي تتستبدل وقت build_html.
CSS = r"""@@CSS_ASSET@@"""

JS = r"""@@JS_ASSET@@"""

TEMPLATE = r"""@@TEMPLATE_ASSET@@"""


# ═════════════════════════════════════════════════════════ Trim data
def _trim_questions(rows: dict | None) -> dict:
    """يقلّم صفوف الأسئلة للبيانات اللي التقرير محتاجها بس."""
    out: dict[str, dict] = {}
    for qid, r in (rows or {}).items():
        r = r or {}
        out[str(qid)] = {
            "id": str(qid),
            "title": r.get("title") or "",
            "prompt": r.get("prompt") or "",
            "why": r.get("why") or "",
            "category": r.get("category") or "",
            "category_name": r.get("category_name") or "",
            "score": r.get("score") or 0,
            "max": r.get("max") or 10,
            "percent": r.get("percent") or 0,
            "passes": r.get("passes") or 1,
            "answer": r.get("answer") or "",
            "chars": r.get("chars") or 0,
            "tokens": r.get("tokens") or 0,
            "seconds": r.get("seconds") or 0,
            "finish": r.get("finish") or "",
            "empty": bool(r.get("empty")),
            "health": r.get("health") or [],
            "criteria": [
                {
                    "label": c.get("label") or "",
                    "points": c.get("points") or 0,
                    "max": c.get("max") or 2,
                    "note": c.get("note") or "",
                }
                for c in (r.get("criteria") or [])
            ],
        }
    return out


def _trim_profile(prof: dict | None) -> dict:
    """يقلّم الأسئلة الاستكشافية (P1..P14) — تقييم مستقل من 20."""
    prof = prof or {}
    return {
        "total": prof.get("total") or 0,
        "max": prof.get("max") or 20,
        "percent": prof.get("percent") or 0,
        "count": prof.get("count") or 0,
        "answered": prof.get("answered") or 0,
        "note": prof.get("note") or "",
        "questions": {
            str(pid): {
                "id": str(pid),
                "domain": q.get("domain") or "",
                "prompt": q.get("prompt") or "",
                "expected": q.get("expected") or "",
                "answer": q.get("answer") or "",
                "score": q.get("score") or 0,
                "max": q.get("max") or 20,
                "percent": q.get("percent") or 0,
                "answered": bool(q.get("answered")),
                "criteria": [
                    {
                        "label": c.get("label") or "",
                        "points": c.get("points") or 0,
                        "max": c.get("max") or 5,
                        "note": c.get("note") or "",
                    }
                    for c in (q.get("criteria") or [])
                ],
            }
            for pid, q in (prof.get("questions") or {}).items()
        },
    }


def _categories(exam_cfg: dict | None) -> dict:
    """مواصفات المحاور الثمانية (اسم · اختصار · وزن · حد أدنى · أسئلة)."""
    raw = (exam_cfg or {}).get("categories") or {}
    if isinstance(raw, dict):
        items = list(raw.items())
    else:  # JSON الخام: categories=list
        items = [
            (str(r.get("key") or r.get("name") or ""), r)
            for r in raw
            if isinstance(r, dict)
        ]
    out: dict[str, dict] = {}
    for key, c in items:
        c = c or {}
        out[str(key)] = {
            "name": str(c.get("name") or key),
            "short": category_short(exam_cfg, str(key)) or str(c.get("name") or key),
            "weight": c.get("weight") or 0,
            "min_percent": c.get("min_percent") or 0,
            "questions": c.get("questions") or [],
        }
    return out


def _reference(exam_cfg: dict | None, categories: dict) -> dict:
    """مرجع Gemini 2.5 Pro — **عرض فقط**.

    الدرجة المحسوبة = مجموع(نسبة المحور × وزنه) / 100 — نفس طريقة المجموع
    الأساسي، عشان المقارنة تكون منصفة. بس ما بتدخلش في درجة ولا حكم أي موديل.
    """
    gem = ((exam_cfg or {}).get("references") or {}).get("gemini") or {}
    detail: dict[str, dict] = {}
    total = 0.0
    for key, row in (gem.get("axes") or {}).items():
        row = row or {}
        value = row.get("value") or 0
        detail[str(key)] = {"value": value, "why": row.get("why") or ""}
        total += float(value or 0) * float((categories.get(str(key)) or {}).get("weight") or 0)
    return {
        "name": gem.get("name") or "Gemini 2.5 Pro",
        "total": round(total / 100.0, 2),
        "color": "#9BB0D4",
        "axes": {k: v["value"] for k, v in detail.items()},
        "axes_detail": detail,
        "note": gem.get("note") or "",
        "source": gem.get("source_model") or "",
        "source_date": gem.get("source_date") or "",
        "kind": gem.get("kind") or "display_only",
    }


# ═════════════════════════════════════════════════════════ Build data
def build_data(
    results: list[dict] | None,
    exam_cfg: dict | None,
    run_meta: dict | None = None,
) -> dict:
    """يبني الـ payload اللي الـ JS بيقرأه (كل الأرقام من نتائج التشغيل)."""
    run = dict(run_meta or {})
    categories = _categories(exam_cfg)
    reference = _reference(exam_cfg, categories)
    settings = (exam_cfg or {}).get("settings") or {}

    models: list[dict] = []
    for i, m in enumerate(results or []):
        m = m or {}
        ex = m.get("exam") or {}
        rt = m.get("runtime") or {}
        perf = rt.get("perf") or {}
        fit = m.get("fit") or {}
        manifest = m.get("manifest") or {}
        status = str(m.get("status") or "ok")

        cats: dict[str, dict] = {}
        for key, c in (ex.get("categories") or {}).items():
            c = c or {}
            cats[str(key)] = {
                "percent": c.get("percent") or 0,
                "points": c.get("points") or 0,
                "score": c.get("score") or 0,
                "max": c.get("max") or 0,
                "failed_min": bool(c.get("failed_min")),
            }

        tg = perf.get("tg_tps") or {}
        pp = perf.get("pp_tps") or {}
        req = perf.get("request_seconds") or {}
        pms = perf.get("prompt_ms") or {}

        models.append(
            {
                "key": f"m{i}",
                "name": m.get("model") or "—",
                "full": m.get("model_full") or m.get("model") or "",
                "repo": manifest.get("repo") or "",
                "sha": (manifest.get("sha") or "")[:8],
                "license": manifest.get("license") or "",
                "quant": manifest.get("quant_chosen") or "",
                "bytes": manifest.get("total_bytes") or 0,
                "color": COLORS[i % len(COLORS)],
                "status": status,
                "error": str(m.get("error") or "") if status != "ok" else "",
                "total": ex.get("total") or 0,
                "max": ex.get("max") or 100,
                "verdict": ex.get("verdict") or ("" if status == "ok" else "فشل"),
                "verdict_note": ex.get("verdict_note") or "",
                "failed_categories": ex.get("failed_categories") or [],
                "cats": cats,
                "questions": _trim_questions(ex.get("questions") or {}),
                "profile": _trim_profile(ex.get("profile") or {}),
                "fit": {
                    "ngl": fit.get("ngl"),
                    "layers": fit.get("n_layers"),
                    "kv": fit.get("kv") or rt.get("kv"),
                    "ctx": fit.get("ctx") or rt.get("ctx"),
                    "threads": fit.get("threads") or rt.get("threads"),
                    "fit_class": fit.get("fit_class") or "",
                },
                "perf": {
                    "tg_avg": tg.get("avg"),
                    "tg_max": tg.get("max"),
                    "pp_avg": pp.get("avg"),
                    "req_avg": req.get("avg"),
                    "req_p95": req.get("p95"),
                    "prompt_ms_avg": pms.get("avg"),
                    "startup": perf.get("startup_seconds"),
                    "generated": perf.get("total_generated_tokens"),
                    "requests": perf.get("requests_count"),
                },
                "runtime": {
                    "seconds_total": rt.get("seconds_total"),
                    "peak_rss_mib": (rt.get("memory") or {}).get("peak_rss_mib"),
                    "peak_vram_mib": (rt.get("memory") or {}).get("peak_vram_mib"),
                    "device": rt.get("device") or "",
                    "gpu": rt.get("gpu_name") or "",
                    "llama_version": rt.get("llama_version") or "",
                },
            }
        )

    first_rt = ((results or [{}])[0] or {}).get("runtime") or {}
    requests = 0
    for m in models:
        value = (m.get("perf") or {}).get("requests")
        if isinstance(value, (int, float)):
            requests = max(requests, int(value))
    seconds = 0.0
    for m in models:
        value = (m.get("runtime") or {}).get("seconds_total")
        if isinstance(value, (int, float)):
            seconds += float(value)

    run_block = {
        "run_id": run.get("run_id") or "",
        "started_at": run.get("started_at") or "",
        "finished_at": run.get("finished_at") or now_iso(),
        "runner_label": runner_label(run),
        "runner_gpu": run.get("runner_gpu") or "",
        "runner_kind": run.get("runner_kind") or "",
        "platform": run.get("platform") or "—",
        "llama_version": run.get("llama_version") or first_rt.get("llama_version") or "",
        "temperature": settings.get("temperature"),
        "top_p": settings.get("top_p"),
        "seed": settings.get("seed"),
        "ctx": run.get("ctx") or settings.get("ctx_size"),
        "quant": run.get("quant_pattern") or "",
        "exam_version": run.get("exam_version") or (exam_cfg or {}).get("version") or "",
        "device": run.get("device") or first_rt.get("device") or "",
        "gpu": first_rt.get("gpu_name") or run.get("runner_gpu") or "",
        "requests_count": requests,
        "seconds_total": round(seconds, 2),
    }

    profile_count = 14
    prof = (exam_cfg or {}).get("profile")
    if isinstance(prof, list):
        profile_count = len(prof) or profile_count

    return {
        "run": run_block,
        "cfg": {
            "version": (exam_cfg or {}).get("version") or "",
            "settings": settings,
            "categories": categories,
            "gemini": {
                "name": reference["name"],
                "note": reference["note"],
                "source_model": reference["source"],
                "source_date": reference["source_date"],
                "axes": reference["axes_detail"],
            },
            "profile_count": profile_count,
        },
        "models": models,
        "ref": reference,
    }


# ═════════════════════════════════════════════════════════ Build HTML
def build_html(
    results: list[dict],
    exam_cfg: dict,
    run_meta: dict | None = None,
) -> str:
    """يبني صفحة HTML كاملة (ملف واحد مستقل)."""
    meta = infer_runner_meta(run_meta, results)
    meta.setdefault("finished_at", now_iso())
    if not meta.get("platform"):
        meta["platform"] = "—"

    data = build_data(results, exam_cfg, meta)
    payload = dump_json_for_html(data)

    return (
        TEMPLATE.replace("__CSS__", CSS)
        .replace("__JS__", JS)
        .replace("__DATA__", payload)
    )


def write_report(
    results: list[dict],
    path: str | Path,
    exam_cfg: dict,
    run_meta: dict | None = None,
) -> Path:
    """يكتب التقرير على القرص ويرجع المسار."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(build_html(results, exam_cfg, run_meta), encoding="utf-8")
    return p


__all__ = ["build_data", "build_html", "write_report"]
